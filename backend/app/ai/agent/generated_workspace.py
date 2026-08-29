"""FORGE-020C/020D — isolated generated-artifact execution workspace.

The build/test truth for a generated artifact must come from a workspace that contains
that artifact, not from building Forge's own source tree. This module creates a fresh,
explicit execution root and writes only caller-supplied generated files into it.

Generated files may be UTF-8 text or opaque bytes. Binary support is required for
runtime templates that include images/fonts, but the same path boundary is applied to
both forms.

020D additionally makes the artifact/document binding executable rather than merely
recorded: every workspace carries a canonical `.forge/document.json` plus metadata,
and verification can fail closed if either is changed before commands run.
"""

from __future__ import annotations

import hashlib
import json
import pathlib
from dataclasses import dataclass
from typing import Mapping

from app.ai.agent.sandbox import ToolSandbox

__all__ = [
    "GeneratedFileContent",
    "GeneratedWorkspace",
    "GeneratedWorkspaceError",
    "materialize_generated_workspace",
]

GeneratedFileContent = str | bytes


class GeneratedWorkspaceError(ValueError):
    """The requested generated workspace violates a fail-closed boundary."""


@dataclass(frozen=True)
class GeneratedWorkspace:
    root: pathlib.Path
    artifact_fingerprint: str
    files: tuple[str, ...]

    def sandbox(self) -> ToolSandbox:
        return ToolSandbox.at(self.root)

    def verify_integrity(self) -> None:
        """Verify materialized metadata/document still match this workspace object."""
        metadata_path = self.root / ".forge" / "artifact.json"
        document_path = self.root / ".forge" / "document.json"
        try:
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            document = json.loads(document_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise GeneratedWorkspaceError(
                "generated workspace integrity metadata unreadable"
            ) from exc

        if not isinstance(metadata, dict) or not isinstance(document, dict):
            raise GeneratedWorkspaceError("generated workspace integrity metadata malformed")
        if metadata.get("artifact_fingerprint") != self.artifact_fingerprint:
            raise GeneratedWorkspaceError("generated workspace artifact fingerprint mismatch")
        if metadata.get("files") != list(self.files):
            raise GeneratedWorkspaceError("generated workspace file manifest mismatch")
        if _fingerprint(document) != self.artifact_fingerprint:
            raise GeneratedWorkspaceError("generated workspace canonical document mismatch")


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


def _canonical_document(document: Mapping[str, object]) -> str:
    return json.dumps(
        document,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _fingerprint(document: Mapping[str, object]) -> str:
    return hashlib.sha256(_canonical_document(document).encode("utf-8")).hexdigest()


def materialize_generated_workspace(
    *,
    root: pathlib.Path,
    forge_document: Mapping[str, object],
    generated_files: Mapping[str, GeneratedFileContent],
) -> GeneratedWorkspace:
    """Create one clean workspace that is cryptographically tied to the artifact.

    `root` must not already exist. Refusing reuse prevents stale files from a previous
    generation from making a broken artifact appear to build successfully.
    """
    root = root.resolve()
    if root.exists():
        raise GeneratedWorkspaceError("generated workspace root already exists")

    normalised: list[tuple[pathlib.PurePosixPath, GeneratedFileContent]] = []
    seen: set[str] = set()
    for raw_path, content in generated_files.items():
        if not isinstance(content, (str, bytes)):
            raise GeneratedWorkspaceError(
                f"unsupported generated content type for {raw_path!r}"
            )
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
            if isinstance(content, bytes):
                target.write_bytes(content)
            else:
                target.write_text(content, encoding="utf-8")

        fingerprint = _fingerprint(forge_document)
        metadata_dir = root / ".forge"
        metadata_dir.mkdir()
        (metadata_dir / "document.json").write_text(
            _canonical_document(forge_document), encoding="utf-8"
        )
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

    workspace = GeneratedWorkspace(
        root=root,
        artifact_fingerprint=fingerprint,
        files=tuple(sorted(seen)),
    )
    workspace.verify_integrity()
    return workspace
