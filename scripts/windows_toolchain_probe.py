#!/usr/bin/env python3
"""TD110 Windows real-toolchain probe (stage 4).

Runs Forge-like Python and Dart test/build/runtime-probe commands inside the
already proven AppContainer + Job Object boundary.

This is still probe/evidence code, not the production sandbox backend.

Security posture:
- AppContainer has no capabilities (network remains denied).
- Only the temporary workspace is granted modify access.
- Installed Python/Dart toolchain roots receive temporary read/execute ACLs for
  this one ephemeral AppContainer SID.
- Those temporary ACLs are removed before the AppContainer profile is deleted.
- The Job Object is attached before execution resumes.
- The child receives a private HOME/APPDATA/TEMP and no host API-key variables.

Fail closed: any command failure or ACL-cleanup failure exits non-zero.
"""

from __future__ import annotations

import ctypes
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import time

import windows_appcontainer_isolation_probe as isolation
import windows_job_resource_probe as resource_probe


if platform.system() != "Windows":
    print(json.dumps({"ok": False, "error": "windows-only probe"}, ensure_ascii=False))
    raise SystemExit(2)


REPO_ROOT = Path(__file__).resolve().parents[1]


def _emit_json(value: object) -> None:
    """Print JSON without depending on the Windows console code page.

    Physical Windows PowerShell can leave BOM/progress characters in captured
    child output.  Encoding them through cp932 can raise UnicodeEncodeError
    even after the probe itself has completed.  ASCII-escaped JSON preserves
    every code point and keeps evidence emission fail-safe.
    """
    print(json.dumps(value, ensure_ascii=True, indent=2))


def _clean_log_text(value: str) -> str:
    """Remove transport-only BOMs while preserving the actual tool output."""
    return value.replace("\ufeff", "")


