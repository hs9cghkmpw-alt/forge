"""生成物についてのEvidence
(FORGE-PRE-R1-INTEGRITY-GATE-013 §4、2026-08-17)。

---

## なぜ`ExperienceRecord`では足りないのか

R0で入れた`ExperienceRecord`は **「1回のAI呼び出しについての事実」**
である。Provider・model・latency・構造化出力の妥当性・Validatorの合否・
利用者の承認/訂正を持つ。

これで測れないものが1つある。

    AIを1回も呼ばずに作られた、良い生成物

実測(2026-08-17、TD65):

| 経路 | 生成stageのAI呼び出し | 残る記録 |
|---|---|---|
| Curated Domain | **0回** | 生成物についての記録は**無い** |
| Generated Domain | 数回 | AI呼び出しの記録に付随して残る |

Curated経路は、**0.01秒・Quota消費0・Validator合格**でアプリを作る。
これは弱点ではなく長所である。しかしForgeは、その成功を
**学習素材として残す場所を持っていなかった**。

### やってはいけない解き方

学習データを作るためだけに、Curatedにも無理やりAIを通す。

これは本末転倒である。速くて安定していて無料な経路を、記録の都合で
遅く・不安定に・有料にすることになる。**記録の形が実行の形を歪めて
いる**という、設計として逆立ちした状態になる。

## 採る形

**AI呼び出しの記録**と、**生成物の記録**を分ける。

    ExperienceRecord   1回のAI呼び出しについての事実（R0、既存）
    GenerationRecord   1つの生成物についての事実（ここ、新規）

`GenerationRecord.source`が由来を持つので、
「Curatedで作った成功例」も「Cloud AIで作った成功例」も、
**同じ形のEvidence**として並ぶ。Local AIの学習では、

    このNeed（の構造的特徴）に対して
    この Capability / Design Language / Forge Language 構造は
    Validatorを通り、Runtimeで動き、利用者に受け入れられた

という単位で使う。これはAIを呼んだかどうかと**独立**である。

## Privacy境界は`ExperienceRecord`と同じ（006 §22）

**利用者の発話も生成物本文も持てない型にしてある。** 持つのは

* 何の種類の問題だったか（domain識別子）
* どんな構造だったか（capability / design roleの**識別子の集合**）
* 検証がどうだったか（Validator / Runtime / 利用者の反応）

であり、`str`の自由入力欄は`source`・`domain`・`forge_language_version`
（いずれも識別子）に限る。テストが型で固定している。

## Curatedの出力をTruthとして固定しない

Product Direction §5 は「Cloud出力はTeacher Candidateであって
Truthではない」と決めている。**Curatedも同じ扱いにする。**

`GenerationRecord`は「Curatedがこう作った」という事実を持つだけで、
「それが正解である」とは言わない。正解の根拠は`validator_passed` /
`runtime_success` / `user_acceptance` の側にある。

家計簿Templateを教師のTruthとして焼き込むと、Product Direction §4が
禁じた「有限Template選択システムへの退化」を、**学習側から**招く。

## 現時点の実装範囲（正直な申告）

**Production配線済み。** `PromptPipeline`が生成を終える地点
（`/generate`・`/converse` BUILDの両方が必ず通る唯一の場所）で1件残す。
Validator不合格でも残す。実測で確認済み:

```
{"source":"curated",  "domain":"household_budget", "ai_calls":0, "validator_passed":true}
{"source":"cloud_ai", "domain":"diary",            "ai_calls":1, "validator_passed":true}
```

**当初はR1へ先送りするつもりだった**——`design_language_roles`が
実在しないので粒度が足りない、という理由である。しかしそれは
「作ったが本番から呼ばれない」を5回目にする判断だったので、
やめて今つないだ。粒度が足りないなら**足りないまま残す**方がよい。

埋まっていないもの（**空であることが事実であり、欠損ではない**）:

* `capabilities` / `design_language_roles` — R1でDesign Languageが
  実在するようになったら埋まる
* `runtime_outcome` — Flutter側から結果が戻る経路がまだ無い
* `user_acceptance` — 生成物に対する明示的な承認を、UIがまだ聞かない

配線しない経路（意図的）:

* `/update` — 既存文書の**変更**であって生成ではない。同じ表へ混ぜると
  「生成の成功率」が変更の成功率で薄まる
"""

