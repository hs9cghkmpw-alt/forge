"""Learning Projection Outbox v1 — **投影の失敗を「無かったこと」にしない**
(FORGE-019C §6、2026-08-25)。

---

## 何が起きていたか

`observe_evidence()` は例外を飲む。利用者の成功を telemetry の都合で
壊さないためであり、その判断自体は正しい。

しかし**飲んだあと何もしていなかった**。

```
Revision 確定 → Learning へ投影 → 失敗 → 例外を握りつぶす → 終わり
```

Learning Event は二度と出ない。Forge にとって最も価値のある
「利用者が直した」という事実が、**静かに消える**。

`CLAUDE.md` §3 の「分からないものを楽観側へ倒さない」と同じ形である
——失敗を「起きなかった」へ倒していた。

## この Outbox がすること

事実の確定と、Learning への投影を**別の寿命**にする。

```
facts commit（確定・巻き戻さない）
    ↓
outbox へ pending として置く
    ↓
投影を試す
    ├─ 成功 → projected
    └─ 失敗 → pending のまま（attempts++ / 失敗の分類を残す）
                ↓
              retry（drain）
```

利用者から見た結果は commit の時点で決まる。**投影の成否は API の
成否を変えない。**

## exactly-once 相当

`(event_type, evidence uid)` で入口を1つに絞る。同じ Evidence を
何度 `submit()` しても entry は1つで、`projected` になったものは
二度と投影しない。したがって **retry で Learning Event が二重に
出ることはない**。

## これは durable ではない（正直な申告）

**IN-MEMORY / NOT DURABLE / UNVERIFIED。**

プロセスが落ちれば pending は消える。DB durable outbox の**ふりを
しない**——「retry できる」と書いてあるのにプロセス再起動で消える方が、
最初から消えると書いてあるより悪い。

将来の置き換え境界は `docs/spec/DESIGN-REVISION-PROPOSAL.md`。
`submit()` を「同じ DB transaction 内で outbox 行を INSERT する」へ、
`drain()` を「別プロセスの worker」へ移す。**この2つの口以外から
投影しない**ようにしてあるのは、そのためである。

## Outbox が持ってよいもの

`entry` が持つのは**識別子と状態だけ**である。

* 生の利用者発話 → **持たない**（006 §22）
* secret / credential → **持たない**（`CLAUDE.md` §4）
* `ArtifactHandle`（Bearer Capability） → **持たない**（017A §3）
* `version_token` → **持たない**

retry のために Evidence オブジェクトそのものは保持するが、
**保持してよい型を whitelist で固定する**（`_RETAINABLE`）。
「たまたま渡ってきたもの」を溜め込む入れ物にしない。
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from uuid import uuid4

__all__ = [
    "LearningProjectionOutbox",
    "OutboxEntry",
    "ProjectionErrorCategory",
    "ProjectionStatus",
    "default_projection_outbox",
]


class ProjectionStatus(str, Enum):
    """投影の状態。**この2つしかない。**"""

    PENDING = "pending"
    """まだ投影できていない。**捨てていない。**"""

    PROJECTED = "projected"
    """投影済み。二度と投影しない。"""


class ProjectionErrorCategory(str, Enum):
    """なぜ失敗したかの**分類だけ**。

    例外メッセージそのものは持たない——Provider の生出力や利用者の
    入力が紛れ込む経路になりうる（`CLAUDE.md` §4）。
    """

    NONE = "none"
    PROJECTION_ERROR = "projection_error"
    """Projector が投影に失敗した。"""

    UNSUPPORTED_EVIDENCE = "unsupported_evidence"
    """投影できない種類の Evidence だった。"""

    UNKNOWN = "unknown"
    """**既定値。** 分類し損ねたものを `NONE` へ倒さない。"""


@dataclass
class OutboxEntry:
    """投影1件分の**状態**。中身は持たない。"""

    entry_id: str
    evidence_kind: str
    """`RevisionRecord` 等の型名。**イベントの種類を粗く表す。**"""

    evidence_uid: str
    """その Evidence の永続 ID（`ArtifactEvidenceId.uid` と同じ系）。"""

    status: ProjectionStatus = ProjectionStatus.PENDING
    attempts: int = 0
    last_error: ProjectionErrorCategory = ProjectionErrorCategory.NONE
    created_at: float = 0.0
    projected_at: float | None = None

    payload: object = field(default=None, repr=False, compare=False)
    """retry のために保持する Evidence 本体。**診断出力には出さない。**"""

    def to_dict(self) -> dict[str, object]:
        """診断・集計用。**`payload` は含めない**——ここが外へ出る形なので、
        Evidence 本体を混ぜると Privacy 境界がこの1行で崩れる。
        """
        return {
            "entry_id": self.entry_id,
            "evidence_kind": self.evidence_kind,
            "evidence_uid": self.evidence_uid,
            "status": self.status.value,
            "attempts": self.attempts,
            "last_error": self.last_error.value,
            "created_at": self.created_at,
            "projected_at": self.projected_at,
        }


#: **retry のために保持してよい型**。
#:
#: 名前で持つのは循環 import を避けるためである。ここに無い型は
#: `submit()` が受け付けない——「たまたま渡ってきたもの」を溜め込む
#: 入れ物にしないための fail closed である。
_RETAINABLE: frozenset[str] = frozenset({
    "GenerationRecord",
    "RevisionRecord",
    "ArtifactFeedbackEvent",
})


class LearningProjectionOutbox:
    """確定した事実を Learning Event へ投影する**唯一の口**。

    thread safe。FastAPI の sync endpoint は thread pool で並行に走るので
    （019C §7）、`dict` の読み書きを裸で行わない。
    """

    _MAX = 2000

    def __init__(self, *, now: object = time.time) -> None:
        self._entries: dict[tuple[str, str], OutboxEntry] = {}
        self._order: list[tuple[str, str]] = []
        self._lock = threading.Lock()
        self._now = now

    # -- 入口 -------------------------------------------------------------

    def submit(self, evidence: object) -> OutboxEntry | None:
        """確定した事実を投影する（失敗しても例外を出さない）。

        同じ Evidence を何度呼んでも entry は1つ。既に `projected` なら
        **何もしない**。
        """
        key = self._key(evidence)
        if key is None:
            return None
        with self._lock:
            entry = self._entries.get(key)
            if entry is None:
                entry = OutboxEntry(
                    entry_id=uuid4().hex,
                    evidence_kind=key[0],
                    evidence_uid=key[1],
                    created_at=float(self._now()),
                    payload=evidence,
                )
                self._entries[key] = entry
                self._order.append(key)
                self._evict_locked()
            elif entry.status is ProjectionStatus.PROJECTED:
                return entry
        self._attempt(entry)
        return entry

    def enqueue(self, evidence: object, *, error: Exception | None = None) -> OutboxEntry | None:
        """**投影を試さずに**保留として置く（FORGE-019C §6）。

        投影の段そのものが落ちた場合に使う——`submit()` は投影を試すので、
        既に落ちたと分かっている経路で二度目を走らせない。`drain()` で
        あらためてやり直す。
        """
        key = self._key(evidence)
        if key is None:
            return None
        with self._lock:
            entry = self._entries.get(key)
            if entry is None:
                entry = OutboxEntry(
                    entry_id=uuid4().hex,
                    evidence_kind=key[0],
                    evidence_uid=key[1],
                    created_at=float(self._now()),
                    payload=evidence,
                )
                self._entries[key] = entry
                self._order.append(key)
                self._evict_locked()
            if entry.status is ProjectionStatus.PROJECTED:
                return entry
            entry.attempts += 1
            entry.last_error = (
                self._classify(error) if error is not None else ProjectionErrorCategory.UNKNOWN
            )
            return entry

    def drain(self) -> int:
        """保留中をまとめて投影し直す。**投影できた件数**を返す。

        既に `projected` のものには触らない——ここが exactly-once を
        保つ場所である。
        """
        with self._lock:
            pending = [e for e in self._entries.values() if e.status is ProjectionStatus.PENDING]
        return sum(1 for entry in pending if self._attempt(entry))

    # -- 参照 -------------------------------------------------------------

    def pending(self) -> tuple[OutboxEntry, ...]:
        with self._lock:
            return tuple(
                e for e in self._entries.values() if e.status is ProjectionStatus.PENDING
            )

    def all_entries(self) -> tuple[OutboxEntry, ...]:
        with self._lock:
            return tuple(self._entries[k] for k in self._order if k in self._entries)

    def size(self) -> int:
        with self._lock:
            return len(self._entries)

    def reset(self) -> None:
        with self._lock:
            self._entries.clear()
            self._order.clear()

    # -- 内部 -------------------------------------------------------------

    @staticmethod
    def _key(evidence: object) -> tuple[str, str] | None:
        """`(型名, uid)`。**保持してよい型でなければ受け取らない。**"""
        kind = type(evidence).__name__
        if kind not in _RETAINABLE:
            return None
        uid = getattr(evidence, "uid", None) or getattr(evidence, "event_id", None)
        if not isinstance(uid, str) or not uid:
            return None
        return (kind, uid)

    def _attempt(self, entry: OutboxEntry) -> bool:
        """1回だけ投影を試す。**例外は外へ出さない。**"""
        from app.ai.gateway.learning_events import (  # noqa: PLC0415 — 循環importを避ける
            default_learning_event_service,
        )

        with self._lock:
            if entry.status is ProjectionStatus.PROJECTED:
                return False
            entry.attempts += 1
            payload = entry.payload

        try:
            default_learning_event_service().observe(payload)
        except Exception as error:  # noqa: BLE001 — 投影の失敗で利用者の成功を壊さない
            with self._lock:
                entry.last_error = self._classify(error)
            from app.ai.gateway.learning_events import (  # noqa: PLC0415
                default_learning_event_service as _service,
            )
            _service().diagnostics.record_failure(error)
            return False

        with self._lock:
            entry.status = ProjectionStatus.PROJECTED
            entry.last_error = ProjectionErrorCategory.NONE
            entry.projected_at = float(self._now())
            # 投影が終われば retry 用の本体は要らない。**持ち続けない。**
            entry.payload = None
        return True

    @staticmethod
    def _classify(error: Exception) -> ProjectionErrorCategory:
        if isinstance(error, (TypeError, ValueError)):
            return ProjectionErrorCategory.UNSUPPORTED_EVIDENCE
        if isinstance(error, RuntimeError):
            return ProjectionErrorCategory.PROJECTION_ERROR
        return ProjectionErrorCategory.UNKNOWN

    def _evict_locked(self) -> None:
        """上限を超えたら古い順に捨てる。**pending は最後まで残す。**

        溢れるほど溜まっているなら、それ自体が異常である。捨てるなら
        「もう投影済みのもの」から捨てる方が、失われる情報が少ない。
        """
        if len(self._entries) <= self._MAX:
            return
        excess = len(self._entries) - self._MAX
        for key in list(self._order):
            if excess <= 0:
                break
            entry = self._entries.get(key)
            if entry is None:
                self._order.remove(key)
                continue
            if entry.status is ProjectionStatus.PROJECTED:
                del self._entries[key]
                self._order.remove(key)
                excess -= 1
        while excess > 0 and self._order:
            key = self._order.pop(0)
            self._entries.pop(key, None)
            excess -= 1


_DEFAULT_OUTBOX = LearningProjectionOutbox()


def default_projection_outbox() -> LearningProjectionOutbox:
    """本番が使う唯一の Outbox。**投影の口を複数作らない。**"""
    return _DEFAULT_OUTBOX
