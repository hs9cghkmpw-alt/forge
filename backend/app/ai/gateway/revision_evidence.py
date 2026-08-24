"""Revision Evidence — **どう直したら受け入れられたか**の記録
(FORGE-016A §4、TD68の設計をProduction型として実装、2026-08-24)。

---

## なぜ生成の記録と分けるのか

`GenerationRecord`へ`operation = generate | update`を足す案もあったが、
**1つの型に混ぜると`validator_passed`の意味がoperationごとに変わる**
（生成の成功率と変更の成功率）。集計のたびに`operation`で割る必要が
あり、割り忘れると静かに混ざる。

013で`/update`を`GenerationRecord`から除外した理由そのものが、型の中へ
戻ってくる。だから別の型にして、**関係で繋ぐ**。

```
GenerationRecord(ref=7, acceptance=CORRECTED)
   ↑ base_generation_ref
RevisionRecord(ref=1, sequence=1, acceptance=ACCEPTED)
```

**この対**がLocal AIにとって最も価値がある。「初回は外したが、
この訂正で受け入れられた」は、完成Documentを何千個集めても得られない。

## 生の発話は持たない（006 §22 / §10）

利用者が何と言って直したかは記録しない。持つのは

* どの画面の、どのWidgetの
* どの軸の
* どのroleから、どのroleへ
* 誰の判断で

という**閉じた識別子だけ**である。

言い回しは無数にあるが、直した事実は有限である。将来Local AIが
自然言語のCorrection Mappingを学ぶ必要が出たら、それは
`LanguageTrainingCandidate`という**別契約**（明示同意・非識別化・
利用規約確認が前提）で扱う。ここへ混ぜない。
"""

from __future__ import annotations

import time
from collections.abc import Sequence
from dataclasses import dataclass, replace
from enum import Enum

from app.ai.gateway.generation_evidence import (
    DesignDecisionSource,
    GenerationSource,
    RuntimeOutcome,
)
from app.ai.gateway.learning_foundation import AcceptanceSignal

__all__ = [
    "DesignRevision",
    "RevisionEvidenceStore",
    "RevisionOperationKind",
    "RevisionRecord",
    "default_revision_store",
]


class RevisionOperationKind(str, Enum):
    """その変更が**何をしたのか**。

    生成の成功率と混ぜないだけでなく、変更の中でも
    「見た目を直した」と「項目を足した」を分けておく。
    後者はデータ構造が変わるので、Runtimeへの影響がまるで違う。
    """

    DESIGN = "design"
    """意味的役割だけを変えた。データ構造は変わらない。"""

    STRUCTURE = "structure"
    """項目・画面・Actionが変わった。"""

    MIXED = "mixed"
    """両方。"""

    UNKNOWN = "unknown"
    """**既定値。** 記録し損ねたものを楽観側へ倒さない。"""


@dataclass(frozen=True)
class DesignRevision:
    """1箇所の意味的役割の変更。

    **識別子しか持たない。** 利用者の発話も、Providerの生出力も、
    色コードもpxも入らない。
    """

    screen_id: str
    """どの画面か。**Document全体ではなく画面単位で持つ**
    ——同じ`target_id`が別画面に在りうる。"""

    target_id: str
    """どのWidgetか。"""

    axis: str
    """`list_surface`等。何についての判断か。"""

    before: str
    """変更前のrole。**これが「外した選択」**として学習素材になる。"""

    after: str
    """変更後のrole。"""

    source: DesignDecisionSource = DesignDecisionSource.UNKNOWN
    """誰の判断か。利用者の指摘で変えたなら`USER_CORRECTION`。"""

    def to_dict(self) -> dict[str, str]:
        return {
            "screen_id": self.screen_id, "target_id": self.target_id,
            "axis": self.axis, "before": self.before, "after": self.after,
            "source": self.source.value,
        }