from __future__ import annotations

import time
from collections.abc import Sequence
from dataclasses import dataclass, field, replace
from enum import Enum

from app.ai.gateway.learning_foundation import AcceptanceSignal

__all__ = [
    "GenerationEvidenceStore",
    "GenerationRecord",
    "GenerationSource",
    "RuntimeOutcome",
    "default_generation_store",
]


class GenerationSource(str, Enum):
    """その生成物を**誰が作ったか**。

    Local AIの学習では、これで層別する必要がある。Curatedの成功を
    「AIが上手くやった」と数えると、AIの実力を過大評価する。
    """

    CURATED = "curated"
    """Curated Domain Libraryのルールベース生成。AI呼び出し0回。"""

    CLOUD_AI = "cloud_ai"
    """Cloud Providerが構造を決めた。**Teacher Candidateであって
    Truthではない**(Product Direction §5)。"""

    LOCAL_AI = "local_ai"
    """Forge自身のLocal Modelが構造を決めた。まだ発生しない。"""

    COMPOSITION = "composition"
    """Curatedを土台にAIが調整した等の複合。TD65の解決案1がこれ。"""

    UNKNOWN = "unknown"
    """**既定値。** 由来が記録されていない。

    学習に使ってよいかを判断する経路では通さない
    (`TrainingProvenance.UNKNOWN`と同じ姿勢)。"""

    @property
    def is_usable_for_training(self) -> bool:
        """由来が分かっているか。**分からないものは使わない。**"""
        return self is not GenerationSource.UNKNOWN


class RuntimeOutcome(str, Enum):
    """Runtimeで実際にどうなったか。

    `UNKNOWN`が既定である——**「落ちなかった」と「確かめていない」を
    混同しない**。Runtime Evidenceは、現時点ではFlutter側から戻って
    こないので、当面ほとんどが`UNKNOWN`になる。それが事実である。
    """

    RENDERED = "rendered"
    """描画まで到達した。"""

    FAILED = "failed"
    """Runtimeで落ちた。**強い負例**である。"""

    UNKNOWN = "unknown"
    """**既定値。** 確かめていない。"""

    @property
    def is_usable_as_supervision(self) -> bool:
        return self is not RuntimeOutcome.UNKNOWN


@dataclass(frozen=True)
class GenerationRecord:
    """1つの生成物についての**Forgeの振る舞いの事実**。

    **`ExperienceRecord`と同じPrivacy境界を持つ**(006 §22)。
    利用者の発話も、生成されたForge Documentの本文も、この型では
    表現できない。持つのは識別子と検証結果だけである。
    """

    source: GenerationSource
    domain: str
    """どの種類の問題だったか。**利用者の言葉ではなく**、Forgeが
    分類した識別子(`household_budget`等)。"""

    validator_passed: bool
    """Forge Language Validatorを通ったか。"""

    capabilities: tuple[str, ...] = ()
    """使われたCapabilityの識別子。**値ではなく名前**。"""

    design_language_roles: tuple[str, ...] = ()
    """選ばれたDesign Languageの役割(`metric.primary`等)。

    R1で実在するようになる。それまでは空——**空であることが
    「まだ語彙が無い」という事実**であり、埋めるべき欠損ではない。"""

    forge_language_version: str = ""
    """生成時のForge Languageのバージョン。仕様が動くので、
    どの仕様下で成立した構造なのかが分からないと後から使えない。"""

    runtime_outcome: RuntimeOutcome = RuntimeOutcome.UNKNOWN
    user_acceptance: AcceptanceSignal = AcceptanceSignal.UNKNOWN
    """`ExperienceRecord`と**同じEnumを使う**。会話側の判定を1つの
    語彙で扱うためであり、ここだけ別の名前にすると突き合わせられない。"""

    repair_attempts: int = 0
    ai_calls: int = 0
    """この生成物のために呼んだAIの回数。**Curatedなら0**。
    0が異常値ではないことが、この型を作った理由である。"""

    recorded_at: float = 0.0
    ref: int = 0

    @property
    def is_positive_example(self) -> bool:
        """教師データの候補になるか。

        **Validator合格だけでは足りない。** 利用者が明示的に受け入れた
        ものだけを正例とする(Product Direction §5、011 §5と同じ基準)。
        由来不明のものも除く。
        """
        return (
            self.validator_passed
            and self.user_acceptance.is_positive
            and self.source.is_usable_for_training
            and self.runtime_outcome is not RuntimeOutcome.FAILED
        )

    def to_dict(self) -> dict[str, object]:
        """診断・集計用。**本文が現れないことが不変条件である。**"""
        return {
            "ref": self.ref,
            "source": self.source.value,
            "domain": self.domain,
            "validator_passed": self.validator_passed,
            "capabilities": list(self.capabilities),
            "design_language_roles": list(self.design_language_roles),
            "forge_language_version": self.forge_language_version,
            "runtime_outcome": self.runtime_outcome.value,
            "user_acceptance": self.user_acceptance.value,
            "repair_attempts": self.repair_attempts,
            "ai_calls": self.ai_calls,
            "recorded_at": self.recorded_at,
        }


