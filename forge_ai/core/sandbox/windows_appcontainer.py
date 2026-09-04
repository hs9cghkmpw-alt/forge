"""Windows AppContainer + Job Object sandbox backend (TD110).

This is the production Windows OS-isolation layer for generated BUILD_TIME code.

Security properties:
- no AppContainer capabilities: outbound network is denied by the OS;
- only the generated workspace receives Modify access;
- resolved Python/Dart toolchain roots receive temporary Read/Execute ACLs for
  one ephemeral AppContainer SID, then those ACEs are removed;
- AppContainer process creation happens suspended, then the process is assigned
  to a bounded Job Object before ResumeThread;
- Job Object enforces CPU time, process count, process/job memory and
  KILL_ON_JOB_CLOSE;
- host wall-clock timeout terminates the whole Job;
- workspace/output growth is monitored and terminates the Job on overflow;
- environment is rebuilt from the caller's already-scrubbed allow-list and
  AppContainer-specific LOCALAPPDATA/TEMP values;
- Windows Dart uses dartvm.exe + package: URIs.  This avoids the documented
  AppContainer incompatibility in Dart's VOLUME_NAME_DOS canonicalization while
  preserving multi-file generated source and a real kernel compilation gate.

The backend fails closed.  It never falls back to a normal subprocess after an
AppContainer setup/launch failure.
"""

from __future__ import annotations

import atexit
import ctypes
from ctypes import wintypes
from functools import lru_cache
import json
import msvcrt
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import threading
import time
import uuid


BACKEND_NAME = "windows-appcontainer+job"

# Win32 constants.
ERROR_INSUFFICIENT_BUFFER = 122
WAIT_OBJECT_0 = 0x00000000
WAIT_TIMEOUT = 0x00000102

CREATE_SUSPENDED = 0x00000004
CREATE_UNICODE_ENVIRONMENT = 0x00000400
EXTENDED_STARTUPINFO_PRESENT = 0x00080000
STARTF_USESTDHANDLES = 0x00000100

PROC_THREAD_ATTRIBUTE_SECURITY_CAPABILITIES = 0x00020009

TOKEN_QUERY = 0x0008
TOKEN_IS_APP_CONTAINER = 29

JOB_OBJECT_LIMIT_PROCESS_TIME = 0x00000002
JOB_OBJECT_LIMIT_JOB_TIME = 0x00000004
JOB_OBJECT_LIMIT_ACTIVE_PROCESS = 0x00000008
JOB_OBJECT_LIMIT_PROCESS_MEMORY = 0x00000100
JOB_OBJECT_LIMIT_JOB_MEMORY = 0x00000200
JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x00002000
JOB_OBJECT_EXTENDED_LIMIT_INFORMATION_CLASS = 9

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


class WindowsSandboxError(RuntimeError):
    """The Windows OS isolation boundary could not be established or preserved."""


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
    _fields_ = [("StartupInfo", STARTUPINFOW), ("lpAttributeList", LPVOID)]


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


