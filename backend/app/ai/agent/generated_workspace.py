"""FORGE-020C — isolated generated-artifact execution workspace.

The build/test truth for a generated artifact must come from a workspace that contains
that artifact, not from building Forge's own source tree.  This module creates a fresh,
explicit execution root and writes only caller-supplied generated files into it.

It deliberately does not know Flutter, npm, or any other build system.  A later
materializer may populate platform-specific files, but every command runner must point
at the returned workspace root.
"""

from __future__ import annotations

import hashlib
import json
import pathlib
from dataclasses import dataclass
from typing import Mapping

from app.ai.agent.sandbox import ToolSandbox

__all__ = [
    "GeneratedWorkspace",
    "GeneratedWorkspaceError",
    "materialize_generated_workspace",
]


class GeneratedWorkspaceError(ValueError):
    """The requested generated workspace violates a fail-closed boundary."""


@dataclass(frozen=True)
class GeneratedWorkspace:
    root: pathlib.Path
    artifact_fingerprint: str
    files: tuple[str, ...]

    def sandbox(self) -> ToolSandbox:
        return ToolSandbox.at(self.root)


def _normalise_relative_path(raw: str) -> pathlib.PurePosixPath:
    path = pathlib.PurePosixPath(raw.replace("\\", "/"))
    if not raw or path.is_absolute() or ".." in path.parts:
        raise GeneratedWorkspaceError(f"unsafe generated path: {raw!r}")
    if any(part in {"", "."} for part in path.parts):
        raise GeneratedWorkspaceError(f"ambiguous generated path: {raw!r}")
    if path.parts[0] in {".git", ".env"} or any(
        part.startswith(".env") for part in path.parts
    ):
        raise GeneratedWorkspaceError(f"denied generated path: {raw!r}")
    return path


def _fingerprint(document: Mapping[str, object]) -> str:
    canonical = json.dumps(
        document,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def materialize_generated_workspace(
    *,
    root: pathlib.Path,
    forge_document: Mapping[str, object],
    generated_files: Mapping[str, str],
) -> GeneratedWorkspace:
    """Create one clean workspace that is cryptographically tied to the artifact.

    `root` must not already exist.  Refusing reuse prevents stale files from a previous
    generation from making a broken artifact appear to build successfully.
    """
    root = root.resolve()
    if root.exists():
        raise GeneratedWorkspaceError("generated workspace root already exists")

    normalised: list[tuple[pathlib.PurePosixPath, str]] = []
    seen: set[str] = set()
    for raw_path, content in generated_files.items():
        path = _normalise_relative_path(raw_path)
        key = path.as_posix()
        if key in seen:
            raise GeneratedWorkspaceError(f"duplicate generated path: {key}")
        seen.add(key)
        normalised.append((path, content))

    if not normalised:
        raise GeneratedWorkspaceError("generated workspace cannot be empty")

    root.mkdir(parents=True, exist_ok=False)
    try:
        for relative, content in sorted(normalised, key=lambda item: item[0].as_posix()):
            target = root.joinpath(*relative.parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")

        fingerprint = _fingerprint(forge_document)
        metadata_dir = root / ".forge"
        metadata_dir.mkdir()
        (metadata_dir / "artifact.json").write_text(
            json.dumps(
                {
                    "artifact_fingerprint": fingerprint,
                    "files": sorted(seen),
                },
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ),
            encoding="utf-8",
        )
    except Exception:
        # Do not leave a half-materialized workspace that could accidentally be run.
        import shutil

        shutil.rmtree(root, ignore_errors=True)
        raise

    return GeneratedWorkspace(
        root=root,
        artifact_fingerprint=fingerprint,
        files=tuple(sorted(seen)),
    )