@dataclass(frozen=True)
class RevisionRecord:
    """1回の変更についての**Forgeの振る舞いの事実**。

    `GenerationRecord`と**同じ語彙**（`AcceptanceSignal` /
    `RuntimeOutcome` / `GenerationSource`）を使う。別系統にすると同じ
    概念が2つの名前を持ち、突き合わせられなくなる（011 §5で一度やった
    失敗）。
    """

    base_generation_ref: int
    """どの生成物への変更か。**関係の起点。**"""

    previous_revision_ref: int | None = None
    """直前の変更。連続で直された場合に鎖になる。"""

    sequence: int = 1
    """同一生成物への何回目の変更か。"""

    operation_kind: RevisionOperationKind = RevisionOperationKind.UNKNOWN
    source: GenerationSource = GenerationSource.UNKNOWN
    validator_passed: bool = False
    runtime_outcome: RuntimeOutcome = RuntimeOutcome.UNKNOWN
    user_acceptance: AcceptanceSignal = AcceptanceSignal.UNKNOWN

    design_revisions: tuple[DesignRevision, ...] = ()
    """何をどう直したか。**生の発話は含まない。**"""

    forge_language_version: str = ""
    recorded_at: float = 0.0
    ref: int = 0

    @property
    def is_positive_example(self) -> bool:
        """教師データの候補になるか。

        **Validator合格だけでは足りない。** 利用者が明示的に受け入れた
        ものだけを正例とする（Product Direction §5）。
        """
        return (
            self.validator_passed
            and self.user_acceptance.is_positive
            and self.runtime_outcome is not RuntimeOutcome.FAILED
        )

    @property
    def user_corrected_roles(self) -> tuple[DesignRevision, ...]:
        """**利用者の指摘で変えたものだけ。**

        AIが勝手に変えたものと混ぜると、「利用者はこう直したがった」と
        いう学習素材が嘘になる。
        """
        return tuple(
            r for r in self.design_revisions
            if r.source is DesignDecisionSource.USER_CORRECTION
        )

    def to_dict(self) -> dict[str, object]:
        """診断・集計用。**本文が現れないことが不変条件である。**"""
        return {
            "ref": self.ref,
            "base_generation_ref": self.base_generation_ref,
            "previous_revision_ref": self.previous_revision_ref,
            "sequence": self.sequence,
            "operation_kind": self.operation_kind.value,
            "source": self.source.value,
            "validator_passed": self.validator_passed,
            "runtime_outcome": self.runtime_outcome.value,
            "user_acceptance": self.user_acceptance.value,
            "design_revisions": [r.to_dict() for r in self.design_revisions],
            "forge_language_version": self.forge_language_version,
            "recorded_at": self.recorded_at,
        }


class RevisionEvidenceStore:
    """`RevisionRecord`の保持。

    `GenerationEvidenceStore`と同じ形にしてある——後から書き足せること、
    プロセス内メモリのみ（TD41）、上限を超えたら古い順に捨てること。
    """

    _MAX_RECORDS = 1000

    def __init__(self, *, now: object = time.time) -> None:
        self._records: dict[int, RevisionRecord] = {}
        self._next_ref = 1
        self._now = now

    def record(self, record: RevisionRecord) -> RevisionRecord:
        stored = replace(
            record, ref=self._next_ref, recorded_at=record.recorded_at or float(self._now()),
        )
        self._records[stored.ref] = stored
        self._next_ref += 1
        if len(self._records) > self._MAX_RECORDS:
            for ref in sorted(self._records)[: len(self._records) - self._MAX_RECORDS]:
                del self._records[ref]
        return stored

    def get(self, ref: int) -> RevisionRecord | None:
        return self._records.get(ref)

    def all_records(self) -> tuple[RevisionRecord, ...]:
        return tuple(self._records[r] for r in sorted(self._records))

    def for_generation(self, generation_ref: int) -> tuple[RevisionRecord, ...]:
        """ある生成物への変更を、**順番どおり**返す。"""
        return tuple(
            r for r in self.all_records() if r.base_generation_ref == generation_ref
        )

    def next_sequence(self, generation_ref: int) -> int:
        """その生成物への何回目の変更になるか。"""
        return len(self.for_generation(generation_ref)) + 1

    def note_user_acceptance(self, refs: Sequence[int], signal: AcceptanceSignal) -> int:
        """後から評価を書き足す。

        **`GenerationEvidenceStore.note_user_acceptance()`と同じ規則で
        なければならない**——先に書かれた信号が勝ち、`UNKNOWN`は上書きの
        理由にならない。

        ここを緩めると、生成と変更で「最初の信号が勝つ」の意味が変わる。
        同じ`AcceptanceSignal`という語彙を使いながら規則が違えば、
        突き合わせたときに静かに嘘になる(011 §5で一度踏んだ形)。
        """
        if signal is AcceptanceSignal.UNKNOWN:
            return 0
        written = 0
        for ref in refs:
            existing = self._records.get(ref)
            if existing is None or existing.user_acceptance is not AcceptanceSignal.UNKNOWN:
                continue
            self._records[ref] = replace(existing, user_acceptance=signal)
            written += 1
        return written

    def note_runtime_outcome(self, refs: Sequence[int], outcome: RuntimeOutcome) -> int:
        """同上。`UNKNOWN`で上書きしない。"""
        if outcome is RuntimeOutcome.UNKNOWN:
            return 0
        written = 0
        for ref in refs:
            existing = self._records.get(ref)
            if existing is None or existing.runtime_outcome is not RuntimeOutcome.UNKNOWN:
                continue
            self._records[ref] = replace(existing, runtime_outcome=outcome)
            written += 1
        return written

    def reset(self) -> None:
        self._records.clear()
        self._next_ref = 1

    def size(self) -> int:
        return len(self._records)


_DEFAULT_STORE = RevisionEvidenceStore()


def default_revision_store() -> RevisionEvidenceStore:
    """本番が使う唯一のStore。"""
    return _DEFAULT_STORE
