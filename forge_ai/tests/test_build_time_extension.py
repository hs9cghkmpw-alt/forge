from __future__ import annotations

from dataclasses import replace

import pytest

from forge_ai.core.orchestration.build_time_extension import (
    BuildTimeBuildResult,
    BuildTimeCapabilityArtifact,
    BuildTimeExtensionError,
    BuildTimeSourceFile,
    LoadedBuildActivation,
    implement_build_time_extension,
)
from forge_ai.core.orchestration.extension_manifest import create_extension_manifest
from forge_ai.core.orchestration.extension_plan import ExtensionCandidate, ExtensionRoute
from forge_ai.core.semantics.capabilities import SafetyClass, SupportLevel


def _candidate() -> ExtensionCandidate:
    return ExtensionCandidate(
        capability_id="view.map",
        label_ja="地図で見る",
        support=SupportLevel.MISSING,
        safety=SafetyClass.SAFE,
        routes=(ExtensionRoute.BUILD_TIME,),
        reason="missing runtime primitive",
        requires_confirmation=False,
    )


def _artifact() -> BuildTimeCapabilityArtifact:
    return BuildTimeCapabilityArtifact(
        capability_id="view.map",
        files=(
            BuildTimeSourceFile("frontend/lib/json_ui/widgets/map_view.dart", "class MapView {}"),
            BuildTimeSourceFile("forge_ai/core/ir/map_binding.py", "MAP_WIDGET = 'map_view'"),
        ),
        reusable_contract="Render coordinate-bearing records using a reusable map primitive.",
        changed_bindings=("language", "validator", "runtime", "compiler"),
    )


def _builder(artifact: BuildTimeCapabilityArtifact) -> BuildTimeBuildResult:
    return BuildTimeBuildResult(
        build_id="build-123",
        source_digest=artifact.source_digest,
        runtime_fingerprint="runtime-abc",
        tests_pass=True,
        build_pass=True,
        runtime_evidence=True,
        sandbox_preflight=True,
        sandbox_policy_version="test-policy-v1",
        sandbox_policy_digest="a" * 64,
    )


def _loader(build: BuildTimeBuildResult) -> LoadedBuildActivation:
    return LoadedBuildActivation(
        capability_id="view.map",
        build_id=build.build_id,
        runtime_fingerprint=build.runtime_fingerprint,
        source_digest=build.source_digest,
    )


def test_build_time_extension_promotes_only_after_exact_build_is_loaded() -> None:
    manifest = create_extension_manifest(_candidate(), ExtensionRoute.BUILD_TIME)
    result = implement_build_time_extension(
        manifest,
        _artifact(),
        builder=_builder,
        load_runtime=_loader,
    )

    assert result.manifest.status.value == "promoted"
    assert result.activation is not None
    assert result.activation.build_id == "build-123"
    assert result.activation.runtime_fingerprint == "runtime-abc"


def test_build_time_extension_without_sandbox_attestation_never_promotes() -> None:
    manifest = create_extension_manifest(_candidate(), ExtensionRoute.BUILD_TIME)

    def unsandboxed_builder(artifact: BuildTimeCapabilityArtifact) -> BuildTimeBuildResult:
        return replace(
            _builder(artifact),
            sandbox_preflight=False,
            sandbox_policy_version="",
            sandbox_policy_digest="",
        )

    result = implement_build_time_extension(
        manifest,
        _artifact(),
        builder=unsandboxed_builder,
        load_runtime=lambda build: pytest.fail("loader must not run without sandbox evidence"),
    )

    assert result.manifest.status.value == "implementing"
    assert result.activation is None
    assert result.manifest.promotion_blockers() == ("sandbox_preflight",)


def test_sandbox_pass_without_policy_identity_is_rejected_as_inconsistent() -> None:
    manifest = create_extension_manifest(_candidate(), ExtensionRoute.BUILD_TIME)

    def inconsistent_builder(artifact: BuildTimeCapabilityArtifact) -> BuildTimeBuildResult:
        return replace(_builder(artifact), sandbox_policy_digest="")

    with pytest.raises(BuildTimeExtensionError, match="policy version and digest"):
        implement_build_time_extension(
            manifest,
            _artifact(),
            builder=inconsistent_builder,
            load_runtime=_loader,
        )


def test_build_failure_never_produces_activation_or_promotion() -> None:
    manifest = create_extension_manifest(_candidate(), ExtensionRoute.BUILD_TIME)

    def failed_builder(artifact: BuildTimeCapabilityArtifact) -> BuildTimeBuildResult:
        return replace(_builder(artifact), build_pass=False, runtime_evidence=False)

    result = implement_build_time_extension(
        manifest,
        _artifact(),
        builder=failed_builder,
        load_runtime=lambda build: pytest.fail("loader must not run for failed build"),
    )

    assert result.manifest.status.value == "implementing"
    assert result.activation is None
    assert "build_pass" in result.manifest.promotion_blockers()
    assert "runtime_evidence" in result.manifest.promotion_blockers()


def test_loaded_runtime_fingerprint_must_match_verified_build() -> None:
    manifest = create_extension_manifest(_candidate(), ExtensionRoute.BUILD_TIME)

    def wrong_loader(build: BuildTimeBuildResult) -> LoadedBuildActivation:
        return replace(_loader(build), runtime_fingerprint="different-runtime")

    with pytest.raises(BuildTimeExtensionError, match="runtime fingerprint"):
        implement_build_time_extension(
            manifest,
            _artifact(),
            builder=_builder,
            load_runtime=wrong_loader,
        )


def test_generated_source_cannot_escape_managed_workspace() -> None:
    artifact = replace(
        _artifact(),
        files=(BuildTimeSourceFile("../../outside.py", "pwn = True"),),
    )
    with pytest.raises(BuildTimeExtensionError, match="unsafe generated source path"):
        artifact.validate()


def test_all_binding_targets_are_required() -> None:
    artifact = replace(_artifact(), changed_bindings=("runtime", "compiler"))
    with pytest.raises(BuildTimeExtensionError, match="required binding targets"):
        artifact.validate()