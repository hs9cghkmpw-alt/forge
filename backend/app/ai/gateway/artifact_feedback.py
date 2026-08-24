"""Artifact Feedback — 「これでいい / 違う」を生成物へ結びつける**唯一の口**
(FORGE-016A §3 / FORGE-017A §2〜§4、2026-08-24)。

---

## なぜServiceを1つにするのか

`note_user_acceptance()`は011から実装されていた。**しかしそれを呼ぶ
経路が1つも無かった**——Forgeが5回繰り返した「作ったが本番から呼ばれ
ない」の状態である（TD65）。

ここで口を作るにあたり、**入口を複数作らない**。

```
/converse の「これでいい」 ─┐
UIの 👍 ボタン（将来）      ─┼→ ArtifactFeedbackService → Evidence
「修正完了」（将来）        ─┘
```

入口が増えるたびに「Evidence Storeを直接呼ぶ近道」が生まれると、
記録の意味が経路ごとにずれる。**通り道を1本にする。**

---

## 3つのIDを混ぜない（017A §3・§4）

commit Bは1つのIDに3つの役目を持たせていた。**分けた。**

| | 何のためか | 寿命 | Clientへ | Cloudへ |
|---|---|---|---|---|
| `ArtifactHandle.handle` | Clientが評価を送り返すため | プロセス内・上限1000件 | **出す** | **出さない** |
| `ArtifactEvidenceId` | Dataset Lineage（系譜） | 記録に貼り付く | 出さない | 出す |
| `version_token` | 世代が変わったかの照合 | ハンドルと同じ | **出す** | **出さない** |

### なぜハンドルを系譜のIDにしてはいけないか

`handle`は**失効する**。プロセスを再起動すれば消えるし、1000件を
超えれば古いものから捨てられる。「どのEventからどのDatasetを作ったか」
をこれで辿ると、**辿れなくなった時点で系譜が切れる**。

さらに`handle`は**Bearer Capability**である——持っている人が評価を
書ける。これをCloudのLearning Eventへ載せると、記録を見た人が誰でも
評価を書き換えられるようになる。用途が正反対である。

### なぜ指紋をClientへ返さないか（017A §4）

commit Bは`document_fingerprint()`（salt無しsha256の先頭32桁）を
そのままClientへ返していた。これは**内容の同一性**を表すので、

* 同じDocumentを作った別々の利用者が**同じ値**を持つ
* 内容の候補が少なければ（低entropy）、**総当たりで中身を言い当てられる**

「hashだから本文は復元不能」という説明は、この2点を無視している。

世代照合に必要なのは「**さっきと同じものか**」だけであり、内容の
同一性ではない。だから**内容と無関係なランダムのtoken**にした。

---

## Feedbackは上書きせず、順番ごと残す（017A §2）

commit Bは2つ目の信号を**捨てて**いた。

```
ACCEPTED → CORRECTED
             ↑ 捨てる
```

`GenerationRecord.user_acceptance`は1つしか値を持てないので、
**要約としては**「最初の信号が勝つ」で良い。後から塗り替えると
「その時点でどう扱われたか」が消えるからである。

しかし**捨ててよいのは要約であって、事実ではない**。

「最初は良いと言ったが、使ってみたら直した」は、Local AIにとって
**最も価値のある系列**である。最初から`CORRECTED`だったものとは
まるで意味が違う（前者は「一見よく見えるが実際には外している」）。
1つのfieldに潰すと、この2つが区別できない。

そこで`ArtifactFeedbackEvent`を**追記専用**で持つ。要約は従来どおり
first-wins、事実は全部残る。

## 同じ送信の繰り返しと、本当の再評価を区別する

ネットワークの再送で同じ評価が2回届くのと、利用者が後から考えを
変えたのとは、**別のこと**である。前者を残すと「2回評価された」と
いう嘘になり、後者を捨てると上に書いた系列が消える。

`idempotency_key`が一致したものだけを再送とみなす。キーが無ければ
**別の評価として追記する**——分からないものを「たぶん再送」へ倒すと、
本物の再評価が静かに消えるからである（`CLAUDE.md` §3）。
"""

