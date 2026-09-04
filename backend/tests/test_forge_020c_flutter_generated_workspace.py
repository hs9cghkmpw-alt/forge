"""FORGE-020C — generated Flutter evidence must execute the generated artifact shell."""

from __future__ import annotations

import json
import os
import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from app.ai.agent.generated_workspace import GeneratedWorkspaceError  # noqa: E402
from app.ai.agent.flutter_generated_workspace import (  # noqa: E402
    materialize_flutter_generated_workspace,
)


class TestFlutterGeneratedWorkspace(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = pathlib.Path(tempfile.mkdtemp())
        self.template = self.temp / "template"
        (self.template / "lib" / "json_ui" / "renderer").mkdir(parents=True)
        (self.template / "assets").mkdir()
        (self.template / "lib" / "main.dart").write_text("old main", encoding="utf-8")
        (self.template / "lib" / "json_ui" / "renderer" / "forge_renderer.dart").write_text(
            "class ForgeDocumentView {}\n", encoding="utf-8"
        )
        (self.template / "pubspec.yaml").write_text(
            "name: forge_app\nflutter:\n  assets:\n    - assets/logo.png\n",
            encoding="utf-8",
        )
        (self.template / "assets" / "logo.png").write_bytes(b"\x89PNG\r\n")
        (self.template / "build").mkdir()
        (self.template / "build" / "stale.txt").write_text("stale", encoding="utf-8")
        (self.template / ".env.local").write_text("SECRET=x", encoding="utf-8")
        self.document = {
            "version": "1.0",
            "initial_screen_id": "home",
            "screens": [{"id": "home", "type": "screen", "children": []}],
        }

    def test_materializes_runtime_shell_and_exact_document(self) -> None:
        root = self.temp / "generated"
        workspace = materialize_flutter_generated_workspace(
            root=root,
            runtime_template_root=self.template,
            forge_document=self.document,
        )
        self.assertEqual(workspace.root, root.resolve())
        embedded = json.loads((root / "assets" / "forge_document.json").read_text(encoding="utf-8"))
        self.assertEqual(embedded, self.document)
        launcher = (root / "lib" / "main.dart").read_text(encoding="utf-8")
        self.assertIn("ForgeDocumentView", launcher)
        self.assertIn("assets/forge_document.json", launcher)
        pubspec = (root / "pubspec.yaml").read_text(encoding="utf-8")
        self.assertIn("assets/forge_document.json", pubspec)

    def test_binary_runtime_assets_are_preserved(self) -> None:
        root = self.temp / "generated"
        materialize_flutter_generated_workspace(
            root=root,
            runtime_template_root=self.template,
            forge_document=self.document,
        )
        self.assertEqual((root / "assets" / "logo.png").read_bytes(), b"\x89PNG\r\n")

    def test_build_outputs_and_secret_files_are_not_snapshotted(self) -> None:
        root = self.temp / "generated"
        materialize_flutter_generated_workspace(
            root=root,
            runtime_template_root=self.template,
            forge_document=self.document,
        )
        self.assertFalse((root / "build").exists())
        self.assertFalse((root / ".env.local").exists())

    def test_crlf_pubspec_is_supported_and_preserved(self) -> None:
        """Windows CRLF must not make a valid Flutter assets section disappear."""
        (self.template / "pubspec.yaml").write_bytes(
            b"name: forge_app\r\nflutter:\r\n  assets:\r\n    - assets/logo.png\r\n"
        )
        root = self.temp / "generated"
        materialize_flutter_generated_workspace(
            root=root,
            runtime_template_root=self.template,
            forge_document=self.document,
        )
        pubspec = (root / "pubspec.yaml").read_bytes()
        self.assertIn(
            b"  assets:\r\n    - assets/forge_document.json\r\n",
            pubspec,
        )

    def test_incomplete_template_fails_closed(self) -> None:
        bad = self.temp / "bad"
        bad.mkdir()
        (bad / "pubspec.yaml").write_text("name: x\n", encoding="utf-8")
        with self.assertRaises(GeneratedWorkspaceError):
            materialize_flutter_generated_workspace(
                root=self.temp / "generated",
                runtime_template_root=bad,
                forge_document=self.document,
            )

    def test_existing_output_root_is_still_refused(self) -> None:
        root = self.temp / "generated"
        root.mkdir()
        with self.assertRaises(GeneratedWorkspaceError):
            materialize_flutter_generated_workspace(
                root=root,
                runtime_template_root=self.template,
                forge_document=self.document,
            )


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
