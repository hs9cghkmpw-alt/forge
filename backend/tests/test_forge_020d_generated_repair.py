"""FORGE-020D — generated repair succeeds only after objective re-verification."""

from __future__ import annotations

import os
import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from app.ai.agent.generated_repair import run_generated_repair_episode  # noqa: E402
from app.ai.agent.generated_verification import GeneratedWorkspaceVerifier  # noqa: E402
from app.ai.agent.generated_workspace import materialize_generated_workspace  # noqa: E402
from app.ai.learning.episode import (  # noqa: E402
    EpisodeOutcome,
    GenerationEpisode,
    StepKind,
    VerificationOutcome,
)


class TestGeneratedRepairLoop(unittest.TestCase):
    def _workspace(self, marker: str = "broken"):
        parent = pathlib.Path(tempfile.mkdtemp())
        return materialize_generated_workspace(
            root=parent / "generated",
            forge_document={"version": "1.0", "screens": []},
            generated_files={"marker.txt": marker},
        )

    def _verifier(self, workspace):
        return GeneratedWorkspaceVerifier(
            workspace=workspace,
            commands={
                "run_test": (
                    sys.executable,
                    "-c",
                    "import pathlib; raise SystemExit(0 if pathlib.Path('marker.txt').read_text() == 'fixed' else 11)",
                ),
                "run_build": (sys.executable, "-c", "raise SystemExit(0)"),
            },
        )

    def test_failed_test_is_repaired_then_objectively_reverified(self) -> None:
        workspace = self._workspace()
        episode = GenerationEpisode(task_id="forge.generated.repair")
        calls: list[tuple[str, int]] = []

        def repair(latest, round_index: int) -> None:
            calls.append((latest.attempt.failure_code, round_index))
            workspace.sandbox().write_text("marker.txt", "fixed")

        result = run_generated_repair_episode(
            episode=episode,
            verifier=self._verifier(workspace),
            repair_action=repair,
            max_repair_rounds=2,
        )

        self.assertEqual(calls, [("test_failed", 1)])
        self.assertEqual(len(result.verifications), 2)
        self.assertEqual(result.initial.attempt.test, VerificationOutcome.FAILED)
        self.assertEqual(result.initial.attempt.build, VerificationOutcome.UNKNOWN)
        self.assertTrue(result.final.attempt.succeeded)
        self.assertEqual(result.final.attempt.test, VerificationOutcome.PASSED)
        self.assertEqual(result.final.attempt.build, VerificationOutcome.PASSED)
        self.assertEqual(result.report.outcome, EpisodeOutcome.SUCCEEDED)
        self.assertEqual(result.report.rounds, 1)

        self.assertEqual(len(episode.repair_rounds), 1)
        self.assertEqual(episode.repair_rounds[0].failure_code, "test_failed")
        self.assertTrue(episode.repair_rounds[0].resolved)
        self.assertTrue(episode.repair_succeeded)
        self.assertEqual(episode.test_outcome, VerificationOutcome.PASSED)
        self.assertEqual(episode.build_outcome, VerificationOutcome.PASSED)

        test_steps = [s for s in episode.steps if s.kind is StepKind.TEST]
        self.assertEqual([s.succeeded for s in test_steps], [False, True])
        build_steps = [s for s in episode.steps if s.kind is StepKind.BUILD]
        self.assertEqual([s.succeeded for s in build_steps], [True])
        self.assertTrue(any(s.kind is StepKind.DIAGNOSE for s in episode.steps))

    def test_repair_callback_cannot_self_claim_success(self) -> None:
        workspace = self._workspace()
        episode = GenerationEpisode(task_id="forge.generated.repair")

        def ineffective_repair(latest, round_index: int) -> None:
            # Returning nothing and changing nothing: only a fresh verifier run decides.
            self.assertEqual(latest.attempt.failure_code, "test_failed")

        result = run_generated_repair_episode(
            episode=episode,
            verifier=self._verifier(workspace),
            repair_action=ineffective_repair,
            max_repair_rounds=1,
        )

        self.assertEqual(result.report.outcome, EpisodeOutcome.ABANDONED)
        self.assertEqual(result.report.stopped_because, "max_repair_rounds")
        self.assertEqual(len(result.verifications), 2)
        self.assertFalse(result.final.attempt.succeeded)
        self.assertEqual(result.final.attempt.test, VerificationOutcome.FAILED)
        self.assertEqual(result.final.attempt.build, VerificationOutcome.UNKNOWN)
        self.assertEqual(len(episode.repair_rounds), 1)
        self.assertFalse(episode.repair_rounds[0].resolved)
        self.assertFalse(episode.repair_succeeded)

    def test_already_green_artifact_never_runs_repair(self) -> None:
        workspace = self._workspace(marker="fixed")
        episode = GenerationEpisode(task_id="forge.generated.repair")
        called = False

        def repair(latest, round_index: int) -> None:
            nonlocal called
            called = True

        result = run_generated_repair_episode(
            episode=episode,
            verifier=self._verifier(workspace),
            repair_action=repair,
        )

        self.assertFalse(called)
        self.assertEqual(result.report.outcome, EpisodeOutcome.SUCCEEDED)
        self.assertEqual(result.report.rounds, 0)
        self.assertEqual(len(result.verifications), 1)
        self.assertEqual(episode.repair_rounds, ())


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
