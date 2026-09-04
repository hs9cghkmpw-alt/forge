#!/usr/bin/env python3
"""Windows AppContainer + Job Object capability probe for TD110.

This is a *probe*, not the production Sandbox backend.

It proves only the first prerequisites on a real Windows machine:

1. Forge can create a per-user AppContainer profile with no capabilities.
2. A harmless Win32 process can be launched with an AppContainer token.
3. The process can be placed in a Job Object before it executes.
4. The Job Object can enforce bounded process/memory lifetime controls.

It does NOT yet prove the full TD110 contract:
network denial, workspace-only file access, secret isolation, toolchain support,
CPU enforcement, escape-corpus coverage, or Self-Extension promotion/reuse.

The script uses only Python stdlib ctypes and Windows APIs.  It must fail closed:
any missing/failed isolation primitive exits non-zero.
"""

from __future__ import annotations

import ctypes
from ctypes import wintypes
import json
import os
import platform
import sys
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
INFINITE = 0xFFFFFFFF

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
    _fields_ = [
        ("Sid", PSID),
        ("Attributes", DWORD),
    ]


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


# API signatures
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

advapi32.FreeSid.argtypes = [PSID]
advapi32.FreeSid.restype = LPVOID

kernel32.InitializeProcThreadAttributeList.argtypes = [
    LPVOID,
    DWORD,
    DWORD,
    ctypes.POINTER(SIZE_T),
]
kernel32.InitializeProcThreadAttributeList.restype = BOOL

kernel32.UpdateProcThreadAttribute.argtypes = [
    LPVOID,
    DWORD,
    SIZE_T,
    LPVOID,
    SIZE_T,
    LPVOID,
    ctypes.POINTER(SIZE_T),
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

kernel32.SetInformationJobObject.argtypes = [
    HANDLE,
    ctypes.c_int,
    LPVOID,
    DWORD,
]
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
    HANDLE,
    ctypes.c_int,
    LPVOID,
    DWORD,
    ctypes.POINTER(DWORD),
]
advapi32.GetTokenInformation.restype = BOOL


def _hresult_failed(hr: int) -> bool:
    return hr < 0


def main() -> int:
    moniker = f"Forge.TD110.Probe.{uuid.uuid4().hex}"
    sid = PSID()
    attr_buffer = None
    attr_list = None
    job = HANDLE()
    pi = PROCESS_INFORMATION()
    token = HANDLE()
    profile_created = False

    result: dict[str, object] = {
        "ok": False,
        "platform": platform.platform(),
        "moniker": moniker,
        "profile_created": False,
        "appcontainer_token": False,
        "job_created": False,
        "job_assigned": False,
        "process_resumed": False,
        "process_exit_code": None,
    }

    try:
        hr = int(
            userenv.CreateAppContainerProfile(
                moniker,
                "Forge TD110 Probe",
                "Temporary Forge AppContainer capability probe",
                None,
                0,
                ctypes.byref(sid),
            )
        )
        if _hresult_failed(hr):
            raise RuntimeError(f"CreateAppContainerProfile failed: HRESULT=0x{hr & 0xFFFFFFFF:08X}")
        profile_created = True
        result["profile_created"] = True

        # Build the extended startup attribute containing the AppContainer SID.
        attr_size = SIZE_T(0)
        ctypes.set_last_error(0)
        first = kernel32.InitializeProcThreadAttributeList(
            None, 1, 0, ctypes.byref(attr_size)
        )
        if first:
            raise RuntimeError("InitializeProcThreadAttributeList sizing unexpectedly succeeded")
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

        # Create a bounded Job Object first.  The child is created suspended, then
        # assigned to this Job before a single instruction of its command runs.
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

        executable = os.path.join(os.environ["SystemRoot"], "System32", "cmd.exe")
        command_line = ctypes.create_unicode_buffer(
            f'"{executable}" /d /s /c "exit /b 0"'
        )

        si = STARTUPINFOEXW()
        si.StartupInfo.cb = ctypes.sizeof(si)
        si.lpAttributeList = attr_list

        creation_flags = (
            CREATE_SUSPENDED
            | CREATE_UNICODE_ENVIRONMENT
            | EXTENDED_STARTUPINFO_PRESENT
        )

        if not kernel32.CreateProcessW(
            executable,
            command_line,
            None,
            None,
            False,
            creation_flags,
            None,
            os.path.dirname(executable),
            ctypes.byref(si.StartupInfo),
            ctypes.byref(pi),
        ):
            raise _winerror("CreateProcessW(AppContainer)")

        # Verify the OS token itself says this process is inside an AppContainer.
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

        wait = kernel32.WaitForSingleObject(pi.hProcess, 10_000)
        if wait == WAIT_TIMEOUT:
            kernel32.TerminateJobObject(job, 124)
            raise RuntimeError("probe process timed out")
        if wait != WAIT_OBJECT_0:
            raise _winerror("WaitForSingleObject")

        exit_code = DWORD(0)
        if not kernel32.GetExitCodeProcess(pi.hProcess, ctypes.byref(exit_code)):
            raise _winerror("GetExitCodeProcess")
        result["process_exit_code"] = int(exit_code.value)
        if exit_code.value != 0:
            raise RuntimeError(f"probe process exited with {exit_code.value}")

        result["ok"] = True
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    except Exception as exc:
        result["error"] = str(exc)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 1

    finally:
        if token:
            kernel32.CloseHandle(token)
        if pi.hThread:
            kernel32.CloseHandle(pi.hThread)
        if pi.hProcess:
            kernel32.CloseHandle(pi.hProcess)
        if job:
            # KILL_ON_JOB_CLOSE ensures any surviving descendants are terminated.
            kernel32.CloseHandle(job)
        if attr_list:
            kernel32.DeleteProcThreadAttributeList(attr_list)
        if sid:
            advapi32.FreeSid(sid)
        if profile_created:
            # The probe profile is disposable.  Failure to delete is not allowed to
            # turn a failed isolation probe into a pass, but cleanup itself happens
            # after the result has already been determined.
            userenv.DeleteAppContainerProfile(moniker)


if __name__ == "__main__":
    raise SystemExit(main())
