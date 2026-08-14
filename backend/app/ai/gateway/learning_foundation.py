"""Local AI Learning Foundation
(FORGE-AI-FOUNDATION-010 Phase K、2026-08-13)。

「いずれForge自身のModelを育てる」ための**境界**を先に置く。
学習そのものはまだ行わない。

---

## なぜ「境界だけ」を先に作るのか

学習用データの収集は、**後から安全にはできない**。

Providerの応答をとりあえず全部保存しておいて、あとで
「これは学習に使ってよい分だけ選ぶ」とすると、その時点で
既に**利用者の入力が保存済み**である。同意も、削除要求への
対応も、後付けになる。

逆に、境界を先に置いても失うものは無い。記録する項目を絞って
おけば、必要になったときに広げられる。

## 3つの境界

### 1. Experience Metadata(何を記録してよいか)

記録するのは**利用者の入力そのものではなく、Forgeの振る舞いに
ついての事実**である。

    記録する: どのTaskか / どのProviderが答えたか / 構造化出力が
              妥当だったか / 何msか / Validatorを通ったか /
              利用者が訂正したか(訂正の**有無**)

    記録しない: 発話文 / build_brief / 生成されたForge Document /
                Providerの応答本文 / セッションを跨いで個人を
                辿れる識別子

`ExperienceRecord`は**記録してよい項目しか持てない**形にして
ある。「うっかり本文を入れる」ができない——文字列フィールドが
そもそも無い。

FORGE-USER-GUIDED-SELF-EXTENSION-006 §22「Trainingへ入れない」の
実装上の担保でもある。

### 2. Shadow Mode(どう評価するか)

育てたModelを本番へ入れる前に、**本番の応答は今までどおり
Cloudから返しつつ、裏で新Modelにも同じTaskを解かせて比べる**。

    利用者が受け取る応答  ← 現行Provider(変わらない)
    比較用に走らせる応答  ← 候補Model(結果は捨てる)

MVPではShadow Modeを**設計として置くだけ**で、実行はしない。
実行するとQuotaとlatencyが倍になるためであり(§29の並列hedgingを
避けたのと同じ理由)、`ShadowPlan`が「いつ・どの割合で・何を
比べるか」を明示的に決めなければ動かない形にしてある。

### 3. Training Provenance(そのModelは何で育ったか)

`TrainingProvenance.UNKNOWN`が**既定値**である。

出所の分からないModelを「安全」とも「危険」とも書かない。
既定を`UNKNOWN`にしておくと、由来を記録し忘れたModelは
**自動的に「不明」として扱われ**、Provenanceを要求する経路で
弾かれる。既定を`PUBLIC_ONLY`のような楽観値にすると、記録漏れが
そのまま「公開データのみで学習済み」という主張になる。

## 現時点で実装していないこと(正直な申告)

* 学習の実行(データ収集も、fine-tuningも、していない)
* Shadow Modeの実行(設計と型のみ)
* 永続化(`ExperienceStore`はプロセス内メモリ、TD41と同じ)
* 利用者への同意取得UI(記録する項目を絞ることで、同意が
  必要な情報を持たない設計にしてある。ただし**Privacy Policyは
  未完成**であり、これで足りるかは判断されていない)
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from enum import Enum

from app.ai.gateway.tasks import ForgeTask

__all__ = [
    "CorrectionSignal",
    "ExperienceRecord",
    "ExperienceStore",
    "ShadowPlan",
    "TrainingProvenance",
    "default_experience_store",
]


class TrainingProvenance(str, Enum):
    """そのModelは**何で育ったか**。

    既定は`UNKNOWN`である(下記`ModelProvenance`参照)。
    """

    UNKNOWN = "unknown"
    """**既定値。** 出所が記録されていない。安全とも危険とも言わない。
    Provenanceを要求する経路では、これは通さない。"""

    PUBLIC_ONLY = "public_only"
    """公開データのみ。Provider公称であって、Forgeが検証したもの
    ではない——**公称を検証済みとして扱わない**(§46)。"""

    FORGE_SYNTHETIC = "forge_synthetic"
    """Forgeが生成した合成データのみ。利用者の入力を含まない。"""

    FORGE_USER_DATA = "forge_user_data"
    """**利用者データを含む。** 現時点でこの値を持つModelは存在せず、
    作る予定も無い。値として置いてあるのは、もし将来そうするなら
    **明示的にこの値を書く必要がある**ようにするためである
    (黙って混ざる経路を作らない)。"""


class CorrectionSignal(str, Enum):
    """利用者がその応答をどう扱ったか。

    **訂正の「有無と向き」だけ**を持つ。訂正の**内容**(何と言って
    直したか)は利用者の発話そのものなので記録しない。
    """

    NONE = "none"
    """訂正されなかった。**「正しかった」ではない**——利用者が
    諦めた場合も、気付かなかった場合も、ここに入る。"""

    CORRECTED = "corrected"
    """次のターンで訂正された。"""

    ABANDONED = "abandoned"
    """会話がそこで終わった。"""


@dataclass(frozen=True)
class ExperienceRecord:
    """1回のAI呼び出しについての**Forgeの振る舞いの事実**。

    **文字列の自由入力欄が無い**のが要点である。利用者の発話も、
    生成物も、Providerの応答本文も、この型では表現できない。
    「うっかり入れてしまう」経路を型で塞いでいる。
    """

    task: ForgeTask
    provider: str
    model: str

    structured_output_valid: bool
    """応答が期待した構造だったか。"""

    validator_passed: bool | None = None
    """生成物がForge Language Validatorを通ったか。
    生成を伴わないTaskでは`None`。"""

    repair_attempts: int = 0
    latency_ms: float = 0.0
    used_fallback: bool = False

    correction: CorrectionSignal = CorrectionSignal.NONE
    """利用者の訂正の**有無**。内容は持たない。"""

    recorded_at: float = 0.0

    def to_dict(self) -> dict[str, object]:
        """診断・集計用。**ここに本文が現れないことが不変条件である。**"""
        return {
            "task": self.task.value,
            "provider": self.provider,
            "model": self.model,
            "structured_output_valid": self.structured_output_valid,
            "validator_passed": self.validator_passed,
            "repair_attempts": self.repair_attempts,
            "latency_ms": round(self.latency_ms, 1),
            "used_fallback": self.used_fallback,
            "correction": self.correction.value,
            "recorded_at": self.recorded_at,
        }


@dataclass(frozen=True)
class ShadowPlan:
    """Shadow Modeの実行計画。**明示的に作らなければ何も起きない。**

    `enabled=False`が既定である。有効化には、何を比べるか
    (`task`)・どのModelか(`candidate_provider`)・どの割合か
    (`sample_rate`)を全部書く必要がある。

    「とりあえず全部のリクエストで裏でも走らせる」ができない形に
    してあるのは、それがQuotaとlatencyを倍にするからである
    (§29で並列hedgingを避けたのと同じ理由)。
    """

    task: ForgeTask
    candidate_provider: str
    sample_rate: float = 0.0
    """0.0〜1.0。**既定は0.0**——計画を書いただけでは走らない。"""

    enabled: bool = False

    @property
    def is_active(self) -> bool:
        return self.enabled and self.sample_rate > 0.0

    def describe(self) -> str:
        if not self.is_active:
            return f"shadow({self.task.value}): 無効"
        return (
            f"shadow({self.task.value}): {self.candidate_provider} を "
            f"{self.sample_rate:.0%} で比較(利用者への応答は現行Providerのまま)"
        )


@dataclass(frozen=True)
class ModelProvenance:
    """あるModelの由来。**既定は`UNKNOWN`。**"""

    model: str
    provenance: TrainingProvenance = TrainingProvenance.UNKNOWN
    note: str = ""

    @property
    def may_be_used_where_provenance_matters(self) -> bool:
        """由来が問われる用途(例: 利用者データを扱うTask)で使ってよいか。

        `UNKNOWN`は**通さない**。「分からないなら止める」であって、
        「分からないなら大丈夫」ではない。
        """
        return self.provenance is not TrainingProvenance.UNKNOWN


class ExperienceStore:
    """`ExperienceRecord`の保持。

    **判断はしない**——ここは事実を貯めるだけである。学習に使うか
    どうかは、使う側が明示的に決める。

    既知の制限: プロセス内メモリのみ(TD41と同じ)。上限を超えた
    古い記録は捨てる——無制限に貯めると、`ConversationStore`と同じ
    メモリ増大問題になる。
    """

    _MAX_RECORDS = 1000

    def __init__(self, *, now: object = time.time) -> None:
        self._records: list[ExperienceRecord] = []
        self._now = now

    def record(self, entry: ExperienceRecord) -> ExperienceRecord:
        if entry.recorded_at <= 0:
            from dataclasses import replace  # noqa: PLC0415

            entry = replace(entry, recorded_at=self._now())
        self._records.append(entry)
        if len(self._records) > self._MAX_RECORDS:
            del self._records[: len(self._records) - self._MAX_RECORDS]
        return entry

    def all_records(self) -> tuple[ExperienceRecord, ...]:
        return tuple(self._records)

    def summary_for(self, task: ForgeTask) -> dict[str, object]:
        """Task別の集計。**Benchmarkの代わりにはならない。**

        これは本番の実利用から得た観測であり、同一Datasetで測った
        ものではない(§19「同一Dataset」)。したがって
        `BenchmarkEvidenceStore`へ流し込んではならない——入力が
        違うものを比べると、Providerの差なのか入力の差なのかが
        分からなくなる。**傾向を見るためだけの数字である。**
        """
        entries = [r for r in self._records if r.task is task]
        if not entries:
            return {"task": task.value, "samples": 0}
        total = len(entries)
        return {
            "task": task.value,
            "samples": total,
            "structured_output_valid_rate": round(
                sum(1 for r in entries if r.structured_output_valid) / total, 3
            ),
            "correction_rate": round(
                sum(1 for r in entries if r.correction is CorrectionSignal.CORRECTED) / total, 3
            ),
            "fallback_rate": round(sum(1 for r in entries if r.used_fallback) / total, 3),
            "note": "本番実利用の観測。同一Datasetではないので Benchmark と混同しないこと。",
        }

    def reset(self) -> None:
        self._records.clear()


_default_store: ExperienceStore | None = None


def default_experience_store() -> ExperienceStore:
    global _default_store  # noqa: PLW0603
    if _default_store is None:
        _default_store = ExperienceStore()
    return _default_store


# 現時点で有効なShadow Planは無い。**空である**ことが状態であって、
# 書き忘れではない(空リストにコメントを付けているのはそのため)。
ACTIVE_SHADOW_PLANS: tuple[ShadowPlan, ...] = ()

# 既知のModelの由来。**どれも`UNKNOWN`である**——Provider公称は
# あるが、Forgeが検証したものではない(§46「Cloud AI Output = Truth
# ではない」と同じ姿勢)。ここを楽観的に埋めないことが、この表の
# 唯一の役目である。
KNOWN_MODEL_PROVENANCE: tuple[ModelProvenance, ...] = (
    ModelProvenance(
        model="gemini-2.0-flash",
        note="Google公称の学習データ構成は未検証。したがってUNKNOWNのまま。",
    ),
)
