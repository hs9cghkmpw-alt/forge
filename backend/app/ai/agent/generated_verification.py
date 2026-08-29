"""FORGE-020C/020D — objective verification for generated workspaces.

Only CommandRunner observations from the generated-artifact workspace can promote
build/test/runtime outcomes. Model text, Forge's repository CI, or log interpretation
are not accepted as verification truth here.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from app.ai.agent.generated_workspace import GeneratedWorkspace, GeneratedWorkspaceError
from app.ai.agent.loop import AgentBudget, AgentLoop, AttemptResult, LoopReport
from app.ai.agent.tools import ToolBroker
from app.ai.agent.toolset import CommandObservation, CommandRunner
from app.ai.learning.episode import GenerationEpisode, VerificationOutcome

__all__ = [
    "GeneratedVerification",
    "GeneratedWorkspaceVerifier",
    "observation_outcome",
    "run_generated_verification_episode",
]


def observation_outcome(observation: CommandObservation) -> VerificationOutcome:
    """Map an OS observation to Forge verification truth without reading model text."""
    return VerificationOutcome.PASSED if observation.passed else VerificationOutcome.FAILED


@dataclass(frozen=True)
class GeneratedVerification:
    """One generated-app verification attempt plus objective command observations."""

    attempt: AttemptResult
    prepare: CommandObservation | None = None
    test: CommandObservation | None = None
    build: CommandObservation | None = None
    runtime: CommandObservation | None = None


@dataclass
class GeneratedWorkspaceVerifier:
    """Run a fixed command plan only inside one generated-artifact workspace.

    The command argv values are owned by Forge/caller configuration, never by the
    model. `CommandRunner` sets cwd to `workspace.root`, so a successful Forge repo
    build cannot accidentally become generated-app evidence.
    """

    workspace: GeneratedWorkspace
    commands: Mapping[str, tuple[str, ...]]
    timeout_seconds: float = 300.0

    def _runner(self) -> CommandRunner:
        return CommandRunner(
            sandbox=self.workspace.sandbox(),
            commands=self.commands,
            timeout_seconds=self.timeout_seconds,
        )

    @staticmethod
    def _failure_code(stage: str, observation: CommandObservation) -> str:
        return f"{stage}_timeout" if observation.timed_out else f"{stage}_failed"

    def verify(self) -> GeneratedVerification:
        """Integrity -> prepare -> test -> build -> runtime, preserving UNKNOWNs."""
        try:
            self.workspace.verify_integrity()
        except GeneratedWorkspaceError:
            # Do not execute even a prepare command against an artifact whose identity
            # can no longer be proven. UNKNOWN is more truthful than pretending the
            # previously validated document is still the one being exercised.
            return GeneratedVerification(
                attempt=AttemptResult(
                    succeeded=False,
                    failure_code="artifact_integrity_failed",
                    validator=VerificationOutcome.UNKNOWN,
                    build=VerificationOutcome.UNKNOWN,
                    test=VerificationOutcome.UNKNOWN,
                    runtime=VerificationOutcome.UNKNOWN,
                    visual=VerificationOutcome.UNKNOWN,
                )
            )

        runner = self._runner()

        prepare: CommandObservation | None = None
        if "prepare" in self.commands:
            prepare = runner.observe("prepare")
            if not prepare.passed:
                return GeneratedVerification(
                    attempt=AttemptResult(
                        succeeded=False,
                        failure_code=self._failure_code("prepare", prepare),
                        validator=VerificationOutcome.PASSED,
                        build=VerificationOutcome.UNKNOWN,
                        test=VerificationOutcome.UNKNOWN,
                        runtime=VerificationOutcome.UNKNOWN,
                    ),
                    prepare=prepare,
                )

        test = runner.observe("run_test")
        test_outcome = observation_outcome(test)
        if not test.passed:
            return GeneratedVerification(
                attempt=AttemptResult(
                    succeeded=False,
                    failure_code=self._failure_code("test", test),
                    validator=VerificationOutcome.PASSED,
                    build=VerificationOutcome.UNKNOWN,
                    test=test_outcome,
                    runtime=VerificationOutcome.UNKNOWN,
                ),
                prepare=prepare,
                test=test,
            )

        build = runner.observe("run_build")
        build_outcome = observation_outcome(build)
        if not build.passed:
            return GeneratedVerification(
                attempt=AttemptResult(
                    succeeded=False,
                    failure_code=self._failure_code("build", build),
                    validator=VerificationOutcome.PASSED,
                    build=build_outcome,
                    test=test_outcome,
                    runtime=VerificationOutcome.UNKNOWN,
                    visual=VerificationOutcome.UNKNOWN,
                ),
                prepare=prepare,
                test=test,
                build=build,
            )

        runtime: CommandObservation | None = None
        runtime_outcome = VerificationOutcome.UNKNOWN
        if "run_runtime" in self.commands:
            runtime = runner.observe("run_runtime")
            runtime_outcome = observation_outcome(runtime)
            if not runtime.passed:
                return GeneratedVerification(
                    attempt=AttemptResult(
                        succeeded=False,
                        failure_code=self._failure_code("runtime", runtime),
                        validator=VerificationOutcome.PASSED,
                        build=build_outcome,
                        test=test_outcome,
                        runtime=runtime_outcome,
                        visual=VerificationOutcome.UNKNOWN,
                    ),
                    prepare=prepare,
                    test=test,
                    build=build,
                    runtime=runtime,
                )

        return GeneratedVerification(
            attempt=AttemptResult(
                succeeded=True,
                failure_code="",
                validator=VerificationOutcome.PASSED,
                build=build_outcome,
                test=test_outcome,
                runtime=runtime_outcome,
                visual=VerificationOutcome.UNKNOWN,
            ),
            prepare=prepare,
            test=test,
            build=build,
            runtime=runtime,
        )


def run_generated_verification_episode(
    *,
    episode: GenerationEpisode,
    verifier: GeneratedWorkspaceVerifier,
) -> tuple[GeneratedVerification, LoopReport]:
    """Record one objective generated-workspace attempt into a GenerationEpisode.

    This is deliberately verification-only: repair budget is zero. A failed stage is
    therefore recorded by AgentLoop and the report stops as ABANDONED because no repair
    was attempted in this stage. A repair stage can reuse this verifier with non-zero
    repair budget.
    """
    captured: GeneratedVerification | None = None

    def attempt() -> AttemptResult:
        nonlocal captured
        captured = verifier.verify()
        return captured.attempt

    loop = AgentLoop(
        broker=ToolBroker(),
        episode=episode,
        budget=AgentBudget(
            max_repair_rounds=0,
            max_tool_calls=0,
            time_budget_seconds=max(verifier.timeout_seconds * 4.0, 1.0),
        ),
    )
    report = loop.run(attempt=attempt, repair=lambda current: current)
    if captured is None:  # pragma: no cover - verifier returns or raises before here
        raise RuntimeError("generated verification produced no observation")
    return captured, report