from __future__ import annotations

import hashlib
import json
import secrets
import time
from dataclasses import dataclass
from enum import Enum
from uuid import uuid4

from app.ai.gateway.generation_evidence import GenerationEvidenceStore, default_generation_store
from app.ai.gateway.learning_foundation import AcceptanceSignal
from app.ai.gateway.revision_evidence import RevisionEvidenceStore, default_revision_store

__all__ = [
    "ArtifactEvidenceId",
    "ArtifactFeedbackEvent",
    "ArtifactFeedbackService",
    "ArtifactHandle",
    "ArtifactRegistry",
    "EvidenceKind",
    "FeedbackEventLog",
    "FeedbackRejected",
    "FeedbackResult",
    "FeedbackSource",
    "default_artifact_registry",
    "default_feedback_log",
    "default_feedback_service",
    "document_fingerprint",
    "new_version_token",
]


def document_fingerprint(document: dict) -> str:
    """Documentの**内容の同一性**を表す指紋。**内部専用**。

    ⚠️ **Clientへ返さない。Learning Eventへ載せない**（017A §4）。

    内容が同じなら誰が作っても同じ値になるので、Cloudへ出すと
    利用者を跨いだ突き合わせに使える。内容の候補が少なければ
    総当たりで中身を言い当てられる（低entropyなDocumentは実在する
    ——「メモ」1画面のアプリなど）。

    「hashだから本文は復元不能」は、この2点を無視した言い方である。

    使ってよいのは、**同じプロセスの中で内容が変わったかを見る**
    ような用途に限る。世代照合には`new_version_token()`を使うこと。

    正準化してから取る——キーの順序が違うだけで別物と判定されると、
    「変わっていないのに別物扱い」になる。
    """
    canonical = json.dumps(document, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:32]


def new_version_token() -> str:
    """世代を表す**内容と無関係な**token（017A §4）。

    必要なのは「さっきと同じものか」だけで、内容の同一性ではない。
    ランダムなので、同じDocumentでも生成のたびに違う値になる
    ——**それで正しい**。別々の利用者の生成物を突き合わせられない。
    """
    return secrets.token_urlsafe(12)


class EvidenceKind(str, Enum):
    """評価を書く先の種類。"""

    GENERATION = "generation"
    REVISION = "revision"


@dataclass(frozen=True)
class ArtifactEvidenceId:
    """**系譜（Dataset Lineage）のためのID**（017A §3）。

    記録そのものの身元（`uid`）を指す。Clientへは出さない——出す必要が
    無いし、出せば`handle`と混同される。

    `ref`も併せて持つのは、プロセス内でStoreを引くためだけである。
    **系譜として意味を持つのは`uid`の方**で、`ref`はStore内の位置に
    すぎない（プロセスを跨ぐと別の記録を指す）。
    """

    kind: EvidenceKind
    uid: str
    ref: int

    def to_dict(self) -> dict[str, object]:
        """Learning Event / 系譜へ載せる形。**`ref`は載せない。**"""
        return {"kind": self.kind.value, "uid": self.uid}


@dataclass(frozen=True)
class ArtifactHandle:
    """Clientが評価を送り返すための**一時的なcapability**（017A §3）。

    ⚠️ **これは認可ではない。** 推測できないだけである。
    「不透明なIDだから権限を確認済み」とは扱わない（017A §13）。
    Cloud / 複数利用者へ広げるときは、所有者・App・Subjectの境界と
    必ず結びつける必要がある。

    プロセス内メモリのみ・上限1000件なので、**失効する**。
    系譜には使えない（`ArtifactEvidenceId`を使う）。
    """

    handle: str
    evidence_id: ArtifactEvidenceId
    version_token: str
    """世代照合用。**内容と無関係なランダム値**（017A §4）。"""

    session_id: str | None = None
    created_at: float = 0.0

    def to_client_dict(self) -> dict[str, str]:
        """Clientへ返す形。**系譜のIDは含まない。**"""
        return {"artifact_id": self.handle, "version_token": self.version_token}


