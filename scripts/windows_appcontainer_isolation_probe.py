#!/usr/bin/env python3
"""TD110 Windows AppContainer isolation probe (stage 2).

This is still a probe, not the production Forge sandbox backend.

It verifies on a real Windows machine that an AppContainer with no capabilities
can be given explicit access to one temporary workspace while remaining denied
from a sibling host file and from outbound network access.

It also verifies that:
- the child receives a minimal environment rather than the host environment;
- the child is assigned to a bounded Job Object before it is resumed;
- harmless work inside the granted workspace succeeds.

The probe is deliberately fail-closed: every security assertion must be observed
as true or the process exits non-zero.

No third-party Python package is required.
"""

from __future__ import annotations

import base64
import ctypes
from ctypes import wintypes
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import tempfile
import uuid


if platform.system() != "Windows":
    print(json.dumps({"ok": False, "error": "windows-only probe"}, ensure_ascii=False))
    raise SystemExit(2)


kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
advapi32 = ctypes.WinDLL("advapi32", use_last_error=True)
userenv = ctypes.WinDLL("userenv", use_last_error=True)

DWORD = wintypes.DWORD
WORD = wintypes.WORD
BOOL = wintypes.BOOL
HANDLE = wintypes.HANDLE
LPVOID = wintypes.LPVOID
SIZE_T = ctypes.c_size_t
ULONG_PTR = ctypes.c_size_t
HRESULT = ctypes.c_long
PSID = ctypes.c_void_p
LPBYTE = ctypes.POINTER(ctypes.c_ubyte)

ERROR_INSUFFICIENT_BUFFER = 122
WAIT_OBJECT_0 = 0x00000000
WAIT_TIMEOUT = 0x00000102

CREATE_SUSPENDED = 0x00000004
CREATE_UNICODE_ENVIRONMENT = 0x00000400
EXTENDED_STARTUPINFO_PRESENT = 0x00080000

PROC_THREAD_ATTRIBUTE_SECURITY_CAPABILITIES = 0x00020009

TOKEN_QUERY = 0x0008
TOKEN_IS_APP_CONTAINER = 29

JOB_OBJECT_LIMIT_ACTIVE_PROCESS = 0x00000008
JOB_OBJECT_LIMIT_PROCESS_MEMORY = 0x00000100
JOB_OBJECT_LIMIT_JOB_MEMORY = 0x00000200
JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x00002000
JOB_OBJECT_EXTENDED_LIMIT_INFORMATION_CLASS = 9


class SID_AND_ATTRIBUTES(ctypes.Structure):
    _fields_ = [("Sid", PSID), ("Attributes", DWORD)]


class SECURITY_CAPABILITIES(ctypes.Structure):
    _fields_ = [
        ("AppContainerSid", PSID),
        ("Capabilities", ctypes.POINTER(SID_AND_ATTRIBUTES)),
        ("CapabilityCount", DWORD),
        ("Reserved", DWORD),
    ]


class STARTUPINFOW(ctypes.Structure):
    _fields_ = [
        ("cb", DWORD),
        ("lpReserved", wintypes.LPWSTR),
        ("lpDesktop", wintypes.LPWSTR),
        ("lpTitle", wintypes.LPWSTR),
        ("dwX", DWORD),
        ("dwY", DWORD),
        ("dwXSize", DWORD),
        ("dwYSize", DWORD),
        ("dwXCountChars", DWORD),
        ("dwYCountChars", DWORD),
        ("dwFillAttribute", DWORD),
        ("dwFlags", DWORD),
        ("wShowWindow", WORD),
        ("cbReserved2", WORD),
        ("lpReserved2", LPBYTE),
        ("hStdInput", HANDLE),
        ("hStdOutput", HANDLE),
        ("hStdError", HANDLE),
    ]


class STARTUPINFOEXW(ctypes.Structure):
    _fields_ = [
        ("StartupInfo", STARTUPINFOW),
        ("lpAttributeList", LPVOID),
    ]


class PROCESS_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("hProcess", HANDLE),
        ("hThread", HANDLE),
        ("dwProcessId", DWORD),
        ("dwThreadId", DWORD),
    ]


class IO_COUNTERS(ctypes.Structure):
    _fields_ = [
        ("ReadOperationCount", ctypes.c_ulonglong),
        ("WriteOperationCount", ctypes.c_ulonglong),
        ("OtherOperationCount", ctypes.c_ulonglong),
        ("ReadTransferCount", ctypes.c_ulonglong),
        ("WriteTransferCount", ctypes.c_ulonglong),
        ("OtherTransferCount", ctypes.c_ulonglong),
    ]


