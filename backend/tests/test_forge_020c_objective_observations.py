"""FORGE-020C — build/test command truth must come from Forge observations.

The Local Agent may read logs, but a model statement is never the source of truth for
build/test success.  CommandRunner.observe() preserves exit code and timeout as typed
facts so later production wiring can map them into GenerationEpisode verification.
"""

from __future__ import annotations

import os
import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from app.ai.agent.sandbox import ToolSandbox  # noqa: E402
from app.ai.agent.toolset import CommandObservation, CommandRunner  # noqa: E402


class TestObjectiveCommandObservation(unittest.TestCase):
    def setUp(self) -> None:
        self.root = pathlib.Path(tempfile.mkdtemp())
        self.sandbox = ToolSandbox.at(self.root)

    def test_zero_exit_is_objective_pass(self) -> None:
        runner = CommandRunner(
            sandbox=self.sandbox,
            commands={"run_test": (sys.executable, "-c", "print('ok')")},
        )
        observed = runner.observe("run_test")
        self.assertIsInstance(observed, CommandObservation)
        self.assertEqual(observed.exit_code, 0)
        self.assertFalse(observed.timed_out)
        self.assertTrue(observed.passed)
        self.assertIn("ok", observed.output)

    def test_nonzero_exit_cannot_be_model_claimed_as_pass(self) -> None:
        runner = CommandRunner(
            sandbox=self.sandbox,
            commands={"run_build": (sys.executable, "-c", "raise SystemExit(7)")},
        )
        observed = runner.observe("run_build")
        self.assertEqual(observed.exit_code, 7)
        self.assertFalse(observed.passed)
        self.assertIn("[exit 7]", observed.render())

    def test_timeout_is_not_a_pass_and_has_no_fake_exit_code(self) -> None:
        runner = CommandRunner(
            sandbox=self.sandbox,
            commands={
                "run_test": (
                    sys.executable,
                    "-c",
                    "import time; time.sleep(0.2)",
                )
            },
            timeout_seconds=0.01,
        )
        observed = runner.observe("run_test")
        self.assertTrue(observed.timed_out)
        self.assertIsNone(observed.exit_code)
        self.assertFalse(observed.passed)

    def test_unknown_command_still_fails_closed(self) -> None:
        runner = CommandRunner(sandbox=self.sandbox, commands={})
        with self.assertRaises(ValueError):
            runner.observe("run_whatever_the_model_invented")

    def test_legacy_tool_text_is_derived_from_the_same_observation(self) -> None:
        runner = CommandRunner(
            sandbox=self.sandbox,
            commands={"run_test": (sys.executable, "-c", "print('done')")},
        )
        rendered = runner.run("run_test")
        self.assertIn("[exit 0]", rendered)
        self.assertIn("done", rendered)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
