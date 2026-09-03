"""Host Projection and least-privilege Host API invariants for Self-Extension.

These tests cover the gap found by the real Dart CI path: a binding is staged
below ``flutter/`` but installed beside ``capability_impl.dart``.  The sandbox may
accept that import only when the exact declared product projection makes it real.
It must not turn this into a general nested-to-root import escape.

They also freeze the generated-extension Host API: renderer/runtime internals stay
outside the Dart package allow-list, while reserved declarative metadata is parsed
and verified but never installed as executable host source.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from forge_ai.core.orchestration.build_time_extension import (
    BuildTimeCapabilityArtifact,
    BuildTimeSourceFile,
)
from forge_ai.core.orchestration.build_time_host_projection import (
    BUILD_TIME_METADATA_PATHS,
    BuildTimeHostProjection,
    HostProjectionError,
)
from forge_ai.core.orchestration.build_time_sandbox import (
    BuildTimeSandboxPolicy,
    SandboxPolicyViolation,
)
from forge_ai.core.orchestration.flutter_capability_installer import (
    INSTALL_ROOT,
    FlutterCapabilityInstaller,
    InstallationError,
)
from forge_ai.core.orchestration.synthesizing_build_time_implementer import (
    VerifiedCapabilityArtifact,
)


HARNESS = frozenset({"capability_test.dart", "probe.dart"})
PROJECTION = BuildTimeHostProjection(
    host_prefix="flutter/",
    excluded_paths=HARNESS,
)


def _artifact(
    *,
    binding: str = "import 'capability_impl.dart';\nconst capability = 0;\n",
    extra_files: tuple[BuildTimeSourceFile, ...] = (),
) -> BuildTimeCapabilityArtifact:
    return BuildTimeCapabilityArtifact(
        capability_id="view.projected_probe",
        reusable_contract="Verify one projected Dart capability.",
        changed_bindings=("language", "validator", "runtime", "compiler"),
        files=(
            BuildTimeSourceFile("capability_impl.dart", "int one() => 1;\n"),
            BuildTimeSourceFile("capability_test.dart", "void main() {}\n"),
            BuildTimeSourceFile("probe.dart", "void main() {}\n"),
            BuildTimeSourceFile("flutter/forge_binding.dart", binding),
            *extra_files,
        ),
    )


def _verified(artifact: BuildTimeCapabilityArtifact) -> VerifiedCapabilityArtifact:
    return VerifiedCapabilityArtifact(
        artifact=artifact,
        source_digest=artifact.source_digest,
        build_id="build-projection-test",
        runtime_fingerprint="runtime-projection-test",
    )


def _contribution(capability_id: str = "view.projected_probe") -> BuildTimeSourceFile:
    return BuildTimeSourceFile(
        "capability_contribution.json",
        json.dumps(
            {
                "capability_id": capability_id,
                "widget_type": "projected_probe_view",
                "widget_id": "projected_probe",
                "document_version": "1.16",
                "properties": [["state_ref", "records"]],
            }
        ),
    )


def test_projection_matches_the_actual_flutter_install_layout() -> None:
    assert PROJECTION.project("capability_impl.dart") == "capability_impl.dart"
    assert PROJECTION.project("flutter/forge_binding.dart") == "forge_binding.dart"
    assert PROJECTION.project("capability_test.dart") is None
    assert PROJECTION.project("probe.dart") is None


def test_projected_relative_import_is_accepted_only_with_declared_projection() -> None:
    artifact = _artifact()
    policy = BuildTimeSandboxPolicy()

    policy.validate_artifact(artifact, host_projection=PROJECTION)
    with pytest.raises(SandboxPolicyViolation, match="declared host projection"):
        policy.validate_artifact(artifact)


def test_projection_does_not_make_parent_traversal_legal() -> None:
    artifact = _artifact(binding="import '../capability_impl.dart';\nconst capability = 0;\n")

    with pytest.raises(SandboxPolicyViolation, match="escapes artifact"):
        BuildTimeSandboxPolicy().validate_artifact(
            artifact,
            host_projection=PROJECTION,
        )


def test_projected_host_source_cannot_import_a_harness_only_file() -> None:
    artifact = _artifact(binding="import 'capability_test.dart';\nconst capability = 0;\n")

    with pytest.raises(SandboxPolicyViolation, match="declared host projection"):
        BuildTimeSandboxPolicy().validate_artifact(
            artifact,
            host_projection=PROJECTION,
        )


def test_two_sources_may_not_collapse_onto_one_host_path() -> None:
    projection = BuildTimeHostProjection(host_prefix="flutter/")

    with pytest.raises(HostProjectionError, match="collision"):
        projection.projected_paths(("foo.dart", "flutter/foo.dart"))


def test_sandbox_attestation_changes_when_host_projection_changes(tmp_path: Path) -> None:
    policy = BuildTimeSandboxPolicy()
    identity = BuildTimeHostProjection()

    assert policy.effective_policy_digest(identity) != policy.effective_policy_digest(PROJECTION)
    evidence = policy.preflight(
        _artifact(),
        (),
        workspace=tmp_path,
        host_projection=PROJECTION,
    )
    assert evidence.host_projection_digest == PROJECTION.digest
    assert evidence.policy_digest == policy.effective_policy_digest(PROJECTION)


def test_installer_rejects_projection_collision_before_writing(tmp_path: Path) -> None:
    (tmp_path / INSTALL_ROOT).mkdir(parents=True)
    artifact = BuildTimeCapabilityArtifact(
        capability_id="view.projected_collision",
        reusable_contract="Collision must never reach product source.",
        changed_bindings=("language", "validator", "runtime", "compiler"),
        files=(
            BuildTimeSourceFile("capability_impl.dart", "int safe() => 1;\n"),
            BuildTimeSourceFile("flutter/capability_impl.dart", "int unsafe() => 2;\n"),
            BuildTimeSourceFile("capability_test.dart", "void main() {}\n"),
            BuildTimeSourceFile("probe.dart", "void main() {}\n"),
            BuildTimeSourceFile("flutter/forge_binding.dart", "const capability = 0;\n"),
        ),
    )
    installer = FlutterCapabilityInstaller(
        frontend_root=tmp_path,
        harness_files=HARNESS,
        host_prefix="flutter/",
    )

    with pytest.raises(InstallationError, match="collision"):
        installer.install(_verified(artifact))

    target = tmp_path / INSTALL_ROOT / "view_projected_collision"
    assert not target.exists()


def test_runtime_and_document_internals_are_not_generated_extension_host_api() -> None:
    artifact = _artifact(
        binding=(
            "import 'package:forge_app/json_ui/renderer/forge_runtime_state.dart';\n"
            "const capability = 0;\n"
        ),
    )
    with pytest.raises(SandboxPolicyViolation, match="not allow-listed"):
        BuildTimeSandboxPolicy().validate_artifact(
            artifact,
            host_projection=PROJECTION,
        )


def test_reserved_metadata_is_verified_but_not_projected_into_host_source() -> None:
    assert "capability_contribution.json" in BUILD_TIME_METADATA_PATHS
    artifact = _artifact(extra_files=(_contribution(),))

    BuildTimeSandboxPolicy().validate_artifact(
        artifact,
        host_projection=PROJECTION,
    )
    assert PROJECTION.project("capability_contribution.json") is None


def test_invalid_reserved_metadata_fails_closed() -> None:
    artifact = _artifact(
        extra_files=(
            BuildTimeSourceFile("capability_contribution.json", "{not-json}"),
        ),
    )
    with pytest.raises(SandboxPolicyViolation, match="not valid JSON"):
        BuildTimeSandboxPolicy().validate_artifact(
            artifact,
            host_projection=PROJECTION,
        )


def test_metadata_cannot_claim_a_different_capability_identity() -> None:
    artifact = _artifact(extra_files=(_contribution("view.someone_else"),))
    with pytest.raises(SandboxPolicyViolation, match="identity mismatch"):
        BuildTimeSandboxPolicy().validate_artifact(
            artifact,
            host_projection=PROJECTION,
        )


def test_unknown_generated_file_format_is_still_rejected() -> None:
    artifact = _artifact(
        extra_files=(BuildTimeSourceFile("notes.yaml", "capability: nope\n"),),
    )
    with pytest.raises(SandboxPolicyViolation, match="no parser"):
        BuildTimeSandboxPolicy().validate_artifact(
            artifact,
            host_projection=PROJECTION,
        )
