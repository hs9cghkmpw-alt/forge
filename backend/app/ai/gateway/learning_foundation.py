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
              利用者がどう扱ったか(承認 / 訂正 / 離脱 / 不明の**別**のみ)

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
from collections.abc import Sequence
from dataclasses import dataclass
from enum import Enum

from app.ai.gateway.tasks import ForgeTask

__all__ = [
    "AcceptanceSignal",
    "acceptance_from_hypothesis_state",
    "ExperienceRecord",
    "ExperienceStore",
    "ShadowPlan",
    "TrainingProvenance",
    "acceptance_from_turn_event",
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


class AcceptanceSignal(str, Enum):
    """利用者がその応答をどう扱ったか
    (FORGE-AI-FOUNDATION-011 §5で`CorrectionSignal`から改称・拡張)。

    **内容は持たない。** 何と言って直したかは利用者の発話そのもの
    なので記録しない。持つのは「どう扱われたか」だけである。

    ---

    ## なぜ`NONE`を割ったか

    010では`NONE / CORRECTED / ABANDONED`の3値で、`NONE`が

    * 利用者が明示的に「それでいい」と**承認した**
    * ただ訂正されなかった(気付かなかった / 諦めた)

    の両方を飲み込んでいた。将来のTeacher Evaluationでは、この2つは
    **正反対の教師信号**である——前者は「この応答は正しかった」の
    根拠になるが、後者は何の根拠にもならない。

    **Forgeは既にACCEPTEDを持っていた。**
    `conversation_types.HypothesisState.ACCEPTED`・
    `capability.CorrectionTarget.ACCEPTED`として、利用者の明示的な
    承認を判定している。それを記録側で捨てていた、というのが実態
    である(`from_hypothesis_state()`で繋がる形にした)。
    """

    ACCEPTED = "accepted"
    """利用者が**明示的に**「それでいい」と言った。

    Teacher Evaluationで使える**唯一の強い正例**である。
    `HypothesisState.ACCEPTED`から写る。"""

    CORRECTED = "corrected"
    """次のターンで訂正された。**強い負例**である。"""

    ABANDONED = "abandoned"
    """会話がそこで終わった。負例ではあるが弱い——利用者が単に
    忙しくなっただけかもしれない。"""

    UNKNOWN = "unknown"
    """**既定値。** 何も分からない。

    「訂正されなかった」はここに入る。**それを承認と読まない**
    ——気付かなかったのかもしれないし、諦めたのかもしれない。
    分からないものを正例へ格上げしない(`TrainingProvenance.UNKNOWN`と
    同じ姿勢)。"""

    @property
    def is_usable_as_supervision(self) -> bool:
        """教師信号として使えるか。

        `UNKNOWN`は使えない。**沈黙は情報ではない。**
        """
        return self is not AcceptanceSignal.UNKNOWN

    @property
    def is_positive(self) -> bool:
        """正例か。`ACCEPTED`だけである。"""
        return self is AcceptanceSignal.ACCEPTED


def acceptance_from_hypothesis_state(state: object) -> AcceptanceSignal:
    """会話側の`HypothesisState`を教師信号へ写す(011 §5)。

    `conversation_types`を**importしない**——学習の境界がConversation
    実装へ依存すると、片方を触るたびにもう片方が動く。値の名前だけで
    対応させる(会話側は`str`ベースのEnum)。

    未知の状態は`UNKNOWN`である。**新しい状態が増えたときに、
    黙って正例へ流れ込まない**方向へ倒してある。
    """
    name = getattr(state, "value", None) or str(state)
    return {
        "accepted": AcceptanceSignal.ACCEPTED,
        "corrected": AcceptanceSignal.CORRECTED,
        "abandoned": AcceptanceSignal.ABANDONED,
    }.get(str(name).lower(), AcceptanceSignal.UNKNOWN)


#: 会話1ターンの出来事 → 教師信号(R0)。
#:
#: `conversation_store.record_hypothesis_event()`が受け取る`event`は
#: `CapabilityTurnKind`の値である(`capability.py`)。ここで名前だけで
#: 対応させているのは`acceptance_from_hypothesis_state()`と同じ理由——
#: 学習の境界がConversation実装へ依存しないようにするためである。
#:
#: **`present`が入っていない**のは、それが「初回の提示」でも
#: 「訂正を受けての作り直し」でも同じ値だからである。前者は評価では
#: ないので、呼び出し側が**前の仮説があった場合だけ**`CORRECTED`を
#: 渡す(`conversation_store`側で判定している)。
_TURN_EVENT_TO_ACCEPTANCE: dict[str, AcceptanceSignal] = {
    # 「それでいい」。**唯一の強い正例**である。
    "accept": AcceptanceSignal.ACCEPTED,
    # 「そこは違う」。仮説は保つが、外していた層があった。
    "clarify": AcceptanceSignal.CORRECTED,
    # 「そもそも違う」。Problem理解まで巻き戻った、最も強い負例。
    "rewind": AcceptanceSignal.CORRECTED,
}


def acceptance_from_turn_event(event: object) -> "AcceptanceSignal":
    """会話1ターンの出来事を教師信号へ写す(R0)。

    未知の出来事は`UNKNOWN`である——新しいイベント種別が増えたときに、
    黙って正例へ流れ込まない(`acceptance_from_hypothesis_state()`と
    同じ方向へ倒す)。
    """
    name = str(getattr(event, "value", None) or event).lower()
    return _TURN_EVENT_TO_ACCEPTANCE.get(name, AcceptanceSignal.UNKNOWN)


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

    acceptance: AcceptanceSignal = AcceptanceSignal.UNKNOWN
    """利用者がこの応答をどう扱ったか。**内容は持たない。**

    既定が`UNKNOWN`なのは、記録し忘れが「承認された」に化けない
    ようにするためである(011 §5)。"""

    recorded_at: float = 0.0

    ref: int = 0
    """`ExperienceStore`が付ける不透明な通し番号。**0は「未保存」。**

    FORGE-ROADMAP R0(2026-08-17)で追加。1回のAI呼び出しについての
    事実は、**同時には揃わない**——Providerとlatencyは呼び出し直後に
    分かるが、Validatorの合否は生成が終わってから、利用者の承認/訂正
    は**次のターン**でしか分からない。後から書き足すには、どの記録に
    書き足すのかを指す手段が要る。

    セッションIDでも利用者IDでもない、**Store内の位置**である
    (§22「セッションを跨いで個人を辿れる識別子を持たない」)。
    プロセスを跨いで意味を持たず、記録が捨てられれば無効になる。
    """

    def to_dict(self) -> dict[str, object]:
        """診断・集計用。**ここに本文が現れないことが不変条件である。**"""
        return {
            "ref": self.ref,
            "task": self.task.value,
            "provider": self.provider,
            "model": self.model,
            "structured_output_valid": self.structured_output_valid,
            "validator_passed": self.validator_passed,
            "repair_attempts": self.repair_attempts,
            "latency_ms": round(self.latency_ms, 1),
            "used_fallback": self.used_fallback,
            "acceptance": self.acceptance.value,
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
        # dictにしているのは、**後から書き足す**ためである(R0)。
        # 挿入順は保たれるので、古い順に捨てる従来の性質は変わらない。
        self._records: dict[int, ExperienceRecord] = {}
        self._next_ref = 1
        self._now = now

    def record(self, entry: ExperienceRecord) -> ExperienceRecord:
        from dataclasses import replace  # noqa: PLC0415

        if entry.recorded_at <= 0:
            entry = replace(entry, recorded_at=self._now())
        entry = replace(entry, ref=self._next_ref)
        self._next_ref += 1
        self._records[entry.ref] = entry
        while len(self._records) > self._MAX_RECORDS:
            del self._records[next(iter(self._records))]
        return entry

    # --- 後から分かる事実を書き足す(R0)---------------------------------
    #
    # **なぜ「後から」が要るのか。**
    #
    # 1回のAI呼び出しについて、事実が揃う時刻は3つに分かれている。
    #
    #   呼び出し直後   Provider / model / latency / fallback / 構造化出力
    #   生成の終わり   Validatorを通ったか
    #   **次のターン** 利用者が承認したか、訂正したか
    #
    # 最後のものが本命である(Product Direction §5: 正しさの根拠は
    # User ACCEPTED / CORRECTED / Validator / Runtime であって、
    # Cloudの出力ではない)。呼び出し時点で全部揃うことを前提にすると、
    # **一番価値のある信号だけが永久に記録されない**。

    def note_generation_outcome(
        self, refs: Sequence[int], *, validator_passed: bool, repair_attempts: int = 0
    ) -> int:
        """それらの呼び出しが寄与した生成物が、Validatorを通ったか。

        `refs`が複数なのは、1つのForge Documentが**Cognitive Pipelineの
        複数段の呼び出し**から出来ているためである。どの段が悪かったかは
        ここでは分からない。分けられないものを分けて記録すると嘘になる
        ので、寄与した全部へ同じ結果を付ける。

        `repair_attempts`も同じ理由で run 単位の属性として付ける
        (「何回直せば通ったか」は生成物についての事実であり、
        個々の呼び出しについての事実ではない)。

        戻り値は実際に書き足せた件数(捨てられた記録は数えない)。
        """
        written = 0
        from dataclasses import replace  # noqa: PLC0415

        for ref in refs:
            existing = self._records.get(ref)
            if existing is None:
                continue
            self._records[ref] = replace(
                existing, validator_passed=validator_passed, repair_attempts=repair_attempts
            )
            written += 1
        return written

    def note_acceptance(self, refs: Sequence[int], signal: AcceptanceSignal) -> int:
        """利用者がその応答をどう扱ったか。

        **先に書かれた信号が勝つ。** 直後の反応がその応答への評価で
        あり、後から来る弱い信号(セッション終了=`ABANDONED`など)で
        上書きしてはならない。「訂正されたが、その後セッションが
        切れた」を`ABANDONED`に書き換えると、**訂正されたという事実が
        消える**。

        `UNKNOWN`を書きに来た場合は何もしない——沈黙は上書きの理由に
        ならない(011 §5)。
        """
        if signal is AcceptanceSignal.UNKNOWN:
            return 0
        written = 0
        from dataclasses import replace  # noqa: PLC0415

        for ref in refs:
            existing = self._records.get(ref)
            if existing is None or existing.acceptance is not AcceptanceSignal.UNKNOWN:
                continue
            self._records[ref] = replace(existing, acceptance=signal)
            written += 1
        return written

    def all_records(self) -> tuple[ExperienceRecord, ...]:
        return tuple(self._records.values())

    def summary_for(self, task: ForgeTask) -> dict[str, object]:
        """Task別の集計。**Benchmarkの代わりにはならない。**

        これは本番の実利用から得た観測であり、同一Datasetで測った
        ものではない(§19「同一Dataset」)。したがって
        `BenchmarkEvidenceStore`へ流し込んではならない——入力が
        違うものを比べると、Providerの差なのか入力の差なのかが
        分からなくなる。**傾向を見るためだけの数字である。**
        """
        entries = [r for r in self._records.values() if r.task is task]
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
                sum(1 for r in entries if r.acceptance is AcceptanceSignal.CORRECTED) / total, 3
            ),
            # §5: 明示的な承認は、訂正されなかっただけのものと分けて数える。
            "explicit_acceptance_rate": round(
                sum(1 for r in entries if r.acceptance is AcceptanceSignal.ACCEPTED) / total, 3
            ),
            "unknown_signal_rate": round(
                sum(1 for r in entries if not r.acceptance.is_usable_as_supervision) / total, 3
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
        model="gemini-flash-latest",
        note="Google公称の学習データ構成は未検証。したがってUNKNOWNのまま。",
    ),
    ModelProvenance(
        model="gemini-flash-lite-latest",
        note="同上。混雑時の代替候補として実際に使う(R0.1)。",
    ),
    ModelProvenance(
        model="gemini-3.5-flash",
        note="同上。混雑時の代替候補として実際に使う(R0.1)。",
    ),
)

# 2026-08-17: `gemini-2.0-flash`をこの表から外した。実際に呼んだところ
# 404「no longer available」だったので、**存在しないModelの由来を
# 記録していた**ことになる。表に載っているだけで使われていない名前は、
# 「これは検討済みだ」という誤った印象を作る。
