from __future__ import annotations

import sys
from dataclasses import replace

import pytest

from forge_ai.core.orchestration.build_time_extension import (
    BuildTimeCapabilityArtifact,
    BuildTimeExtensionError,
    BuildTimeSourceFile,
    implement_build_time_extension,
)
from forge_ai.core.orchestration.build_time_workspace import BuildCommand, ManagedBuildWorkspaceRunner
from forge_ai.core.orchestration.extension_manifest import create_extension_manifest
from forge_ai.core.orchestration.extension_plan import ExtensionCandidate, ExtensionRoute
from forge_ai.core.orchestration.managed_build_time_implementer import ManagedBuildTimeImplementer
from forge_ai.core.semantics.capabilities import SafetyClass, SupportLevel


def _candidate() -> ExtensionCandidate:
    return ExtensionCandidate(
        capability_id="view.synthetic_probe",
        label_ja="検証用表示",
        support=SupportLevel.MISSING,
        safety=SafetyClass.SAFE,
        routes=(ExtensionRoute.BUILD_TIME,),
        reason="test concrete managed build bridge",
        requires_confirmation=False,
    )


def _artifact(*, probe_exit: int = 0) -> BuildTimeCapabilityArtifact:
    probe_tail = (
        "print('runtime-probe-pass')\n"
        if probe_exit == 0
        else f"raise SystemExit({probe_exit})\n"
    )
    return BuildTimeCapabilityArtifact(
        capability_id="view.synthetic_probe",
        files=(
            BuildTimeSourceFile(
                path="capability.py",
                content=(
                    "def render(value: int) -> str:\n"
                    "    return f'probe:{value}'\n"
                ),
            ),
            BuildTimeSourceFile(
                path="capability_test.py",
                content=(
                    "from capability import render\n"
                    "assert render(2) == 'probe:2'\n"
                    "print('test-pass')\n"
                ),
            ),
            BuildTimeSourceFile(
                path="verify.py",
                content=(
                    "from capability import render\n"
                    "assert render(7) == 'probe:7'\n"
                    + probe_tail
                ),
            ),
        ),
        reusable_contract="render(int) -> deterministic probe string",
        changed_bindings=("language", "validator", "runtime", "compiler"),
    )


def _commands() -> tuple[BuildCommand, ...]:
    return (
        BuildCommand("test", (sys.executable, "capability_test.py")),
        BuildCommand("build", (sys.executable, "-m", "compileall", "-q", ".")),
        BuildCommand("runtime_probe", (sys.executable, "verify.py")),
    )


def test_real_managed_commands_can_promote_and_activate_exact_build(tmp_path) -> None:
    manifest = create_extension_manifest(_candidate(), ExtensionRoute.BUILD_TIME)
    bridge = ManagedBuildTimeImplementer(
        capability_id="view.synthetic_probe",
        commands=_commands(),
        runner=ManagedBuildWorkspaceRunner(root=tmp_path),
    )

    implementation = implement_build_time_extension(
        manifest,
        _artifact(),
        builder=bridge.build,
        load_runtime=bridge.load_runtime,
    )

    assert implementation.manifest.status.value == "promoted"
    assert implementation.activation is not None
    assert implementation.activation.loaded is True
    assert implementation.activation.capability_id == "view.synthetic_probe"
    evidence = bridge.last_execution
    assert evidence is not None
    assert evidence.evidence.passed("test")
    assert evidence.evidence.passed("build")
    assert evidence.evidence.passed("runtime_probe")
    assert evidence.evidence.sandbox_preflight_pass
    assert "runtime-probe-pass" in evidence.evidence.commands[-1].stdout


def test_loader_rejects_build_metadata_not_produced_by_exact_execution(tmp_path) -> None:
    bridge = ManagedBuildTimeImplementer(
        capability_id="view.synthetic_probe",
        commands=_commands(),
        runner=ManagedBuildWorkspaceRunner(root=tmp_path),
    )
    build = bridge.build(_artifact())
    forged = replace(build, build_id="other-build")

    with pytest.raises(BuildTimeExtensionError, match="exact managed build"):
        bridge.load_runtime(forged)


def test_failed_runtime_probe_never_becomes_loaded_activation(tmp_path) -> None:
    bridge = ManagedBuildTimeImplementer(
        capability_id="view.synthetic_probe",
        commands=_commands(),
        runner=ManagedBuildWorkspaceRunner(root=tmp_path),
    )
    manifest = create_extension_manifest(_candidate(), ExtensionRoute.BUILD_TIME)

    implementation = implement_build_time_extension(
        manifest,
        _artifact(probe_exit=9),
        builder=bridge.build,
        load_runtime=bridge.load_runtime,
    )

    assert implementation.manifest.status.value == "implementing"
    assert implementation.activation is None
    execution = bridge.last_execution
    assert execution is not None
    assert execution.evidence.passed("test")
    assert execution.evidence.passed("build")
    assert not execution.evidence.passed("runtime_probe")
    assert execution.evidence.commands[-1].exit_code == 9
