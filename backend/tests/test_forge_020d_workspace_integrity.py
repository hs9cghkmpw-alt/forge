from __future__ import annotations

import json
import pathlib
import sys

import pytest

from app.ai.agent.generated_verification import GeneratedWorkspaceVerifier
from app.ai.agent.generated_workspace import (
    GeneratedWorkspaceError,
    materialize_generated_workspace,
)
from app.ai.learning.episode import VerificationOutcome


def _workspace(tmp_path: pathlib.Path):
    return materialize_generated_workspace(
        root=tmp_path / "generated",
        forge_document={
            "version": "1.13",
            "initial_screen_id": "home",
            "screens": [{"id": "home", "title": "x", "body": {"type": "text", "id": "x", "value": "ok"}}],
        },
        generated_files={"marker.txt": "safe"},
    )


def test_materialized_workspace_verifies_its_document_and_manifest(tmp_path: pathlib.Path) -> None:
    workspace = _workspace(tmp_path)
    workspace.verify_integrity()
    assert (workspace.root / ".forge" / "document.json").is_file()


def test_canonical_document_tampering_is_rejected(tmp_path: pathlib.Path) -> None:
    workspace = _workspace(tmp_path)
    path = workspace.root / ".forge" / "document.json"
    document = json.loads(path.read_text(encoding="utf-8"))
    document["initial_screen_id"] = "tampered"
    path.write_text(json.dumps(document), encoding="utf-8")

    with pytest.raises(GeneratedWorkspaceError, match="canonical document mismatch"):
        workspace.verify_integrity()


def test_metadata_fingerprint_tampering_is_rejected(tmp_path: pathlib.Path) -> None:
    workspace = _workspace(tmp_path)
    path = workspace.root / ".forge" / "artifact.json"
    metadata = json.loads(path.read_text(encoding="utf-8"))
    metadata["artifact_fingerprint"] = "0" * 64
    path.write_text(json.dumps(metadata), encoding="utf-8")

    with pytest.raises(GeneratedWorkspaceError, match="artifact fingerprint mismatch"):
        workspace.verify_integrity()


def test_verifier_fails_closed_before_any_command_on_tampering(tmp_path: pathlib.Path) -> None:
    workspace = _workspace(tmp_path)
    (workspace.root / ".forge" / "document.json").write_text("{}", encoding="utf-8")
    touched = workspace.root / "command-ran.txt"
    command = (
        sys.executable,
        "-c",
        "from pathlib import Path; Path('command-ran.txt').write_text('yes')",
    )
    verifier = GeneratedWorkspaceVerifier(
        workspace=workspace,
        commands={"run_test": command, "run_build": command},
        timeout_seconds=5.0,
    )

    verification = verifier.verify()

    assert verification.attempt.succeeded is False
    assert verification.attempt.failure_code == "artifact_integrity_failed"
    assert verification.attempt.validator is VerificationOutcome.UNKNOWN
    assert verification.attempt.test is VerificationOutcome.UNKNOWN
    assert verification.attempt.build is VerificationOutcome.UNKNOWN
    assert not touched.exists()
