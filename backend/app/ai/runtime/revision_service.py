"""Revision Service — **変更の唯一の本番経路**（FORGE-019A §1・§2・§3・§5）。

---

## なぜServiceを1つにするのか

019は`/update`へSemantic Revisionを入れたが、**`/converse`のUPDATEは
旧`ForgeOperationEngine`へ直接流れたまま**だった。

```
/update        → TargetResolver → 局所patch → RevisionRecord → LearningEvent
/converse UPDATE → ForgeOperationEngine（全体書き直し。記録も残らない）
```

**会話がForgeの本線である。** 本線の方が古い経路を通っていたので、
実機で最もよく使われる直し方だけがEvidenceを1件も残していなかった。

これは013で`/generate`と`/update`の両方にRouter迂回があったのと同じ形
——「片方だけ直して終わりにした」である。**二重Architectureにしない。**

## この経路が必ず通すもの

```
artifact capability（handle）
  → version token（世代）
  → document binding（中身の身元）      ← FORGE-019A §1で追加
  → TargetResolver / 全体再生成fallback
  → Forge Validator
  → Semantic Design Critic
  → RevisionRecord（lineage）
  → CORRECTED FeedbackEvent
  → REVISION LearningEvent
  → 新しい artifact version
```

**全体再生成fallbackも同じ経路を通る**（§5）。以前はfallbackだけ
Evidenceを1件も残さず、「Revisionが起きた事実」が消えていた。
局所patchのふりもしない——`patch_mode`と`fallback_reason`で区別する。
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from app.ai.gateway.artifact_feedback import (
    ArtifactHandle,
    EvidenceKind,
    default_artifact_registry,
    default_feedback_service,
)
from app.ai.gateway.generation_evidence import (
    DesignDecisionSource,
    GenerationSource,
    RuntimeOutcome,
    default_generation_store,
)
from app.ai.gateway.learning_foundation import AcceptanceSignal
from app.ai.gateway.revision_evidence import (
    DesignRevision,
    RevisionOperationKind,
    RevisionPatchMode,
    RevisionRecord,
    default_revision_store,
)
from app.ai.runtime.semantic_revision import (
    AppliedSemanticRevision,
    RevisionMode,
    SemanticTarget,
    TargetResolution,
    TargetResolutionStatus,
    apply_semantic_intent,
)
from app.ai.validators.schema_validator import ValidationResult

__all__ = [
    "RevisionOutcome",
    "RevisionRejected",
    "RevisionRejectionStage",
    "RevisionService",
    "default_revision_service",
]


class RevisionRejectionStage(str, Enum):
    """どこで断ったか。**理由を返さずに断らない。**"""

    ARTIFACT_CAPABILITY = "artifact_capability"
    """handleが無い・失効している。"""

    STALE_VERSION = "stale_version"
    """利用者が見ていた版と、いまの版が違う。"""

    DOCUMENT_BINDING = "document_binding"
    """**handleとtokenは正しいが、送られてきたDocumentが別物**（§1）。"""

    EVIDENCE_MISSING = "evidence_missing"
    """記録の起点が引けない。"""

    TARGET_RESOLUTION = "target_resolution"
    """どこを直すのか決められない（曖昧・不在）。**推測しない。**"""

    NO_CHANGE = "no_change"
    """**要求どおりの状態に既になっている**（FORGE-019A）。

    「残高を目立たせて」と言われたが、残高は既にその画面で一番目立つ
    role を持っていた、という場合である。

    ここで成功として記録すると、**何も直していない変更**がlineageへ
    入る。それは §4 が防ごうとしているもの——「利用者が不満を言った
    回数」を「うまく直せた回数」として数える——を、さらに悪い形で
    起こす。直していないのに「直して受け入れられた」になりうる。
    """

    REVISION_EVIDENCE = "revision_evidence"
    """記録に失敗した。**記録できないなら成功にしない。**"""


class RevisionRejected(Exception):
    """変更を受け付けなかった。"""

    def __init__(self, stage: RevisionRejectionStage, reason: str) -> None:
        super().__init__(reason)
        self.stage = stage
        self.reason = reason


@dataclass(frozen=True)
class RevisionOutcome:
    """成功した変更1件分。"""

    document: dict
    validation: ValidationResult
    record: RevisionRecord
    handle: ArtifactHandle
    mode: RevisionMode
    critic_passed: bool
    attempts: int = 1
    operation_id: str | None = None
    target: SemanticTarget | None = None
    fallback_reason: str | None = None


class RevisionService:
    """`/update`と`/converse`のUPDATEが**共通で通る**唯一のService。"""

    def revise(
        self,
        *,
        artifact_id: str | None,
        seen_version_token: str | None,
        document: dict,
        change_request: str,
        idempotency_key: str = "",
        full_regen: object | None = None,
    ) -> RevisionOutcome:
        """1回の変更を、記録まで含めて行う。

        `full_regen`は「局所操作へ落とせなかったときに全体を作り直す」
        呼び出し可能オブジェクト（`document, change_request` を受け取り
        `(document, validation, attempts)` を返す）。`None`なら
        fallbackを許さない——**呼び出し側が明示的に許可した場合だけ**
        全体書き直しへ進む。
        """
        capability = self._capability(artifact_id, seen_version_token, document)
        base_generation_ref, previous_revision_ref = self._lineage(capability)

        semantic = apply_semantic_intent(document, change_request)

        if isinstance(semantic, TargetResolution) and semantic.status in {
            TargetResolutionStatus.AMBIGUOUS,
            TargetResolutionStatus.NEEDS_CLARIFICATION,
        }:
            # **曖昧なまま全体へ適用しない。** 聞き返す方が安い。
            raise RevisionRejected(RevisionRejectionStage.TARGET_RESOLUTION, semantic.reason)

        if isinstance(semantic, AppliedSemanticRevision):
            if not semantic.changed_widget_ids:
                # **何も変わっていないなら記録しない**（FORGE-019A）。
                # 直していない変更をlineageへ入れると、「直して受け入れ
                # られた」という嘘の教師信号が作れてしまう。
                raise RevisionRejected(
                    RevisionRejectionStage.NO_CHANGE,
                    "すでに要求どおりの状態になっています",
                )
            return self._record(
                capability=capability, document=document, revised=semantic.document,
                validation=semantic.validation, base_generation_ref=base_generation_ref,
                previous_revision_ref=previous_revision_ref,
                mode=RevisionMode.LOCAL_SEMANTIC_PATCH,
                design_revisions=self._design_revisions(document, semantic),
                operation_id=semantic.operation.kind.value,
                target=semantic.operation.target,
                critic_passed=True, idempotency_key=idempotency_key,
            )

        # --- 全体再生成fallback（§5） ---------------------------------
        #
        # **同じ経路を通す。** 以前はここだけEvidenceを1件も残さず、
        # 「Revisionが起きた事実」が消えていた。
        if full_regen is None:
            raise RevisionRejected(
                RevisionRejectionStage.TARGET_RESOLUTION,
                semantic.reason if isinstance(semantic, TargetResolution)
                else "この変更要求に対応する意味的操作がありません",
            )
        reason = (
            semantic.reason if isinstance(semantic, TargetResolution)
            else "unsupported semantic intent"
        )
        revised, validation, attempts = full_regen(document, change_request)
        return self._record(
            capability=capability, document=document, revised=revised,
            validation=validation, base_generation_ref=base_generation_ref,
            previous_revision_ref=previous_revision_ref,
            mode=RevisionMode.FULL_REGEN_FALLBACK,
            design_revisions=(),
            operation_id=None, target=None,
            # **Criticを通していないものをPASSと書かない。**
            critic_passed=False, idempotency_key=idempotency_key,
            fallback_reason=reason, attempts=attempts,
        )

    # -- 内部 -------------------------------------------------------------

    def _capability(
        self, artifact_id: str | None, seen_version_token: str | None, document: dict
    ) -> ArtifactHandle:
        capability = default_artifact_registry().resolve(artifact_id or "")
        if capability is None:
            raise RevisionRejected(
                RevisionRejectionStage.ARTIFACT_CAPABILITY,
                "semantic revision requires a current artifact capability",
            )
        if seen_version_token != capability.version_token:
            raise RevisionRejected(
                RevisionRejectionStage.STALE_VERSION, "stale artifact version"
            )
        if not capability.binds(document):
            # **§1の要点。** handleとtokenが正しくても、送られてきた
            # Documentが別物なら「その生成物を直した」という記録は嘘に
            # なる。Revision lineageを汚染できる穴だった。
            raise RevisionRejected(
                RevisionRejectionStage.DOCUMENT_BINDING,
                "submitted document does not match the current artifact version",
            )
        return capability

    def _lineage(self, capability: ArtifactHandle) -> tuple[int, int | None]:
        revisions = default_revision_store()
        if capability.evidence_id.kind is EvidenceKind.REVISION:
            previous = revisions.get(capability.evidence_id.ref)
            if previous is None:
                raise RevisionRejected(
                    RevisionRejectionStage.EVIDENCE_MISSING,
                    "revision evidence is unavailable",
                )
            return previous.base_generation_ref, previous.ref
        base = capability.evidence_id.ref
        if default_generation_store().get(base) is None:
            raise RevisionRejected(
                RevisionRejectionStage.EVIDENCE_MISSING,
                "generation evidence is unavailable",
            )
        return base, None

    @staticmethod
    def _design_revisions(
        document: dict, semantic: AppliedSemanticRevision
    ) -> tuple[DesignRevision, ...]:
        target = semantic.operation.target
        before_role = ""
        stack: list[object] = list(document.get("screens", ()) or ())
        while stack:
            node = stack.pop()
            if isinstance(node, dict):
                if node.get("id") == target.widget_id:
                    before_role = str(node.get("style_role") or "")
                stack.extend(node.values())
            elif isinstance(node, list):
                stack.extend(node)
        return (
            DesignRevision(
                screen_id=target.screen_id, target_id=target.widget_id,
                axis="primary_metric", before=before_role, after="metric.primary",
                source=DesignDecisionSource.USER_CORRECTION,
            ),
        )

    def _record(
        self,
        *,
        capability: ArtifactHandle,
        document: dict,
        revised: dict,
        validation: ValidationResult,
        base_generation_ref: int,
        previous_revision_ref: int | None,
        mode: RevisionMode,
        design_revisions: tuple[DesignRevision, ...],
        operation_id: str | None,
        target: SemanticTarget | None,
        critic_passed: bool,
        idempotency_key: str,
        fallback_reason: str | None = None,
        attempts: int = 1,
    ) -> RevisionOutcome:
        revisions = default_revision_store()
        stored = revisions.record(RevisionRecord(
            base_generation_ref=base_generation_ref,
            previous_revision_ref=previous_revision_ref,
            sequence=revisions.next_sequence(base_generation_ref),
            operation_kind=(
                RevisionOperationKind.DESIGN
                if mode is RevisionMode.LOCAL_SEMANTIC_PATCH
                else RevisionOperationKind.UNKNOWN
            ),
            source=GenerationSource.COMPOSITION,
            validator_passed=bool(validation.valid),
            runtime_outcome=RuntimeOutcome.UNKNOWN,
            design_revisions=design_revisions,
            patch_mode=(
                RevisionPatchMode.LOCAL_SEMANTIC_PATCH
                if mode is RevisionMode.LOCAL_SEMANTIC_PATCH
                else RevisionPatchMode.FULL_REGEN_FALLBACK
            ),
            semantic_operation_ids=(operation_id,) if operation_id else (),
            fallback_reason=fallback_reason,
            critic_passed=critic_passed,
            # **本番では絶対に埋めない**（FORGE-019A §3）。
            #
            # 019は固定文字列でmanifestのパスを入れていたので、実利用者の
            # 変更に「この画像がその証拠です」という偽の紐付けが付いていた。
            # 実際にそのRevisionをrender/captureしたときだけ、後から
            # `attach_visual_evidence()`で明示的に付ける。
            visual_evidence_reference=None,
            forge_language_version=str(revised.get("version") or ""),
        ))

        correction = default_feedback_service().record(
            signal=AcceptanceSignal.CORRECTED,
            artifact_id=capability.handle,
            seen_version_token=capability.version_token,
            idempotency_key=idempotency_key,
        )
        if not correction.recorded:
            raise RevisionRejected(
                RevisionRejectionStage.REVISION_EVIDENCE,
                "correction evidence could not be recorded",
            )

        # **変更後のDocumentへ束縛し直す**（§1）。渡し忘れると次の
        # Revisionが通らなくなるので、ここが唯一の進め方である。
        advanced = default_artifact_registry().advance_to_revision(
            handle=capability.handle, revision_ref=stored.ref,
            revision_uid=stored.uid, document=revised,
        )
        return RevisionOutcome(
            document=revised, validation=validation, record=stored, handle=advanced,
            mode=mode, critic_passed=critic_passed, attempts=attempts,
            operation_id=operation_id, target=target, fallback_reason=fallback_reason,
        )


_DEFAULT_SERVICE = RevisionService()


def default_revision_service() -> RevisionService:
    """本番が使う唯一のService。**変更の入口を複数作らない。**"""
    return _DEFAULT_SERVICE