class FeedbackSource(str, Enum):
    """その評価が**どこから来たか**。"""

    USER_EXPLICIT = "user_explicit"
    """利用者が明示的に伝えた（ボタン・「これでいい」）。**最も強い**。"""

    INFERRED = "inferred"
    """Forgeが会話から推定した。利用者が言い切ってはいない。"""

    SYSTEM = "system"
    """Forge自身の判定（Runtimeで落ちた等）。"""

    UNKNOWN = "unknown"
    """**既定値。** 由来を記録し損ねた。楽観側へ倒さない。"""

    @property
    def is_usable_as_supervision(self) -> bool:
        """教師信号として使ってよいか。

        `INFERRED`は**使わない**。Forgeの推定を「利用者がそう言った」
        として学習すると、Forge自身の思い込みを増幅する。
        """
        return self is FeedbackSource.USER_EXPLICIT


@dataclass(frozen=True)
class ArtifactFeedbackEvent:
    """1回の評価。**追記専用**（017A §2）。

    **生の発話を持たない。** 何と言って評価したかは記録しない
    （006 §22 / 016A §10と同じPrivacy境界）。
    """

    event_id: str
    artifact_evidence_ref: ArtifactEvidenceId
    signal: AcceptanceSignal
    sequence: int
    """同じ生成物への何回目の評価か。**1から始まる。**"""

    source: FeedbackSource = FeedbackSource.UNKNOWN
    recorded_at: float = 0.0
    idempotency_key: str = ""
    """同じ送信の繰り返しを見分けるためのキー。**空なら再送ではない。**"""

    def to_dict(self) -> dict[str, object]:
        """診断・集計用。**本文が現れないことが不変条件である。**"""
        return {
            "event_id": self.event_id,
            "artifact_evidence_ref": self.artifact_evidence_ref.to_dict(),
            "signal": self.signal.value,
            "sequence": self.sequence,
            "source": self.source.value,
            "recorded_at": self.recorded_at,
        }


class FeedbackRejected(str, Enum):
    """受け付けなかった理由。**黙って捨てない。**"""

    UNKNOWN_ARTIFACT = "unknown_artifact"
    """そんな生成物は知らない（またはハンドルが失効した）。"""

    STALE_ARTIFACT = "stale_artifact"
    """利用者が見ていたものと、いまの世代が違う。"""

    DUPLICATE_REQUEST = "duplicate_request"
    """**同じ送信の繰り返し**（`idempotency_key`が一致した）。

    「もう評価済み」とは違う。後から考えが変わった評価は
    **追記される**（017A §2）。
    """

    UNUSABLE_SIGNAL = "unusable_signal"
    """`UNKNOWN`を送ってきた。沈黙は情報ではない。"""


@dataclass(frozen=True)
class FeedbackResult:
    """記録できたか、できなかったならなぜか。"""

    recorded: bool
    """**Eventとして追記できたか。**"""

    signal: AcceptanceSignal
    summary_updated: bool = False
    """要約（`user_acceptance`）が更新されたか。

    2回目以降は`False`になる——要約は最初の信号が勝つ。
    **`recorded=True, summary_updated=False`は正常**であり、
    「事実は残ったが要約は変えなかった」という意味である。
    """

    rejected: FeedbackRejected | None = None
    event: ArtifactFeedbackEvent | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "recorded": self.recorded,
            "signal": self.signal.value,
            "summary_updated": self.summary_updated,
            "rejected": self.rejected.value if self.rejected else None,
        }


