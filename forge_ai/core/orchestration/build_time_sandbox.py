"""Default-deny preflight for generated BUILD_TIME source.

This is the first enforceable sandbox layer around Self-Extension.  It is not an
OS VM/container and does not claim network-namespace isolation.  It closes four
concrete host-escape paths that existed in ``ManagedBuildWorkspaceRunner``:

1. generated source could import host I/O / process / network APIs;
2. a BuildCommand could name an arbitrary executable / ``python -c`` payload;
3. subprocesses inherited the complete host environment, including API keys;
4. a PATH lookup could select an unexpected executable after validation.

It also binds Dart import validation to the exact Host Projection used when a
verified artifact is installed.  A binding may therefore refer to a generated
file that becomes its sibling after projection, but only when that destination
is explicitly declared, collision-free, and part of the same artifact.

The policy is deliberately capability-based and fail-closed.  A future OS
backend (AppContainer / namespace / WASI / VM) can sit underneath the same
contract; this module must not be described as the final EXT-08 proof by itself.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from hashlib import sha256
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
from typing import Iterable

from forge_ai.core.orchestration.build_time_extension import (
    BuildTimeCapabilityArtifact,
    BuildTimeExtensionError,
)
from forge_ai.core.orchestration.build_time_host_projection import (
    BuildTimeHostProjection,
)

__all__ = [
    "BUILD_TIME_SANDBOX_POLICY_VERSION",
    "BuildTimeSandboxPolicy",
    "SandboxPolicyViolation",
    "SandboxPreflightEvidence",
]


BUILD_TIME_SANDBOX_POLICY_VERSION = "2026-09-03.v2"


class SandboxPolicyViolation(BuildTimeExtensionError):
    """Generated source or a build command asked for an effect not permitted."""


@dataclass(frozen=True, slots=True)
class SandboxPreflightEvidence:
    policy_version: str
    policy_digest: str
    source_files_scanned: int
    commands_scanned: int
    environment_names: tuple[str, ...]
    host_projection_digest: str = ""


_PYTHON_ALLOWED_LIBRARY_ROOTS = frozenset(
    {
        "collections",
        "dataclasses",
        "decimal",
        "enum",
        "fractions",
        "functools",
        "itertools",
        "json",
        "math",
        "operator",
        "re",
        "statistics",
        "string",
        "typing",
        "unittest",
    }
)

_PYTHON_DENIED_CALL_NAMES = frozenset(
    {
        "__import__",
        "breakpoint",
        "compile",
        "delattr",
        "eval",
        "exec",
        "getattr",
        "globals",
        "input",
        "locals",
        "open",
        "setattr",
        "vars",
    }
)

_PYTHON_DENIED_ATTRIBUTES = frozenset(
    {
        "bind",
        "chmod",
        "chown",
        "connect",
        "environ",
        "exec",
        "fork",
        "getenv",
        "kill",
        "link",
        "listen",
        "open",
        "popen",
        "read_bytes",
        "read_text",
        "remove",
        "rename",
        "replace",
        "rmdir",
        "rmtree",
        "socket",
        "spawn",
        "symlink",
        "system",
        "unlink",
        "write_bytes",
        "write_text",
    }
)

_DART_ALLOWED_SDK_IMPORTS = frozenset(
    {
        "dart:collection",
        "dart:convert",
        "dart:math",
        "dart:typed_data",
    }
)

_DART_ALLOWED_PACKAGE_IMPORTS = frozenset(
    {
        "package:flutter/material.dart",
        "package:forge_app/json_ui/acquired/acquired_capability.dart",
        "package:forge_app/json_ui/schema/acquired_widget_types.dart",
    }
)

_DART_DANGEROUS_TOKENS = (
    "BasicMessageChannel",
    "Directory",
    "DynamicLibrary",
    "EventChannel",
    "File",
    "HttpClient",
    "InternetAddress",
    "Isolate",
    "Link",
    "MethodChannel",
    "Platform.environment",
    "Process",
    "RawSocket",
    "ServerSocket",
    "Socket",
    "WebSocket",
)

_IMPORT_RE = re.compile(
    r"^\s*(import|export|part)\s+(?:of\s+)?['\"]([^'\"]+)['\"]",
    re.MULTILINE,
)
_PYTHON_EXE_RE = re.compile(r"^python(?:\d+(?:\.\d+)?)?(?:\.exe)?$", re.IGNORECASE)
_DART_EXE_RE = re.compile(r"^dart(?:\.exe)?$", re.IGNORECASE)


class _PythonSafetyVisitor(ast.NodeVisitor):
    def __init__(self, *, path: str, local_roots: frozenset[str]) -> None:
        self.path = path
        self.local_roots = local_roots

    def _reject(self, reason: str) -> None:
        raise SandboxPolicyViolation(f"sandbox source policy rejected {self.path!r}: {reason}")

    def _check_import_root(self, module: str | None) -> None:
        if not module:
            return
        root = module.split(".", 1)[0]
        if root in self.local_roots or root in _PYTHON_ALLOWED_LIBRARY_ROOTS:
            return
        self._reject(f"python import {module!r} is not allow-listed")

    def visit_Import(self, node: ast.Import) -> None:  # noqa: N802
        for alias in node.names:
            self._check_import_root(alias.name)
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:  # noqa: N802
        if node.level == 0:
            self._check_import_root(node.module)
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:  # noqa: N802
        if isinstance(node.func, ast.Name) and node.func.id in _PYTHON_DENIED_CALL_NAMES:
            self._reject(f"python call {node.func.id!r} is not permitted")
        self.generic_visit(node)

    def visit_Attribute(self, node: ast.Attribute) -> None:  # noqa: N802
        attr = node.attr
        if attr.startswith("__") or attr.endswith("__"):
            self._reject(f"python reflective attribute {attr!r} is not permitted")
        if attr in _PYTHON_DENIED_ATTRIBUTES:
            self._reject(f"python effectful attribute {attr!r} is not permitted")
        self.generic_visit(node)


@dataclass(frozen=True, slots=True)
class BuildTimeSandboxPolicy:
    """Static/effect preflight plus a scrubbed subprocess environment."""

    policy_version: str = BUILD_TIME_SANDBOX_POLICY_VERSION

    @property
    def policy_digest(self) -> str:
        """Digest of the static policy; execution evidence also binds projection."""
        payload = {
            "version": self.policy_version,
            "python_allowed_library_roots": sorted(_PYTHON_ALLOWED_LIBRARY_ROOTS),
            "python_denied_calls": sorted(_PYTHON_DENIED_CALL_NAMES),
            "python_denied_attributes": sorted(_PYTHON_DENIED_ATTRIBUTES),
            "dart_allowed_sdk": sorted(_DART_ALLOWED_SDK_IMPORTS),
            "dart_allowed_packages": sorted(_DART_ALLOWED_PACKAGE_IMPORTS),
            "dart_dangerous_tokens": sorted(_DART_DANGEROUS_TOKENS),
            "command_profiles": ["python-safe", "dart-safe"],
            "environment_mode": "allow-list-private-home-workspace-pythonpath",
            "host_projection_mode": "explicit-prefix-exclusions-v1",
        }
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return sha256(encoded).hexdigest()

    def effective_policy_digest(self, host_projection: BuildTimeHostProjection) -> str:
        """Bind the static policy to the exact product-layout projection."""
        h = sha256()
        h.update(self.policy_digest.encode("ascii"))
        h.update(b"\0")
        h.update(host_projection.digest.encode("ascii"))
        return h.hexdigest()

    def preflight(
        self,
        artifact: BuildTimeCapabilityArtifact,
        commands: Iterable[object],
        *,
        workspace: Path,
        host_projection: BuildTimeHostProjection | None = None,
    ) -> SandboxPreflightEvidence:
        artifact.validate()
        projection = host_projection or BuildTimeHostProjection()
        command_plan = tuple(commands)
        self.validate_artifact(artifact, host_projection=projection)
        for command in command_plan:
            kind = str(getattr(command, "kind", ""))
            argv = tuple(str(value) for value in getattr(command, "argv", ()))
            self.validate_command(kind=kind, argv=argv)
        env = self.build_environment(workspace)
        return SandboxPreflightEvidence(
            policy_version=self.policy_version,
            policy_digest=self.effective_policy_digest(projection),
            source_files_scanned=len(artifact.files),
            commands_scanned=len(command_plan),
            environment_names=tuple(sorted(env)),
            host_projection_digest=projection.digest,
        )

    def validate_artifact(
        self,
        artifact: BuildTimeCapabilityArtifact,
        *,
        host_projection: BuildTimeHostProjection | None = None,
    ) -> None:
        projection = host_projection or BuildTimeHostProjection()
        local_python_roots = frozenset(
            PurePosixPath(source.path).stem
            for source in artifact.files
            if source.path.lower().endswith(".py")
        )
        artifact_paths = frozenset(PurePosixPath(source.path).as_posix() for source in artifact.files)
        projected_by_source = projection.projected_paths(artifact_paths)
        projected_paths = frozenset(projected_by_source.values())

        for source in artifact.files:
            lowered = source.path.lower()
            if lowered.endswith(".py"):
                self._validate_python(source.path, source.content, local_python_roots)
            elif lowered.endswith(".dart"):
                self._validate_dart(
                    source.path,
                    source.content,
                    artifact_paths,
                    projected_by_source,
                    projected_paths,
                )
            else:
                raise SandboxPolicyViolation(
                    f"sandbox source policy has no parser for generated file {source.path!r}"
                )

    def _validate_python(
        self,
        path: str,
        content: str,
        local_roots: frozenset[str],
    ) -> None:
        try:
            tree = ast.parse(content, filename=path)
        except SyntaxError:
            # Invalid Python cannot execute.  Treat syntax validity as a build/test
            # concern, not a security-policy verdict: the mandatory compile/test
            # phases will fail closed and promotion remains impossible.
            return
        _PythonSafetyVisitor(path=path, local_roots=local_roots).visit(tree)

    def _validate_dart(
        self,
        path: str,
        content: str,
        artifact_paths: frozenset[str],
        projected_by_source: dict[str, str],
        projected_paths: frozenset[str],
    ) -> None:
        # Remove comments before token checks so prose cannot produce false positives.
        stripped = re.sub(r"/\*.*?\*/", "", content, flags=re.DOTALL)
        stripped = re.sub(r"//.*", "", stripped)

        for token in _DART_DANGEROUS_TOKENS:
            if token in stripped:
                raise SandboxPolicyViolation(
                    f"sandbox source policy rejected {path!r}: Dart effect {token!r} is not permitted"
                )

        normalized_source = PurePosixPath(path).as_posix()
        for statement, uri in _IMPORT_RE.findall(stripped):
            if statement != "import":
                raise SandboxPolicyViolation(
                    f"sandbox source policy rejected {path!r}: Dart {statement} is not permitted"
                )
            if uri in _DART_ALLOWED_SDK_IMPORTS or uri in _DART_ALLOWED_PACKAGE_IMPORTS:
                continue
            if uri.startswith("dart:") or uri.startswith("package:"):
                raise SandboxPolicyViolation(
                    f"sandbox source policy rejected {path!r}: Dart import {uri!r} is not allow-listed"
                )

            relative = PurePosixPath(uri.replace("\\", "/"))
            if relative.is_absolute() or ".." in relative.parts:
                raise SandboxPolicyViolation(
                    f"sandbox source policy rejected {path!r}: relative import {uri!r} escapes artifact"
                )

            # First accept the literal verification-workspace layout.
            workspace_target = (
                PurePosixPath(normalized_source).parent / relative
            ).as_posix()
            if workspace_target in artifact_paths:
                continue

            # Some generated files are verified under a staging prefix but installed
            # with that prefix removed.  Accept only the exact declared product layout.
            projected_source = projected_by_source.get(normalized_source)
            if projected_source is not None:
                projected_target = (
                    PurePosixPath(projected_source).parent / relative
                ).as_posix()
                if projected_target in projected_paths:
                    continue

            raise SandboxPolicyViolation(
                f"sandbox source policy rejected {path!r}: relative import {uri!r} "
                "resolves to neither verified workspace nor declared host projection"
            )

    def validate_command(self, *, kind: str, argv: tuple[str, ...]) -> None:
        if kind not in {"test", "build", "runtime_probe", "safety"}:
            raise SandboxPolicyViolation(f"sandbox command kind {kind!r} is not permitted")
        if not argv:
            raise SandboxPolicyViolation("sandbox command has no executable")

        executable = Path(argv[0]).name
        args = argv[1:]
        if _PYTHON_EXE_RE.match(executable):
            self._validate_python_command(args)
            return
        if _DART_EXE_RE.match(executable):
            self._validate_dart_command(args)
            return
        raise SandboxPolicyViolation(
            f"sandbox executable {executable!r} is not allow-listed"
        )

    def _validate_python_command(self, args: tuple[str, ...]) -> None:
        if not args:
            raise SandboxPolicyViolation("sandbox Python command requires a script or safe -m profile")
        if args[0] in {"-c", "-", "-i"}:
            raise SandboxPolicyViolation(f"sandbox Python option {args[0]!r} is not permitted")
        if args[0] == "-m":
            if len(args) < 2 or args[1] not in {"compileall", "unittest"}:
                raise SandboxPolicyViolation(
                    "sandbox Python -m only permits compileall or unittest"
                )
            self._validate_relative_arguments(args[2:])
            return
        if not args[0].lower().endswith(".py"):
            raise SandboxPolicyViolation("sandbox Python direct execution requires a .py entry file")
        self._validate_relative_arguments(args)

    def _validate_dart_command(self, args: tuple[str, ...]) -> None:
        if len(args) < 2 or args[0] not in {"run", "analyze"}:
            raise SandboxPolicyViolation("sandbox Dart only permits `dart run` or `dart analyze`")
        self._validate_relative_arguments(args[1:])
        candidates = [value for value in args[1:] if not value.startswith("-")]
        if not candidates or any(not value.lower().endswith(".dart") for value in candidates):
            raise SandboxPolicyViolation("sandbox Dart command may only name generated .dart files")

    @staticmethod
    def _validate_relative_arguments(args: tuple[str, ...]) -> None:
        for value in args:
            if value.startswith("-") or value in {".", "*_test.py"}:
                continue
            # unittest module/config words are not paths.
            if value in {"discover", "compileall", "unittest"}:
                continue
            path = PurePosixPath(value.replace("\\", "/"))
            if path.is_absolute() or ".." in path.parts:
                raise SandboxPolicyViolation(
                    f"sandbox command argument escapes workspace: {value!r}"
                )

    def resolve_executable(self, executable: str) -> str:
        """Resolve before environment scrubbing so PATH cannot change the selected tool."""
        self.validate_command_executable_name(executable)
        path = Path(executable)
        resolved = str(path.resolve()) if path.is_absolute() and path.exists() else shutil.which(executable)
        if not resolved:
            raise SandboxPolicyViolation(f"sandbox executable is unavailable: {executable!r}")
        return resolved

    @staticmethod
    def validate_command_executable_name(executable: str) -> None:
        name = Path(executable).name
        if not (_PYTHON_EXE_RE.match(name) or _DART_EXE_RE.match(name)):
            raise SandboxPolicyViolation(f"sandbox executable {name!r} is not allow-listed")

    def build_environment(self, workspace: Path) -> dict[str, str]:
        """Return an allow-listed environment containing no inherited secrets."""
        private_home = workspace / ".sandbox-home"
        private_tmp = workspace / ".sandbox-tmp"
        private_home.mkdir(parents=True, exist_ok=True)
        private_tmp.mkdir(parents=True, exist_ok=True)

        env: dict[str, str] = {}
        for name in ("PATH", "PATHEXT", "SYSTEMROOT", "WINDIR", "COMSPEC", "LANG", "LC_ALL"):
            value = os.environ.get(name)
            if value:
                env[name] = value

        env.update(
            {
                "HOME": str(private_home),
                "USERPROFILE": str(private_home),
                "APPDATA": str(private_home / "AppData" / "Roaming"),
                "LOCALAPPDATA": str(private_home / "AppData" / "Local"),
                "TMP": str(private_tmp),
                "TEMP": str(private_tmp),
                "TMPDIR": str(private_tmp),
                "PYTHONNOUSERSITE": "1",
                "PYTHONSAFEPATH": "1",
                # PYTHONSAFEPATH removes implicit cwd injection.  Add back exactly
                # the generated workspace, and nothing from the host project/user.
                "PYTHONPATH": str(workspace.resolve()),
                "CI": "true",
                "FORGE_BUILD_SANDBOX": "1",
            }
        )
        return env