class GenerationEvidenceStore:
    """`GenerationRecord`の保持。

    `ExperienceStore`と同じ形にしてある——後から書き足せること、
    プロセス内メモリのみ(TD41)、上限を超えたら古い順に捨てること。
    """

    _MAX_RECORDS = 1000

    def __init__(self, *, now: object = time.time) -> None:
        self._records: dict[int, GenerationRecord] = {}
        self._next_ref = 1
        self._now = now

    def record(self, entry: GenerationRecord) -> GenerationRecord:
        if entry.recorded_at <= 0:
            entry = replace(entry, recorded_at=self._now())
        entry = replace(entry, ref=self._next_ref)
        self._next_ref += 1
        self._records[entry.ref] = entry
        while len(self._records) > self._MAX_RECORDS:
            del self._records[next(iter(self._records))]
        return entry

    def note_user_acceptance(self, refs: Sequence[int], signal: AcceptanceSignal) -> int:
        """利用者がその生成物をどう扱ったか。

        `ExperienceStore.note_acceptance()`と同じ規則——**先に書かれた
        信号が勝つ**、`UNKNOWN`は上書きの理由にならない。
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

    def all_records(self) -> tuple[GenerationRecord, ...]:
        return tuple(self._records.values())

    def training_candidates(self) -> tuple[GenerationRecord, ...]:
        """教師データの候補。**判断はここでしない**——条件は
        `GenerationRecord.is_positive_example`が持つ。"""
        return tuple(r for r in self._records.values() if r.is_positive_example)

    def summary_by_source(self) -> dict[str, dict[str, object]]:
        """由来別の集計。

        **Curatedの成功をAIの成功として数えない**ために、必ず
        `source`で割る。混ぜると、Local AIを昇格させてよいかの判断が
        Curatedの成績で押し上げられる。
        """
        summary: dict[str, dict[str, object]] = {}
        for source in GenerationSource:
            entries = [r for r in self._records.values() if r.source is source]
            if not entries:
                continue
            total = len(entries)
            summary[source.value] = {
                "samples": total,
                "validator_pass_rate": round(
                    sum(1 for r in entries if r.validator_passed) / total, 3
                ),
                "explicit_acceptance_rate": round(
                    sum(1 for r in entries if r.user_acceptance.is_positive) / total, 3
                ),
                "training_candidates": sum(1 for r in entries if r.is_positive_example),
                "mean_ai_calls": round(sum(r.ai_calls for r in entries) / total, 2),
            }
        return summary

    def reset(self) -> None:
        self._records.clear()


_default_store: GenerationEvidenceStore | None = None


def default_generation_store() -> GenerationEvidenceStore:
    global _default_store  # noqa: PLW0603 — プロセス内Singleton(既存のStoreと同じ方針)
    if _default_store is None:
        _default_store = GenerationEvidenceStore()
    return _default_store
