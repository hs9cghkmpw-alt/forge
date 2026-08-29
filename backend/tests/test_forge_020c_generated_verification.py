"""FORGE-020C — generated app build/test truth comes from its isolated workspace."""

from __future__ import annotations

import os
import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from app.ai.agent.generated_verification import (  # noqa: E402
    GeneratedWorkspaceVerifier,
    run_generated_verification_episode,
)
from app.ai.agent.generated_workspace import materialize_generated_workspace  # noqa: E402
from app.ai.learning.episode import (  # noqa: E402
    EpisodeOutcome,
    GenerationEpisode,
    StepKind,
    VerificationOutcome,
)


class TestGeneratedWorkspaceVerification(unittest.TestCase):
    def _workspace(self):
        parent = pathlib.Path(tempfile.mkdtemp())
        root = parent / "generated"
        return materialize_generated_workspace(
            root=root,
            forge_document={"version": "1.0", "screens": []},
            generated_files={"marker.txt": "generated-only"},
        )

    def test_pass_requires_objective_test_and_build_zero_exit(self) -> None:
        workspace = self._workspace()
        verifier = GeneratedWorkspaceVerifier(
            workspace=workspace,
            commands={
                "prepare": (sys.executable, "-c", "print('prepared')"),
                "run_test": (sys.executable, "-c", "print(open('marker.txt').read())"),
                "run_build": (sys.executable, "-c", "import pathlib; pathlib.Path('built.ok').write_text('yes')"),
            },
        )
        result = verifier.verify()
        self.assertTrue(result.attempt.succeeded)
        self.assertEqual(result.attempt.test, VerificationOutcome.PASSED)
        self.assertEqual(result.attempt.build, VerificationOutcome.PASSED)
        self.assertEqual(result.attempt.runtime, VerificationOutcome.UNKNOWN)
        self.assertTrue((workspace.root / "built.ok").is_file())
        self.assertIn("generated-only", result.test.output)

    def test_prepare_failure_does_not_fabricate_test_or_build(self) -> None:
        workspace = self._workspace()
        result = GeneratedWorkspaceVerifier(
            workspace=workspace,
            commands={
                "prepare": (sys.executable, "-c", "raise SystemExit(3)"),
                "run_test": (sys.executable, "-c", "raise SystemExit(0)"),
                "run_build": (sys.executable, "-c", "raise SystemExit(0)"),
            },
        ).verify()
        self.assertFalse(result.attempt.succeeded)
        self.assertEqual(result.attempt.failure_code, "prepare_failed")
        self.assertEqual(result.attempt.test, VerificationOutcome.UNKNOWN)
        self.assertEqual(result.attempt.build, VerificationOutcome.UNKNOWN)
        self.assertIsNone(result.test)
        self.assertIsNone(result.build)

    def test_test_failure_leaves_unexecuted_build_unknown(self) -> None:
        workspace = self._workspace()
        result = GeneratedWorkspaceVerifier(
            workspace=workspace,
            commands={
                "run_test": (sys.executable, "-c", "raise SystemExit(9)"),
                "run_build": (sys.executable, "-c", "raise SystemExit(0)"),
            },
        ).verify()
        self.assertFalse(result.attempt.succeeded)
        self.assertEqual(result.attempt.failure_code, "test_failed")
        self.assertEqual(result.attempt.test, VerificationOutcome.FAILED)
        self.assertEqual(result.attempt.build, VerificationOutcome.UNKNOWN)
        self.assertIsNone(result.build)

    def test_timeout_is_failed_not_unknown_or_passed(self) -> None:
        workspace = self._workspace()
        result = GeneratedWorkspaceVerifier(
            workspace=workspace,
            commands={
                "run_test": (sys.executable, "-c", "import time; time.sleep(0.2)"),
                "run_build": (sys.executable, "-c", "raise SystemExit(0)"),
            },
            timeout_seconds=0.01,
        ).verify()
        self.assertEqual(result.attempt.failure_code, "test_timeout")
        self.assertEqual(result.attempt.test, VerificationOutcome.FAILED)
        self.assertEqual(result.attempt.build, VerificationOutcome.UNKNOWN)

    def test_commands_run_from_generated_workspace_not_repo(self) -> None:
        workspace = self._workspace()
        result = GeneratedWorkspaceVerifier(
            workspace=workspace,
            commands={
                "run_test": (
                    sys.executable,
                    "-c",
                    "import pathlib; raise SystemExit(0 if pathlib.Path('marker.txt').read_text() == 'generated-only' else 8)",
                ),
                "run_build": (sys.executable, "-c", "raise SystemExit(0)"),
            },
        ).verify()
        self.assertTrue(result.attempt.succeeded)

    def test_objective_results_are_recorded_into_episode_steps(self) -> None:
        workspace = self._workspace()
        episode = GenerationEpisode(task_id="forge.generated.verify")
        verification, report = run_generated_verification_episode(
            episode=episode,
            verifier=GeneratedWorkspaceVerifier(
                workspace=workspace,
                commands={
                    "run_test": (sys.executable, "-c", "raise SystemExit(0)"),
                    "run_build": (sys.executable, "-c", "raise SystemExit(0)"),
                },
            ),
        )
        self.assertTrue(verification.attempt.succeeded)
        self.assertEqual(report.outcome, EpisodeOutcome.SUCCEEDED)
        self.assertEqual(episode.test_outcome, VerificationOutcome.PASSED)
        self.assertEqual(episode.build_outcome, VerificationOutcome.PASSED)
        typed = {(step.kind, step.name): step for step in episode.steps}
        self.assertTrue(typed[(StepKind.TEST, "test")].succeeded)
        self.assertTrue(typed[(StepKind.BUILD, "build")].succeeded)
        self.assertNotIn((StepKind.RUN, "runtime"), typed)
        self.assertNotIn((StepKind.VISUAL, "visual"), typed)

    def test_failed_test_is_episode_failed_fact_but_unrun_build_stays_unknown(self) -> None:
        workspace = self._workspace()
        episode = GenerationEpisode(task_id="forge.generated.verify")
        verification, report = run_generated_verification_episode(
            episode=episode,
            verifier=GeneratedWorkspaceVerifier(
                workspace=workspace,
                commands={
                    "run_test": (sys.executable, "-c", "raise SystemExit(12)"),
                    "run_build": (sys.executable, "-c", "raise SystemExit(0)"),
                },
            ),
        )
        self.assertEqual(verification.attempt.test, VerificationOutcome.FAILED)
        self.assertEqual(verification.attempt.build, VerificationOutcome.UNKNOWN)
        self.assertEqual(report.outcome, EpisodeOutcome.ABANDONED)
        self.assertEqual(episode.test_outcome, VerificationOutcome.FAILED)
        self.assertEqual(episode.build_outcome, VerificationOutcome.UNKNOWN)
        typed = {(step.kind, step.name) for step in episode.steps}
        self.assertIn((StepKind.TEST, "test"), typed)
        self.assertNotIn((StepKind.BUILD, "build"), typed)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
