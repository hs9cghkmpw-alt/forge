"""FORGE-020D — objective repair loop for generated-app workspaces.

A repair may change files inside the isolated generated workspace, but success is
accepted only after the same fixed verifier observes test/build again. The repair
callback never gets to declare PASS; it only performs a bounded mutation.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from app.ai.agent.generated_verification import (
    GeneratedVerification,
    GeneratedWorkspaceVerifier,
)
from app.ai.agent.loop import AgentBudget, AgentLoop, AttemptResult, LoopReport
from app.ai.agent.tools import ToolBroker
from app.ai.learning.episode import GenerationEpisode

__all__ = [
    "GeneratedRepairResult",
    "GeneratedRepairAction",
    "run_generated_repair_episode",
]

GeneratedRepairAction = Callable[[GeneratedVerification, int], None]


@dataclass(frozen=True)
class GeneratedRepairResult:
    """Full objective trajectory for one bounded repair episode."""

    verifications: tuple[GeneratedVerification, ...]
    report: LoopReport

    @property
    def initial(self) -> GeneratedVerification:
        return self.verifications[0]

    @property
    def final(self) -> GeneratedVerification:
        return self.verifications[-1]


def run_generated_repair_episode(
    *,
    episode: GenerationEpisode,
    verifier: GeneratedWorkspaceVerifier,
    repair_action: GeneratedRepairAction,
    max_repair_rounds: int = 3,
    max_repeated_failure: int = 2,
) -> GeneratedRepairResult:
    """Verify -> repair -> re-verify, with Forge observations as the only truth.

    `repair_action` is a trusted Forge-side mutation hook. It receives the latest
    objective verification and the 1-based repair round. It cannot return an outcome;
    the verifier is always run again after the mutation, so a repair cannot self-claim
    success.
    """
    history: list[GeneratedVerification] = []

    def observe() -> GeneratedVerification:
        verification = verifier.verify()
        history.append(verification)
        return verification

    def attempt() -> AttemptResult:
        return observe().attempt

    def repair(current: AttemptResult) -> AttemptResult:
        if not history:
            raise RuntimeError("repair requested before an objective verification")
        round_index = len(history)
        repair_action(history[-1], round_index)
        return observe().attempt

    loop = AgentLoop(
        broker=ToolBroker(),
        episode=episode,
        budget=AgentBudget(
            max_repair_rounds=max_repair_rounds,
            max_tool_calls=0,
            time_budget_seconds=max(
                verifier.timeout_seconds * 3.0 * (max_repair_rounds + 1),
                1.0,
            ),
            max_repeated_failure=max_repeated_failure,
        ),
    )
    report = loop.run(attempt=attempt, repair=repair)
    if not history:  # pragma: no cover - verifier returns or raises before here
        raise RuntimeError("generated repair produced no verification")
    return GeneratedRepairResult(verifications=tuple(history), report=report)