def _run_icacls(args: list[str]) -> subprocess.CompletedProcess[str]:
    icacls = shutil.which("icacls.exe") or os.path.join(
        os.environ["SystemRoot"], "System32", "icacls.exe"
    )
    return subprocess.run(
        [icacls, *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )


def _grant_read_execute(path: Path, sid_text: str, *, recursive: bool) -> None:
    if not path.exists():
        raise RuntimeError(f"toolchain path does not exist: {path}")

    args = [
        str(path),
        "/grant",
        f"*{sid_text}:(OI)(CI)RX" if recursive else f"*{sid_text}:RX",
    ]
    if recursive:
        args.extend(["/T", "/C"])
    args.append("/Q")

    completed = _run_icacls(args)
    if completed.returncode != 0:
        raise RuntimeError(
            "icacls RX grant failed: "
            f"path={path} recursive={recursive} exit={completed.returncode} "
            f"stdout={completed.stdout!r} stderr={completed.stderr!r}"
        )


def _remove_sid_acl(path: Path, sid_text: str, *, recursive: bool) -> None:
    args = [str(path), "/remove", f"*{sid_text}"]
    if recursive:
        args.extend(["/T", "/C"])
    args.append("/Q")

    completed = _run_icacls(args)
    if completed.returncode != 0:
        raise RuntimeError(
            "icacls SID cleanup failed: "
            f"path={path} recursive={recursive} exit={completed.returncode} "
            f"stdout={completed.stdout!r} stderr={completed.stderr!r}"
        )


def _ancestor_directories(path: Path) -> tuple[Path, ...]:
    """Return non-volume-root ancestors needed to traverse to *path*."""
    resolved = path.resolve()
    anchor = Path(resolved.anchor)
    ancestors: list[Path] = []
    current = resolved.parent
    while current != anchor and current != current.parent:
        ancestors.append(current)
        current = current.parent
    ancestors.reverse()
    return tuple(ancestors)


def _venv_python() -> tuple[Path, Path]:
    python = REPO_ROOT / ".venv" / "Scripts" / "python.exe"
    cfg = REPO_ROOT / ".venv" / "pyvenv.cfg"
    if not python.is_file() or not cfg.is_file():
        raise RuntimeError("repository-local .venv Python is missing")

    home = None
    for line in cfg.read_text(encoding="utf-8", errors="replace").splitlines():
        key, sep, value = line.partition("=")
        if sep and key.strip().lower() == "home":
            home = Path(value.strip())
            break
    if home is None or not home.exists():
        raise RuntimeError("could not resolve base Python from .venv/pyvenv.cfg")
    return python, home


def _dart_executable() -> tuple[Path, Path]:
    found = shutil.which("dart")
    if not found:
        raise RuntimeError("dart is not on PATH")
    candidate = Path(found).resolve()

    if candidate.suffix.lower() in {".bat", ".cmd"}:
        # Flutter's bin/dart.bat delegates to the cached SDK executable.
        flutter_root = candidate.parent.parent
        dart_sdk = flutter_root / "bin" / "cache" / "dart-sdk"
        dart = dart_sdk / "bin" / "dart.exe"
    else:
        dart = candidate
        # Standalone SDK layout: <sdk>/bin/dart.exe
        dart_sdk = dart.parent.parent

    if not dart.is_file():
        raise RuntimeError(f"resolved Dart executable does not exist: {dart}")
    if not dart_sdk.is_dir():
        raise RuntimeError(f"resolved Dart SDK root does not exist: {dart_sdk}")
    return dart, dart_sdk


def _write_fixtures(workspace: Path) -> None:
    (workspace / "language_binding.py").write_text(
        "VIEW_TYPE = 'unseen_probe'\n",
        encoding="utf-8",
    )
    (workspace / "validator_binding.py").write_text(
        "def valid(value): return isinstance(value, dict)\n",
        encoding="utf-8",
    )
    (workspace / "runtime_binding.py").write_text(
        "def render(value): return 'probe:' + str(value['label'])\n",
        encoding="utf-8",
    )
    (workspace / "compiler_binding.py").write_text(
        "def compile_view(label): return {'label': label}\n",
        encoding="utf-8",
    )
    (workspace / "test_extension.py").write_text(
        "from compiler_binding import compile_view\n"
        "from validator_binding import valid\n"
        "assert valid(compile_view('A'))\n"
        "print('PY_TEST=PASS')\n",
        encoding="utf-8",
    )
    (workspace / "runtime_probe.py").write_text(
        "from compiler_binding import compile_view\n"
        "from runtime_binding import render\n"
        "assert render(compile_view('E2E')) == 'probe:E2E'\n"
        "print('PY_RUNTIME=PASS')\n",
        encoding="utf-8",
    )

    (workspace / "capability_impl.dart").write_text(
        "List<List<T>> chunkRows<T>(List<T> items, int columns) {\n"
        "  if (columns < 1) { throw ArgumentError.value(columns); }\n"
        "  final rows = <List<T>>[];\n"
        "  for (var i = 0; i < items.length; i += columns) {\n"
        "    final end = i + columns > items.length ? items.length : i + columns;\n"
        "    rows.add(items.sublist(i, end));\n"
        "  }\n"
        "  return rows;\n"
        "}\n",
        encoding="utf-8",
    )
    (workspace / "capability_test.dart").write_text(
        "import 'capability_impl.dart';\n"
        "void main() {\n"
        "  final rows = chunkRows(<int>[1,2,3,4,5], 2);\n"
        "  if (rows.length != 3) { throw StateError('bad rows'); }\n"
        "  print('DART_TEST=PASS');\n"
        "}\n",
        encoding="utf-8",
    )
    (workspace / "probe.dart").write_text(
        "import 'capability_impl.dart';\n"
        "void main() {\n"
        "  final rows = chunkRows(<String>['a','b','c'], 2);\n"
        "  if (rows.toString() != '[[a, b], [c]]') { throw StateError('bad'); }\n"
        "  print('DART_RUNTIME=PASS');\n"
        "}\n",
        encoding="utf-8",
    )


def _toolchain_environment(
    ctx: resource_probe.Context,
    *,
    python: Path,
    dart: Path,
) -> ctypes.Array:
    """Build a secret-free Windows environment block for direct toolchain launch."""
    workspace = ctx.workspace
    private_home = workspace / ".sandbox-home"
    private_roaming = private_home / "AppData" / "Roaming"
    private_home.mkdir(parents=True, exist_ok=True)
    private_roaming.mkdir(parents=True, exist_ok=True)

    system_root = os.environ["SystemRoot"]
    container_local = ctx.appcontainer_local
    container_temp = container_local / "Temp"
    container_temp.mkdir(parents=True, exist_ok=True)

    drive = workspace.drive.upper()
    path_value = ";".join(
        dict.fromkeys(
            (
                str(python.parent),
                str(dart.parent),
                os.path.join(system_root, "System32"),
                os.path.join(system_root, "System32", "WindowsPowerShell", "v1.0"),
            )
        )
    )
    entries = [
        (f"={drive}", str(workspace)),
        ("APPDATA", str(private_roaming)),
        ("CI", "true"),
        ("ComSpec", os.path.join(system_root, "System32", "cmd.exe")),
        ("FORGE_BUILD_SANDBOX", "1"),
        ("HOME", str(private_home)),
        ("LOCALAPPDATA", str(container_local)),
        ("PATH", path_value),
        ("PYTHONNOUSERSITE", "1"),
        ("PYTHONPATH", str(workspace)),
        ("PYTHONSAFEPATH", "1"),
        ("SystemRoot", system_root),
        ("TEMP", str(container_temp)),
        ("TMP", str(container_temp)),
        ("TMPDIR", str(container_temp)),
        ("USERPROFILE", str(private_home)),
        ("WINDIR", system_root),
    ]
    entries.sort(key=lambda item: item[0].casefold())
    block = "\0".join(f"{name}={value}" for name, value in entries) + "\0\0"
    return ctypes.create_unicode_buffer(block)


def _direct_appcontainer_run(
    ctx: resource_probe.Context,
    *,
    executable: Path,
    args: tuple[str, ...],
    python: Path,
    dart: Path,
    timeout_ms: int = 20_000,
) -> dict[str, object]:
    """Launch one native toolchain process directly under AppContainer + Job."""
    job = ctx._new_job(
        flags=(
            isolation.JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
            | isolation.JOB_OBJECT_LIMIT_ACTIVE_PROCESS
            | isolation.JOB_OBJECT_LIMIT_PROCESS_MEMORY
            | isolation.JOB_OBJECT_LIMIT_JOB_MEMORY
        ),
        active_process_limit=64,
        process_memory=4 * 1024 * 1024 * 1024,
        job_memory=8 * 1024 * 1024 * 1024,
    )
    pi = isolation.PROCESS_INFORMATION()
    token = isolation.HANDLE()
    result: dict[str, object] = {
        "created": False,
        "appcontainer_token": False,
        "timed_out": False,
        "exit_code": None,
    }

    try:
        si = isolation.STARTUPINFOEXW()
        si.StartupInfo.cb = ctypes.sizeof(si)
        si.lpAttributeList = ctx.attr_list
        env_block = _toolchain_environment(ctx, python=python, dart=dart)
        command_line = ctypes.create_unicode_buffer(
            subprocess.list2cmdline([str(executable), *args])
        )

        if not isolation.kernel32.CreateProcessW(
            str(executable),
            command_line,
            None,
            None,
            False,
            isolation.CREATE_SUSPENDED
            | isolation.CREATE_UNICODE_ENVIRONMENT
            | isolation.EXTENDED_STARTUPINFO_PRESENT,
            ctypes.cast(env_block, isolation.LPVOID),
            str(ctx.workspace),
            ctypes.byref(si.StartupInfo),
            ctypes.byref(pi),
        ):
            code = ctypes.get_last_error()
            result["create_winerror"] = code
            result["create_error"] = ctypes.FormatError(code).strip()
            return result

        result["created"] = True

        if not isolation.advapi32.OpenProcessToken(
            pi.hProcess, isolation.TOKEN_QUERY, ctypes.byref(token)
        ):
            code = ctypes.get_last_error()
            result["token_winerror"] = code
            result["token_error"] = ctypes.FormatError(code).strip()
            return result

        is_appcontainer = isolation.DWORD(0)
        returned = isolation.DWORD(0)
        if not isolation.advapi32.GetTokenInformation(
            token,
            isolation.TOKEN_IS_APP_CONTAINER,
            ctypes.byref(is_appcontainer),
            ctypes.sizeof(is_appcontainer),
            ctypes.byref(returned),
        ):
            code = ctypes.get_last_error()
            result["token_info_winerror"] = code
            result["token_info_error"] = ctypes.FormatError(code).strip()
            return result
        result["appcontainer_token"] = bool(is_appcontainer.value)

        if not isolation.kernel32.AssignProcessToJobObject(job, pi.hProcess):
            code = ctypes.get_last_error()
            result["job_winerror"] = code
            result["job_error"] = ctypes.FormatError(code).strip()
            return result

        if isolation.kernel32.ResumeThread(pi.hThread) == 0xFFFFFFFF:
            code = ctypes.get_last_error()
            result["resume_winerror"] = code
            result["resume_error"] = ctypes.FormatError(code).strip()
            return result

        wait = isolation.kernel32.WaitForSingleObject(pi.hProcess, timeout_ms)
        if wait == isolation.WAIT_TIMEOUT:
            result["timed_out"] = True
            isolation.kernel32.TerminateJobObject(job, 124)
            isolation.kernel32.WaitForSingleObject(pi.hProcess, 5_000)
        elif wait != isolation.WAIT_OBJECT_0:
            result["wait_code"] = int(wait)
            return result

        exit_code = isolation.DWORD(0)
        if isolation.kernel32.GetExitCodeProcess(pi.hProcess, ctypes.byref(exit_code)):
            result["exit_code"] = int(exit_code.value)
            result["exit_code_hex"] = f"0x{int(exit_code.value):08X}"

        return result
    finally:
        if token:
            isolation.kernel32.CloseHandle(token)
        if pi.hThread:
            isolation.kernel32.CloseHandle(pi.hThread)
        if pi.hProcess:
            isolation.kernel32.CloseHandle(pi.hProcess)
        isolation.kernel32.CloseHandle(job)


def _ps_quote(value: str) -> str:
    return value.replace("'", "''")


def _toolchain_script(
    workspace: Path,
    python: Path,
    dart: Path,
    result_file: Path,
    appcontainer_local: Path,
) -> str:
    w = _ps_quote(str(workspace))
    py = _ps_quote(str(python))
    dart_exe = _ps_quote(str(dart))
    result = _ps_quote(str(result_file))
    appcontainer_local_text = _ps_quote(str(appcontainer_local))

    return rf"""
$ErrorActionPreference = 'Continue'

# Do not rely on PowerShell's provider current location inside AppContainer.
# On the physical Windows 10 Home probe, relative redirection unexpectedly
# resolved to D:\ even though CreateProcessW received the workspace as its
# current directory.  Production Forge launches toolchains directly, but this
# probe uses PowerShell as an orchestration shell, so bind every path explicitly.
$workspace = '{w}'
try {{
  Set-Location -LiteralPath $workspace
}} catch {{
  # Absolute command/log paths below remain authoritative even if the provider
  # refuses to adopt the AppContainer workspace as its shell location.
}}

$privateHome = Join-Path '{w}' '.sandbox-home'
$privateRoaming = Join-Path $privateHome 'AppData\Roaming'
$appContainerLocal = '{appcontainer_local_text}'
$appContainerTemp = Join-Path $appContainerLocal 'Temp'
New-Item -ItemType Directory -Force -Path $privateRoaming | Out-Null
New-Item -ItemType Directory -Force -Path $appContainerTemp | Out-Null

$env:HOME = $privateHome
$env:USERPROFILE = $privateHome
$env:APPDATA = $privateRoaming

# Keep Windows' AppContainer-specific LOCALAPPDATA/TEMP contract intact for
# nested native launches. The earlier physical probe showed that replacing these
# with ordinary user/workspace paths can make CreateProcess fail before the
# child toolchain even starts.
$env:LOCALAPPDATA = $appContainerLocal
$env:TEMP = $appContainerTemp
$env:TMP = $appContainerTemp
$env:TMPDIR = $appContainerTemp
$env:PYTHONNOUSERSITE = '1'
$env:PYTHONSAFEPATH = '1'
$env:PYTHONPATH = '{w}'
$env:CI = 'true'
$env:FORGE_BUILD_SANDBOX = '1'

$probe = [ordered]@{{
  host_secret_absent = [string]::IsNullOrEmpty($env:OPENAI_API_KEY) -and
                       [string]::IsNullOrEmpty($env:GEMINI_API_KEY) -and
                       [string]::IsNullOrEmpty($env:ANTHROPIC_API_KEY)
  python_visible = Test-Path -LiteralPath '{py}'
  dart_visible = Test-Path -LiteralPath '{dart_exe}'
  python_smoke = $false
  dart_smoke = $false
  python_test = $false
  python_build = $false
  python_runtime = $false
  dart_test = $false
  dart_analyze = $false
  dart_runtime = $false

  # AppContainer-safe Dart route. The ordinary dartdev commands above are kept
  # as diagnostics because current Dart calls Platform.resolvedExecutable,
  # which canonicalizes via GetFinalPathNameByHandle(VOLUME_NAME_DOS) and can
  # fail inside AppContainer even when the executable/file itself is readable.
  dart_vm_test = $false
  dart_vm_build = $false
  dart_vm_runtime = $false
  exit_codes = [ordered]@{{}}
  errors = @()
}}

$pyTest = Join-Path $workspace 'test_extension.py'
$pyProbe = Join-Path $workspace 'runtime_probe.py'
$dartTest = Join-Path $workspace 'capability_test.dart'
$dartImpl = Join-Path $workspace 'capability_impl.dart'
$dartProbe = Join-Path $workspace 'probe.dart'

$pySmokeLog = Join-Path $workspace 'python-smoke.log'
$dartSmokeLog = Join-Path $workspace 'dart-smoke.log'
$pyTestLog = Join-Path $workspace 'python-test.log'
$pyBuildLog = Join-Path $workspace 'python-build.log'
$pyRuntimeLog = Join-Path $workspace 'python-runtime.log'
$dartTestLog = Join-Path $workspace 'dart-test.log'
$dartAnalyzeLog = Join-Path $workspace 'dart-analyze.log'
$dartRuntimeLog = Join-Path $workspace 'dart-runtime.log'
$dartVmTestLog = Join-Path $workspace 'dart-vm-test.log'
$dartVmBuildLog = Join-Path $workspace 'dart-vm-build.log'
$dartVmRuntimeLog = Join-Path $workspace 'dart-vm-runtime.log'
$dartKernel = Join-Path $workspace 'capability-test.dill'

function Invoke-ProbeCommand(
  [string]$Name,
  [string]$FilePath,
  [string[]]$ArgumentList,
  [string]$LogPath
) {{
  $ErrorLog = "$LogPath.err"
  try {{
    $p = Start-Process -FilePath $FilePath -ArgumentList $ArgumentList -WorkingDirectory $workspace -RedirectStandardOutput $LogPath -RedirectStandardError $ErrorLog -PassThru -Wait -WindowStyle Hidden -ErrorAction Stop

    $probe.exit_codes[$Name] = [int]$p.ExitCode
    if (Test-Path -LiteralPath $ErrorLog) {{
      Get-Content -LiteralPath $ErrorLog -ErrorAction SilentlyContinue | Add-Content -LiteralPath $LogPath -Encoding UTF8
    }}
    return ($p.ExitCode -eq 0)
  }} catch {{
    $probe.exit_codes[$Name] = $null
    $message = "$($Name): $($_.Exception.GetType().FullName): $($_.Exception.Message)"
    $probe.errors += $message
    $message | Out-File -LiteralPath $LogPath -Encoding UTF8 -Append
    return $false
  }}
}}

$probe.python_smoke = Invoke-ProbeCommand 'python-smoke' '{py}' @('--version') $pySmokeLog
$probe.dart_smoke = Invoke-ProbeCommand 'dart-smoke' '{dart_exe}' @('--version') $dartSmokeLog
$probe.python_test = Invoke-ProbeCommand 'python-test' '{py}' @($pyTest) $pyTestLog
$probe.python_build = Invoke-ProbeCommand 'python-build' '{py}' @('-m','compileall','-q',$workspace) $pyBuildLog
$probe.python_runtime = Invoke-ProbeCommand 'python-runtime' '{py}' @($pyProbe) $pyRuntimeLog
$probe.dart_test = Invoke-ProbeCommand 'dart-test' '{dart_exe}' @('run',$dartTest) $dartTestLog
$probe.dart_analyze = Invoke-ProbeCommand 'dart-analyze' '{dart_exe}' @('analyze',$dartImpl,$dartTest,$dartProbe) $dartAnalyzeLog
$probe.dart_runtime = Invoke-ProbeCommand 'dart-runtime' '{dart_exe}' @('run',$dartProbe) $dartRuntimeLog

# Bypass dartdev but keep the same Dart VM / frontend compiler. This is the
# candidate production route for AppContainer: execute generated Dart directly
# and force a kernel compilation as the build/type-checking gate.
$probe.dart_vm_test = Invoke-ProbeCommand 'dart-vm-test' '{dart_exe}' @('--disable-dart-dev',$dartTest) $dartVmTestLog
$probe.dart_vm_build = Invoke-ProbeCommand 'dart-vm-build' '{dart_exe}' @('--disable-dart-dev','--snapshot-kind=kernel',"--snapshot=$dartKernel",$dartTest) $dartVmBuildLog
$probe.dart_vm_runtime = Invoke-ProbeCommand 'dart-vm-runtime' '{dart_exe}' @('--disable-dart-dev',$dartProbe) $dartVmRuntimeLog

$probe | ConvertTo-Json -Compress | Set-Content -LiteralPath '{result}' -Encoding UTF8
if ($probe.python_visible -and $probe.dart_visible -and
    $probe.python_smoke -and $probe.dart_smoke -and
    $probe.python_test -and $probe.python_build -and $probe.python_runtime -and
    $probe.dart_vm_test -and $probe.dart_vm_build -and $probe.dart_vm_runtime -and
    $probe.host_secret_absent) {{
  exit 0
}}
exit 7
"""


def main() -> int:
    ctx = None
    granted_recursive: list[Path] = []
    granted_ancestors: list[Path] = []
    result: dict[str, object] = {
        "ok": False,
        "platform": platform.platform(),
        "assertions": {},
        "acl_cleanup": False,
    }

    saved = {
        name: os.environ.get(name)
        for name in ("OPENAI_API_KEY", "GEMINI_API_KEY", "ANTHROPIC_API_KEY")
    }
    os.environ["OPENAI_API_KEY"] = "must-not-reach-toolchain"
    os.environ["GEMINI_API_KEY"] = "must-not-reach-toolchain"
    os.environ["ANTHROPIC_API_KEY"] = "must-not-reach-toolchain"

    try:
        python, python_home = _venv_python()
        dart, dart_sdk = _dart_executable()

        result["python_executable"] = str(python)
        result["python_home"] = str(python_home)
        result["dart_executable"] = str(dart)
        result["dart_sdk"] = str(dart_sdk)

        ctx = resource_probe.Context()
        result["moniker"] = ctx.moniker
        result["appcontainer_sid"] = ctx.sid_text

        _write_fixtures(ctx.workspace)
        result_file = ctx.workspace / "toolchain-result.json"

        # Grant read/execute to toolchain trees and non-inheriting traversal
        # rights to their ancestors. Sibling project/source files do not inherit.
        toolchain_roots = tuple(
            dict.fromkeys(
                root.resolve()
                for root in (REPO_ROOT / ".venv", python_home, dart_sdk)
            )
        )
        ancestor_set = {
            ancestor
            for root in toolchain_roots
            for ancestor in _ancestor_directories(root)
        }
        for ancestor in sorted(ancestor_set, key=lambda item: len(item.parts)):
            _grant_read_execute(ancestor, ctx.sid_text, recursive=False)
            granted_ancestors.append(ancestor)

        for resolved in toolchain_roots:
            _grant_read_execute(resolved, ctx.sid_text, recursive=True)
            granted_recursive.append(resolved)

        result["acl_ancestor_grants"] = [str(p) for p in granted_ancestors]
        result["acl_toolchain_grants"] = [str(p) for p in granted_recursive]

        # Production Forge will launch the validated toolchain executable
        # directly, not through PowerShell. Probe that exact primitive as well
        # as the richer child-orchestration run below.
        python_direct = _direct_appcontainer_run(
            ctx,
            executable=python,
            args=("--version",),
            python=python,
            dart=dart,
        )
        dart_direct = _direct_appcontainer_run(
            ctx,
            executable=dart,
            args=("--version",),
            python=python,
            dart=dart,
        )
        result["direct_smoke"] = {
            "python": python_direct,
            "dart": dart_direct,
        }
        direct_smoke_ok = all(
            item.get("created") is True
            and item.get("appcontainer_token") is True
            and item.get("timed_out") is False
            and item.get("exit_code") == 0
            for item in (python_direct, dart_direct)
        )
        result["direct_smoke_ok"] = direct_smoke_ok

        job = ctx._new_job(
            flags=(
                isolation.JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
                | isolation.JOB_OBJECT_LIMIT_ACTIVE_PROCESS
                | isolation.JOB_OBJECT_LIMIT_PROCESS_MEMORY
                | isolation.JOB_OBJECT_LIMIT_JOB_MEMORY
            ),
            active_process_limit=64,
            process_memory=4 * 1024 * 1024 * 1024,
            job_memory=8 * 1024 * 1024 * 1024,
        )

        script = _toolchain_script(
            ctx.workspace,
            python,
            dart,
            result_file,
            ctx.appcontainer_local,
        )
        started = time.monotonic()
        pi = ctx._start(script, job)
        wait, exit_code = resource_probe._wait_exit(pi, 180_000)
        elapsed = time.monotonic() - started

        result["elapsed_seconds"] = round(elapsed, 3)
        result["process_exit_code"] = exit_code

        if wait == isolation.WAIT_TIMEOUT:
            isolation.kernel32.TerminateJobObject(job, 124)
            raise RuntimeError("toolchain probe timed out")
        if wait != isolation.WAIT_OBJECT_0:
            raise RuntimeError(f"unexpected toolchain wait result: {wait}")

        resource_probe._close_pi(pi)
        isolation.kernel32.CloseHandle(job)

        if not result_file.is_file():
            logs = {}
            for name in (
                "python-smoke.log",
                "dart-smoke.log",
                "python-test.log",
                "python-build.log",
                "python-runtime.log",
                "dart-test.log",
                "dart-analyze.log",
                "dart-runtime.log",
                "dart-vm-test.log",
                "dart-vm-build.log",
                "dart-vm-runtime.log",
            ):
                path = ctx.workspace / name
                if path.is_file():
                    logs[name] = _clean_log_text(
                        path.read_text(encoding="utf-8", errors="replace")
                    )[-4000:]
            result["logs"] = logs
            raise RuntimeError("toolchain child did not produce result JSON")

        assertions = json.loads(result_file.read_text(encoding="utf-8-sig"))
        result["assertions"] = assertions

        logs = {}
        for name in (
            "python-smoke.log",
            "dart-smoke.log",
            "python-test.log",
            "python-build.log",
            "python-runtime.log",
            "dart-test.log",
            "dart-analyze.log",
            "dart-runtime.log",
            "dart-vm-test.log",
            "dart-vm-build.log",
            "dart-vm-runtime.log",
        ):
            path = ctx.workspace / name
            if path.is_file():
                logs[name] = _clean_log_text(
                    path.read_text(encoding="utf-8", errors="replace")
                )[-2000:]
        result["logs"] = logs

        required = (
            "host_secret_absent",
            "python_visible",
            "dart_visible",
            "python_smoke",
            "dart_smoke",
            "python_test",
            "python_build",
            "python_runtime",
            "dart_vm_test",
            "dart_vm_build",
            "dart_vm_runtime",
        )
        result["dartdev_cli_compatible"] = all(
            assertions.get(name) is True
            for name in ("dart_test", "dart_analyze", "dart_runtime")
        )
        result["appcontainer_safe_dart_route"] = all(
            assertions.get(name) is True
            for name in ("dart_vm_test", "dart_vm_build", "dart_vm_runtime")
        )

        failed = [name for name in required if assertions.get(name) is not True]
        # The PowerShell orchestrator intentionally still exits 7 when dartdev
        # itself fails, so do not use its aggregate exit code as the Stage-4
        # verdict. The per-command evidence above is authoritative here.
        if failed or not direct_smoke_ok:
            pieces: list[str] = []
            if failed:
                pieces.append(", ".join(failed))
            if exit_code != 0:
                pieces.append(f"orchestrator_exit={exit_code} (diagnostic only)")
            if not direct_smoke_ok:
                pieces.append("direct_smoke")
            raise RuntimeError("toolchain assertions failed: " + "; ".join(pieces))

        result["ok"] = True

    except Exception as exc:
        result["error"] = str(exc)

    finally:
        cleanup_errors: list[str] = []
        if ctx is not None:
            for root in reversed(granted_recursive):
                try:
                    _remove_sid_acl(root, ctx.sid_text, recursive=True)
                except Exception as exc:
                    cleanup_errors.append(str(exc))
            for ancestor in reversed(granted_ancestors):
                try:
                    _remove_sid_acl(ancestor, ctx.sid_text, recursive=False)
                except Exception as exc:
                    cleanup_errors.append(str(exc))
            try:
                ctx.close()
            except Exception as exc:
                cleanup_errors.append(f"context cleanup: {exc}")

        for name, value in saved.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value

        result["acl_cleanup"] = not cleanup_errors
        if cleanup_errors:
            result["cleanup_errors"] = cleanup_errors
            result["ok"] = False

    _emit_json(result)
    return 0 if result.get("ok") is True else 1


if __name__ == "__main__":
    raise SystemExit(main())
