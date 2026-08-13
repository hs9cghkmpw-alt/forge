"""Provider Benchmark(FORGE-QUALITY-AI-INDEPENDENCE-003 Phase I、
2026-08-12、指示書19章)。

同一Task・同一Datasetで、複数Providerを**同じ評価基準**で比較する。

指示書3章の禁止事項——「GeminiとLocalのどちらが優秀か」という
大雑把な比較——を構造的に防ぐため、Benchmarkは必ず`ForgeTask`単位で
実行する。結果も`(task, provider)`の組でしか出ない。

指示書19章の最低指標のうち、このモジュールが測るもの:

* `schema_valid_rate` — 応答が期待スキーマの必須キーを満たした割合
* `task_accuracy` — ケースごとの合否判定(Task固有の判定関数)
* `latency_ms` — Provider呼び出しの所要時間(p50/平均)
* `failure_rate` — 例外・パース失敗の割合

`cost`は測っていない。Geminiの課金情報はAPIレスポンスに含まれず、
ローカルは金銭コストが0であるため、**両者を同じ土俵の数値にできない**
(指示書19章は「可能なら」としている)。代わりにlatencyを必ず記録し、
ローカルの実コストであるCPU時間の代理指標としている。
"""

from __future__ import annotations

import statistics
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from app.ai.gateway.model_gateway import ForgeTask, ModelGateway

__all__ = [
    "BenchmarkCase",
    "BenchmarkReport",
    "ProviderScore",
    "run_benchmark",
]


@dataclass(frozen=True)
class BenchmarkCase:
    """1件の評価ケース。

    `check`は「この応答はこのケースの正解か」を判定する関数。
    Task固有の正解条件(例: Impact分類なら`unknowns[0].impact == "high"`)
    をここに閉じ込めることで、Benchmark本体はTaskの中身を知らずに済む。
    """

    name: str
    prompt: str
    response_schema: dict[str, Any]
    required_keys: tuple[str, ...] = ()
    check: Callable[[dict[str, Any]], bool] | None = None


@dataclass
class ProviderScore:
    """1 Provider × 1 Taskのスコア(指示書19章の指標)。"""

    provider: str
    task: ForgeTask
    total: int = 0
    schema_valid: int = 0
    correct: int = 0
    failures: int = 0
    latencies_ms: list[float] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def schema_valid_rate(self) -> float:
        return self.schema_valid / self.total if self.total else 0.0

    @property
    def task_accuracy(self) -> float:
        return self.correct / self.total if self.total else 0.0

    @property
    def failure_rate(self) -> float:
        return self.failures / self.total if self.total else 0.0

    @property
    def latency_p50_ms(self) -> float:
        return statistics.median(self.latencies_ms) if self.latencies_ms else 0.0

    @property
    def latency_mean_ms(self) -> float:
        return statistics.fmean(self.latencies_ms) if self.latencies_ms else 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "task": self.task.value,
            "cases": self.total,
            "schema_valid_rate": round(self.schema_valid_rate, 3),
            "task_accuracy": round(self.task_accuracy, 3),
            "failure_rate": round(self.failure_rate, 3),
            "latency_p50_ms": round(self.latency_p50_ms, 1),
            "latency_mean_ms": round(self.latency_mean_ms, 1),
        }


@dataclass
class BenchmarkReport:
    task: ForgeTask
    scores: list[ProviderScore] = field(default_factory=list)

    def winner(
        self, *, min_schema_valid_rate: float = 0.9, min_task_accuracy: float = 0.5
    ) -> str | None:
        """このTaskで**採用しうる**Providerのうち、最も精度が高いもの。
        条件を満たすものが無ければ`None`(=このTaskはまだ誰にも任せられない)。

        2つの下限を課している。どちらも指示書18章「『動いた』だけでは
        採用しない。Forge Benchmarkで合格すること」の実装である。

        * `min_schema_valid_rate` — 応答が構造として使えること。
          Forgeは応答をJSONとして解釈するため、たまに崩れるProviderは
          精度が高くてもRouting先にできない。
        * `min_task_accuracy` — **実際に正解すること**。

        **`min_task_accuracy`は、このBenchmarkを最初に走らせて見つけた
        実バグの修正である**: 以前は適合率の下限しか無かったため、
        `mock`(常に`"mock_result"`を返す=schema適合率100%・正答率0%)が
        「勝者」として選ばれてしまった。形式さえ整っていれば中身が
        まるで違っていても採用される、という穴だった。
        """
        eligible = [
            s for s in self.scores
            if s.schema_valid_rate >= min_schema_valid_rate
            and s.task_accuracy >= min_task_accuracy
        ]
        if not eligible:
            return None
        return max(eligible, key=lambda s: (s.task_accuracy, -s.latency_p50_ms)).provider

    def to_dict(self) -> dict[str, Any]:
        return {
            "task": self.task.value,
            "scores": [s.to_dict() for s in self.scores],
            "winner": self.winner(),
        }


def run_benchmark(
    gateway: ModelGateway,
    task: ForgeTask,
    cases: list[BenchmarkCase],
    providers: list[str],
) -> BenchmarkReport:
    """同一Task・同一Datasetで、各Providerを順に評価する。

    Providerが例外を投げても止まらない(それ自体が`failure_rate`と
    いう測定結果である)。**片方が落ちたからBenchmarkが取れない、
    という事態を避ける**——指示書27章「Geminiの枠が尽きても進める」の
    実装上の担保でもある。
    """
    report = BenchmarkReport(task=task)
    for provider in providers:
        score = ProviderScore(provider=provider, task=task)
        for case in cases:
            score.total += 1
            try:
                result = gateway.generate(
                    task, case.prompt, case.response_schema, provider=provider,
                )
            except Exception as exc:  # noqa: BLE001 — 失敗率も測定対象
                score.failures += 1
                score.errors.append(f"{case.name}: {str(exc)[:120]}")
                continue

            score.latencies_ms.append(result.latency_ms)
            value = result.value
            if all(k in value for k in case.required_keys):
                score.schema_valid += 1
            if case.check is not None and case.check(value):
                score.correct += 1
            elif case.check is None:
                # 判定関数が無いケースは、schema適合＝正解とみなす。
                if all(k in value for k in case.required_keys):
                    score.correct += 1
        report.scores.append(score)
    return report
