"""FORGE-020C — materialize a real Flutter runtime shell around one Forge Document.

This snapshots the checked-in Flutter runtime into a fresh generated-artifact
workspace, replaces the app entrypoint with a tiny document launcher, and embeds the
exact Forge Document as an asset. Build/test commands can then run from that isolated
workspace without mistaking Forge's own repository build for generated-app evidence.
"""

from __future__ import annotations

import json
import pathlib
from collections.abc import Mapping

from app.ai.agent.generated_workspace import (
    GeneratedFileContent,
    GeneratedWorkspace,
    GeneratedWorkspaceError,
    materialize_generated_workspace,
)

__all__ = ["materialize_flutter_generated_workspace"]

_EXCLUDED_PARTS = {
    ".dart_tool",
    ".git",
    ".idea",
    "build",
}

_LAUNCHER = """import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart' show rootBundle;

import 'json_ui/renderer/forge_renderer.dart';

void main() {
  runApp(const GeneratedForgeApp());
}

class GeneratedForgeApp extends StatelessWidget {
  const GeneratedForgeApp({super.key});

  Future<Map<String, dynamic>> _loadDocument() async {
    final raw = await rootBundle.loadString('assets/forge_document.json');
    return jsonDecode(raw) as Map<String, dynamic>;
  }

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      debugShowCheckedModeBanner: false,
      home: FutureBuilder<Map<String, dynamic>>(
        future: _loadDocument(),
        builder: (context, snapshot) {
          if (snapshot.hasError) {
            return const Scaffold(body: Center(child: Text('Generated app failed to load')));
          }
          if (!snapshot.hasData) {
            return const Scaffold(body: Center(child: CircularProgressIndicator()));
          }
          return Scaffold(body: SafeArea(child: ForgeDocumentView(rawJson: snapshot.data!)));
        },
      ),
    );
  }
}
"""


def _snapshot_runtime(template_root: pathlib.Path) -> dict[str, GeneratedFileContent]:
    template_root = template_root.resolve()
    if not template_root.is_dir():
        raise GeneratedWorkspaceError("Flutter runtime template root is missing")
    required = (
        template_root / "pubspec.yaml",
        template_root / "lib" / "json_ui" / "renderer" / "forge_renderer.dart",
    )
    if any(not path.is_file() for path in required):
        raise GeneratedWorkspaceError("Flutter runtime template is incomplete")

    files: dict[str, GeneratedFileContent] = {}
    for candidate in sorted(template_root.rglob("*")):
        if not candidate.is_file():
            continue
        relative = candidate.relative_to(template_root)
        if any(part in _EXCLUDED_PARTS or part.startswith(".env") for part in relative.parts):
            continue
        files[relative.as_posix()] = candidate.read_bytes()
    return files


def _with_document_asset(pubspec: bytes) -> bytes:
    try:
        text = pubspec.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise GeneratedWorkspaceError("pubspec.yaml is not UTF-8") from exc
    asset_line = "    - assets/forge_document.json"
    if asset_line in text:
        return pubspec
    marker = "  assets:\n"
    if marker not in text:
        raise GeneratedWorkspaceError("Flutter runtime pubspec has no assets section")
    return text.replace(marker, marker + asset_line + "\n", 1).encode("utf-8")


def materialize_flutter_generated_workspace(
    *,
    root: pathlib.Path,
    runtime_template_root: pathlib.Path,
    forge_document: Mapping[str, object],
) -> GeneratedWorkspace:
    """Create a buildable generated Flutter app tied to exactly one Forge Document."""
    files = _snapshot_runtime(runtime_template_root)
    files["lib/main.dart"] = _LAUNCHER
    files["assets/forge_document.json"] = json.dumps(
        forge_document,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    files["pubspec.yaml"] = _with_document_asset(files["pubspec.yaml"])
    return materialize_generated_workspace(
        root=root,
        forge_document=forge_document,
        generated_files=files,
    )
