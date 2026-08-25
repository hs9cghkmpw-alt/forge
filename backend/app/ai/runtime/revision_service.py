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

import hashlib
import json
from dataclasses import dataclass, replace
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

#: LLMを使わない、Forge自身の決定的な操作（FORGE-019B §4）。
#:
#: Provider名の位置にこれが入っていれば「AIは呼んでいない」という意味
#: である。空文字やNoneにしないのは、**記録し忘れと区別する**ため。
FORGE_DETERMINISTIC = "forge_deterministic"

__all__ = [
    "FORGE_DETERMINISTIC",
    "RevisionOutcome",
    "RevisionRejected",
    "RevisionRejectionStage",
    "RevisionReplayLog",
    "RevisionService",
    "default_replay_log",
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

    IDEMPOTENCY_CONFLICT = "idempotency_conflict"
    """**同じ冪等キーで、違う要求が来た**（FORGE-019B §2）。

    冪等キーは1つの論理的な要求に紐づく。別の要求に使い回されたら、
    それは Client の誤りである。**replay もせず、処理もしない**
    ——どちらへ倒しても嘘になる（replayすれば別の要求を無視したこと
    になり、処理すれば冪等性の約束が消える）。
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

    revision_provider: str = FORGE_DETERMINISTIC
    """**実際にこの文書を変えたのは誰か**（FORGE-019B §4）。

    局所patchは Forge の決定的な操作であって、LLMを1回も呼ばない。
    それを会話のProvider名で報告すると「geminiが直しました」という嘘に
    なる——Providerの成績を測るときに、**呼んでもいないProviderの手柄**
    が混ざる。

    全体再生成へ落ちた場合は、会話のProviderではなく**実際に生成した
    Provider**が入る（Routerがfallbackした先かもしれない）。
    """

    replayed: bool = False
    """再送に対して、以前の結果をそのまま返したか（§2）。"""


@dataclass(frozen=True)
class _RequestIdentity:
    """1つの論理的な変更要求の身元（FORGE-019B §2）。

    **冪等キーだけを鍵にしない。** キーだけで replay を返すと、
    Client が同じキーを別の要求へ使い回した瞬間、**別の要求に対して
    以前の結果が返る**——それは検査の迂回であり、`document_binding`
    （019A §1）で塞いだ穴を冪等性の側から開け直すことになる。

    したがって「元の生成物・元の版・送られた文書・要求文・キー」を
    まとめて身元とする。1つでも違えば別の要求である。

    要求文は**そのまま持たない**（利用者の発話であるため、006 §22）。
    ハッシュだけを持つ。
    """

    artifact_id: str
    version_token: str
    document_binding: str
    change_request_fingerprint: str
    idempotency_key: str


class RevisionReplayLog:
    """成功した変更の結果を、再送に備えて覚えておく（FORGE-019B §2）。

    ---

    ## なぜ要るのか

    019A で Flutter は「同じ操作の再送は同じキー」にした。しかし
    **Backend の Revision 自体は冪等でなかった**ので、

        1. V1 で Revision 成功（サーバは V2 へ進む）
        2. 応答が Client へ届かない
        3. Client は V1・古い文書・同じキーで再送
        4. サーバは `stale_version` で拒否

    となる。利用者から見ると「直したのに直っていない」うえ、もう一度
    押しても永久に通らない。**通信が切れただけで詰む。**

    プロセス内メモリのみ（TD41）。再起動で消えるので、そのときは
    `stale_version` に戻る——**安全側に壊れる**（二重適用はしない）。
    """

    _MAX = 500

    def __init__(self) -> None:
        self._by_identity: dict[_RequestIdentity, RevisionOutcome] = {}
        self._keys: dict[str, _RequestIdentity] = {}

    def find(self, identity: _RequestIdentity) -> RevisionOutcome | None:
        return self._by_identity.get(identity)

    def conflicting_key(self, identity: _RequestIdentity) -> bool:
        """同じキーが、**違う要求**で既に使われているか。"""
        if not identity.idempotency_key:
            return False
        known = self._keys.get(identity.idempotency_key)
        return known is not None and known != identity

    def remember(self, identity: _RequestIdentity, outcome: RevisionOutcome) -> None:
        self._by_identity[identity] = outcome
        if identity.idempotency_key:
            self._keys[identity.idempotency_key] = identity
        while len(self._by_identity) > self._MAX:
            oldest = next(iter(self._by_identity))
            self._by_identity.pop(oldest, None)
            self._keys.pop(oldest.idempotency_key, None)

    def reset(self) -> None:
        self._by_identity.clear()
        self._keys.clear()

    def size(self) -> int:
        return len(self._by_identity)


_DEFAULT_REPLAY_LOG = RevisionReplayLog()


def default_replay_log() -> RevisionReplayLog:
    return _DEFAULT_REPLAY_LOG


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
        # --- 再送の判定を、検査より先に行う（FORGE-019B §2） ---------
        #
        # 応答が届かなかった Client は「古い版・古い文書」で再送してくる。
        # 先に通常検査へ通すと必ず `stale_version` で落ちるので、
        # **その要求が既に成功しているか**を先に見る。
        #
        # ただし冪等キーだけで返さない。要求の身元がすべて一致したときだけ
        # replay する（`_RequestIdentity`）。
        identity = self._identity(
            artifact_id=artifact_id, seen_version_token=seen_version_token,
            document=document, change_request=change_request,
            idempotency_key=idempotency_key,
        )
        replay_log = default_replay_log()
        if identity is not None:
            previous = replay_log.find(identity)
            if previous is not None:
                return replace(previous, replayed=True)
            if replay_log.conflicting_key(identity):
                # **同じキーで違う要求。** replay も処理もしない。
                raise RevisionRejected(
                    RevisionRejectionStage.IDEMPOTENCY_CONFLICT,
                    "this idempotency key belongs to a different revision request",
                )

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
                identity=identity, revision_provider=FORGE_DETERMINISTIC,
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
        regenerated = full_regen(document, change_request)
        revised, validation, attempts = regenerated[0], regenerated[1], regenerated[2]
        # **実際に生成したProviderを受け取る**（FORGE-019B §4）。
        # 4つ目を返さない呼び出し側とも壊れずに動くようにしてある。
        provider_used = regenerated[3] if len(regenerated) > 3 else ""
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
            identity=identity,
            # 空なら「記録し損ねた」——`FORGE_DETERMINISTIC`（AIを呼んで
            # いない）とは**別物**なので、そちらへ倒さない。
            revision_provider=provider_used or "unknown",
        )

    # -- 内部 -------------------------------------------------------------

    @staticmethod
    def _identity(
        *, artifact_id: str | None, seen_version_token: str | None,
        document: dict, change_request: str, idempotency_key: str,
    ) -> "_RequestIdentity | None":
        """この要求の身元（FORGE-019B §2）。

        キーが無ければ`None`——**再送とみなさない**。分からないものを
        「たぶん再送」へ倒すと、本物の別要求が黙って捨てられる
        （017A §2 と同じ姿勢）。
        """
        if not idempotency_key or not artifact_id or not seen_version_token:
            return None
        canonical = json.dumps(
            document, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
        )
        return _RequestIdentity(
            artifact_id=artifact_id,
            version_token=seen_version_token,
            document_binding=hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
            # **要求文そのものは持たない**（利用者の発話、006 §22）。
            change_request_fingerprint=hashlib.sha256(
                change_request.encode("utf-8")
            ).hexdigest(),
            idempotency_key=idempotency_key,
        )

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
        identity: "_RequestIdentity | None" = None,
        revision_provider: str = FORGE_DETERMINISTIC,
        fallback_reason: str | None = None,
        attempts: int = 1,
    ) -> RevisionOutcome:
        """1回の変更を、**まとめて成立させるか、何も残さないか**にする
        （FORGE-019B §1）。

        ---

        ## 以前の順序が壊れていた

            RevisionRecord.record()   ← ここで Learning Event も出ていた
            → Feedback.record()        ← ここで失敗しうる
            → artifact advance

        Feedback が失敗すると API は 422 を返すのに、**RevisionRecord と
        REVISION Learning Event は残った**。残った記録は対応する CORRECTED
        を持たない孤児であり、019A §4 の join からは永久に `NO_FEEDBACK`
        に見える——**評価されないまま Evidence を汚し続ける**。

        ## prepare → validate → commit

        1. **validate**: 書く前に「評価を書けるか」を確かめる（`admit()`）
        2. **stage**: RevisionRecord を置く。ただし
           `observe=False` なので **Learning Event はまだ出さない**
        3. **commit**: 評価 → 版の前進 → 確定した Learning Event

        3 の途中で落ちたら、置いた record を `discard()` して巻き戻す。
        Learning Event はまだ出ていないので、**外から見て何も起きていない**。

        ## DB化するときの移行境界

        いまは単一プロセス・in-memory なので、`admit()` と `record()` の
        間に割り込みが無いことを前提にできる。DB化したら:

        * 1〜3 を**1つの DB transaction** に入れる
        * Learning Event の送信は **durable outbox** へ入れ、commit 後に
          別プロセスが流す（transaction 内でネットワークI/Oをしない）

        `publish()` を独立させてあるのは、その差し替え点にするためである。
        """
        feedback = default_feedback_service()

        # --- 1. validate（まだ1バイトも書かない） ---------------------
        refusal = feedback.admit(
            signal=AcceptanceSignal.CORRECTED,
            artifact_id=capability.handle,
            seen_version_token=capability.version_token,
            idempotency_key=idempotency_key,
        )
        if refusal is not None:
            raise RevisionRejected(
                RevisionRejectionStage.REVISION_EVIDENCE,
                f"correction evidence could not be recorded ({refusal.value})",
            )

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
            provider_id=revision_provider,
            forge_language_version=str(revised.get("version") or ""),
        # --- 2. stage（Learning Event はまだ出さない） ----------------
        ), observe=False)

        # --- 3. commit ------------------------------------------------
        try:
            correction = default_feedback_service().record(
                signal=AcceptanceSignal.CORRECTED,
                artifact_id=capability.handle,
                seen_version_token=capability.version_token,
                idempotency_key=idempotency_key,
            )
            if not correction.recorded:
                # `admit()` を通ったのに落ちた＝想定外。**成功にしない。**
                raise RevisionRejected(
                    RevisionRejectionStage.REVISION_EVIDENCE,
                    "correction evidence could not be recorded",
                )
            # **変更後のDocumentへ束縛し直す**（019A §1）。渡し忘れると
            # 次のRevisionが通らなくなるので、ここが唯一の進め方である。
            advanced = default_artifact_registry().advance_to_revision(
                handle=capability.handle, revision_ref=stored.ref,
                revision_uid=stored.uid, document=revised,
            )
        except Exception:
            # 置いただけの record を取り消す。Learning Event はまだ
            # 出ていないので、外から見て**何も起きていない**。
            revisions.discard(stored.ref)
            raise

        # 確定したので Learning Event を出す。
        revisions.publish(stored)

        outcome = RevisionOutcome(
            document=revised, validation=validation, record=stored, handle=advanced,
            mode=mode, critic_passed=critic_passed, attempts=attempts,
            operation_id=operation_id, target=target, fallback_reason=fallback_reason,
            revision_provider=revision_provider,
        )
        if identity is not None:
            default_replay_log().remember(identity, outcome)
        return outcome


_DEFAULT_SERVICE = RevisionService()


def default_revision_service() -> RevisionService:
    """本番が使う唯一のService。**変更の入口を複数作らない。**"""
    return _DEFAULT_SERVICE
