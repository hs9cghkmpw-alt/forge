"""Agent Loop + Autonomous Repair — **落ちたら診て直す**
(FORGE-020 §24、2026-08-25)。

---

## 何を回すのか

```
generate → validate → build/test → 失敗を観測 → 診断 → 修正 → 再検証
```

Local AI が「知らないから作れません」で止まらないための輪である。
ただし**輪は必ず止まる**ようにする。

## 予算を持つ

止まらない Agent は、止まらないだけで害である。

| 予算 | 既定 | 何を防ぐ |
|---|---|---|
| `max_repair_rounds` | 3 | 同じ場所を延々と直し続ける |
| `max_tool_calls` | 40 | 道具を呼び続ける |
| `time_budget_seconds` | 120 | 全体が終わらない |

## 同じ失敗を繰り返さない

予算の中でも、**同じ失敗分類が2回続いたら止める**。「直したつもりが
同じ所で落ちる」は、その方針では直らないという情報である。回数を
使い切るより、早く諦めて残す方が Episode として価値がある。

## 予算切れは失敗ではない

`ABANDONED` を `FAILED` と別にしてある。「やり方が悪くて落ちた」と
「時間が足りなかった」は、学習素材として意味が違う。
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass

from app.ai.agent.tools import ToolBroker, ToolCall, ToolResult
from app.ai.learning.episode import (
    EpisodeOutcome,
    EpisodeStep,
    GenerationEpisode,
    RepairRound,
    StepKind,
    VerificationOutcome,
)

__all__ = [
    "AgentBudget",
    "AgentLoop",
    "AttemptResult",
    "BudgetExhausted",
    "LoopReport",
]


@dataclass(frozen=True)
class AgentBudget:
    """輪が止まるための上限。**既定で有限。**"""

    max_repair_rounds: int = 3
    max_tool_calls: int = 40
    time_budget_seconds: float = 120.0
    max_repeated_failure: int = 2
    """同じ失敗分類が続いてよい回数。**超えたら方針を変えるべき。**"""


class BudgetExhausted(Exception):
    """予算を使い切った。**失敗とは別に扱う。**"""

    def __init__(self, which: str) -> None:
        super().__init__(which)
        self.which = which


@dataclass(frozen=True)
class AttemptResult:
    """1回の「作って検証する」の結果。"""

    succeeded: bool
    failure_code: str = ""
    """落ちた理由の**分類**。例外メッセージそのものは入れない。"""

    validator: VerificationOutcome = VerificationOutcome.UNKNOWN
    build: VerificationOutcome = VerificationOutcome.UNKNOWN
    test: VerificationOutcome = VerificationOutcome.UNKNOWN
    runtime: VerificationOutcome = VerificationOutcome.UNKNOWN
    visual: VerificationOutcome = VerificationOutcome.UNKNOWN
    artifact: object = None


@dataclass
class LoopReport:
    """輪が回った結果。**Episode と対になる。**"""

    outcome: EpisodeOutcome
    rounds: int = 0
    tool_calls: int = 0
    elapsed_seconds: float = 0.0
    stopped_because: str = ""
    result: AttemptResult | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "outcome": self.outcome.value, "rounds": self.rounds,
            "tool_calls": self.tool_calls,
            "elapsed_seconds": round(self.elapsed_seconds, 3),
            "stopped_because": self.stopped_because,
        }


class AgentLoop:
    """生成 → 検証 → 診断 → 修正 の輪。

    **生成器そのものは持たない。** `attempt` / `repair` を受け取る
    ——Local でも Cloud でも、Forge の決定的な操作でも同じ輪を回せる。
    """

    def __init__(
        self,
        *,
        broker: ToolBroker,
        episode: GenerationEpisode,
        budget: AgentBudget | None = None,
        now: Callable[[], float] = time.monotonic,
    ) -> None:
        self._broker = broker
        self._episode = episode
        self._budget = budget or AgentBudget()
        self._now = now
        self._started = 0.0
        self._tool_calls = 0

    # -- 道具 -------------------------------------------------------------

    def call_tool(self, call: ToolCall) -> ToolResult:
        """道具を1つ呼ぶ。**予算を数え、Episode へ残す。**"""
        if self._tool_calls >= self._budget.max_tool_calls:
            raise BudgetExhausted("max_tool_calls")
        self._check_time()
        self._tool_calls += 1
        result = self._broker.invoke(call)
        self._episode.record_step(EpisodeStep(
            kind=StepKind.TOOL_CALL, name=call.tool,
            succeeded=result.ok, detail_code=result.outcome.value,
            duration_ms=result.duration_ms, at=time.time(),
        ))
        return result

    # -- 輪 ---------------------------------------------------------------

    def run(
        self,
        *,
        attempt: Callable[[], AttemptResult],
        repair: Callable[[AttemptResult], AttemptResult],
    ) -> LoopReport:
        """作って、落ちたら直す。**必ず止まる。**"""
        self._started = self._now()
        report = LoopReport(outcome=EpisodeOutcome.UNKNOWN)

        try:
            current = attempt()
        except BudgetExhausted as exhausted:
            return self._abandon(report, exhausted.which)
        self._note_attempt(current)

        repeated = 0
        last_failure = ""
        while not current.succeeded:
            if report.rounds >= self._budget.max_repair_rounds:
                return self._abandon(report, "max_repair_rounds", current)
            if current.failure_code and current.failure_code == last_failure:
                repeated += 1
                if repeated >= self._budget.max_repeated_failure:
                    # **同じ所で落ち続けている。** 回数を使い切る前に止める。
                    return self._abandon(report, "repeated_failure", current)
            else:
                repeated = 0
            last_failure = current.failure_code

            try:
                self._check_time()
            except BudgetExhausted as exhausted:
                return self._abandon(report, exhausted.which, current)

            report.rounds += 1
            self._episode.record_step(EpisodeStep(
                kind=StepKind.DIAGNOSE, name=current.failure_code or "unknown",
                succeeded=False, at=time.time(),
            ))
            try:
                repaired = repair(current)
            except BudgetExhausted as exhausted:
                return self._abandon(report, exhausted.which, current)
            self._episode.record_repair(RepairRound(
                round_index=report.rounds,
                failure_code=current.failure_code or "unknown",
                diagnosis_code=current.failure_code or "unknown",
                action="repair",
                resolved=repaired.succeeded,
            ))
            self._note_attempt(repaired)
            current = repaired

        report.outcome = EpisodeOutcome.SUCCEEDED
        return self._finish(report, current)

    # -- 内部 -------------------------------------------------------------

    def _check_time(self) -> None:
        if self._now() - self._started > self._budget.time_budget_seconds:
            raise BudgetExhausted("time_budget_seconds")

    def _note_attempt(self, result: AttemptResult) -> None:
        self._episode.validator_outcome = result.validator
        self._episode.build_outcome = result.build
        self._episode.test_outcome = result.test
        self._episode.runtime_outcome = result.runtime
        self._episode.visual_outcome = result.visual
        self._episode.record_step(EpisodeStep(
            kind=StepKind.VALIDATE, name="attempt",
            succeeded=result.succeeded,
            detail_code=result.failure_code, at=time.time(),
        ))

    def _abandon(
        self, report: LoopReport, why: str, result: AttemptResult | None = None
    ) -> LoopReport:
        """**予算切れは `FAILED` ではない**（§24）。"""
        report.outcome = EpisodeOutcome.ABANDONED
        report.stopped_because = why
        return self._finish(report, result)

    def _finish(self, report: LoopReport, result: AttemptResult | None) -> LoopReport:
        report.tool_calls = self._tool_calls
        report.elapsed_seconds = self._now() - self._started
        report.result = result
        self._episode.final_outcome = report.outcome
        return report