class JOBOBJECT_BASIC_LIMIT_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("PerProcessUserTimeLimit", ctypes.c_longlong),
        ("PerJobUserTimeLimit", ctypes.c_longlong),
        ("LimitFlags", DWORD),
        ("MinimumWorkingSetSize", SIZE_T),
        ("MaximumWorkingSetSize", SIZE_T),
        ("ActiveProcessLimit", DWORD),
        ("Affinity", ULONG_PTR),
        ("PriorityClass", DWORD),
        ("SchedulingClass", DWORD),
    ]


class JOBOBJECT_EXTENDED_LIMIT_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("BasicLimitInformation", JOBOBJECT_BASIC_LIMIT_INFORMATION),
        ("IoInfo", IO_COUNTERS),
        ("ProcessMemoryLimit", SIZE_T),
        ("JobMemoryLimit", SIZE_T),
        ("PeakProcessMemoryUsed", SIZE_T),
        ("PeakJobMemoryUsed", SIZE_T),
    ]


def _winerror(label: str) -> RuntimeError:
    code = ctypes.get_last_error()
    return RuntimeError(f"{label} failed: winerror={code} ({ctypes.FormatError(code).strip()})")


userenv.CreateAppContainerProfile.argtypes = [
    wintypes.LPCWSTR,
    wintypes.LPCWSTR,
    wintypes.LPCWSTR,
    ctypes.POINTER(SID_AND_ATTRIBUTES),
    DWORD,
    ctypes.POINTER(PSID),
]
userenv.CreateAppContainerProfile.restype = HRESULT

userenv.DeleteAppContainerProfile.argtypes = [wintypes.LPCWSTR]
userenv.DeleteAppContainerProfile.restype = HRESULT

advapi32.ConvertSidToStringSidW.argtypes = [PSID, ctypes.POINTER(wintypes.LPWSTR)]
advapi32.ConvertSidToStringSidW.restype = BOOL

advapi32.FreeSid.argtypes = [PSID]
advapi32.FreeSid.restype = LPVOID

kernel32.LocalFree.argtypes = [LPVOID]
kernel32.LocalFree.restype = LPVOID

kernel32.InitializeProcThreadAttributeList.argtypes = [
    LPVOID, DWORD, DWORD, ctypes.POINTER(SIZE_T)
]
kernel32.InitializeProcThreadAttributeList.restype = BOOL

kernel32.UpdateProcThreadAttribute.argtypes = [
    LPVOID, DWORD, SIZE_T, LPVOID, SIZE_T, LPVOID, ctypes.POINTER(SIZE_T)
]
kernel32.UpdateProcThreadAttribute.restype = BOOL

kernel32.DeleteProcThreadAttributeList.argtypes = [LPVOID]
kernel32.DeleteProcThreadAttributeList.restype = None

kernel32.CreateProcessW.argtypes = [
    wintypes.LPCWSTR,
    wintypes.LPWSTR,
    LPVOID,
    LPVOID,
    BOOL,
    DWORD,
    LPVOID,
    wintypes.LPCWSTR,
    ctypes.POINTER(STARTUPINFOW),
    ctypes.POINTER(PROCESS_INFORMATION),
]
kernel32.CreateProcessW.restype = BOOL

kernel32.CreateJobObjectW.argtypes = [LPVOID, wintypes.LPCWSTR]
kernel32.CreateJobObjectW.restype = HANDLE

kernel32.SetInformationJobObject.argtypes = [HANDLE, ctypes.c_int, LPVOID, DWORD]
kernel32.SetInformationJobObject.restype = BOOL

kernel32.AssignProcessToJobObject.argtypes = [HANDLE, HANDLE]
kernel32.AssignProcessToJobObject.restype = BOOL

kernel32.TerminateJobObject.argtypes = [HANDLE, wintypes.UINT]
kernel32.TerminateJobObject.restype = BOOL

kernel32.ResumeThread.argtypes = [HANDLE]
kernel32.ResumeThread.restype = DWORD

kernel32.WaitForSingleObject.argtypes = [HANDLE, DWORD]
kernel32.WaitForSingleObject.restype = DWORD

kernel32.GetExitCodeProcess.argtypes = [HANDLE, ctypes.POINTER(DWORD)]
kernel32.GetExitCodeProcess.restype = BOOL

