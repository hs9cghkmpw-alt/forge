"""FORGE-020C — generated execution workspaces are isolated and fail closed."""

from __future__ import annotations

import json
import os
import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from app.ai.agent.generated_workspace import (  # noqa: E402
    GeneratedWorkspaceError,
    materialize_generated_workspace,
)
from app.ai.agent.toolset import CommandRunner  # noqa: E402


class TestGeneratedExecutionWorkspace(unittest.TestCase):
    def setUp(self) -> None:
        self.parent = pathlib.Path(tempfile.mkdtemp())
        self.root = self.parent / "generated"
        self.document = {"version": "1.0", "screens": [{"id": "home"}]}

    def _materialize(self, files: dict[str, str] | None = None):
        return materialize_generated_workspace(
            root=self.root,
            forge_document=self.document,
            generated_files=files or {"app/main.txt": "generated\n"},
        )

    def test_workspace_contains_only_generated_files_plus_forge_metadata(self) -> None:
        workspace = self._materialize()
        self.assertEqual(workspace.files, ("app/main.txt",))
        self.assertEqual((workspace.root / "app/main.txt").read_text(), "generated\n")
        metadata = json.loads((workspace.root / ".forge/artifact.json").read_text())
        self.assertEqual(metadata["artifact_fingerprint"], workspace.artifact_fingerprint)
        self.assertEqual(metadata["files"], ["app/main.txt"])

    def test_fingerprint_is_stable_for_equivalent_document_order(self) -> None:
        first = self._materialize()
        second_root = self.parent / "generated-2"
        second = materialize_generated_workspace(
            root=second_root,
            forge_document={"screens": [{"id": "home"}], "version": "1.0"},
            generated_files={"app/main.txt": "generated\n"},
        )
        self.assertEqual(first.artifact_fingerprint, second.artifact_fingerprint)

    def test_existing_root_is_refused_to_prevent_stale_success(self) -> None:
        self.root.mkdir()
        (self.root / "stale.txt").write_text("old", encoding="utf-8")
        with self.assertRaises(GeneratedWorkspaceError):
            self._materialize()

    def test_path_traversal_and_sensitive_paths_are_refused(self) -> None:
        for path in ("../escape", "/absolute", ".env", ".env.local", ".git/config"):
            with self.subTest(path=path):
                root = self.parent / ("case-" + str(abs(hash(path))))
                with self.assertRaises(GeneratedWorkspaceError):
                    materialize_generated_workspace(
                        root=root,
                        forge_document=self.document,
                        generated_files={path: "x"},
                    )
                self.assertFalse(root.exists())

    def test_empty_workspace_is_refused(self) -> None:
        with self.assertRaises(GeneratedWorkspaceError):
            materialize_generated_workspace(
                root=self.root,
                forge_document=self.document,
                generated_files={},
            )

    def test_command_runner_executes_inside_generated_workspace_not_forge_repo(self) -> None:
        workspace = self._materialize({"marker.txt": "artifact-marker"})
        runner = CommandRunner(
            sandbox=workspace.sandbox(),
            commands={
                "run_test": (
                    sys.executable,
                    "-c",
                    "from pathlib import Path; print(Path('marker.txt').read_text())",
                )
            },
        )
        observed = runner.observe("run_test")
        self.assertTrue(observed.passed)
        self.assertIn("artifact-marker", observed.output)
        self.assertEqual(runner.sandbox.root, workspace.root)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
