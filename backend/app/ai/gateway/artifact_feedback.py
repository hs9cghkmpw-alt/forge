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
import hmac
import json
import secrets
import threading
import time
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from enum import Enum
from uuid import uuid4

from app.ai.gateway.generation_evidence import GenerationEvidenceStore, default_generation_store
from app.ai.gateway.learning_foundation import AcceptanceSignal
from app.ai.gateway.revision_evidence import RevisionEvidenceStore, default_revision_store

__all__ = [
    "ArtifactCasConflict",
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
    "StagedFeedbackEvent",
    "default_artifact_registry",
    "default_feedback_log",
    "default_feedback_service",
    "document_binding",
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


#: **Documentの身元を照合するための、プロセス内だけの鍵**（FORGE-019A §1）。
#:
#: `document_fingerprint()`（salt無しsha256）を使わない理由:
#:
#: * 内容が同じなら誰が作っても同じ値になる → 利用者を跨いだ突き合わせに使える
#: * 低entropyな内容は総当たりで言い当てられる
#:
#: HMACなら、鍵を知らない側は値から内容を復元も照合もできない。鍵はプロセス
#: 起動ごとに変わる——**保存もしないし、外へも出さない**。
_DOCUMENT_BINDING_KEY = secrets.token_bytes(32)


def document_binding(document: dict) -> str:
    """そのDocumentの**身元**（FORGE-019A §1）。**内部専用。**

    ⚠️ **Clientへ返さない。Learning Eventへ載せない。**

    ---

    ## 何を防ぐためのものか

    017Aで`artifact_id`（capability）と`version_token`（世代）を分けた。
    しかし**Documentそのものは照合していなかった**ので、

    ```
    正しい artifact_id + 正しい version_token + 別のDocument
    ```

    が通ってしまった。Revisionは「その生成物をこう直した」という記録
    なので、**直した対象が別物なら記録は嘘になる**——Revision lineageを
    汚染できる。

    Handleを持っている人が、自分で作った任意のJSONを「Forgeが生成した
    ものを直した」ことにできる、という形である。

    ## 正準化してから取る

    キーの順序が違うだけで別物と判定されると、往復しただけで拒否される。
    """
    canonical = json.dumps(document, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hmac.new(_DOCUMENT_BINDING_KEY, canonical.encode("utf-8"), hashlib.sha256).hexdigest()


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

    document_binding: str = ""
    """この版の**Documentの身元**（FORGE-019A §1）。**内部専用。**

    `version_token`は「さっきと同じ版か」しか言わない。Clientが
    正しいhandleと正しいtokenを持ったまま**別のDocument**を送ると、
    017Aの検査は全部通る。Revisionは「その生成物をこう直した」という
    記録なので、直した対象が別物なら記録は嘘になる。

    空文字は「束縛していない」——古い経路との互換のために許すが、
    Revisionは**束縛が無ければ通さない**（`RevisionService`）。
    """

    session_id: str | None = None
    created_at: float = 0.0

    def to_client_dict(self) -> dict[str, str]:
        """Clientへ返す形。**系譜のIDも、Documentの身元も含まない。**"""
        return {"artifact_id": self.handle, "version_token": self.version_token}

    def binds(self, document: dict) -> bool:
        """このcapabilityが、その`document`のものか（FORGE-019A §1）。

        **束縛が無ければ`False`。** 「記録し忘れ」を「照合済み」へ
        倒さない（`CLAUDE.md` §3）。
        """
        if not self.document_binding:
            return False
        return hmac.compare_digest(self.document_binding, document_binding(document))


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


@dataclass(frozen=True)
class StagedFeedbackEvent:
    """**まだ書いていない**評価（FORGE-019C §5）。

    ---

    ## なぜ「まだ書いていない」形が要るのか

    019B は Revision の途中で `record()` を呼び、失敗したら
    `RevisionRecord` の方を巻き戻していた。しかし **`FeedbackEventLog`
    は追記専用なので巻き戻せない**——だから
    「advance が落ちると CORRECTED だけ残る」が仕様として残った。

    追記できないなら、**追記する前に版を進めればよい。**

        prepare（書かない）
          → 版の CAS 前進（ここだけが競合で落ちうる）
          → commit（ここで初めて追記する）

    こうすると、落ちる可能性のある段が追記より前に来るので、
    **巻き戻す必要が無い**。追記専用の契約を1文字も緩めずに atomic に
    できる。

    ## これ自体は事実ではない

    `StagedFeedbackEvent` は「こう書くつもりだ」という**意図**である。
    捨てても何も失われない（`discard_staged_event()` が何もしないのは
    そのため）。事実になるのは `commit_event()` を通ったときだけ。
    """

    evidence_id: ArtifactEvidenceId
    signal: AcceptanceSignal
    source: FeedbackSource
    idempotency_key: str


class FeedbackEventLog:
    """`ArtifactFeedbackEvent`の**追記専用**の保持。

    更新も削除も無い。プロセス内メモリのみ（TD41）。
    """

    _MAX_EVENTS = 5000

    def __init__(self, *, now: object = time.time) -> None:
        self._events: list[ArtifactFeedbackEvent] = []
        # **キーだけでなく、どの生成物への評価かも込みで見る**（019B §3）。
        #
        # 以前は raw key だけの global dict だったので、Client が単純な
        # 連番キーを使うと**無関係な生成物への評価が「重複」として捨て
        # られた**。評価が黙って消えるのは、記録の穴として最も悪い部類
        # である（利用者は言ったつもりで、Forgeは聞いていない）。
        #
        # 将来 subject / app の境界を足すときは、このtupleを伸ばす。
        self._by_idempotency: dict[tuple[str, str], ArtifactFeedbackEvent] = {}
        self._now = now

    def prepare_event(
        self,
        *,
        evidence_id: ArtifactEvidenceId,
        signal: AcceptanceSignal,
        source: FeedbackSource = FeedbackSource.UNKNOWN,
        idempotency_key: str = "",
    ) -> StagedFeedbackEvent:
        """**1バイトも書かずに**「こう書くつもりだ」を作る（019C §5）。"""
        return StagedFeedbackEvent(
            evidence_id=evidence_id, signal=signal, source=source,
            idempotency_key=idempotency_key,
        )

    def commit_event(self, staged: StagedFeedbackEvent) -> ArtifactFeedbackEvent:
        """staged を**事実にする**。ここで初めて追記される。

        **投影はしない。** Learning への投影は確定後に Outbox が行う
        （019C §6）——追記の途中でネットワークI/Oの都合を持ち込まない。
        """
        event = ArtifactFeedbackEvent(
            event_id=uuid4().hex,
            artifact_evidence_ref=staged.evidence_id,
            signal=staged.signal,
            sequence=self.next_sequence(staged.evidence_id),
            source=staged.source,
            recorded_at=float(self._now()),
            idempotency_key=staged.idempotency_key,
        )
        self._events.append(event)
        if staged.idempotency_key:
            self._by_idempotency[
                self._scope(staged.evidence_id, staged.idempotency_key)
            ] = event
        while len(self._events) > self._MAX_EVENTS:
            dropped = self._events.pop(0)
            self._by_idempotency.pop(
                self._scope(dropped.artifact_evidence_ref, dropped.idempotency_key), None,
            )
        return event

    def discard_staged_event(self, staged: StagedFeedbackEvent) -> None:
        """staged を捨てる。**何も書いていないので、何も起きない。**

        呼ぶ側が「巻き戻した」と書けるようにするためだけに在る。
        追記専用の log を削る口をここに作らない。
        """
        _ = staged

    def append(
        self,
        *,
        evidence_id: ArtifactEvidenceId,
        signal: AcceptanceSignal,
        source: FeedbackSource = FeedbackSource.UNKNOWN,
        idempotency_key: str = "",
    ) -> ArtifactFeedbackEvent:
        """単独の `/feedback` 用。**prepare → commit → 投影**をまとめる。

        Revision は自分で段を分けるのでこれを使わない（019C §5）。
        """
        event = self.commit_event(self.prepare_event(
            evidence_id=evidence_id, signal=signal, source=source,
            idempotency_key=idempotency_key,
        ))
        from app.ai.gateway.learning_outbox import (  # noqa: PLC0415
            default_projection_outbox,
        )
        default_projection_outbox().submit(event)
        return event

    @staticmethod
    def _scope(evidence_id: ArtifactEvidenceId, key: str) -> tuple[str, str]:
        """冪等キーが効く範囲（019B §3）。**生成物ごとに独立。**"""
        return (evidence_id.uid, key)

    def find_by_idempotency_key(
        self, key: str, *, evidence_id: ArtifactEvidenceId | None = None,
    ) -> ArtifactFeedbackEvent | None:
        """同じ生成物への、同じキーの評価を探す。

        `evidence_id`を省略した場合は**どの生成物とも一致しない**
        ——範囲が分からないものを「重複」へ倒さない（`CLAUDE.md` §3）。
        """
        if not key or evidence_id is None:
            return None
        return self._by_idempotency.get(self._scope(evidence_id, key))

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


class ArtifactCasConflict(Exception):
    """**期待していた版と、いまの版が違う**（FORGE-019C §7.3）。

    ---

    ## blind overwrite をやめた

    019B の `advance_to_revision()` は、現在値を見ずに新しい
    `ArtifactHandle` を書き込んでいた。単一プロセスなら直前に解決した
    ハンドルがそのまま有効だ、という前提だった。

    その前提は成り立たない。FastAPI の `def`（async でない）endpoint は
    **thread pool で並行に走る**ので、同じ版から始まった2つの Revision が
    どちらも「自分が正しい」と思ったまま書き込める。あとから書いた方が
    勝ち、先の変更は**痕跡なく消える**（Lost Update）。

    ## 期待値を省略できないようにした

    `expected` を渡さない呼び出しも conflict にする。「省略したら
    無条件で上書き」を残すと、**その口が新しい blind overwrite になる**
    ——`CLAUDE.md` §3 の「忘れずに呼ばれる保証が無いものは忘れられる」
    と同じ形である。
    """


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
        # **生成物ごとの直列化**（019C §7）。
        #
        # global lock にすると、無関係な利用者の変更まで1本に並ぶ。
        # 逆に lock を作りっぱなしにすると map が無限に増える。
        # 使用中だけ保持し、最後の1人が抜けたら捨てる。
        self._locks: dict[str, tuple[threading.RLock, list[int]]] = {}
        self._locks_guard = threading.Lock()

    @contextmanager
    def lock_for(self, handle: str) -> "Iterator[None]":
        """その生成物だけを直列化する（019C §7）。

        * global lock で全 Artifact を無駄に直列化しない
        * lock map を無限に増やさない（使用中だけ持つ）
        * 例外でも必ず解放する（`finally`）
        * **入れ子にしない**——同時に持つ lock は常に1つなので deadlock しない
        """
        with self._locks_guard:
            entry = self._locks.get(handle)
            if entry is None:
                entry = (threading.RLock(), [0])
                self._locks[handle] = entry
            lock, waiters = entry
            waiters[0] += 1
        lock.acquire()
        try:
            yield
        finally:
            lock.release()
            with self._locks_guard:
                waiters[0] -= 1
                if waiters[0] <= 0:
                    self._locks.pop(handle, None)

    def register(
        self,
        *,
        generation_ref: int,
        generation_uid: str,
        session_id: str | None = None,
        revision_ref: int | None = None,
        revision_uid: str = "",
        document: dict | None = None,
    ) -> ArtifactHandle:
        """評価とRevisionを受け付けられるようにする。

        `document`は**身元の照合にだけ**使う（FORGE-019A §1）。
        HMACを取ったら捨てるので、内容はここに残らない。

        017Aでは「見ないなら受け取らない」として`document`を外したが、
        **見る必要が出た**——Revisionは「その生成物を直した」という記録
        なので、直した対象が同じものかを確かめないと記録が嘘になりうる。
        受け取るからには、**内容を保持せず・外へ出さない**形にする。
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
            document_binding=document_binding(document) if document is not None else "",
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

    def advance_to_revision(
        self, *, handle: str, revision_ref: int, revision_uid: str,
        document: dict | None = None,
        expected: ArtifactHandle | None = None,
    ) -> ArtifactHandle:
        """**Compare-and-swap** で版を進める（FORGE-019A §1 / 019C §7.3）。

        `expected` は「自分が検査したときの版」である。いまの版がそれと
        違えば `ArtifactCasConflict`——**誰かが先に進めた**ので、
        この変更はもう成り立たない。

        照合するのは3つとも:

        * `version_token` — 世代
        * `evidence_id.uid` — 系譜の位置
        * `document_binding` — その版の中身の身元

        1つでも欠けた比較にしない。`version_token` だけ見ると、同じ
        token のまま別の系譜へ差し替えられた場合を見逃す。

        `document`（変更後のもの）を渡すと、次のRevisionはその文書に
        束縛される。渡さないと束縛が空になり、**次のRevisionは通らない**
        ——連鎖を切らないために必ず渡すこと。
        """
        current = self._by_handle.get(handle)
        if current is None:
            raise KeyError("unknown artifact capability")
        if expected is None:
            # **期待値を渡さない呼び出しを許さない**（fail closed）。
            raise ArtifactCasConflict(
                "advancing an artifact requires the version it was checked against"
            )
        if (
            expected.version_token != current.version_token
            or expected.evidence_id.uid != current.evidence_id.uid
            or expected.document_binding != current.document_binding
        ):
            raise ArtifactCasConflict("artifact advanced concurrently")
        advanced = ArtifactHandle(
            handle=current.handle,
            evidence_id=ArtifactEvidenceId(EvidenceKind.REVISION, revision_uid, revision_ref),
            version_token=new_version_token(),
            document_binding=document_binding(document) if document is not None else "",
            session_id=current.session_id,
            created_at=float(self._now()),
        )
        self._by_handle[handle] = advanced
        return advanced

    def restore(self, previous: ArtifactHandle) -> None:
        """**Transactionの巻き戻し専用**（FORGE-019C §4）。

        ⚠️ これは「版を戻してよい」という意味ではない。CAS で進めた直後に
        後段が落ちた場合、**その版はまだ誰にも見えていない**——
        `lock_for()` を握ったままなので、他の要求は入れない。その狭い窓の
        中だけで使う。

        確定した版を戻す用途に使ってはならない。
        """
        self._by_handle[previous.handle] = previous

    def latest_for_session(self, session_id: str) -> ArtifactHandle | None:
        handle = self._latest_by_session.get(session_id)
        return self._by_handle.get(handle) if handle else None

    def reset(self) -> None:
        self._by_handle.clear()
        self._latest_by_session.clear()
        with self._locks_guard:
            self._locks.clear()

    def size(self) -> int:
        return len(self._by_handle)

    def lock_table_size(self) -> int:
        """保持している lock の数。**無限増殖していないこと**を見るため。"""
        with self._locks_guard:
            return len(self._locks)


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

        duplicate = self._events.find_by_idempotency_key(
            idempotency_key, evidence_id=handle.evidence_id,
        )
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

    def _admit_handle(
        self, *, signal: AcceptanceSignal, handle: ArtifactHandle, idempotency_key: str,
    ) -> FeedbackRejected | None:
        """解決済みハンドルに対する検査（FORGE-019C §5）。

        ---

        ## `admit()` を消した

        019B は「書かずに、書けるかどうかだけ調べる」`admit()` を持って
        いた。019C で `prepare()`（調べたうえで、そのまま commit できる
        staged を返す）に置き換えたので、**`admit()` を呼ぶ経路は1つも
        無くなった**。

        残しておけば「調べるだけの口」と「調べて組み立てる口」が並び、
        片方だけ条件が緩む余地ができる（011 §5 で踏んだ形）。
        `CLAUDE.md` §3 の「本番から呼ばれないものを作らない」に従って
        消した。
        """
        if signal is AcceptanceSignal.UNKNOWN:
            return FeedbackRejected.UNUSABLE_SIGNAL
        if self._events.find_by_idempotency_key(
            idempotency_key, evidence_id=handle.evidence_id,
        ) is not None:
            return FeedbackRejected.DUPLICATE_REQUEST
        if self._store_for(handle.evidence_id.kind).get(handle.evidence_id.ref) is None:
            return FeedbackRejected.UNKNOWN_ARTIFACT
        return None

    def prepare(
        self,
        *,
        signal: AcceptanceSignal,
        handle: ArtifactHandle,
        source: FeedbackSource = FeedbackSource.USER_EXPLICIT,
        idempotency_key: str = "",
    ) -> "StagedFeedbackEvent | FeedbackRejected":
        """**書かずに**、書ける形まで組み立てる（FORGE-019C §5）。

        `admit()` は「書けるか」だけを答えた。`prepare()` は同じ検査を
        したうえで、**そのまま commit できる staged** を返す。

        検査と組み立てを1回にしてあるのは、`RevisionUnitOfWork` が
        「調べたものと書くもの」を取り違えられないようにするためである。
        """
        refusal = self._admit_handle(
            signal=signal, handle=handle, idempotency_key=idempotency_key,
        )
        if refusal is not None:
            return refusal
        return self._events.prepare_event(
            evidence_id=handle.evidence_id, signal=signal, source=source,
            idempotency_key=idempotency_key,
        )

    def commit_prepared(
        self, staged: StagedFeedbackEvent
    ) -> FeedbackResult:
        """staged を事実にする。**投影はしない**（Outbox が行う）。"""
        event = self._events.commit_event(staged)
        store = self._store_for(staged.evidence_id.kind)
        summary_updated = bool(
            store.note_user_acceptance([staged.evidence_id.ref], staged.signal)
        )
        return FeedbackResult(
            True, staged.signal, summary_updated=summary_updated, event=event,
        )

    def discard_prepared(self, staged: StagedFeedbackEvent) -> None:
        """staged を捨てる。**追記していないので何も残らない。**"""
        self._events.discard_staged_event(staged)

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
