"""Novel Software Generation Benchmark — **最重要KPI**
(FORGE-020 §22・§23、2026-08-25)。

---

## 何を KPI にしないか

```
❌  Widget 数 / Template 数 / 対応ジャンル数
```

これらは**足せば増える**。増やしても「未知の Need に応えられるか」は
1ミリも動かない。むしろ「専用 template を足す」方向へ引っ張るので、
Product Direction が禁じている finite Widget Builder へ寄る。

```
✅  training に入れていない Task で、実際に動くものが出せるか
```

## 専用 template 禁止

Novel Task に対して専用 template を用意したら、それは Novel ではない。
`NovelBenchmarkRun` は**その Task が held-out であること**を要求する
——training に入っている Task を Novel として数えると、
数字が静かに嘘になる（011 §3 の dataset identity と同じ形）。

## できないことは `unsupported` と書く

Game Runtime がまだ無い Task は「0点」ではなく `unsupported` である。
0点は「やって落ちた」、`unsupported` は「そもそも能力が無い」。
混ぜると、能力を足したときに数字がどう動くべきかが分からなくなる。

**Fake PASS を作らない。**

## versioned score

比較できることが要件なので、`scoring_version` を持つ。
配点を変えたら version を上げる——上げずに変えると、
過去の run と比べたときに**改善したように見える**。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from app.ai.learning.gym import GymTask, TaskSplit

__all__ = [
    "AxisResult",
    "NovelBenchmarkRun",
    "NovelBenchmarkSummary",
    "NovelScore",
    "SCORING_VERSION",
    "score_novel_run",
]

#: 配点の版。**変えたら上げる。**
SCORING_VERSION = "novel-v1"

#: 100点の内訳。`Need interpretation` から `Efficiency` まで。
_WEIGHTS: dict[str, int] = {
    "need_interpretation": 10,
    "architecture": 10,
    "capability_decomposition": 10,
    "build": 15,
    "tests": 10,
    "runtime": 15,
    "visual": 10,
    "intent_fit": 10,
    "repair_success": 5,
    "security": 5,
}


class AxisResult(str, Enum):
    PASSED = "passed"
    FAILED = "failed"
    UNSUPPORTED = "unsupported"
    """**Forge にまだその能力が無い。** 0点ではない。"""

    NOT_EVALUATED = "not_evaluated"
    """**既定値。** 測っていないものを PASS へ倒さない。"""


@dataclass(frozen=True)
class NovelScore:
    """versioned score。**満点も内訳も固定。**"""

    earned: int
    possible: int
    unsupported_weight: int
    not_evaluated_weight: int
    scoring_version: str = SCORING_VERSION

    @property
    def ratio(self) -> float:
        """**able な範囲での達成率。**

        `unsupported` を分母から外す。外さないと、能力が無いだけで
        点が下がり、「実装したのに下がった/上がった」が読めなくなる。
        """
        if self.possible <= 0:
            return 0.0
        return self.earned / self.possible

    @property
    def raw_ratio(self) -> float:
        """**100点満点での素点。** 対外的にはこちらが実力である。"""
        total = sum(_WEIGHTS.values())
        return self.earned / total if total else 0.0

    def to_dict(self) -> dict[str, object]:
        return {
            "earned": self.earned, "possible": self.possible,
            "unsupported_weight": self.unsupported_weight,
            "not_evaluated_weight": self.not_evaluated_weight,
            "ratio": round(self.ratio, 4), "raw_ratio": round(self.raw_ratio, 4),
            "scoring_version": self.scoring_version,
        }


@dataclass(frozen=True)
class NovelBenchmarkRun:
    """1 Task × 1 Provider の結果。"""

    task: GymTask
    provider: str
    model: str
    axes: dict[str, AxisResult] = field(default_factory=dict)
    episode_id: str = ""
    used_dedicated_template: bool = False
    """**専用 template を使ったか。** 使っていたら Novel として数えない。"""

    recorded_at: float = 0.0

    def __post_init__(self) -> None:
        if self.task.split is not TaskSplit.HELD_OUT:
            # **training の Task を Novel として数えない。**
            msg = (
                f"{self.task.task_id} は held-out ではない。"
                "training に入れた Task を Novel Benchmark に使わない"
            )
            raise ValueError(msg)
        unknown = sorted(set(self.axes) - set(_WEIGHTS))
        if unknown:
            msg = f"配点に無い軸: {unknown}"
            raise ValueError(msg)

    @property
    def counts_as_novel(self) -> bool:
        """**専用 template を使った run は Novel ではない**（§22）。"""
        return not self.used_dedicated_template

    def to_dict(self) -> dict[str, object]:
        return {
            "task_id": self.task.task_id,
            "task_identity": self.task.identity,
            "provider": self.provider, "model": self.model,
            "axes": {k: v.value for k, v in self.axes.items()},
            "episode_id": self.episode_id,
            "used_dedicated_template": self.used_dedicated_template,
            "counts_as_novel": self.counts_as_novel,
            "recorded_at": self.recorded_at,
            "score": score_novel_run(self).to_dict(),
        }


def score_novel_run(run: NovelBenchmarkRun) -> NovelScore:
    """配点する。**未評価も unsupported も、加点しない。**"""
    earned = 0
    unsupported = 0
    not_evaluated = 0
    for axis, weight in _WEIGHTS.items():
        result = run.axes.get(axis, AxisResult.NOT_EVALUATED)
        if result is AxisResult.PASSED:
            earned += weight
        elif result is AxisResult.UNSUPPORTED:
            unsupported += weight
        elif result is AxisResult.NOT_EVALUATED:
            not_evaluated += weight
    possible = sum(_WEIGHTS.values()) - unsupported
    return NovelScore(
        earned=earned, possible=possible,
        unsupported_weight=unsupported, not_evaluated_weight=not_evaluated,
    )


@dataclass(frozen=True)
class NovelBenchmarkSummary:
    """複数 run のまとめ。**混ぜてはいけないものを混ぜない。**"""

    runs: tuple[NovelBenchmarkRun, ...]

    @property
    def novel_runs(self) -> tuple[NovelBenchmarkRun, ...]:
        return tuple(r for r in self.runs if r.counts_as_novel)

    @property
    def excluded_runs(self) -> tuple[NovelBenchmarkRun, ...]:
        """**専用 template を使ったので除外した run。** 隠さず数える。"""
        return tuple(r for r in self.runs if not r.counts_as_novel)

    def mean_raw_ratio(self) -> float:
        scored = [score_novel_run(r).raw_ratio for r in self.novel_runs]
        return sum(scored) / len(scored) if scored else 0.0

    def to_dict(self) -> dict[str, object]:
        return {
            "scoring_version": SCORING_VERSION,
            "novel_runs": len(self.novel_runs),
            "excluded_runs": len(self.excluded_runs),
            "mean_raw_ratio": round(self.mean_raw_ratio(), 4),
            "runs": [r.to_dict() for r in self.runs],
        }