class FeedbackEventLog:
    """`ArtifactFeedbackEvent`の**追記専用**の保持。

    更新も削除も無い。プロセス内メモリのみ（TD41）。
    """

    _MAX_EVENTS = 5000

    def __init__(self, *, now: object = time.time) -> None:
        self._events: list[ArtifactFeedbackEvent] = []
        self._by_idempotency: dict[str, ArtifactFeedbackEvent] = {}
        self._now = now

    def append(
        self,
        *,
        evidence_id: ArtifactEvidenceId,
        signal: AcceptanceSignal,
        source: FeedbackSource = FeedbackSource.UNKNOWN,
        idempotency_key: str = "",
    ) -> ArtifactFeedbackEvent:
        event = ArtifactFeedbackEvent(
            event_id=uuid4().hex,
            artifact_evidence_ref=evidence_id,
            signal=signal,
            sequence=self.next_sequence(evidence_id),
            source=source,
            recorded_at=float(self._now()),
            idempotency_key=idempotency_key,
        )
        self._events.append(event)
        if idempotency_key:
            self._by_idempotency[idempotency_key] = event
        while len(self._events) > self._MAX_EVENTS:
            dropped = self._events.pop(0)
            self._by_idempotency.pop(dropped.idempotency_key, None)
        return event

    def find_by_idempotency_key(self, key: str) -> ArtifactFeedbackEvent | None:
        return self._by_idempotency.get(key) if key else None

    def for_evidence(self, evidence_id: ArtifactEvidenceId) -> tuple[ArtifactFeedbackEvent, ...]:
        """ある生成物への評価を、**届いた順**に返す。"""
        return tuple(
            e for e in self._events
            if e.artifact_evidence_ref.uid == evidence_id.uid
        )

    def next_sequence(self, evidence_id: ArtifactEvidenceId) -> int:
        return len(self.for_evidence(evidence_id)) + 1

    def all_events(self) -> tuple[ArtifactFeedbackEvent, ...]:
        return tuple(self._events)

    def reset(self) -> None:
        self._events.clear()
        self._by_idempotency.clear()

    def size(self) -> int:
        return len(self._events)


class ArtifactRegistry:
    """`handle` → 生成物。プロセス内メモリのみ（TD41）。

    **失効することが前提の入れ物である。** ここに入っているかどうかは
    「その生成物が存在するか」ではなく「まだ評価を受け付けられるか」
    でしかない。
    """

    _MAX = 1000

    def __init__(self, *, now: object = time.time) -> None:
        self._by_handle: dict[str, ArtifactHandle] = {}
        self._latest_by_session: dict[str, str] = {}
        self._now = now

    def register(
        self,
        *,
        generation_ref: int,
        generation_uid: str,
        session_id: str | None = None,
        revision_ref: int | None = None,
        revision_uid: str = "",
    ) -> ArtifactHandle:
        """評価を受け付けられるようにする。

        **Documentを受け取らない**（017A §4）。世代tokenは内容から
        作らないので、そもそもDocumentを見る必要が無い。見ないなら
        受け取らない——受け取れば、いつか誰かが内容から何かを作る。
        """
        if revision_ref is not None:
            evidence_id = ArtifactEvidenceId(EvidenceKind.REVISION, revision_uid, revision_ref)
        else:
            evidence_id = ArtifactEvidenceId(EvidenceKind.GENERATION, generation_uid, generation_ref)

        handle = ArtifactHandle(
            # 推測できないハンドルにする。連番だと他人の生成物へ評価を書ける。
            handle=secrets.token_urlsafe(16),
            evidence_id=evidence_id,
            version_token=new_version_token(),
            session_id=session_id,
            created_at=float(self._now()),
        )
        self._by_handle[handle.handle] = handle
        if session_id:
            self._latest_by_session[session_id] = handle.handle
        if len(self._by_handle) > self._MAX:
            for key in sorted(
                self._by_handle, key=lambda h: self._by_handle[h].created_at
            )[: len(self._by_handle) - self._MAX]:
                del self._by_handle[key]
        return handle

    def resolve(self, handle: str) -> ArtifactHandle | None:
        return self._by_handle.get(handle)

    def latest_for_session(self, session_id: str) -> ArtifactHandle | None:
        handle = self._latest_by_session.get(session_id)
        return self._by_handle.get(handle) if handle else None

    def reset(self) -> None:
        self._by_handle.clear()
        self._latest_by_session.clear()

    def size(self) -> int:
        return len(self._by_handle)


