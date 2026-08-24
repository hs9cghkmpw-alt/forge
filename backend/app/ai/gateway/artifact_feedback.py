"""Artifact Feedback — 「これでいい / 違う」を生成物へ結びつける**唯一の口**
(FORGE-016A §3、2026-08-24)。

---

## なぜServiceを1つにするのか

`note_user_acceptance()`は前から実装されていた。**しかしそれを呼ぶ
経路が1つも無かった**——Forgeが4回繰り返した「作ったが本番から呼ばれ
ない」の状態である（TD65）。

ここで口を作るにあたり、**入口を複数作らない**。

```
/converse の「これでいい」 ─┐
UIの 👍 ボタン（将来）      ─┼→ ArtifactFeedbackService → Evidence
「修正完了」（将来）        ─┘
```

入口が増えるたびに「Evidence Storeを直接呼ぶ近道」が生まれると、
記録の意味が経路ごとにずれる。**通り道を1本にする。**

## Clientに生のrefを触らせない

```
❌ client → {"generation_refs": [7, 8, 9], "signal": "accepted"}
✅ client → {"artifact_id": "<Forgeが発行した不透明なID>", "signal": "accepted"}
```

任意のrefを信用すると、利用者が見てもいない生成物へ「受け入れた」を
書けてしまう。**それは学習素材の捏造である。** Forgeが発行したIDから
Forge自身が解決する。

## なぜSessionだけで解決しないのか

`/converse`はBUILD/UPDATEの後に`ConversationStore.discard()`で
セッションを捨てる（本番のコードで確認済み）。捨てた後にも
「これでいい」は来るので、セッションだけを頼りにできない。

そこで**生成物そのものにIDを振り**、セッションIDは付随情報として持つ。
セッションが生きている間は`session_id`からも引ける。

## 最初の信号が勝つ

同じ生成物へ`ACCEPTED`と`CORRECTED`が両方来たら、**最初のものを残す**。

理由: 利用者は「これでいい」と言った後で気が変わることがあるが、
その場合は**新しい生成物**（変更後のもの）に対する評価になるべきで
ある。同じ生成物の評価を後から塗り替えると、「その時点でどう扱われた
か」という事実が消える。
"""

from __future__ import annotations

import hashlib
import json
import secrets
import time
from dataclasses import dataclass
from enum import Enum

from app.ai.gateway.generation_evidence import GenerationEvidenceStore, default_generation_store
from app.ai.gateway.learning_foundation import AcceptanceSignal
from app.ai.gateway.revision_evidence import RevisionEvidenceStore, default_revision_store

__all__ = [
    "ArtifactFeedbackService",
    "ArtifactIdentity",
    "ArtifactRegistry",
    "FeedbackRejected",
    "FeedbackResult",
    "default_artifact_registry",
    "default_feedback_service",
    "document_fingerprint",
]


def document_fingerprint(document: dict) -> str:
    """Documentの世代を表す短い指紋（§5 Optimistic Concurrency）。

    **内容そのものは持たない。** ハッシュなので、ここから本文は復元
    できない（006 §22のPrivacy境界を越えない）。

    正準化してから取る——キーの順序が違うだけで別物と判定されると、
    「変わっていないのに古い扱い」になる。
    """
    canonical = json.dumps(document, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:32]


class FeedbackRejected(str, Enum):
    """受け付けなかった理由。**黙って捨てない。**"""

    UNKNOWN_ARTIFACT = "unknown_artifact"
    """そんな生成物は知らない。"""

    STALE_ARTIFACT = "stale_artifact"
    """利用者が見ていたものと、いまの世代が違う（§5）。"""

    ALREADY_RECORDED = "already_recorded"
    """既に評価が付いている（最初の信号が勝つ）。"""


@dataclass(frozen=True)
class ArtifactIdentity:
    """利用者が見ている生成物1つ分の身元。

    **Forgeが発行する。** Clientは`artifact_id`だけを持ち、内部のrefは
    知らない。
    """

    artifact_id: str
    generation_ref: int
    revision_ref: int | None = None
    """変更後なら、その変更の番号。評価はこちらへ付く。"""

    session_id: str | None = None
    fingerprint: str = ""
    """この世代のDocumentの指紋。古いものへ評価やPatchを当てないため。"""

    created_at: float = 0.0

    @property
    def evidence_ref(self) -> tuple[str, int]:
        """評価を書く先。**変更があれば変更へ、無ければ生成へ。**"""
        if self.revision_ref is not None:
            return ("revision", self.revision_ref)
        return ("generation", self.generation_ref)


@dataclass(frozen=True)
class FeedbackResult:
    """記録できたか、できなかったならなぜか。"""

    recorded: bool
    signal: AcceptanceSignal
    rejected: FeedbackRejected | None = None
    identity: ArtifactIdentity | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "recorded": self.recorded,
            "signal": self.signal.value,
            "rejected": self.rejected.value if self.rejected else None,
        }


