from __future__ import annotations

from pathlib import Path
import sys

import pytest

from forge_ai.core.sandbox import SandboxUnavailable

from forge_ai.core.orchestration.build_time_extension import (
    BuildTimeCapabilityArtifact,
    BuildTimeSourceFile,
)
from forge_ai.core.orchestration.build_time_sandbox import (
    BuildTimeSandboxPolicy,
    SandboxPolicyViolation,
)
from forge_ai.core.orchestration.build_time_workspace import (
    BuildCommand,
    ManagedBuildWorkspaceRunner,
)


def _artifact(*, test_content: str | None = None, extra_files: tuple[BuildTimeSourceFile, ...] = ()) -> BuildTimeCapabilityArtifact:
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
                test_content
                or (
                    "from compiler_binding import compile_view\n"
                    "from validator_binding import valid\n"
                    "assert valid(compile_view('A'))\n"
                ),
            ),
            BuildTimeSourceFile(
                "runtime_probe.py",
                "from compiler_binding import compile_view\n"
                "from runtime_binding import render\n"
                "assert render(compile_view('E2E')) == 'probe:E2E'\n"
                "print('FORGE_UNSEEN_EXTENSION_RUNTIME=PASS')\n",
            ),
            *extra_files,
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
    assert execution.evidence.sandbox_preflight_pass
    assert execution.evidence.sandbox_policy_digest
    assert execution.evidence.sandbox_policy_version
    runtime = next(item for item in execution.evidence.commands if item.kind == "runtime_probe")
    assert "FORGE_UNSEEN_EXTENSION_RUNTIME=PASS" in runtime.stdout
    assert not any(tmp_path.iterdir())


def test_managed_workspace_stops_after_first_failed_phase(tmp_path: Path) -> None:
    artifact = _artifact(test_content="raise SystemExit(7)\n")
    execution = ManagedBuildWorkspaceRunner(root=tmp_path).run(artifact, _commands())

    assert not execution.result.tests_pass
    assert not execution.result.build_pass
    assert not execution.result.runtime_evidence
    assert len(execution.evidence.commands) == 1
    assert execution.evidence.commands[0].exit_code == 7


def test_generated_code_actually_runs_inside_the_sandbox(tmp_path: Path) -> None:
    """**「作ったが本番から呼ばれない」を作らない**（EXT-08 / SEC-04、2026-09-04）。

    Sandbox を書いただけでは意味が無い。生成物を実際に走らせる唯一の場所
    （`ManagedBuildWorkspaceRunner._execute`）が Sandbox を通っていること
    を、Evidence 側から確かめる。

    配線破壊試験: `_execute` を素の `subprocess.run` へ戻すと、
    `sandbox_backend` が空になりこの試験が落ちる。
    """
    from forge_ai.core.sandbox import available_backend

    if available_backend() is None:
        pytest.skip("この環境に隔離 backend が無い（素通しで PASS にしない）")

    execution = ManagedBuildWorkspaceRunner(root=tmp_path).run(_artifact(), _commands())

    backends = {
        evidence.sandbox_backend
        for evidence in execution.evidence.commands
    }
    assert backends, "command evidence が空である"
    assert "" not in backends, (
        "隔離されずに走った command がある（Sandbox を通っていない）: "
        f"{[(e.kind, e.sandbox_backend) for e in execution.evidence.commands]}"
    )


def test_without_a_sandbox_nothing_runs(tmp_path: Path) -> None:
    """**隔離できないなら動かさない**（fail closed）。

    Windows / macOS で起きること。素通しで実行して「PASS」にしない。
    """
    from unittest.mock import patch

    with patch(
        "forge_ai.core.orchestration.build_time_workspace.run_in_sandbox",
        side_effect=SandboxUnavailable("backend なし"),
    ):
        execution = ManagedBuildWorkspaceRunner(root=tmp_path).run(_artifact(), _commands())

    assert not execution.result.tests_pass, "Sandbox が無いのに test が PASS している"
    assert not execution.result.build_pass, "Sandbox が無いのに build が PASS している"
    for evidence in execution.evidence.commands:
        assert evidence.sandbox_backend == ""
        assert "refused to run" in evidence.stderr


def test_host_secrets_are_not_in_the_sandbox_environment(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "never-copy-this-secret")
    monkeypatch.setenv("GEMINI_API_KEY", "never-copy-this-secret-either")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "also-secret")

    env = BuildTimeSandboxPolicy().build_environment(tmp_path)

    assert "OPENAI_API_KEY" not in env
    assert "GEMINI_API_KEY" not in env
    assert "ANTHROPIC_API_KEY" not in env
    assert env["HOME"].startswith(str(tmp_path))
    assert env["TMP"].startswith(str(tmp_path))
    assert env["PYTHONPATH"] == str(tmp_path.resolve())
    assert env["FORGE_BUILD_SANDBOX"] == "1"


def test_generated_python_cannot_import_host_io_before_any_process_runs(tmp_path: Path) -> None:
    artifact = _artifact(
        extra_files=(
            BuildTimeSourceFile(
                "escape_test.py",
                "import os\nprint(os.environ.get('OPENAI_API_KEY'))\n",
            ),
        ),
    )

    with pytest.raises(SandboxPolicyViolation, match="import 'os'|import .*os"):
        ManagedBuildWorkspaceRunner(root=tmp_path).run(artifact, _commands())

    assert not any(tmp_path.iterdir())


def test_generated_dart_cannot_import_dart_io_before_any_process_runs(tmp_path: Path) -> None:
    artifact = _artifact(
        extra_files=(
            BuildTimeSourceFile(
                "escape_probe.dart",
                "import 'dart:io';\nvoid main() {}\n",
            ),
        ),
    )

    with pytest.raises(SandboxPolicyViolation, match="dart:io"):
        ManagedBuildWorkspaceRunner(root=tmp_path).run(artifact, _commands())

    assert not any(tmp_path.iterdir())


def test_arbitrary_shell_command_is_rejected_before_execution(tmp_path: Path) -> None:
    commands = (
        BuildCommand("test", ("sh", "-c", "echo should-not-run")),
        BuildCommand("build", (sys.executable, "-m", "compileall", "-q", ".")),
        BuildCommand("runtime_probe", (sys.executable, "runtime_probe.py")),
    )

    with pytest.raises(SandboxPolicyViolation, match="executable 'sh'"):
        ManagedBuildWorkspaceRunner(root=tmp_path).run(_artifact(), commands)

    assert not any(tmp_path.iterdir())


def test_python_dash_c_is_rejected_even_with_an_allowed_executable(tmp_path: Path) -> None:
    commands = (
        BuildCommand("test", (sys.executable, "-c", "import os; print(os.environ)")),
        BuildCommand("build", (sys.executable, "-m", "compileall", "-q", ".")),
        BuildCommand("runtime_probe", (sys.executable, "runtime_probe.py")),
    )

    with pytest.raises(SandboxPolicyViolation, match="Python option '-c'"):
        ManagedBuildWorkspaceRunner(root=tmp_path).run(_artifact(), commands)

    assert not any(tmp_path.iterdir())