class _Apis:
    def __init__(self) -> None:
        self.kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        self.advapi32 = ctypes.WinDLL("advapi32", use_last_error=True)
        self.userenv = ctypes.WinDLL("userenv", use_last_error=True)
        self.ole32 = ctypes.OleDLL("ole32")

        self.userenv.CreateAppContainerProfile.argtypes = [
            wintypes.LPCWSTR,
            wintypes.LPCWSTR,
            wintypes.LPCWSTR,
            ctypes.POINTER(SID_AND_ATTRIBUTES),
            DWORD,
            ctypes.POINTER(PSID),
        ]
        self.userenv.CreateAppContainerProfile.restype = HRESULT
        self.userenv.DeleteAppContainerProfile.argtypes = [wintypes.LPCWSTR]
        self.userenv.DeleteAppContainerProfile.restype = HRESULT
        self.userenv.GetAppContainerFolderPath.argtypes = [
            wintypes.LPCWSTR,
            ctypes.POINTER(wintypes.LPWSTR),
        ]
        self.userenv.GetAppContainerFolderPath.restype = HRESULT

        self.ole32.CoTaskMemFree.argtypes = [LPVOID]
        self.ole32.CoTaskMemFree.restype = None

        self.advapi32.ConvertSidToStringSidW.argtypes = [
            PSID,
            ctypes.POINTER(wintypes.LPWSTR),
        ]
        self.advapi32.ConvertSidToStringSidW.restype = BOOL
        self.advapi32.FreeSid.argtypes = [PSID]
        self.advapi32.FreeSid.restype = LPVOID
        self.advapi32.OpenProcessToken.argtypes = [
            HANDLE,
            DWORD,
            ctypes.POINTER(HANDLE),
        ]
        self.advapi32.OpenProcessToken.restype = BOOL
        self.advapi32.GetTokenInformation.argtypes = [
            HANDLE,
            ctypes.c_int,
            LPVOID,
            DWORD,
            ctypes.POINTER(DWORD),
        ]
        self.advapi32.GetTokenInformation.restype = BOOL

        self.kernel32.LocalFree.argtypes = [LPVOID]
        self.kernel32.LocalFree.restype = LPVOID
        self.kernel32.InitializeProcThreadAttributeList.argtypes = [
            LPVOID,
            DWORD,
            DWORD,
            ctypes.POINTER(SIZE_T),
        ]
        self.kernel32.InitializeProcThreadAttributeList.restype = BOOL
        self.kernel32.UpdateProcThreadAttribute.argtypes = [
            LPVOID,
            DWORD,
            SIZE_T,
            LPVOID,
            SIZE_T,
            LPVOID,
            ctypes.POINTER(SIZE_T),
        ]
        self.kernel32.UpdateProcThreadAttribute.restype = BOOL
        self.kernel32.DeleteProcThreadAttributeList.argtypes = [LPVOID]
        self.kernel32.DeleteProcThreadAttributeList.restype = None

        self.kernel32.CreateProcessW.argtypes = [
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
        self.kernel32.CreateProcessW.restype = BOOL
        self.kernel32.CreateJobObjectW.argtypes = [LPVOID, wintypes.LPCWSTR]
        self.kernel32.CreateJobObjectW.restype = HANDLE
        self.kernel32.SetInformationJobObject.argtypes = [
            HANDLE,
            ctypes.c_int,
            LPVOID,
            DWORD,
        ]
        self.kernel32.SetInformationJobObject.restype = BOOL
        self.kernel32.AssignProcessToJobObject.argtypes = [HANDLE, HANDLE]
        self.kernel32.AssignProcessToJobObject.restype = BOOL
        self.kernel32.TerminateJobObject.argtypes = [HANDLE, wintypes.UINT]
        self.kernel32.TerminateJobObject.restype = BOOL
        self.kernel32.ResumeThread.argtypes = [HANDLE]
        self.kernel32.ResumeThread.restype = DWORD
        self.kernel32.WaitForSingleObject.argtypes = [HANDLE, DWORD]
        self.kernel32.WaitForSingleObject.restype = DWORD
        self.kernel32.GetExitCodeProcess.argtypes = [HANDLE, ctypes.POINTER(DWORD)]
        self.kernel32.GetExitCodeProcess.restype = BOOL
        self.kernel32.CloseHandle.argtypes = [HANDLE]
        self.kernel32.CloseHandle.restype = BOOL


def _apis() -> _Apis:
    if os.name != "nt":
        raise WindowsSandboxError("Windows AppContainer backend requested on non-Windows")
    return _Apis()


def _hresult_failed(hr: int) -> bool:
    return hr < 0


def _winerror(label: str) -> WindowsSandboxError:
    code = ctypes.get_last_error()
    return WindowsSandboxError(
        f"{label} failed: winerror={code} ({ctypes.FormatError(code).strip()})"
    )


def _sid_string(api: _Apis, sid: PSID) -> str:
    value = wintypes.LPWSTR()
    if not api.advapi32.ConvertSidToStringSidW(sid, ctypes.byref(value)):
        raise _winerror("ConvertSidToStringSidW")
    try:
        return value.value
    finally:
        api.kernel32.LocalFree(ctypes.cast(value, LPVOID))


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


def _grant(path: Path, sid_text: str, permission: str, *, recursive: bool) -> None:
    if not path.exists():
        raise WindowsSandboxError(f"ACL target does not exist: {path}")
    ace = f"*{sid_text}:(OI)(CI){permission}" if recursive else f"*{sid_text}:{permission}"
    args = [str(path), "/grant", ace]
    if recursive:
        args.extend(["/T", "/C"])
    args.append("/Q")
    completed = _run_icacls(args)
    if completed.returncode != 0:
        raise WindowsSandboxError(
            "icacls grant failed: "
            f"path={path} recursive={recursive} exit={completed.returncode} "
            f"stdout={completed.stdout!r} stderr={completed.stderr!r}"
        )


def _remove_acl(path: Path, sid_text: str, *, recursive: bool) -> None:
    if not path.exists():
        return
    args = [str(path), "/remove", f"*{sid_text}"]
    if recursive:
        args.extend(["/T", "/C"])
    args.append("/Q")
    completed = _run_icacls(args)
    if completed.returncode != 0:
        raise WindowsSandboxError(
            "icacls cleanup failed: "
            f"path={path} recursive={recursive} exit={completed.returncode} "
            f"stdout={completed.stdout!r} stderr={completed.stderr!r}"
        )


def _ancestors(path: Path) -> tuple[Path, ...]:
    resolved = path.resolve()
    anchor = Path(resolved.anchor)
    values: list[Path] = []
    current = resolved.parent
    while current != anchor and current != current.parent:
        values.append(current)
        current = current.parent
    values.reverse()
    return tuple(values)


def _python_roots(executable: Path) -> tuple[Path, ...]:
    executable = executable.resolve()
    roots: list[Path] = []

    # venv layout: <venv>\Scripts\python.exe + <venv>\pyvenv.cfg
    if executable.parent.name.lower() == "scripts":
        venv = executable.parent.parent
        cfg = venv / "pyvenv.cfg"
        if cfg.is_file():
            roots.append(venv)
            for line in cfg.read_text(encoding="utf-8", errors="replace").splitlines():
                key, sep, value = line.partition("=")
                if sep and key.strip().lower() == "home":
                    home = Path(value.strip())
                    if home.exists():
                        roots.append(home)
                    break

    if not roots:
        roots.append(executable.parent)

    return tuple(dict.fromkeys(path.resolve() for path in roots))


def _dart_paths(executable: Path) -> tuple[Path, Path]:
    executable = executable.resolve()
    if executable.suffix.lower() in {".bat", ".cmd"}:
        # Flutter exposes dart through <flutter>\bin\dart.bat; the actual SDK
        # is cached under <flutter>\bin\cache\dart-sdk.
        flutter_root = executable.parent.parent
        sdk = flutter_root / "bin" / "cache" / "dart-sdk"
    else:
        sdk = executable.parent.parent
    dartvm = sdk / "bin" / "dartvm.exe"
    if not dartvm.is_file():
        raise WindowsSandboxError(f"Dart VM not found in resolved SDK: {dartvm}")
    return sdk.resolve(), dartvm.resolve()


def _environment_block(
    *,
    workspace: Path,
    appcontainer_local: Path,
    base_env: dict[str, str],
    executable_dirs: tuple[Path, ...],
) -> ctypes.Array:
    system_root = base_env.get("SYSTEMROOT") or base_env.get("SystemRoot") or os.environ["SystemRoot"]
    private_home = workspace / ".sandbox-home"
    private_roaming = private_home / "AppData" / "Roaming"
    private_home.mkdir(parents=True, exist_ok=True)
    private_roaming.mkdir(parents=True, exist_ok=True)

    container_temp = appcontainer_local / "Temp"
    container_temp.mkdir(parents=True, exist_ok=True)

    env: dict[str, str] = {}
    # The caller already scrubbed this mapping. Preserve only ordinary values,
    # then replace security-sensitive location variables with sandbox values.
    for name, value in base_env.items():
        if value is not None:
            env[str(name)] = str(value)

    path_parts = [str(path) for path in executable_dirs]
    for item in (
        os.path.join(system_root, "System32"),
        os.path.join(system_root, "System32", "WindowsPowerShell", "v1.0"),
    ):
        if item not in path_parts:
            path_parts.append(item)

    env.update(
        {
            "APPDATA": str(private_roaming),
            "CI": "true",
            "COMSPEC": os.path.join(system_root, "System32", "cmd.exe"),
            "FORGE_BUILD_SANDBOX": "1",
            "HOME": str(private_home),
            "LOCALAPPDATA": str(appcontainer_local),
            "PATH": ";".join(path_parts),
            "PYTHONNOUSERSITE": "1",
            "PYTHONPATH": str(workspace),
            "PYTHONSAFEPATH": "1",
            "SYSTEMROOT": system_root,
            "TEMP": str(container_temp),
            "TMP": str(container_temp),
            "TMPDIR": str(container_temp),
            "USERPROFILE": str(private_home),
            "WINDIR": system_root,
        }
    )

    drive = workspace.drive.upper()
    entries = [(f"={drive}", str(workspace)), *env.items()]
    entries.sort(key=lambda item: item[0].casefold())
    block = "\0".join(f"{name}={value}" for name, value in entries) + "\0\0"
    return ctypes.create_unicode_buffer(block)


def _package_config(workspace: Path, work_dir: Path) -> Path:
    path = work_dir / "package_config.json"
    root_uri = workspace.resolve().as_uri()
    if not root_uri.endswith("/"):
        root_uri += "/"
    path.write_text(
        json.dumps(
            {
                "configVersion": 2,
                "packages": [
                    {
                        "name": "forge_extension",
                        "rootUri": root_uri,
                        "packageUri": "",
                        "languageVersion": "3.0",
                    }
                ],
            },
            ensure_ascii=True,
            separators=(",", ":"),
        ),
        encoding="utf-8",
    )
    return path


def _dart_invocations(
    *,
    original_executable: Path,
    args: list[str],
    workspace: Path,
    work_dir: Path,
) -> list[tuple[Path, list[str]]]:
    sdk, dartvm = _dart_paths(original_executable)
    del sdk  # ACL setup uses the SDK root separately.

    identity = [
        f"--executable_name={dartvm}",
        f"--resolved_executable_name={dartvm}",
    ]
    packages = _package_config(workspace, work_dir)
    package_arg = f"--packages={packages}"

    if len(args) >= 2 and args[0] == "run":
        target = Path(args[1]).as_posix().lstrip("./")
        return [(dartvm, [*identity, package_arg, f"package:forge_extension/{target}"])]

    if len(args) >= 2 and args[0] == "analyze":
        # dartdev's analyzer cannot initialize inside AppContainer because Dart's
        # Windows VOLUME_NAME_DOS canonicalization is denied.  Compile every
        # executable verification entry point instead.  capability_impl.dart is
        # imported by both test/probe and therefore type-checked as part of these
        # kernel builds.  This preserves the fail-closed "bad Dart cannot promote"
        # property without weakening AppContainer.
        targets = [
            Path(value).as_posix().lstrip("./")
            for value in args[1:]
            if value.lower().endswith(".dart")
            and Path(value).name.lower() != "capability_impl.dart"
        ]
        if not targets:
            raise WindowsSandboxError("Dart analyze translation has no executable entry point")
        invocations: list[tuple[Path, list[str]]] = []
        for index, target in enumerate(targets):
            snapshot = work_dir / f"build-check-{index}.dill"
            invocations.append(
                (
                    dartvm,
                    [
                        *identity,
                        package_arg,
                        "--snapshot-kind=kernel",
                        f"--snapshot={snapshot}",
                        f"package:forge_extension/{target}",
                    ],
                )
            )
        return invocations

    raise WindowsSandboxError(f"unsupported Dart command for Windows backend: {args!r}")


class _Session:
    """One ephemeral AppContainer identity reused for this host Python process.

    The expensive recursive RX projection over Python/Dart SDK trees is tied to
    the AppContainer SID, not to one generated workspace. Reusing one random SID
    for the lifetime of the test/build process makes the production path fast
    enough for the full Self-Extension suite while preserving isolation between
    workspaces: every workspace still receives and later loses its own Modify ACE.

    If the host process crashes, the random SID is effectively dead because the
    moniker contains an unguessable UUID. Normal interpreter shutdown removes all
    projected toolchain ACEs and deletes the profile.
    """

    def __init__(self) -> None:
        self.api = _apis()
        self.moniker = f"Forge.Sandbox.Session.{uuid.uuid4().hex}"
        self.sid = PSID()
        self.sid_text = ""
        self.profile_created = False
        self.granted_recursive: list[Path] = []
        self.granted_ancestors: list[Path] = []
        self._lock = threading.RLock()
        self._closed = False

        hr = int(
            self.api.userenv.CreateAppContainerProfile(
                self.moniker,
                "Forge Sandbox Session",
                "Ephemeral Forge generated-code sandbox session",
                None,
                0,
                ctypes.byref(self.sid),
            )
        )
        if _hresult_failed(hr):
            raise WindowsSandboxError(
                f"CreateAppContainerProfile failed: HRESULT=0x{hr & 0xFFFFFFFF:08X}"
            )
        self.profile_created = True
        self.sid_text = _sid_string(self.api, self.sid)

        folder_ptr = wintypes.LPWSTR()
        hr = int(
            self.api.userenv.GetAppContainerFolderPath(
                self.sid_text,
                ctypes.byref(folder_ptr),
            )
        )
        if _hresult_failed(hr):
            raise WindowsSandboxError(
                f"GetAppContainerFolderPath failed: HRESULT=0x{hr & 0xFFFFFFFF:08X}"
            )
        try:
            self.appcontainer_local = Path(folder_ptr.value)
        finally:
            self.api.ole32.CoTaskMemFree(ctypes.cast(folder_ptr, LPVOID))

        (self.appcontainer_local / "Temp").mkdir(parents=True, exist_ok=True)
        (self.appcontainer_local / "Forge").mkdir(parents=True, exist_ok=True)

    def grant_toolchain(self, roots: tuple[Path, ...]) -> None:
        with self._lock:
            unique_roots = tuple(dict.fromkeys(path.resolve() for path in roots))
            ancestor_set = {
                ancestor
                for root in unique_roots
                for ancestor in _ancestors(root)
            }
            for ancestor in sorted(ancestor_set, key=lambda item: len(item.parts)):
                if ancestor in self.granted_ancestors:
                    continue
                _grant(ancestor, self.sid_text, "RX", recursive=False)
                self.granted_ancestors.append(ancestor)
            for root in unique_roots:
                if root in self.granted_recursive:
                    continue
                _grant(root, self.sid_text, "RX", recursive=True)
                self.granted_recursive.append(root)

    def close(self) -> None:
        with self._lock:
            if self._closed:
                return
            self._closed = True
            errors: list[str] = []
            for path in reversed(self.granted_recursive):
                try:
                    _remove_acl(path, self.sid_text, recursive=True)
                except Exception as exc:
                    errors.append(str(exc))
            for path in reversed(self.granted_ancestors):
                try:
                    _remove_acl(path, self.sid_text, recursive=False)
                except Exception as exc:
                    errors.append(str(exc))
            if self.sid:
                self.api.advapi32.FreeSid(self.sid)
                self.sid = PSID()
            if self.profile_created:
                self.api.userenv.DeleteAppContainerProfile(self.moniker)
                self.profile_created = False
            if errors:
                raise WindowsSandboxError("; ".join(errors))


_SESSION_LOCK = threading.RLock()
_SESSION: _Session | None = None


def _session() -> _Session:
    global _SESSION
    with _SESSION_LOCK:
        if _SESSION is None:
            _SESSION = _Session()
            atexit.register(_close_session_at_exit)
        return _SESSION


def _close_session_at_exit() -> None:
    global _SESSION
    with _SESSION_LOCK:
        session = _SESSION
        _SESSION = None
    if session is not None:
        try:
            session.close()
        except Exception:
            # atexit cannot safely surface sandbox evidence. Per-run workspace
            # cleanup remains strict; this is best-effort recovery for host exit.
            pass


class _Context:
    def __init__(self, workspace: Path) -> None:
        self.session = _session()
        self.api = self.session.api
        self.workspace = workspace.resolve()
        self.sid = self.session.sid
        self.sid_text = self.session.sid_text
        self.appcontainer_local = self.session.appcontainer_local
        self.attr_buffer = None
        self.attr_list = None
        self.security_capabilities = None
        self.workspace_granted = False
        self.work_dir = (
            self.appcontainer_local / "Forge" / f"run-{uuid.uuid4().hex}"
        )
        self.work_dir.mkdir(parents=True, exist_ok=True)

        _grant(self.workspace, self.sid_text, "M", recursive=True)
        self.workspace_granted = True

        attr_size = SIZE_T(0)
        ctypes.set_last_error(0)
        first = self.api.kernel32.InitializeProcThreadAttributeList(
            None, 1, 0, ctypes.byref(attr_size)
        )
        if first or ctypes.get_last_error() != ERROR_INSUFFICIENT_BUFFER:
            raise _winerror("InitializeProcThreadAttributeList(size)")

        self.attr_buffer = ctypes.create_string_buffer(attr_size.value)
        self.attr_list = ctypes.cast(self.attr_buffer, LPVOID)
        if not self.api.kernel32.InitializeProcThreadAttributeList(
            self.attr_list, 1, 0, ctypes.byref(attr_size)
        ):
            raise _winerror("InitializeProcThreadAttributeList")

        self.security_capabilities = SECURITY_CAPABILITIES(
            AppContainerSid=self.sid,
            Capabilities=None,
            CapabilityCount=0,
            Reserved=0,
        )
        if not self.api.kernel32.UpdateProcThreadAttribute(
            self.attr_list,
            0,
            SIZE_T(PROC_THREAD_ATTRIBUTE_SECURITY_CAPABILITIES),
            ctypes.byref(self.security_capabilities),
            ctypes.sizeof(self.security_capabilities),
            None,
            None,
        ):
            raise _winerror("UpdateProcThreadAttribute(SECURITY_CAPABILITIES)")

    def grant_toolchain(self, roots: tuple[Path, ...]) -> None:
        self.session.grant_toolchain(roots)

    def new_job(
        self,
        *,
        cpu_seconds: int,
        memory_bytes: int,
        max_processes: int,
    ) -> HANDLE:
        job = self.api.kernel32.CreateJobObjectW(None, None)
        if not job:
            raise _winerror("CreateJobObjectW")

        limits = JOBOBJECT_EXTENDED_LIMIT_INFORMATION()
        limits.BasicLimitInformation.LimitFlags = (
            JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
            | JOB_OBJECT_LIMIT_JOB_TIME
            | JOB_OBJECT_LIMIT_PROCESS_TIME
            | JOB_OBJECT_LIMIT_ACTIVE_PROCESS
            | JOB_OBJECT_LIMIT_PROCESS_MEMORY
            | JOB_OBJECT_LIMIT_JOB_MEMORY
        )
        budget_100ns = max(1, int(cpu_seconds)) * 10_000_000
        limits.BasicLimitInformation.PerProcessUserTimeLimit = budget_100ns
        limits.BasicLimitInformation.PerJobUserTimeLimit = budget_100ns
        limits.BasicLimitInformation.ActiveProcessLimit = max(1, int(max_processes))
        limits.ProcessMemoryLimit = max(1, int(memory_bytes))
        limits.JobMemoryLimit = max(1, int(memory_bytes))

        if not self.api.kernel32.SetInformationJobObject(
            job,
            JOB_OBJECT_EXTENDED_LIMIT_INFORMATION_CLASS,
            ctypes.byref(limits),
            ctypes.sizeof(limits),
        ):
            self.api.kernel32.CloseHandle(job)
            raise _winerror("SetInformationJobObject")
        return job

    def close(self) -> None:
        errors: list[str] = []
        if self.attr_list:
            self.api.kernel32.DeleteProcThreadAttributeList(self.attr_list)
            self.attr_list = None
        if self.workspace_granted:
            try:
                _remove_acl(self.workspace, self.sid_text, recursive=True)
            except Exception as exc:
                errors.append(str(exc))
            self.workspace_granted = False
        try:
            shutil.rmtree(self.work_dir, ignore_errors=True)
        except Exception as exc:
            errors.append(str(exc))
        if errors:
            raise WindowsSandboxError("; ".join(errors))


def _workspace_limit_exceeded(
    roots: tuple[Path, ...],
    *,
    max_file_bytes: int,
) -> Path | None:
    for root in roots:
        if not root.exists():
            continue
        for path in root.rglob("*"):
            try:
                if path.is_file() and path.stat().st_size > max_file_bytes:
                    return path
            except OSError:
                continue
    return None


def _run_one(
    ctx: _Context,
    *,
    executable: Path,
    args: list[str],
    env_block: ctypes.Array,
    timeout_seconds: float,
    cpu_seconds: int,
    memory_bytes: int,
    max_processes: int,
    max_file_bytes: int,
    max_output_bytes: int,
) -> dict[str, object]:
    job = ctx.new_job(
        cpu_seconds=cpu_seconds,
        memory_bytes=memory_bytes,
        max_processes=max_processes,
    )
    pi = PROCESS_INFORMATION()
    token = HANDLE()

    stdout_path = ctx.work_dir / f"stdout-{uuid.uuid4().hex}.txt"
    stderr_path = ctx.work_dir / f"stderr-{uuid.uuid4().hex}.txt"

    stdin_file = open(os.devnull, "rb")
    stdout_file = open(stdout_path, "w+b")
    stderr_file = open(stderr_path, "w+b")

    for file in (stdin_file, stdout_file, stderr_file):
        os.set_handle_inheritable(msvcrt.get_osfhandle(file.fileno()), True)

    try:
        si = STARTUPINFOEXW()
        si.StartupInfo.cb = ctypes.sizeof(si)
        si.StartupInfo.dwFlags |= STARTF_USESTDHANDLES
        si.StartupInfo.hStdInput = HANDLE(msvcrt.get_osfhandle(stdin_file.fileno()))
        si.StartupInfo.hStdOutput = HANDLE(msvcrt.get_osfhandle(stdout_file.fileno()))
        si.StartupInfo.hStdError = HANDLE(msvcrt.get_osfhandle(stderr_file.fileno()))
        si.lpAttributeList = ctx.attr_list

        command_line = ctypes.create_unicode_buffer(
            subprocess.list2cmdline([str(executable), *args])
        )

        if not ctx.api.kernel32.CreateProcessW(
            str(executable),
            command_line,
            None,
            None,
            True,
            CREATE_SUSPENDED
            | CREATE_UNICODE_ENVIRONMENT
            | EXTENDED_STARTUPINFO_PRESENT,
            ctypes.cast(env_block, LPVOID),
            str(ctx.workspace),
            ctypes.byref(si.StartupInfo),
            ctypes.byref(pi),
        ):
            raise _winerror("CreateProcessW(AppContainer toolchain)")

        if not ctx.api.advapi32.OpenProcessToken(
            pi.hProcess, TOKEN_QUERY, ctypes.byref(token)
        ):
            raise _winerror("OpenProcessToken")

        is_appcontainer = DWORD(0)
        returned = DWORD(0)
        if not ctx.api.advapi32.GetTokenInformation(
            token,
            TOKEN_IS_APP_CONTAINER,
            ctypes.byref(is_appcontainer),
            ctypes.sizeof(is_appcontainer),
            ctypes.byref(returned),
        ):
            raise _winerror("GetTokenInformation(TokenIsAppContainer)")
        if not is_appcontainer.value:
            raise WindowsSandboxError("created child token is not AppContainer")

        if not ctx.api.kernel32.AssignProcessToJobObject(job, pi.hProcess):
            raise _winerror("AssignProcessToJobObject")

        if ctx.api.kernel32.ResumeThread(pi.hThread) == 0xFFFFFFFF:
            raise _winerror("ResumeThread")

        started = time.monotonic()
        timed_out = False
        file_limit_path: Path | None = None
        output_limit = False

        while True:
            wait = ctx.api.kernel32.WaitForSingleObject(pi.hProcess, 50)
            if wait == WAIT_OBJECT_0:
                break
            if wait != WAIT_TIMEOUT:
                raise _winerror("WaitForSingleObject")

            if time.monotonic() - started >= timeout_seconds:
                timed_out = True
                ctx.api.kernel32.TerminateJobObject(job, 124)
                ctx.api.kernel32.WaitForSingleObject(pi.hProcess, 5_000)
                break

            file_limit_path = _workspace_limit_exceeded(
                (ctx.workspace,),
                max_file_bytes=max_file_bytes,
            )
            if file_limit_path is not None:
                ctx.api.kernel32.TerminateJobObject(job, 126)
                ctx.api.kernel32.WaitForSingleObject(pi.hProcess, 5_000)
                break

            try:
                output_limit = (
                    stdout_path.stat().st_size > max_output_bytes
                    or stderr_path.stat().st_size > max_output_bytes
                )
            except OSError:
                output_limit = False
            if output_limit:
                ctx.api.kernel32.TerminateJobObject(job, 127)
                ctx.api.kernel32.WaitForSingleObject(pi.hProcess, 5_000)
                break

        exit_code = DWORD(0)
        if not ctx.api.kernel32.GetExitCodeProcess(pi.hProcess, ctypes.byref(exit_code)):
            raise _winerror("GetExitCodeProcess")

        stdout_file.flush()
        stderr_file.flush()
        stdout_file.seek(0)
        stderr_file.seek(0)
        stdout = stdout_file.read(max_output_bytes).decode("utf-8", "replace")
        stderr = stderr_file.read(max_output_bytes).decode("utf-8", "replace")

        if file_limit_path is not None:
            stderr += (
                "\nWindows sandbox file limit exceeded; Job terminated: "
                + str(file_limit_path)
            )
        if output_limit:
            stderr += "\nWindows sandbox output limit exceeded; Job terminated"

        return {
            "exit_code": int(exit_code.value),
            "stdout": stdout,
            "stderr": stderr,
            "timed_out": timed_out,
            "file_limit": file_limit_path is not None,
            "output_limit": output_limit,
        }
    finally:
        if token:
            ctx.api.kernel32.CloseHandle(token)
        if pi.hThread:
            ctx.api.kernel32.CloseHandle(pi.hThread)
        if pi.hProcess:
            ctx.api.kernel32.CloseHandle(pi.hProcess)
        ctx.api.kernel32.CloseHandle(job)
        stdin_file.close()
        stdout_file.close()
        stderr_file.close()
        for path in (stdout_path, stderr_path):
            try:
                path.unlink()
            except OSError:
                pass


@lru_cache(maxsize=1)
def is_available() -> bool:
    """Probe the actual AppContainer primitive once per process."""
    if os.name != "nt":
        return False
    api = None
    sid = PSID()
    moniker = f"Forge.Sandbox.Probe.{uuid.uuid4().hex}"
    created = False
    try:
        api = _apis()
        hr = int(
            api.userenv.CreateAppContainerProfile(
                moniker,
                "Forge Sandbox Probe",
                "Ephemeral availability probe",
                None,
                0,
                ctypes.byref(sid),
            )
        )
        if _hresult_failed(hr):
            return False
        created = True

        job = api.kernel32.CreateJobObjectW(None, None)
        if not job:
            return False
        try:
            limits = JOBOBJECT_EXTENDED_LIMIT_INFORMATION()
            limits.BasicLimitInformation.LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
            if not api.kernel32.SetInformationJobObject(
                job,
                JOB_OBJECT_EXTENDED_LIMIT_INFORMATION_CLASS,
                ctypes.byref(limits),
                ctypes.sizeof(limits),
            ):
                return False
        finally:
            api.kernel32.CloseHandle(job)
        return True
    except Exception:
        return False
    finally:
        if api is not None and sid:
            api.advapi32.FreeSid(sid)
        if api is not None and created:
            api.userenv.DeleteAppContainerProfile(moniker)


def run(
    argv: list[str],
    *,
    workspace: Path,
    timeout_seconds: float,
    cpu_seconds: int,
    memory_bytes: int,
    max_processes: int,
    max_file_bytes: int,
    max_output_bytes: int,
    env_override: dict[str, str] | None,
) -> dict[str, object]:
    """Run one Forge command through the Windows OS sandbox."""
    if not is_available():
        raise WindowsSandboxError("Windows AppContainer + Job Object backend unavailable")
    if not argv:
        raise WindowsSandboxError("empty argv")

    workspace = workspace.resolve()
    original_executable = Path(argv[0]).resolve()
    if not original_executable.is_file():
        raise WindowsSandboxError(f"resolved executable does not exist: {original_executable}")

    ctx = _Context(workspace)
    started = time.monotonic()
    cleanup_error: Exception | None = None

    try:
        name = original_executable.name.lower()
        executable_dirs: list[Path] = []
        invocations: list[tuple[Path, list[str]]]

        if name in {"dart.exe", "dart", "dart.bat", "dart.cmd"}:
            sdk, dartvm = _dart_paths(original_executable)
            ctx.grant_toolchain((sdk,))
            executable_dirs.extend((dartvm.parent,))
            invocations = _dart_invocations(
                original_executable=original_executable,
                args=list(argv[1:]),
                workspace=workspace,
                work_dir=ctx.work_dir,
            )
        else:
            roots = _python_roots(original_executable)
            ctx.grant_toolchain(roots)
            executable_dirs.extend(path for root in roots for path in (root, root / "Scripts"))
            invocations = [(original_executable, list(argv[1:]))]

        env_block = _environment_block(
            workspace=workspace,
            appcontainer_local=ctx.appcontainer_local,
            base_env=env_override or {},
            executable_dirs=tuple(dict.fromkeys(executable_dirs)),
        )

        stdout_parts: list[str] = []
        stderr_parts: list[str] = []
        exit_code: int | None = 0
        timed_out = False
        deadline = started + timeout_seconds

        for executable, args in invocations:
            remaining = max(0.05, deadline - time.monotonic())
            item = _run_one(
                ctx,
                executable=executable,
                args=args,
                env_block=env_block,
                timeout_seconds=remaining,
                cpu_seconds=cpu_seconds,
                memory_bytes=memory_bytes,
                max_processes=max_processes,
                max_file_bytes=max_file_bytes,
                max_output_bytes=max_output_bytes,
            )
            stdout_parts.append(str(item["stdout"]))
            stderr_parts.append(str(item["stderr"]))
            exit_code = int(item["exit_code"])
            timed_out = bool(item["timed_out"])
            if timed_out or exit_code != 0:
                break

        return {
            "exit_code": exit_code,
            "stdout": "".join(stdout_parts)[:max_output_bytes],
            "stderr": "".join(stderr_parts)[:max_output_bytes],
            "timed_out": timed_out,
            "backend": BACKEND_NAME,
            "duration_seconds": time.monotonic() - started,
        }
    finally:
        try:
            ctx.close()
        except Exception as exc:
            cleanup_error = exc
        if cleanup_error is not None:
            # Cleanup failure is a sandbox failure, never a successful execution.
            raise WindowsSandboxError(f"Windows sandbox cleanup failed: {cleanup_error}")
