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
from app.ai.gateway.generation_evidence import GenerationSource
from app.ai.gateway.learning_events import Deployment
from app.ai.gateway.tasks import ForgeTask

__all__ = [
    "Level0Outcome",
    "LocalRuntimeBackend",
    "RealLocalModelRun",
    "RealLocalModelRunLog",
    "default_real_local_run_log",
]


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


class Level0Outcome(str, Enum):
    """Vision §39 Level 0（Local Model が動く）の判定。"""

    PASSED = "passed"
    FAILED = "failed"
    """試したが通らなかった。**理由が残る。**"""

    NOT_ATTEMPTED = "not_attempted"
    """**まだ試していない。** 失敗と区別する。"""


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

    runtime_backend: LocalRuntimeBackend = LocalRuntimeBackend.UNKNOWN
    runtime_version: str = ""
    model_digest: str = ""
    """**Runtime 自身が返した重みの識別子**（Ollama の digest 等）。

    fixture や手書きの偽サーバには通常無い。無ければ数えない
    ——「どの重みで動いたか言えない実行」を実測にしない。
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
        if not self.model_digest.strip():
            reasons.append("重みの識別子（model_digest）が無い")
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
    def level0_outcome(self) -> Level0Outcome:
        return Level0Outcome.PASSED if self.counts_as_real_local else Level0Outcome.FAILED

    def to_dict(self) -> dict[str, object]:
        """報告へそのまま載せられる形。**数えなかった理由も出す。**"""
        return {
            "provider": self.provider,
            "model": self.model,
            "model_digest": self.model_digest,
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
        """Vision §39 Level 0 の到達判定。"""
        if not self._runs:
            return Level0Outcome.NOT_ATTEMPTED
        return Level0Outcome.PASSED if self.count() > 0 else Level0Outcome.FAILED

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
