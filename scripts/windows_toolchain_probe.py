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


def _grant_read_execute(path: Path, sid_text: str) -> None:
    if not path.exists():
        raise RuntimeError(f"toolchain path does not exist: {path}")
    completed = _run_icacls(
        [
            str(path),
            "/grant",
            f"*{sid_text}:(OI)(CI)RX",
            "/T",
            "/C",
            "/Q",
        ]
    )
    if completed.returncode != 0:
        raise RuntimeError(
            "icacls RX grant failed: "
            f"path={path} exit={completed.returncode} "
            f"stdout={completed.stdout!r} stderr={completed.stderr!r}"
        )


def _remove_sid_acl(path: Path, sid_text: str) -> None:
    completed = _run_icacls(
        [
            str(path),
            "/remove",
            f"*{sid_text}",
            "/T",
            "/C",
            "/Q",
        ]
    )
    if completed.returncode != 0:
        raise RuntimeError(
            "icacls SID cleanup failed: "
            f"path={path} exit={completed.returncode} "
            f"stdout={completed.stdout!r} stderr={completed.stderr!r}"
        )


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


def _ps_quote(value: str) -> str:
    return value.replace("'", "''")


def _toolchain_script(
    workspace: Path,
    python: Path,
    dart: Path,
    result_file: Path,
) -> str:
    w = _ps_quote(str(workspace))
    py = _ps_quote(str(python))
    dart_exe = _ps_quote(str(dart))
    result = _ps_quote(str(result_file))

    return rf"""
$ErrorActionPreference = 'Continue'

$privateHome = Join-Path '{w}' '.sandbox-home'
$privateRoaming = Join-Path $privateHome 'AppData\Roaming'
$privateLocal = Join-Path $privateHome 'AppData\Local'
$privateTmp = Join-Path '{w}' '.sandbox-tmp'
New-Item -ItemType Directory -Force -Path $privateRoaming | Out-Null
New-Item -ItemType Directory -Force -Path $privateLocal | Out-Null
New-Item -ItemType Directory -Force -Path $privateTmp | Out-Null

$env:HOME = $privateHome
$env:USERPROFILE = $privateHome
$env:APPDATA = $privateRoaming
$env:LOCALAPPDATA = $privateLocal
$env:TEMP = $privateTmp
$env:TMP = $privateTmp
$env:TMPDIR = $privateTmp
$env:PYTHONNOUSERSITE = '1'
$env:PYTHONSAFEPATH = '1'
$env:PYTHONPATH = '{w}'
$env:CI = 'true'
$env:FORGE_BUILD_SANDBOX = '1'

$probe = [ordered]@{{
  host_secret_absent = [string]::IsNullOrEmpty($env:OPENAI_API_KEY) -and
                       [string]::IsNullOrEmpty($env:GEMINI_API_KEY) -and
                       [string]::IsNullOrEmpty($env:ANTHROPIC_API_KEY)
  python_test = $false
  python_build = $false
  python_runtime = $false
  dart_test = $false
  dart_analyze = $false
  dart_runtime = $false
}}

& '{py}' test_extension.py *> python-test.log
$probe.python_test = ($LASTEXITCODE -eq 0)

& '{py}' -m compileall -q . *> python-build.log
$probe.python_build = ($LASTEXITCODE -eq 0)

& '{py}' runtime_probe.py *> python-runtime.log
$probe.python_runtime = ($LASTEXITCODE -eq 0)

& '{dart_exe}' run capability_test.dart *> dart-test.log
$probe.dart_test = ($LASTEXITCODE -eq 0)

& '{dart_exe}' analyze capability_impl.dart capability_test.dart probe.dart *> dart-analyze.log
$probe.dart_analyze = ($LASTEXITCODE -eq 0)

& '{dart_exe}' run probe.dart *> dart-runtime.log
$probe.dart_runtime = ($LASTEXITCODE -eq 0)

$probe | ConvertTo-Json -Compress | Set-Content -LiteralPath '{result}' -Encoding UTF8
if ($probe.python_test -and $probe.python_build -and $probe.python_runtime -and
    $probe.dart_test -and $probe.dart_analyze -and $probe.dart_runtime -and
    $probe.host_secret_absent) {{
  exit 0
}}
exit 7
"""


def main() -> int:
    ctx = None
    granted: list[Path] = []
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

        # Grant the ephemeral AppContainer SID only read/execute to the installed
        # toolchain files.  The generated workspace already has explicit modify.
        for root in (REPO_ROOT / ".venv", python_home, dart_sdk):
            resolved = root.resolve()
            if resolved in granted:
                continue
            _grant_read_execute(resolved, ctx.sid_text)
            granted.append(resolved)

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

        script = _toolchain_script(ctx.workspace, python, dart, result_file)
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
                "python-test.log",
                "python-build.log",
                "python-runtime.log",
                "dart-test.log",
                "dart-analyze.log",
                "dart-runtime.log",
            ):
                path = ctx.workspace / name
                if path.is_file():
                    logs[name] = path.read_text(encoding="utf-8", errors="replace")[-4000:]
            result["logs"] = logs
            raise RuntimeError("toolchain child did not produce result JSON")

        assertions = json.loads(result_file.read_text(encoding="utf-8-sig"))
        result["assertions"] = assertions

        logs = {}
        for name in (
            "python-test.log",
            "python-build.log",
            "python-runtime.log",
            "dart-test.log",
            "dart-analyze.log",
            "dart-runtime.log",
        ):
            path = ctx.workspace / name
            if path.is_file():
                logs[name] = path.read_text(encoding="utf-8", errors="replace")[-2000:]
        result["logs"] = logs

        required = (
            "host_secret_absent",
            "python_test",
            "python_build",
            "python_runtime",
            "dart_test",
            "dart_analyze",
            "dart_runtime",
        )
        failed = [name for name in required if assertions.get(name) is not True]
        if exit_code != 0 or failed:
            raise RuntimeError(
                "toolchain assertions failed: "
                + (", ".join(failed) if failed else f"exit={exit_code}")
            )

        result["ok"] = True

    except Exception as exc:
        result["error"] = str(exc)

    finally:
        cleanup_errors: list[str] = []
        if ctx is not None:
            for root in reversed(granted):
                try:
                    _remove_sid_acl(root, ctx.sid_text)
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

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("ok") is True else 1


if __name__ == "__main__":
    raise SystemExit(main())