class ArtifactRegistry:
    """`artifact_id` → 身元。プロセス内メモリのみ（TD41）。"""

    _MAX = 1000

    def __init__(self, *, now: object = time.time) -> None:
        self._by_id: dict[str, ArtifactIdentity] = {}
        self._latest_by_session: dict[str, str] = {}
        self._now = now

    def register(
        self,
        *,
        generation_ref: int,
        document: dict | None = None,
        session_id: str | None = None,
        revision_ref: int | None = None,
    ) -> ArtifactIdentity:
        identity = ArtifactIdentity(
            # 推測できないIDにする。連番だと他人の生成物へ評価を書ける。
            artifact_id=secrets.token_urlsafe(16),
            generation_ref=generation_ref,
            revision_ref=revision_ref,
            session_id=session_id,
            fingerprint=document_fingerprint(document) if document is not None else "",
            created_at=float(self._now()),
        )
        self._by_id[identity.artifact_id] = identity
        if session_id:
            self._latest_by_session[session_id] = identity.artifact_id
        if len(self._by_id) > self._MAX:
            for artifact_id in sorted(
                self._by_id, key=lambda a: self._by_id[a].created_at
            )[: len(self._by_id) - self._MAX]:
                del self._by_id[artifact_id]
        return identity

    def resolve(self, artifact_id: str) -> ArtifactIdentity | None:
        return self._by_id.get(artifact_id)

    def latest_for_session(self, session_id: str) -> ArtifactIdentity | None:
        artifact_id = self._latest_by_session.get(session_id)
        return self._by_id.get(artifact_id) if artifact_id else None

    def reset(self) -> None:
        self._by_id.clear()
        self._latest_by_session.clear()

    def size(self) -> int:
        return len(self._by_id)


class ArtifactFeedbackService:
    """「これでいい / 違う」を記録する**唯一のService**。"""

    def __init__(
        self,
        *,
        registry: ArtifactRegistry | None = None,
        generations: GenerationEvidenceStore | None = None,
        revisions: RevisionEvidenceStore | None = None,
    ) -> None:
        self._registry = registry or default_artifact_registry()
        self._generations = generations or default_generation_store()
        self._revisions = revisions or default_revision_store()

    def record(
        self,
        *,
        signal: AcceptanceSignal,
        artifact_id: str | None = None,
        session_id: str | None = None,
        seen_fingerprint: str | None = None,
    ) -> FeedbackResult:
        """評価を記録する。

        `artifact_id`か`session_id`のどちらかで生成物を指す。
        **Clientから生成物の内部refは受け取らない。**

        `seen_fingerprint`が渡され、いまの世代と違えば拒否する
        ——利用者が見ていたものと違うものへ評価を書かない（§5）。
        """
        identity = self._resolve(artifact_id=artifact_id, session_id=session_id)
        if identity is None:
            return FeedbackResult(False, signal, FeedbackRejected.UNKNOWN_ARTIFACT)

        if (
            seen_fingerprint
            and identity.fingerprint
            and seen_fingerprint != identity.fingerprint
        ):
            return FeedbackResult(False, signal, FeedbackRejected.STALE_ARTIFACT, identity)

        kind, ref = identity.evidence_ref
        store = self._revisions if kind == "revision" else self._generations

        # **「既に評価済みか」はEvidence自身へ聞く。**
        #
        # Service側に「記録したartifact_id」の集合を持つ設計にしかけたが、
        # やめた。同じ事実の写しが2箇所にできると必ずずれる——Storeだけを
        # resetしたテストでは「Serviceは記録済みと言うがEvidenceは空」に
        # なる。Storeが唯一の真実である。
        existing = store.get(ref)
        if existing is None:
            return FeedbackResult(False, signal, FeedbackRejected.UNKNOWN_ARTIFACT, identity)
        if existing.user_acceptance is not AcceptanceSignal.UNKNOWN:
            # **最初の信号が勝つ。** 後から塗り替えると「その時点でどう
            # 扱われたか」という事実が消える。
            return FeedbackResult(False, signal, FeedbackRejected.ALREADY_RECORDED, identity)

        if not store.note_user_acceptance([ref], signal):
            # `UNKNOWN`を渡された場合(沈黙は情報ではない、`AcceptanceSignal`)。
            return FeedbackResult(False, signal, FeedbackRejected.UNKNOWN_ARTIFACT, identity)
        return FeedbackResult(True, signal, None, identity)

    def _resolve(
        self, *, artifact_id: str | None, session_id: str | None
    ) -> ArtifactIdentity | None:
        if artifact_id:
            return self._registry.resolve(artifact_id)
        if session_id:
            return self._registry.latest_for_session(session_id)
        return None


_DEFAULT_REGISTRY = ArtifactRegistry()
_DEFAULT_SERVICE = ArtifactFeedbackService(registry=_DEFAULT_REGISTRY)


def default_artifact_registry() -> ArtifactRegistry:
    return _DEFAULT_REGISTRY


def default_feedback_service() -> ArtifactFeedbackService:
    """本番が使う唯一のService。**Evidence Storeを直接呼ぶ口を作らない。**"""
    return _DEFAULT_SERVICE
