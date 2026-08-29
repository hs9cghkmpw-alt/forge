"""FORGE-020E — runtime truth is observed, never inferred from build success."""

from __future__ import annotations

import os
import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from app.ai.agent.generated_verification import GeneratedWorkspaceVerifier  # noqa: E402
from app.ai.agent.generated_workspace import materialize_generated_workspace  # noqa: E402
from app.ai.learning.episode import VerificationOutcome  # noqa: E402


class TestGeneratedRuntimeVerification(unittest.TestCase):
    def _workspace(self):
        parent = pathlib.Path(tempfile.mkdtemp())
        return materialize_generated_workspace(
            root=parent / "generated",
            forge_document={"version": "1.0", "screens": []},
            generated_files={"marker.txt": "generated-only"},
        )

    def test_runtime_pass_requires_zero_exit_after_test_and_build(self) -> None:
        workspace = self._workspace()
        result = GeneratedWorkspaceVerifier(
            workspace=workspace,
            commands={
                "run_test": (sys.executable, "-c", "raise SystemExit(0)"),
                "run_build": (sys.executable, "-c", "raise SystemExit(0)"),
                "run_runtime": (
                    sys.executable,
                    "-c",
                    "import pathlib; raise SystemExit(0 if pathlib.Path('marker.txt').exists() else 7)",
                ),
            },
        ).verify()
        self.assertTrue(result.attempt.succeeded)
        self.assertEqual(result.attempt.test, VerificationOutcome.PASSED)
        self.assertEqual(result.attempt.build, VerificationOutcome.PASSED)
        self.assertEqual(result.attempt.runtime, VerificationOutcome.PASSED)
        self.assertIsNotNone(result.runtime)

    def test_runtime_failure_cannot_be_hidden_by_successful_build(self) -> None:
        workspace = self._workspace()
        result = GeneratedWorkspaceVerifier(
            workspace=workspace,
            commands={
                "run_test": (sys.executable, "-c", "raise SystemExit(0)"),
                "run_build": (sys.executable, "-c", "raise SystemExit(0)"),
                "run_runtime": (sys.executable, "-c", "raise SystemExit(23)"),
            },
        ).verify()
        self.assertFalse(result.attempt.succeeded)
        self.assertEqual(result.attempt.failure_code, "runtime_failed")
        self.assertEqual(result.attempt.build, VerificationOutcome.PASSED)
        self.assertEqual(result.attempt.runtime, VerificationOutcome.FAILED)

    def test_unconfigured_runtime_stays_unknown_and_unexecuted(self) -> None:
        workspace = self._workspace()
        result = GeneratedWorkspaceVerifier(
            workspace=workspace,
            commands={
                "run_test": (sys.executable, "-c", "raise SystemExit(0)"),
                "run_build": (sys.executable, "-c", "raise SystemExit(0)"),
            },
        ).verify()
        self.assertTrue(result.attempt.succeeded)
        self.assertEqual(result.attempt.runtime, VerificationOutcome.UNKNOWN)
        self.assertIsNone(result.runtime)

    def test_failed_build_never_fabricates_runtime_observation(self) -> None:
        workspace = self._workspace()
        result = GeneratedWorkspaceVerifier(
            workspace=workspace,
            commands={
                "run_test": (sys.executable, "-c", "raise SystemExit(0)"),
                "run_build": (sys.executable, "-c", "raise SystemExit(8)"),
                "run_runtime": (sys.executable, "-c", "raise SystemExit(0)"),
            },
        ).verify()
        self.assertEqual(result.attempt.build, VerificationOutcome.FAILED)
        self.assertEqual(result.attempt.runtime, VerificationOutcome.UNKNOWN)
        self.assertIsNone(result.runtime)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
