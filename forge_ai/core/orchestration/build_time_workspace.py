"""Concrete managed workspace runner for BUILD_TIME capability acquisition.

This module is intentionally generic: it does not know about map/calendar/game or
any other product domain.  It materializes an already-decomposed reusable
BuildTimeCapabilityArtifact into an isolated staging directory, executes an
explicit allow-listed command plan without shell interpolation, records concrete
evidence, and returns the exact source/runtime fingerprint used by the promotion
gate.

It is *not* an arbitrary command endpoint.  Callers must provide argv tuples;
``shell=True`` is never used, cwd is pinned to the generated workspace, execution
is bounded by timeout, paths are checked before materialization, and output is
truncated before it can become unbounded evidence.
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
import shutil
import subprocess
import tempfile
from typing import Iterable
from uuid import uuid4

from forge_ai.core.orchestration.build_time_extension import (
    BuildTimeBuildResult,
    BuildTimeCapabilityArtifact,
    BuildTimeExtensionError,
)


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

    def passed(self, kind: str) -> bool:
        matching = [item for item in self.commands if item.kind == kind]
        return bool(matching) and all(item.passed for item in matching)


@dataclass(frozen=True, slots=True)
class ManagedBuildExecution:
    result: BuildTimeBuildResult
    evidence: ManagedBuildEvidence


class ManagedBuildWorkspaceRunner:
    """Materialize and execute one BUILD_TIME artifact in a controlled workspace."""

    def __init__(
        self,
        *,
        root: Path | None = None,
        max_output_chars: int = 20_000,
        keep_workspace: bool = False,
    ) -> None:
        if max_output_chars <= 0:
            raise ValueError("max_output_chars must be positive")
        self._root = root
        self._max_output_chars = max_output_chars
        self._keep_workspace = keep_workspace

    def run(
        self,
        artifact: BuildTimeCapabilityArtifact,
        commands: Iterable[BuildCommand],
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
                artifact.capability_id, build_id, workspace_digest, tuple(evidence)
            )
            bundle = ManagedBuildEvidence(
                build_id=build_id,
                workspace_digest=workspace_digest,
                source_digest=artifact.source_digest,
                runtime_fingerprint=fingerprint,
                commands=tuple(evidence),
            )
            result = BuildTimeBuildResult(
                build_id=build_id,
                source_digest=artifact.source_digest,
                runtime_fingerprint=fingerprint,
                tests_pass=bundle.passed("test"),
                build_pass=bundle.passed("build"),
                runtime_evidence=bundle.passed("runtime_probe"),
                safety_review=(bundle.passed("safety") if "safety" in present else False),
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
        try:
            completed = subprocess.run(
                list(command.argv),
                cwd=workspace,
                check=False,
                capture_output=True,
                text=True,
                timeout=command.timeout_seconds,
                shell=False,
            )
            return CommandEvidence(
                kind=command.kind,
                argv=command.argv,
                exit_code=completed.returncode,
                timed_out=False,
                stdout=self._bounded(completed.stdout),
                stderr=self._bounded(completed.stderr),
            )
        except subprocess.TimeoutExpired as exc:
            return CommandEvidence(
                kind=command.kind,
                argv=command.argv,
                exit_code=None,
                timed_out=True,
                stdout=self._bounded(self._decode_timeout_stream(exc.stdout)),
                stderr=self._bounded(self._decode_timeout_stream(exc.stderr)),
            )
        except OSError as exc:
            return CommandEvidence(
                kind=command.kind,
                argv=command.argv,
                exit_code=None,
                timed_out=False,
                stdout="",
                stderr=self._bounded(str(exc)),
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
        evidence: tuple[CommandEvidence, ...],
    ) -> str:
        h = sha256()
        h.update(capability_id.encode("utf-8"))
        h.update(b"\0")
        h.update(build_id.encode("utf-8"))
        h.update(b"\0")
        h.update(source_digest.encode("ascii"))
        for item in evidence:
            h.update(item.kind.encode("utf-8"))
            h.update(b"\0")
            h.update(str(item.exit_code).encode("ascii"))
            h.update(b"\0")
            h.update(str(item.timed_out).encode("ascii"))
        return h.hexdigest()