class ArtifactFeedbackService:
    """「これでいい / 違う」を記録する**唯一のService**。"""

    def __init__(
        self,
        *,
        registry: ArtifactRegistry | None = None,
        generations: GenerationEvidenceStore | None = None,
        revisions: RevisionEvidenceStore | None = None,
        events: FeedbackEventLog | None = None,
    ) -> None:
        self._registry = registry or default_artifact_registry()
        self._generations = generations or default_generation_store()
        self._revisions = revisions or default_revision_store()
        self._events = events or default_feedback_log()

    def record(
        self,
        *,
        signal: AcceptanceSignal,
        artifact_id: str | None = None,
        session_id: str | None = None,
        seen_version_token: str | None = None,
        source: FeedbackSource = FeedbackSource.USER_EXPLICIT,
        idempotency_key: str = "",
    ) -> FeedbackResult:
        """評価を記録する。

        `artifact_id`（ハンドル）か`session_id`のどちらかで生成物を指す。
        **Clientから生成物の内部refは受け取らない。**

        `seen_version_token`が渡され、いまの世代と違えば拒否する
        ——利用者が見ていたものと違うものへ評価を書かない。
        """
        if signal is AcceptanceSignal.UNKNOWN:
            # 沈黙は情報ではない。要約にも事実にも残さない。
            return FeedbackResult(False, signal, rejected=FeedbackRejected.UNUSABLE_SIGNAL)

        handle = self._resolve(artifact_id=artifact_id, session_id=session_id)
        if handle is None:
            return FeedbackResult(False, signal, rejected=FeedbackRejected.UNKNOWN_ARTIFACT)

        if seen_version_token and seen_version_token != handle.version_token:
            return FeedbackResult(False, signal, rejected=FeedbackRejected.STALE_ARTIFACT)

        duplicate = self._events.find_by_idempotency_key(idempotency_key)
        if duplicate is not None:
            # **同じ送信の繰り返し。** 「もう評価済み」とは違う。
            return FeedbackResult(
                False, signal, rejected=FeedbackRejected.DUPLICATE_REQUEST, event=duplicate
            )

        store = self._store_for(handle.evidence_id.kind)
        if store.get(handle.evidence_id.ref) is None:
            return FeedbackResult(False, signal, rejected=FeedbackRejected.UNKNOWN_ARTIFACT)

        # **1. 事実を追記する。** 2回目以降も捨てない（017A §2）。
        event = self._events.append(
            evidence_id=handle.evidence_id,
            signal=signal,
            source=source,
            idempotency_key=idempotency_key,
        )

        # **2. 要約は最初の信号が勝つ。** 塗り替えると「その時点でどう
        #     扱われたか」が消える。0件でも失敗ではない。
        summary_updated = bool(store.note_user_acceptance([handle.evidence_id.ref], signal))

        return FeedbackResult(True, signal, summary_updated=summary_updated, event=event)

    def history(self, evidence_id: ArtifactEvidenceId) -> tuple[ArtifactFeedbackEvent, ...]:
        """その生成物への評価の**時系列**。"""
        return self._events.for_evidence(evidence_id)

    def _store_for(self, kind: EvidenceKind):  # noqa: ANN202
        return self._revisions if kind is EvidenceKind.REVISION else self._generations

    def _resolve(
        self, *, artifact_id: str | None, session_id: str | None
    ) -> ArtifactHandle | None:
        if artifact_id:
            return self._registry.resolve(artifact_id)
        if session_id:
            return self._registry.latest_for_session(session_id)
        return None


_DEFAULT_REGISTRY = ArtifactRegistry()
_DEFAULT_EVENT_LOG = FeedbackEventLog()
_DEFAULT_SERVICE = ArtifactFeedbackService(
    registry=_DEFAULT_REGISTRY, events=_DEFAULT_EVENT_LOG
)


def default_artifact_registry() -> ArtifactRegistry:
    return _DEFAULT_REGISTRY


def default_feedback_log() -> FeedbackEventLog:
    return _DEFAULT_EVENT_LOG


def default_feedback_service() -> ArtifactFeedbackService:
    """本番が使う唯一のService。**Evidence Storeを直接呼ぶ口を作らない。**"""
    return _DEFAULT_SERVICE
