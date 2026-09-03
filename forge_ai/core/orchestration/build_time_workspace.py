"""Concrete managed workspace runner for BUILD_TIME capability acquisition.

This module materializes an already-decomposed reusable BuildTimeCapabilityArtifact
into a staging directory, applies the default-deny BuildTimeSandboxPolicy before
any generated code can execute, runs an explicit allow-listed command plan, and
records the exact evidence used by the promotion gate.

The workspace alone is not called a sandbox.  The enforceable sandbox layer lives
in ``build_time_sandbox.py`` and currently provides source/effect policy, command
profiles, executable pinning, environment scrubbing, cwd pinning and timeout.
OS-level network namespaces / AppContainer / VM isolation remain separate proof.
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
import shutil
import subprocess

from forge_ai.core.sandbox import (
    SandboxPolicy,
    SandboxUnavailable,
    SandboxViolation,
    run_in_sandbox,
)
import tempfile
from typing import Iterable
from uuid import uuid4

from forge_ai.core.orchestration.build_time_extension import (
    BuildTimeBuildResult,
    BuildTimeCapabilityArtifact,
    BuildTimeExtensionError,
)
from forge_ai.core.orchestration.build_time_host_projection import (
    BuildTimeHostProjection,
)
from forge_ai.core.orchestration.build_time_sandbox import BuildTimeSandboxPolicy


@dataclass(frozen=True, slots=True)
class BuildCommand:
    """One explicit process invocation in a managed build plan."""

    kind: str
    argv: tuple[str, ...]
    timeout_seconds: float = 120.0

    def validate(self) -> None:
        if self.kind not in {"test", "build", "runtime_probe", "safety"}:
            raise BuildTimeExtensionError(f"unsupported build command kind: {self.kind!r}")
        if not self.argv or not self.argv[0].strip():
            raise BuildTimeExtensionError("build command requires non-empty argv")
        if self.timeout_seconds <= 0 or self.timeout_seconds > 900:
            raise BuildTimeExtensionError("build command timeout must be > 0 and <= 900 seconds")


@dataclass(frozen=True, slots=True)
class CommandEvidence:
    kind: str
    argv: tuple[str, ...]
    exit_code: int | None
    timed_out: bool
    stdout: str
    stderr: str

    sandbox_backend: str = ""
    """どの隔離 backend で走ったか。**空なら走っていない。**

    EXT-08 / SEC-04（2026-09-04）。生成物を「どこで動かしたか」は
    Evidence の一部である。隔離せずに動かした結果を、隔離した結果と
    同じ扱いにしない。
    """

    @property
    def passed(self) -> bool:
        return not self.timed_out and self.exit_code == 0


@dataclass(frozen=True, slots=True)
class ManagedBuildEvidence:
    build_id: str
    workspace_digest: str
    source_digest: str
    runtime_fingerprint: str
    commands: tuple[CommandEvidence, ...]
    # Empty/False means "no sandbox evidence".  Defaults preserve compatibility
    # with deliberately forged/fake evidence tests without ever treating absence
    # as a pass.
    sandbox_policy_version: str = ""
    sandbox_policy_digest: str = ""
    sandbox_preflight_pass: bool = False
    sandbox_environment_names: tuple[str, ...] = ()
    sandbox_host_projection_digest: str = ""

    def passed(self, kind: str) -> bool:
        matching = [item for item in self.commands if item.kind == kind]
        return bool(matching) and all(item.passed for item in matching)


@dataclass(frozen=True, slots=True)
class ManagedBuildExecution:
    result: BuildTimeBuildResult
    evidence: ManagedBuildEvidence


class ManagedBuildWorkspaceRunner:
    """Materialize and execute one BUILD_TIME artifact behind sandbox preflight."""

    def __init__(
        self,
        *,
        root: Path | None = None,
        max_output_chars: int = 20_000,
        keep_workspace: bool = False,
        sandbox_policy: BuildTimeSandboxPolicy | None = None,
    ) -> None:
        if max_output_chars <= 0:
            raise ValueError("max_output_chars must be positive")
        self._root = root
        self._max_output_chars = max_output_chars
        self._keep_workspace = keep_workspace
        self._sandbox_policy = sandbox_policy or BuildTimeSandboxPolicy()

    def run(
        self,
        artifact: BuildTimeCapabilityArtifact,
        commands: Iterable[BuildCommand],
        *,
        host_projection: BuildTimeHostProjection | None = None,
    ) -> ManagedBuildExecution:
        artifact.validate()
        command_plan = tuple(commands)
        if not command_plan:
            raise BuildTimeExtensionError("managed build requires at least one command")
        for command in command_plan:
            command.validate()

        required_kinds = {"test", "build", "runtime_probe"}
        present = {command.kind for command in command_plan}
        missing = required_kinds.difference(present)
        if missing:
            raise BuildTimeExtensionError(
                "managed build command plan missing required evidence kinds: "
                + ", ".join(sorted(missing))
            )

        base = self._root
        if base is not None:
            base.mkdir(parents=True, exist_ok=True)
            workspace = Path(tempfile.mkdtemp(prefix="forge-extension-", dir=base))
        else:
            workspace = Path(tempfile.mkdtemp(prefix="forge-extension-"))

        try:
            self._materialize(workspace, artifact)
            workspace_digest = self._workspace_digest(workspace)
            if workspace_digest != artifact.source_digest:
                raise BuildTimeExtensionError(
                    "materialized workspace digest differs from generated artifact"
                )

            # Crucial ordering: preflight runs before the first subprocess.  A rejected
            # artifact therefore cannot obtain a single instruction of host execution.
            sandbox = self._sandbox_policy.preflight(
                artifact,
                command_plan,
                workspace=workspace,
                host_projection=host_projection,
            )

            evidence: list[CommandEvidence] = []
            for command in command_plan:
                item = self._execute(workspace, command)
                evidence.append(item)
                if not item.passed:
                    # Fail closed: later phases are not evidence for a build whose
                    # prerequisite phase already failed.
                    break

            build_id = f"build-{uuid4().hex}"
            fingerprint = self._runtime_fingerprint(
                artifact.capability_id,
                build_id,
                workspace_digest,
                sandbox.policy_digest,
                tuple(evidence),
            )
            bundle = ManagedBuildEvidence(
                build_id=build_id,
                workspace_digest=workspace_digest,
                source_digest=artifact.source_digest,
                runtime_fingerprint=fingerprint,
                commands=tuple(evidence),
                sandbox_policy_version=sandbox.policy_version,
                sandbox_policy_digest=sandbox.policy_digest,
                sandbox_preflight_pass=True,
                sandbox_environment_names=sandbox.environment_names,
                sandbox_host_projection_digest=sandbox.host_projection_digest,
            )
            result = BuildTimeBuildResult(
                build_id=build_id,
                source_digest=artifact.source_digest,
                runtime_fingerprint=fingerprint,
                tests_pass=bundle.passed("test"),
                build_pass=bundle.passed("build"),
                runtime_evidence=bundle.passed("runtime_probe"),
                safety_review=(bundle.passed("safety") if "safety" in present else False),
                sandbox_preflight=bundle.sandbox_preflight_pass,
                sandbox_policy_version=bundle.sandbox_policy_version,
                sandbox_policy_digest=bundle.sandbox_policy_digest,
            )
            return ManagedBuildExecution(result=result, evidence=bundle)
        finally:
            if not self._keep_workspace:
                shutil.rmtree(workspace, ignore_errors=True)

    def _materialize(self, workspace: Path, artifact: BuildTimeCapabilityArtifact) -> None:
        root = workspace.resolve()
        for source in artifact.files:
            target = (workspace / source.path).resolve()
            try:
                target.relative_to(root)
            except ValueError as exc:
                raise BuildTimeExtensionError(
                    f"generated source escapes managed workspace: {source.path!r}"
                ) from exc
            target.parent.mkdir(parents=True, exist_ok=True)
            # A parent symlink created by a previous file must never redirect a later write.
            current = target.parent
            while current != root:
                if current.is_symlink():
                    raise BuildTimeExtensionError(
                        f"generated source traverses symlink: {source.path!r}"
                    )
                current = current.parent
            target.write_text(source.content, encoding="utf-8", newline="\n")

    def _execute(self, workspace: Path, command: BuildCommand) -> CommandEvidence:
        """生成物を**隔離して**走らせる（EXT-08 / SEC-04、2026-09-04）。

        ここが「AI が書いたコードを実際に動かす」唯一の場所である。
        以前は素の `subprocess.run` で、**ホストの権限と環境変数をそのまま**
        渡していた。生成物から見れば network も secret も開いていた。

        ## 2 層を重ねる

        1. **Policy 層**（`build_time_sandbox`）——実行ファイルをホスト上で
           一度だけ解決して固定し（あとから PATH を変えても差し替わらない）、
           環境変数を scrub する。静的 preflight（import / 実行ファイル
           allowlist）もここに属する。
        2. **OS 層**（`forge_ai.core.sandbox`）——network namespace、
           PID namespace、CPU / memory / file size の rlimit、壁時計 timeout。

        Policy 層だけでは「読み落とした 1 つ」で破れる。OS 層だけでは
        どの実行ファイルが選ばれたか分からない。**両方要る。**

        隔離できない環境（Windows / macOS の OS backend は未実装）では
        **実行せずに失敗として返す**。`passed` が False になるので Promotion
        まで進まない——fail closed である。「Sandbox が無いから素通しで動かす」
        は最悪の設計であり、それをしないことがこの分岐の目的である。
        """
        # Policy 層: 実行ファイルを一度だけ解決して固定し、環境を scrub する。
        resolved_executable = self._sandbox_policy.resolve_executable(command.argv[0])
        argv = [resolved_executable, *command.argv[1:]]
        env = self._sandbox_policy.build_environment(workspace)
        try:
            # OS 層: 上で固定した argv と環境を、namespace と rlimit の中で走らせる。
            result = run_in_sandbox(
                argv,
                workspace=workspace,
                policy=SandboxPolicy(
                    timeout_seconds=float(command.timeout_seconds),
                    # CPU 秒も別に取る。壁時計だけでは「速く回り続けるもの」を
                    # 止められない。
                    cpu_seconds=max(1, int(command.timeout_seconds)),
                ),
                env_override=env,
            )
        except (SandboxUnavailable, SandboxViolation) as exc:
            return CommandEvidence(
                kind=command.kind,
                argv=command.argv,
                exit_code=None,
                timed_out=False,
                stdout="",
                stderr=self._bounded(f"sandbox unavailable, refused to run: {exc}"),
                sandbox_backend="",
            )
        return CommandEvidence(
            kind=command.kind,
            argv=command.argv,
            exit_code=result.exit_code,
            timed_out=result.timed_out,
            stdout=self._bounded(result.stdout),
            stderr=self._bounded(result.stderr),
            sandbox_backend=result.backend,
        )

    @staticmethod
    def _decode_timeout_stream(value: str | bytes | None) -> str:
        if value is None:
            return ""
        if isinstance(value, bytes):
            return value.decode("utf-8", errors="replace")
        return value

    def _bounded(self, text: str) -> str:
        if len(text) <= self._max_output_chars:
            return text
        return text[: self._max_output_chars] + "\n...[truncated]"

    @staticmethod
    def _workspace_digest(workspace: Path) -> str:
        h = sha256()
        files = sorted(path for path in workspace.rglob("*") if path.is_file())
        for path in files:
            relative = path.relative_to(workspace).as_posix()
            h.update(relative.encode("utf-8"))
            h.update(b"\0")
            h.update(path.read_bytes())
            h.update(b"\0")
        return h.hexdigest()

    @staticmethod
    def _runtime_fingerprint(
        capability_id: str,
        build_id: str,
        source_digest: str,
        sandbox_policy_digest: str,
        evidence: tuple[CommandEvidence, ...],
    ) -> str:
        h = sha256()
        h.update(capability_id.encode("utf-8"))
        h.update(b"\0")
        h.update(build_id.encode("utf-8"))
        h.update(b"\0")
        h.update(source_digest.encode("ascii"))
        h.update(b"\0")
        # Runtime evidence is meaningful only together with the exact policy that
        # permitted execution.  Tightening/loosening policy therefore changes the
        # fingerprint and prevents stale evidence from silently carrying forward.
        h.update(sandbox_policy_digest.encode("ascii"))
        for item in evidence:
            h.update(item.kind.encode("utf-8"))
            h.update(b"\0")
            h.update(str(item.exit_code).encode("ascii"))
            h.update(b"\0")
            h.update(str(item.timed_out).encode("ascii"))
        return h.hexdigest()
