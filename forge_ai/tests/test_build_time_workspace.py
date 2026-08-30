from __future__ import annotations

from pathlib import Path
import sys

from forge_ai.core.orchestration.build_time_extension import (
    BuildTimeCapabilityArtifact,
    BuildTimeSourceFile,
)
from forge_ai.core.orchestration.build_time_workspace import (
    BuildCommand,
    ManagedBuildWorkspaceRunner,
)


def _artifact() -> BuildTimeCapabilityArtifact:
    return BuildTimeCapabilityArtifact(
        capability_id="view.unseen_probe",
        reusable_contract="Render a generic verified probe view from declarative input.",
        changed_bindings=("language", "validator", "runtime", "compiler"),
        files=(
            BuildTimeSourceFile("language_binding.py", "VIEW_TYPE = 'unseen_probe'\n"),
            BuildTimeSourceFile("validator_binding.py", "def valid(value): return isinstance(value, dict)\n"),
            BuildTimeSourceFile("runtime_binding.py", "def render(value): return 'probe:' + str(value['label'])\n"),
            BuildTimeSourceFile("compiler_binding.py", "def compile_view(label): return {'label': label}\n"),
            BuildTimeSourceFile(
                "test_extension.py",
                "from compiler_binding import compile_view\n"
                "from validator_binding import valid\n"
                "assert valid(compile_view('A'))\n",
            ),
            BuildTimeSourceFile(
                "runtime_probe.py",
                "from compiler_binding import compile_view\n"
                "from runtime_binding import render\n"
                "assert render(compile_view('E2E')) == 'probe:E2E'\n"
                "print('FORGE_UNSEEN_EXTENSION_RUNTIME=PASS')\n",
            ),
        ),
    )


def _commands() -> tuple[BuildCommand, ...]:
    return (
        BuildCommand("test", (sys.executable, "test_extension.py")),
        BuildCommand("build", (sys.executable, "-m", "compileall", "-q", ".")),
        BuildCommand("runtime_probe", (sys.executable, "runtime_probe.py")),
    )


def test_managed_workspace_runs_real_test_build_and_runtime_probe(tmp_path: Path) -> None:
    artifact = _artifact()
    execution = ManagedBuildWorkspaceRunner(root=tmp_path).run(artifact, _commands())

    assert execution.result.source_digest == artifact.source_digest
    assert execution.result.tests_pass
    assert execution.result.build_pass
    assert execution.result.runtime_evidence
    assert execution.evidence.passed("test")
    assert execution.evidence.passed("build")
    assert execution.evidence.passed("runtime_probe")
    runtime = next(item for item in execution.evidence.commands if item.kind == "runtime_probe")
    assert "FORGE_UNSEEN_EXTENSION_RUNTIME=PASS" in runtime.stdout
    assert not any(tmp_path.iterdir())


def test_managed_workspace_stops_after_first_failed_phase(tmp_path: Path) -> None:
    artifact = _artifact()
    commands = (
        BuildCommand("test", (sys.executable, "-c", "raise SystemExit(7)")),
        BuildCommand("build", (sys.executable, "-c", "raise SystemExit(0)")),
        BuildCommand("runtime_probe", (sys.executable, "runtime_probe.py")),
    )
    execution = ManagedBuildWorkspaceRunner(root=tmp_path).run(artifact, commands)

    assert not execution.result.tests_pass
    assert not execution.result.build_pass
    assert not execution.result.runtime_evidence
    assert len(execution.evidence.commands) == 1
    assert execution.evidence.commands[0].exit_code == 7