kernel32.CloseHandle.argtypes = [HANDLE]
kernel32.CloseHandle.restype = BOOL

advapi32.OpenProcessToken.argtypes = [HANDLE, DWORD, ctypes.POINTER(HANDLE)]
advapi32.OpenProcessToken.restype = BOOL

advapi32.GetTokenInformation.argtypes = [
    HANDLE, ctypes.c_int, LPVOID, DWORD, ctypes.POINTER(DWORD)
]
advapi32.GetTokenInformation.restype = BOOL


def _hresult_failed(hr: int) -> bool:
    return hr < 0


def _sid_string(sid: PSID) -> str:
    value = wintypes.LPWSTR()
    if not advapi32.ConvertSidToStringSidW(sid, ctypes.byref(value)):
        raise _winerror("ConvertSidToStringSidW")
    try:
        return value.value
    finally:
        kernel32.LocalFree(ctypes.cast(value, LPVOID))


def _grant_workspace(workspace: Path, sid_text: str) -> None:
    """Grant only this AppContainer SID modify access to the temporary workspace."""
    icacls = shutil.which("icacls.exe") or os.path.join(
        os.environ["SystemRoot"], "System32", "icacls.exe"
    )
    completed = subprocess.run(
        [
            icacls,
            str(workspace),
            "/grant",
            f"*{sid_text}:(OI)(CI)M",
            "/T",
            "/C",
            "/Q",
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            "icacls grant failed: "
            f"exit={completed.returncode} stdout={completed.stdout!r} stderr={completed.stderr!r}"
        )


def _minimal_environment(workspace: Path) -> ctypes.Array:
    system_root = os.environ["SystemRoot"]
    env = {
        "SystemRoot": system_root,
        "WINDIR": system_root,
        "ComSpec": os.path.join(system_root, "System32", "cmd.exe"),
        "PATH": (
            os.path.join(system_root, "System32")
            + ";"
            + os.path.join(system_root, "System32", "WindowsPowerShell", "v1.0")
        ),
        "TEMP": str(workspace),
        "TMP": str(workspace),
        "FORGE_PROBE_VISIBLE": "yes",
    }
    block = "\0".join(f"{k}={v}" for k, v in sorted(env.items())) + "\0\0"
    return ctypes.create_unicode_buffer(block)


def _encoded_powershell_command(
    workspace: Path,
    outside_file: Path,
    result_file: Path,
) -> str:
    w = str(workspace).replace("'", "''")
    outside = str(outside_file).replace("'", "''")
    result = str(result_file).replace("'", "''")

    script = rf"""
$ErrorActionPreference = 'Stop'
$probe = [ordered]@{{
  inside_write = $false
  outside_read_blocked = $false
  network_blocked = $false
  host_secret_absent = $false
  minimal_env = $false
  child_spawned = $false
}}

try {{
  Set-Content -LiteralPath '{w}\inside.txt' -Value 'inside-ok' -Encoding UTF8
  $probe.inside_write = (Test-Path -LiteralPath '{w}\inside.txt')
}} catch {{
  $probe.inside_write = $false
}}

try {{
  [void](Get-Content -LiteralPath '{outside}' -ErrorAction Stop)
  $probe.outside_read_blocked = $false
}} catch {{
  $probe.outside_read_blocked = $true
}}

try {{
  $client = New-Object System.Net.Sockets.TcpClient
  $iar = $client.BeginConnect('1.1.1.1', 80, $null, $null)
  if (-not $iar.AsyncWaitHandle.WaitOne(3000, $false)) {{
    $client.Close()
    throw 'connect-timeout'
  }}
  $client.EndConnect($iar)
  $client.Close()
  $probe.network_blocked = $false
}} catch {{
  $probe.network_blocked = $true
}}

$probe.host_secret_absent = [string]::IsNullOrEmpty($env:FORGE_TD110_SECRET)
$names = @(Get-ChildItem Env: | ForEach-Object {{ $_.Name }})
$probe.minimal_env = (
  $names.Count -le 12 -and
  $names -notcontains 'FORGE_TD110_SECRET' -and
  $env:FORGE_PROBE_VISIBLE -eq 'yes'
)

try {{
  $p = Start-Process -FilePath "$env:SystemRoot\System32\cmd.exe" `
      -ArgumentList '/d','/s','/c','exit /b 0' `
      -Wait -PassThru -WindowStyle Hidden
  $probe.child_spawned = ($p.ExitCode -eq 0)
}} catch {{
  $probe.child_spawned = $false
}}

$probe | ConvertTo-Json -Compress | Set-Content -LiteralPath '{result}' -Encoding UTF8
"""
    return base64.b64encode(script.encode("utf-16le")).decode("ascii")


def main() -> int:
    moniker = f"Forge.TD110.IsolationProbe.{uuid.uuid4().hex}"
    sid = PSID()
    attr_buffer = None
    attr_list = None
    job = HANDLE()
    pi = PROCESS_INFORMATION()
    token = HANDLE()
    profile_created = False
    tmp_root = None

    result: dict[str, object] = {
        "ok": False,
        "platform": platform.platform(),
        "moniker": moniker,
        "profile_created": False,
        "appcontainer_token": False,
        "workspace_acl_granted": False,
        "job_created": False,
        "job_assigned": False,
        "process_resumed": False,
        "process_exit_code": None,
        "assertions": {},
    }

    saved_secret = os.environ.get("FORGE_TD110_SECRET")
    os.environ["FORGE_TD110_SECRET"] = "must-not-reach-appcontainer"

    try:
        tmp_root = tempfile.TemporaryDirectory(prefix="forge-td110-")
        root = Path(tmp_root.name)
        workspace = root / "workspace"
        workspace.mkdir()
        outside_file = root / "outside-secret.txt"
        outside_file.write_text("host-only-sentinel", encoding="utf-8")
        result_file = workspace / "probe-result.json"

        hr = int(
            userenv.CreateAppContainerProfile(
                moniker,
                "Forge TD110 Isolation Probe",
                "Temporary Forge AppContainer isolation probe",
                None,
                0,
                ctypes.byref(sid),
            )
        )
        if _hresult_failed(hr):
            raise RuntimeError(
                f"CreateAppContainerProfile failed: HRESULT=0x{hr & 0xFFFFFFFF:08X}"
            )
        profile_created = True
        result["profile_created"] = True

        sid_text = _sid_string(sid)
        result["appcontainer_sid"] = sid_text
        _grant_workspace(workspace, sid_text)
        result["workspace_acl_granted"] = True

        attr_size = SIZE_T(0)
        ctypes.set_last_error(0)
        first = kernel32.InitializeProcThreadAttributeList(
            None, 1, 0, ctypes.byref(attr_size)
        )
        if first:
            raise RuntimeError(
                "InitializeProcThreadAttributeList sizing unexpectedly succeeded"
            )
        if ctypes.get_last_error() != ERROR_INSUFFICIENT_BUFFER:
            raise _winerror("InitializeProcThreadAttributeList(size)")

        attr_buffer = ctypes.create_string_buffer(attr_size.value)
        attr_list = ctypes.cast(attr_buffer, LPVOID)
        if not kernel32.InitializeProcThreadAttributeList(
            attr_list, 1, 0, ctypes.byref(attr_size)
        ):
            raise _winerror("InitializeProcThreadAttributeList")

        security_capabilities = SECURITY_CAPABILITIES(
            AppContainerSid=sid,
            Capabilities=None,
            CapabilityCount=0,
            Reserved=0,
        )
        if not kernel32.UpdateProcThreadAttribute(
            attr_list,
            0,
            SIZE_T(PROC_THREAD_ATTRIBUTE_SECURITY_CAPABILITIES),
            ctypes.byref(security_capabilities),
            ctypes.sizeof(security_capabilities),
            None,
            None,
        ):
            raise _winerror("UpdateProcThreadAttribute(SECURITY_CAPABILITIES)")

        job = kernel32.CreateJobObjectW(None, None)
        if not job:
            raise _winerror("CreateJobObjectW")
        result["job_created"] = True

        limits = JOBOBJECT_EXTENDED_LIMIT_INFORMATION()
        limits.BasicLimitInformation.LimitFlags = (
            JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
            | JOB_OBJECT_LIMIT_ACTIVE_PROCESS
            | JOB_OBJECT_LIMIT_PROCESS_MEMORY
            | JOB_OBJECT_LIMIT_JOB_MEMORY
        )
        limits.BasicLimitInformation.ActiveProcessLimit = 8
        limits.ProcessMemoryLimit = 512 * 1024 * 1024
        limits.JobMemoryLimit = 1024 * 1024 * 1024
        if not kernel32.SetInformationJobObject(
            job,
            JOB_OBJECT_EXTENDED_LIMIT_INFORMATION_CLASS,
            ctypes.byref(limits),
            ctypes.sizeof(limits),
        ):
            raise _winerror("SetInformationJobObject")

        powershell = os.path.join(
            os.environ["SystemRoot"],
            "System32",
            "WindowsPowerShell",
            "v1.0",
            "powershell.exe",
        )
        encoded = _encoded_powershell_command(workspace, outside_file, result_file)
        command_line = ctypes.create_unicode_buffer(
            f'"{powershell}" -NoLogo -NoProfile -NonInteractive '
            f'-ExecutionPolicy Bypass -EncodedCommand {encoded}'
        )

        si = STARTUPINFOEXW()
        si.StartupInfo.cb = ctypes.sizeof(si)
        si.lpAttributeList = attr_list
        env_block = _minimal_environment(workspace)

        if not kernel32.CreateProcessW(
            powershell,
            command_line,
            None,
            None,
            False,
            CREATE_SUSPENDED | CREATE_UNICODE_ENVIRONMENT | EXTENDED_STARTUPINFO_PRESENT,
            ctypes.cast(env_block, LPVOID),
            str(workspace),
            ctypes.byref(si.StartupInfo),
            ctypes.byref(pi),
        ):
            raise _winerror("CreateProcessW(AppContainer PowerShell)")

        if not advapi32.OpenProcessToken(pi.hProcess, TOKEN_QUERY, ctypes.byref(token)):
            raise _winerror("OpenProcessToken")
        is_appcontainer = DWORD(0)
        returned = DWORD(0)
        if not advapi32.GetTokenInformation(
            token,
            TOKEN_IS_APP_CONTAINER,
            ctypes.byref(is_appcontainer),
            ctypes.sizeof(is_appcontainer),
            ctypes.byref(returned),
        ):
            raise _winerror("GetTokenInformation(TokenIsAppContainer)")
        result["appcontainer_token"] = bool(is_appcontainer.value)
        if not is_appcontainer.value:
            raise RuntimeError("child token is NOT an AppContainer token")

        if not kernel32.AssignProcessToJobObject(job, pi.hProcess):
            raise _winerror("AssignProcessToJobObject")
        result["job_assigned"] = True

        previous_suspend_count = kernel32.ResumeThread(pi.hThread)
        if previous_suspend_count == 0xFFFFFFFF:
            raise _winerror("ResumeThread")
        result["process_resumed"] = True

        wait = kernel32.WaitForSingleObject(pi.hProcess, 20_000)
        if wait == WAIT_TIMEOUT:
            kernel32.TerminateJobObject(job, 124)
            raise RuntimeError("isolation probe timed out")
        if wait != WAIT_OBJECT_0:
            raise _winerror("WaitForSingleObject")

        exit_code = DWORD(0)
        if not kernel32.GetExitCodeProcess(pi.hProcess, ctypes.byref(exit_code)):
            raise _winerror("GetExitCodeProcess")
        result["process_exit_code"] = int(exit_code.value)
        if exit_code.value != 0:
            raise RuntimeError(f"probe process exited with {exit_code.value}")

        if not result_file.is_file():
            raise RuntimeError("AppContainer child did not produce probe-result.json")
        raw = result_file.read_text(encoding="utf-8-sig")
        assertions = json.loads(raw)
        result["assertions"] = assertions

        required_true = (
            "inside_write",
            "outside_read_blocked",
            "network_blocked",
            "host_secret_absent",
            "minimal_env",
            "child_spawned",
        )
        failed = [name for name in required_true if assertions.get(name) is not True]
        if failed:
            raise RuntimeError("security assertions failed: " + ", ".join(failed))

        result["ok"] = True
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    except Exception as exc:
        result["error"] = str(exc)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 1

    finally:
        if saved_secret is None:
            os.environ.pop("FORGE_TD110_SECRET", None)
        else:
            os.environ["FORGE_TD110_SECRET"] = saved_secret

        if token:
            kernel32.CloseHandle(token)
        if pi.hThread:
            kernel32.CloseHandle(pi.hThread)
        if pi.hProcess:
            kernel32.CloseHandle(pi.hProcess)
        if job:
            kernel32.CloseHandle(job)
        if attr_list:
            kernel32.DeleteProcThreadAttributeList(attr_list)
        if sid:
            advapi32.FreeSid(sid)
        if profile_created:
            userenv.DeleteAppContainerProfile(moniker)
        if tmp_root is not None:
            tmp_root.cleanup()


if __name__ == "__main__":
    raise SystemExit(main())
