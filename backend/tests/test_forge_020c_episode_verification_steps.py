"""FORGE-020C — objective verification outcomes must remain typed in Episode steps."""

from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from app.ai.agent.loop import AgentBudget, AgentLoop, AttemptResult  # noqa: E402
from app.ai.agent.tools import ToolBroker  # noqa: E402
from app.ai.learning.episode import (  # noqa: E402
    GenerationEpisode,
    StepKind,
    VerificationOutcome,
)


class TestVerificationTrajectoryTruth(unittest.TestCase):
    def _run_once(self, result: AttemptResult) -> GenerationEpisode:
        episode = GenerationEpisode(task_id="forge.test")
        loop = AgentLoop(
            broker=ToolBroker(),
            episode=episode,
            budget=AgentBudget(max_repair_rounds=0),
        )
        loop.run(attempt=lambda: result, repair=lambda current: current)
        return episode

    def test_build_and_test_results_have_their_own_step_kinds(self) -> None:
        episode = self._run_once(AttemptResult(
            succeeded=False,
            failure_code="test_failed",
            validator=VerificationOutcome.PASSED,
            build=VerificationOutcome.PASSED,
            test=VerificationOutcome.FAILED,
        ))
        typed = {(step.kind, step.name): step for step in episode.steps}

        self.assertTrue(typed[(StepKind.BUILD, "build")].succeeded)
        self.assertEqual(
            typed[(StepKind.BUILD, "build")].detail_code,
            VerificationOutcome.PASSED.value,
        )
        self.assertFalse(typed[(StepKind.TEST, "test")].succeeded)
        self.assertEqual(
            typed[(StepKind.TEST, "test")].detail_code,
            VerificationOutcome.FAILED.value,
        )

    def test_unknown_is_not_fabricated_into_an_executed_step(self) -> None:
        episode = self._run_once(AttemptResult(
            succeeded=True,
            validator=VerificationOutcome.PASSED,
            runtime=VerificationOutcome.UNKNOWN,
            visual=VerificationOutcome.UNKNOWN,
        ))
        typed_names = {(step.kind, step.name) for step in episode.steps}
        self.assertNotIn((StepKind.RUN, "runtime"), typed_names)
        self.assertNotIn((StepKind.VISUAL, "visual"), typed_names)

    def test_unsupported_is_recorded_but_never_as_success(self) -> None:
        episode = self._run_once(AttemptResult(
            succeeded=True,
            validator=VerificationOutcome.PASSED,
            visual=VerificationOutcome.UNSUPPORTED,
        ))
        visual = next(
            step for step in episode.steps
            if step.kind is StepKind.VISUAL and step.name == "visual"
        )
        self.assertFalse(visual.succeeded)
        self.assertEqual(visual.detail_code, VerificationOutcome.UNSUPPORTED.value)

    def test_validator_step_is_distinct_from_attempt_summary(self) -> None:
        episode = self._run_once(AttemptResult(
            succeeded=False,
            failure_code="build_failed",
            validator=VerificationOutcome.PASSED,
            build=VerificationOutcome.FAILED,
        ))
        attempt = next(step for step in episode.steps if step.name == "attempt")
        validator = next(step for step in episode.steps if step.name == "validator")

        self.assertFalse(attempt.succeeded)
        self.assertTrue(validator.succeeded)
        self.assertEqual(validator.detail_code, VerificationOutcome.PASSED.value)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
