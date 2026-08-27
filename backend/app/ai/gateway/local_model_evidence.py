"""Real Local Model Evidence — **何を「実モデルで動いた」と数えるか**
(FORGE-020A / Vision §39 Level 0、2026-08-26)。

---

## なぜ専用の型が要るのか

「Local Model を動かした」は、いちばん誤魔化しやすい主張である。

* Mock Provider が応答した
* localhost の偽 OpenAI 互換サーバが応答した
* 記録済みの fixture を読み返した
* Provider 名だけ `local` にした

いずれも「動いた」ように**見える**。実際 Forge は 011 のときに
localhost の偽サーバで配線確認をしており（TD67）、それは配線の確認
としては正しいが、**Local AI の能力の証拠ではない**。

CEO 決定（2026-08-26）:

> Real Local Model runs は、実際の open-weight model から応答が返り、
> **Forge production path を通った場合だけ**加算する。
> fake server / mock / fixture は加算しない。

数えるための条件を、コメントではなく**型と述語**にする。

## この型が保証できること / できないこと

**できる**:

* Mock / Test Double を**うっかり**数えてしまう事故を防ぐ
* 本番経路を通っていない実行（横から呼んだ script 等）を弾く
* 「何をもって数えたか」を後から全部読める形で残す

**できない**:

* 「悪意を持って本物そっくりの偽サーバを立てる」ことの検出

後者は原理的に不可能である。**だから隠さずに書く**——
`runtime_backend` と `model_digest` と `host_id` を**記録として残す**
ことで、偽るなら記録に嘘を書くしかない形にする。それが限界であり、
限界だと明記しておく方が「検証済み」と言い切るより誠実である。

## この container では PASS しない（正しい状態）

CEO 決定により、本 container の network policy は広げない。
Level 0 の実測は**インターネットへ通常接続できる別の実機**で行う。

したがって本 container では `Level0Outcome.NOT_ATTEMPTED` のままであり、
`docs/LEARNABLE-LOCAL-AI-VISION.md` の Level 0 は **UNVERIFIED** を維持する。
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum

from app.ai.gateway.benchmark_evidence import Verification
from app.ai.gateway.capability_evidence import (
    GenerationStructureSource,
    structure_source_is_ai,
)
from app.ai.gateway.generation_evidence import GenerationSource
from app.ai.gateway.learning_events import Deployment
from app.ai.gateway.tasks import ForgeTask

__all__ = [
    "CURATED_DOMAIN_RESOLUTION",
    "GenerationStructureSource",
    "Level0Outcome",
    "LocalRuntimeBackend",
    "RealLocalModelRun",
    "RealLocalModelRunLog",
    "WeightIdentity",
    "default_real_local_run_log",
]

#: `decision_trace` の `domain_resolution` が「Curated 定義を使った」と
#: 言うときの値。**Level 0 の probe がここへ落ちたら計測が無効である。**
CURATED_DOMAIN_RESOLUTION = "curated"


class LocalRuntimeBackend(str, Enum):
    """何が推論を実行したか。

    **`UNKNOWN` は数えない。** どの Runtime が動いたか言えない実行を
    「実モデルで動いた」の証拠にしない（`CLAUDE.md` §3）。
    """

    OLLAMA = "ollama"
    LLAMA_CPP = "llama_cpp"
    LM_STUDIO = "lm_studio"
    VLLM = "vllm"
    OPENAI_COMPATIBLE_OTHER = "openai_compatible_other"

    TEST_DOUBLE = "test_double"
    """**偽サーバ・fixture・Mock。** 配線確認には使うが、数えない。"""

    UNKNOWN = "unknown"
    """**既定値。** 記録し損ねたものを実測側へ倒さない。"""


class WeightIdentity(str, Enum):
    """**どの重みで動いたかを言えるか**（020A1、2026-08-26）。

    ---

    ## `model_id` を digest 扱いしていた

    以前この script は OpenAI 互換 `/v1/models` の `id`
    （`qwen2.5:1.5b-instruct` のような**ただの名前**）を、digest が
    取れなかったときの代わりに `model_digest` へ入れていた。

    名前は重みの識別子ではない。同じ名前で中身の違う重みを配ることは
    誰にでもできる。**名前を digest と呼んだ時点で、その欄は嘘になる。**

    分ける:

    * `model_id`   — Runtime が名乗る名前。ほぼ必ず取れる
    * `model_digest` — **Runtime が返した重みのハッシュ**。Ollama は返す。
      llama-server 等は返さないことがある

    digest が取れなければ `UNVERIFIED`。**それは Level 0 の失敗ではない**
    ——Level 0 が証明するのは経路であって重みの同一性ではない
    （下の `Level0Outcome` 参照）。重みの同一性を要求するのは
    Level 0.5（Baseline Benchmark）である。
    """

    VERIFIED_DIGEST = "verified_digest"
    """Runtime 自身が返した重みのハッシュがある。"""

    UNVERIFIED = "unverified"
    """**既定値。** 取れなかったものを取れたことにしない。"""


class Level0Outcome(str, Enum):
    """Vision §39 Level 0（Local Model が動く）の判定。"""

    PASSED = "passed"
    FAILED = "failed"
    """試したが通らなかった。**理由が残る。**"""

    NOT_ATTEMPTED = "not_attempted"
    """**まだ試していない。** 失敗と区別する。"""

    INVALID_PROBE = "invalid_probe"
    """**測定そのものが成立していない**（020A1、2026-08-26）。

    Local Model の失敗ではない。**Local Model に仕事が回っていない。**

    実例: 既定の probe「毎日の支出を記録して合計を見たい」は
    `household_budget` の Curated Domain Library へ解決される
    （実測: `domain_resolution=curated`）。Curated 経路は**AI を1回も
    呼ばずに**決定的に文書を作るので、Runtime が動いていようがいまいが
    HTTP 200 が返り、Validator も通る。

    これを `FAILED` と書くと「Local Model が駄目だった」という嘘になり、
    `PASSED` と書けばもっと悪い。**probe が不適切だった**という第三の
    結果を持つ。`NOT_APPLICABLE` 相当である。
    """


#: Provider 名として現れうる Test Double。**名前で弾く第一段。**
_TEST_DOUBLE_PROVIDERS: frozenset[str] = frozenset({
    "mock", "fake", "stub", "test", "double", "fixture", "dummy",
})


@dataclass(frozen=True)
class RealLocalModelRun:
    """実 Local Model が Forge の本番経路を通った1回分。

    **`counts_as_real_local` が `True` のものだけを数える。**
    """

    provider: str
    model: str
    task: ForgeTask
    """**この実行が実際に AIRouter へ渡した Task。**

    ---

    ## 手で書くと嘘になる（020A1、2026-08-26）

    以前 script はここへ `ForgeTask.FORGE_LANGUAGE_UPDATE` を**定数として**
    書いていた。実際に `/generate` が通るのは
    `ForgeTask.COGNITIVE_STAGE` である（`prompt_pipeline.py` の
    `ai_router.bind(ForgeTask.COGNITIVE_STAGE, ...)`）。

    Task ごとに Routing も評価も分ける設計（011 §3）なので、
    **記録した Task が違えば、その実測は別の Task の成績として
    集計される。** 存在しない実績が生まれる。

    `observed_tasks` と突き合わせて、**主張と観測が一致しなければ
    数えない**。
    """

    observed_tasks: tuple[ForgeTask, ...] = ()
    """**実際に AIRouter を通った Task の観測結果**（020A1）。

    `ExperienceRecord.task` から読む——AIRouter が呼ばれるたびに
    自分で残している事実であり、script の主張ではない。

    空なら「観測できていない」。**その場合 `task` の主張は検証されて
    いない**ので数えない。
    """

    structure_source: GenerationStructureSource = GenerationStructureSource.UNKNOWN
    """**その文書の構造を誰が作ったか**（020A2 §3、2026-08-26）。

    ---

    ## `domain_resolution != curated` では足りない

    R4 以降、`Capability Plan → 決定的な EntitySpec → IR` で構造が
    決まったあと、**Design Intent だけ Local Model を呼ぶ**ことがある。
    そのとき `domain_resolution` は `generated` で、
    `last_provider_used` は `local` になる——両方の条件を満たすのに、
    **Local Model はソフトウェアの構造を1つも作っていない。**

    Level 0 が証明したいのは「Local Model が構造生成を担当した」こと
    である。`structure_source_is_ai()` がその判定であり、
    `DETERMINISTIC_CAPABILITY_PLAN` は通らない。

    通らなかった場合は `INVALID_PROBE`——**Local Model の失敗ではなく、
    その probe では測れていない**。
    """

    domain_resolution: str = ""
    """`decision_trace` の `domain_resolution` 段が返した判断（020A1）。

    `"curated"` なら **Curated Domain Library が決定的に文書を作った**
    ——AI は1回も呼ばれていない。Local Model の実測にならない。
    `Level0Outcome.INVALID_PROBE` の判定に使う。
    """

    runtime_backend: LocalRuntimeBackend = LocalRuntimeBackend.UNKNOWN
    runtime_version: str = ""

    model_id: str = ""
    """**Runtime が名乗る Model の名前**（`qwen2.5:1.5b-instruct` 等）。

    ほぼ必ず取れる。**これは重みの識別子ではない**（`model_digest` 参照）。
    """

    model_digest: str = ""
    """**Runtime 自身が返した重みのハッシュ**（Ollama の digest 等）。

    llama-server 等は返さないことがある。**`model_id` を代わりに入れない**
    ——名前は重みの識別子ではない（`WeightIdentity` 参照）。

    無いことは Level 0 の失敗ではない。Level 0 が証明するのは経路であって
    重みの同一性ではない。**`weight_identity` が `UNVERIFIED` になるだけ**
    であり、それを Level 0.5（Baseline Benchmark）が要求する。
    """

    quantization: str = ""
    deployment: Deployment = Deployment.UNKNOWN

    latency_ms: float = 0.0
    structured_output_ok: bool = False
    validator_passed: bool = False

    generation_evidence_uid: str = ""
    """**本番経路を通った証拠。**

    `/api/v1/ai/generate` が `GenerationRecord` を残したときの `uid`。
    横から Provider を直接叩いた実行はここが空になるので数えない
    ——「Provider は応答したが Forge は何も作っていない」を Level 0 に
    しないため。
    """

    generation_source: GenerationSource = GenerationSource.UNKNOWN
    """**その文書を実際に作ったのは何か**（FORGE-020A、決定的な検査）。

    ---

    ## これが無いと 200 OK に騙される

    Runtime を起動していない状態で `provider="local"` を指定して
    `/generate` を叩いたところ、**HTTP 200 が返った**（実測、97ms）。
    Validator も通っている。

    作ったのは Curated Domain Library であり、**LLM は1回も呼ばれて
    いない**（`GenerationSource.CURATED`）。それでも当時の
    `diagnostics.provider_used` は `"local"` と報告していた。

    つまり「Local を指定したら 200 が返った」は Level 0 の証拠に
    まったくならない。**誰が作ったかを Evidence 層に訊く。**

    `LOCAL_AI` 以外は数えない。`CURATED` も `COMPOSITION` も
    「Forge が決定的に組んだ」であって Local Model の成果ではない。
    """

    host_id: str = ""
    """**どの実機で測ったか。** 開発 container と実機を混ぜない。"""

    ram_total_mb: int = 0
    vram_total_mb: int = 0
    """取得できたときだけ入れる。**0 は「取れなかった」。**"""

    verification: Verification = Verification.UNVERIFIED
    recorded_at: float = 0.0
    refusal_reasons: tuple[str, ...] = field(default=())

    # -- 判定 -------------------------------------------------------------

    @property
    def counts_as_real_local(self) -> bool:
        """**Real Local Model runs に加算してよいか。**

        1つでも欠けたら数えない。「だいたい本物」で数えると、
        あとから何を根拠に数えたのか分からなくなる
        （`LocalPromotionGate` と同じ姿勢、017A §7）。
        """
        return not self.why_not_counted()

    def why_not_counted(self) -> tuple[str, ...]:
        """数えない理由。**「数えない」だけ返さない。**"""
        reasons: list[str] = []

        if self.provider.strip().lower() in _TEST_DOUBLE_PROVIDERS:
            reasons.append(f"Provider が Test Double（{self.provider}）")
        if self.runtime_backend is LocalRuntimeBackend.TEST_DOUBLE:
            reasons.append("Runtime が Test Double（偽サーバ / fixture）")
        if self.runtime_backend is LocalRuntimeBackend.UNKNOWN:
            reasons.append("どの Runtime が動いたか記録されていない")
        if self.deployment is not Deployment.LOCAL:
            reasons.append(f"LOCAL 実行ではない（{self.deployment.value}）")
        if not self.model.strip():
            reasons.append("Model 名が無い")
        if not self.model_id.strip():
            reasons.append("Runtime が名乗る Model 名（model_id）が無い")

        # **重みの digest は Level 0 の条件から外した**（020A1、2026-08-26）。
        #
        # 以前はここで digest を必須にしていた。理由は2つ混ざっていた——
        # 「どの重みで動いたか言えること」と「fixture を弾くこと」。
        # 1つの欄に2つの仕事をさせていたので、どちらも半端だった:
        #
        # * digest を返さない Runtime（llama-server 等）が、本物でも
        #   永久に Level 0 へ到達できない
        # * digest を返す偽サーバは、digest があるので通ってしまう
        #
        # fixture を弾くのは `runtime_backend` / `generation_source` /
        # `deployment` の仕事である。重みの同一性は `weight_identity` が
        # 別に持ち、**Level 0.5（Baseline Benchmark）が要求する**。
        #
        # **これは緩和である。** 緩めたことを隠さずに書く。
        # 代わりに `domain_resolution` と `observed_tasks` という、
        # 以前は見ていなかった2つの検査を足した。

        if self.domain_resolution.strip().lower() == CURATED_DOMAIN_RESOLUTION:
            # **Curated 経路は AI を1回も呼ばない。**
            # Runtime が動いていなくても 200 が返る（実測）。
            reasons.append(
                "Curated Domain Library が作った"
                "（domain_resolution=curated / probe が不適切）"
            )
        if not structure_source_is_ai(self.structure_source):
            # **構造を作ったのが AI でなければ、Level 0 の証拠にならない**
            # （020A2 §3）。Design Intent だけ Local Model を呼んでも、
            # ソフトウェアの構造は Forge が決定的に組んでいる。
            reasons.append(
                f"Local Model が構造生成を担当していない"
                f"（structure_source={self.structure_source.value}）"
            )
        if not self.observed_tasks:
            reasons.append("AIRouter を通った Task を観測できていない")
        elif self.task not in self.observed_tasks:
            reasons.append(
                f"記録した Task（{self.task.value}）が、実際に通った Task"
                f"（{', '.join(t.value for t in self.observed_tasks)}）に無い"
            )
        if not self.generation_evidence_uid.strip():
            # **本番経路を通っていない実行を Level 0 にしない。**
            reasons.append("Forge の本番経路を通った証拠（Evidence uid）が無い")
        if self.generation_source is not GenerationSource.LOCAL_AI:
            # **決定的な検査。** 200 OK でも、作ったのが Curated なら
            # Local Model の成果ではない。
            reasons.append(
                f"文書を作ったのが Local Model ではない"
                f"（{self.generation_source.value}）"
            )
        if not self.structured_output_ok:
            reasons.append("構造化出力が得られていない")
        if not self.validator_passed:
            reasons.append("Forge Validator を通っていない")
        if self.latency_ms <= 0:
            reasons.append("応答時間が記録されていない")
        if self.verification is not Verification.REAL:
            reasons.append(f"実測として記録されていない（{self.verification.value}）")

        return tuple(reasons)

    @property
    def weight_identity(self) -> WeightIdentity:
        """**どの重みで動いたか言えるか。** 名前では言えない。"""
        return (
            WeightIdentity.VERIFIED_DIGEST
            if self.model_digest.strip()
            else WeightIdentity.UNVERIFIED
        )

    @property
    def probe_was_curated(self) -> bool:
        """**Local Model に仕事が回らない probe だったか。**

        020A2 で条件を広げた。Curated へ落ちた場合だけでなく、
        **構造を Forge が決定的に組んでしまった場合**も同じである——
        どちらも「Local Model に構造生成の仕事が回らなかった」。
        """
        if self.domain_resolution.strip().lower() == CURATED_DOMAIN_RESOLUTION:
            return True
        return self.structure_source in (
            GenerationStructureSource.CURATED,
            GenerationStructureSource.DETERMINISTIC_CAPABILITY_PLAN,
        )

    @property
    def level0_outcome(self) -> Level0Outcome:
        if self.counts_as_real_local:
            return Level0Outcome.PASSED
        if self.probe_was_curated:
            # **Local Model の失敗ではない。測定が成立していない。**
            return Level0Outcome.INVALID_PROBE
        return Level0Outcome.FAILED

    @property
    def ready_for_baseline(self) -> bool:
        """**Level 0.5（Baseline Benchmark）へ進んでよいか**（020A1）。

        Level 0 より厳しい。重みの同一性が言えなければ、
        「どの重みの成績なのか」が分からない記録が Benchmark へ入る。
        """
        return self.counts_as_real_local and (
            self.weight_identity is WeightIdentity.VERIFIED_DIGEST
        )

    def to_dict(self) -> dict[str, object]:
        """報告へそのまま載せられる形。**数えなかった理由も出す。**"""
        return {
            "provider": self.provider,
            "model": self.model,
            "model_id": self.model_id,
            "model_digest": self.model_digest,
            "weight_identity": self.weight_identity.value,
            "domain_resolution": self.domain_resolution,
            "structure_source": self.structure_source.value,
            "observed_tasks": [t.value for t in self.observed_tasks],
            "ready_for_baseline": self.ready_for_baseline,
            "quantization": self.quantization,
            "runtime_backend": self.runtime_backend.value,
            "runtime_version": self.runtime_version,
            "deployment": self.deployment.value,
            "task": self.task.value,
            "latency_ms": round(self.latency_ms, 1),
            "structured_output_ok": self.structured_output_ok,
            "validator_passed": self.validator_passed,
            "generation_evidence_uid": self.generation_evidence_uid,
            "generation_source": self.generation_source.value,
            "host_id": self.host_id,
            "ram_total_mb": self.ram_total_mb,
            "vram_total_mb": self.vram_total_mb,
            "verification": self.verification.value,
            "counts_as_real_local": self.counts_as_real_local,
            "why_not_counted": list(self.why_not_counted()),
            "level0_outcome": self.level0_outcome.value,
            "recorded_at": self.recorded_at,
        }


class RealLocalModelRunLog:
    """Real Local Model runs の**唯一の数え場所**。

    プロセス内メモリのみ（TD41）。**IN-MEMORY / NOT DURABLE。**
    実機での実測は script が JSON として書き出す
    （`scripts/verify_local_model_level0.py`）。
    """

    def __init__(self, *, now: object = time.time) -> None:
        self._runs: list[RealLocalModelRun] = []
        self._now = now

    def record(self, run: RealLocalModelRun) -> RealLocalModelRun:
        """1件記録する。**数えないものも記録は残す。**

        数えなかった実行を捨てると、「なぜ0件なのか」が後から分からない。
        """
        stored = run if run.recorded_at else _with_time(run, float(self._now()))
        self._runs.append(stored)
        return stored

    def counted_runs(self) -> tuple[RealLocalModelRun, ...]:
        return tuple(r for r in self._runs if r.counts_as_real_local)

    def rejected_runs(self) -> tuple[RealLocalModelRun, ...]:
        return tuple(r for r in self._runs if not r.counts_as_real_local)

    def count(self) -> int:
        """**報告に書いてよい「Real Local Model runs」。**"""
        return len(self.counted_runs())

    def all_runs(self) -> tuple[RealLocalModelRun, ...]:
        return tuple(self._runs)

    def level0(self) -> Level0Outcome:
        """Vision §39 Level 0 の到達判定。

        **`INVALID_PROBE` を `FAILED` へ丸めない**（020A1）。
        Curated へ落ちた計測は「Local Model が駄目だった」ではなく
        「Local Model に仕事が回っていない」である。
        """
        if not self._runs:
            return Level0Outcome.NOT_ATTEMPTED
        if self.count() > 0:
            return Level0Outcome.PASSED
        rejected = self.rejected_runs()
        if rejected and all(r.probe_was_curated for r in rejected):
            return Level0Outcome.INVALID_PROBE
        return Level0Outcome.FAILED

    def baseline_ready_runs(self) -> tuple[RealLocalModelRun, ...]:
        """**Level 0.5 へ渡してよい実行**（020A1）。

        Level 0 を通っただけでは足りない。重みの同一性が言えるものだけ。
        """
        return tuple(r for r in self._runs if r.ready_for_baseline)

    def reset(self) -> None:
        self._runs.clear()

    def size(self) -> int:
        return len(self._runs)


def _with_time(run: RealLocalModelRun, when: float) -> RealLocalModelRun:
    from dataclasses import replace  # noqa: PLC0415

    return replace(run, recorded_at=when)


_DEFAULT_LOG = RealLocalModelRunLog()


def default_real_local_run_log() -> RealLocalModelRunLog:
    """本番・script が共通で使う唯一の Log。**数える口を複数作らない。**"""
    return _DEFAULT_LOG
