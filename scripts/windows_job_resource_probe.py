#!/usr/bin/env python3
"""TD110 Windows Job Object resource/cleanup probe (stage 3).

Requires the stage-2 AppContainer probe helpers and runs every case inside the
same no-capability AppContainer boundary.  This is still evidence/probing code,
not the production Forge sandbox backend.

Proves on physical Windows:
- Job CPU-time limit stops a busy loop.
- Job/process memory limits stop a memory bomb.
- Active-process limit bounds child creation.
- Host wall-clock timeout can terminate the whole job.
- KILL_ON_JOB_CLOSE removes a surviving descendant.

Fail closed: all assertions must be true or exit code is non-zero.
"""

from __future__ import annotations

import base64
import ctypes
from ctypes import wintypes
import json
import os
from pathlib import Path
import platform
import tempfile
import time
import uuid

import windows_appcontainer_isolation_probe as base


if platform.system() != "Windows":
    print(json.dumps({"ok": False, "error": "windows-only probe"}, ensure_ascii=False))
    raise SystemExit(2)


JOB_OBJECT_LIMIT_JOB_TIME = 0x00000004
SYNCHRONIZE = 0x00100000
STILL_ACTIVE = 259

base.kernel32.OpenProcess.argtypes = [base.DWORD, base.BOOL, base.DWORD]
base.kernel32.OpenProcess.restype = base.HANDLE


def _encode(script: str) -> str:
    return base64.b64encode(script.encode("utf-16le")).decode("ascii")


class Context:
    def __init__(self) -> None:
        self.moniker = f"Forge.TD110.ResourceProbe.{uuid.uuid4().hex}"
        self.sid = base.PSID()
        self.attr_buffer = None
        self.attr_list = None
        self.profile_created = False
        self.tmp_root = tempfile.TemporaryDirectory(prefix="forge-td110-resource-")
        self.root = Path(self.tmp_root.name)
        self.workspace = self.root / "workspace"
        self.workspace.mkdir()

        hr = int(
            base.userenv.CreateAppContainerProfile(
                self.moniker,
                "Forge TD110 Resource Probe",
                "Temporary Forge AppContainer resource probe",
                None,
                0,
                ctypes.byref(self.sid),
            )
        )
        if base._hresult_failed(hr):
            raise RuntimeError(
                f"CreateAppContainerProfile failed: HRESULT=0x{hr & 0xFFFFFFFF:08X}"
            )
        self.profile_created = True

        self.sid_text = base._sid_string(self.sid)
        base._grant_workspace(self.workspace, self.sid_text)

        folder_ptr = wintypes.LPWSTR()
        hr = int(
            base.userenv.GetAppContainerFolderPath(
                self.sid_text,
                ctypes.byref(folder_ptr),
            )
        )
        if base._hresult_failed(hr):
            raise RuntimeError(
                f"GetAppContainerFolderPath failed: HRESULT=0x{hr & 0xFFFFFFFF:08X}"
            )
        try:
            self.appcontainer_local = Path(folder_ptr.value)
        finally:
            base.ole32.CoTaskMemFree(ctypes.cast(folder_ptr, base.LPVOID))
        (self.appcontainer_local / "Temp").mkdir(parents=True, exist_ok=True)

        attr_size = base.SIZE_T(0)
        ctypes.set_last_error(0)
        first = base.kernel32.InitializeProcThreadAttributeList(
            None, 1, 0, ctypes.byref(attr_size)
        )
        if first or ctypes.get_last_error() != base.ERROR_INSUFFICIENT_BUFFER:
            raise base._winerror("InitializeProcThreadAttributeList(size)")

        self.attr_buffer = ctypes.create_string_buffer(attr_size.value)
        self.attr_list = ctypes.cast(self.attr_buffer, base.LPVOID)
        if not base.kernel32.InitializeProcThreadAttributeList(
            self.attr_list, 1, 0, ctypes.byref(attr_size)
        ):
            raise base._winerror("InitializeProcThreadAttributeList")

        # IMPORTANT: UpdateProcThreadAttribute keeps the pointer to the
        # SECURITY_CAPABILITIES value for later CreateProcessW use; it does not
        # make this Python ctypes object magically immortal.  Stage-2 kept the
        # structure alive as a local in main(), but this Context constructor used
        # to let it go out of scope before _start().  On physical Windows 10 that
        # became an access violation while CreateProcessW dereferenced the stale
        # pointer.  Keep the backing object alive for the lifetime of attr_list.
        self.security_capabilities = base.SECURITY_CAPABILITIES(
            AppContainerSid=self.sid,
            Capabilities=None,
            CapabilityCount=0,
            Reserved=0,
        )
        if not base.kernel32.UpdateProcThreadAttribute(
            self.attr_list,
            0,
            base.SIZE_T(base.PROC_THREAD_ATTRIBUTE_SECURITY_CAPABILITIES),
            ctypes.byref(self.security_capabilities),
            ctypes.sizeof(self.security_capabilities),
            None,
            None,
        ):
            raise base._winerror("UpdateProcThreadAttribute(SECURITY_CAPABILITIES)")

        self.powershell = os.path.join(
            os.environ["SystemRoot"],
            "System32",
            "WindowsPowerShell",
            "v1.0",
            "powershell.exe",
        )

    def close(self) -> None:
        if self.attr_list:
            base.kernel32.DeleteProcThreadAttributeList(self.attr_list)
            self.attr_list = None
        if self.sid:
            base.advapi32.FreeSid(self.sid)
            self.sid = base.PSID()
        if self.profile_created:
            base.userenv.DeleteAppContainerProfile(self.moniker)
            self.profile_created = False
        self.tmp_root.cleanup()

    def _new_job(
        self,
        *,
        flags: int,
        active_process_limit: int = 0,
        process_memory: int = 0,
        job_memory: int = 0,
        job_time_100ns: int = 0,
    ):
        job = base.kernel32.CreateJobObjectW(None, None)
        if not job:
            raise base._winerror("CreateJobObjectW")

        limits = base.JOBOBJECT_EXTENDED_LIMIT_INFORMATION()
        limits.BasicLimitInformation.LimitFlags = flags
        limits.BasicLimitInformation.ActiveProcessLimit = active_process_limit
        limits.BasicLimitInformation.PerJobUserTimeLimit = job_time_100ns
        limits.ProcessMemoryLimit = process_memory
        limits.JobMemoryLimit = job_memory

        if not base.kernel32.SetInformationJobObject(
            job,
            base.JOB_OBJECT_EXTENDED_LIMIT_INFORMATION_CLASS,
            ctypes.byref(limits),
            ctypes.sizeof(limits),
        ):
            base.kernel32.CloseHandle(job)
            raise base._winerror("SetInformationJobObject")
        return job

    def _start(self, script: str, job) -> base.PROCESS_INFORMATION:
        encoded = _encode(script)
        command_line = ctypes.create_unicode_buffer(
            f'"{self.powershell}" -NoLogo -NoProfile -NonInteractive '
            f'-ExecutionPolicy Bypass -EncodedCommand {encoded}'
        )
        si = base.STARTUPINFOEXW()
        si.StartupInfo.cb = ctypes.sizeof(si)
        si.lpAttributeList = self.attr_list
        env_block = base._minimal_environment(self.workspace, self.appcontainer_local)
        pi = base.PROCESS_INFORMATION()

        if not base.kernel32.CreateProcessW(
            self.powershell,
            command_line,
            None,
            None,
            False,
            base.CREATE_SUSPENDED
            | base.CREATE_UNICODE_ENVIRONMENT
            | base.EXTENDED_STARTUPINFO_PRESENT,
            ctypes.cast(env_block, base.LPVOID),
            str(self.workspace),
            ctypes.byref(si.StartupInfo),
            ctypes.byref(pi),
        ):
            raise base._winerror("CreateProcessW(AppContainer PowerShell)")

        token = base.HANDLE()
        try:
            if not base.advapi32.OpenProcessToken(
                pi.hProcess, base.TOKEN_QUERY, ctypes.byref(token)
            ):
                raise base._winerror("OpenProcessToken")
            is_appcontainer = base.DWORD(0)
            returned = base.DWORD(0)
            if not base.advapi32.GetTokenInformation(
                token,
                base.TOKEN_IS_APP_CONTAINER,
                ctypes.byref(is_appcontainer),
                ctypes.sizeof(is_appcontainer),
                ctypes.byref(returned),
            ):
                raise base._winerror("GetTokenInformation(TokenIsAppContainer)")
            if not is_appcontainer.value:
                raise RuntimeError("child token is NOT an AppContainer token")
        finally:
            if token:
                base.kernel32.CloseHandle(token)

        if not base.kernel32.AssignProcessToJobObject(job, pi.hProcess):
            base.kernel32.CloseHandle(pi.hThread)
            base.kernel32.CloseHandle(pi.hProcess)
            raise base._winerror("AssignProcessToJobObject")

        if base.kernel32.ResumeThread(pi.hThread) == 0xFFFFFFFF:
            base.kernel32.CloseHandle(pi.hThread)
            base.kernel32.CloseHandle(pi.hProcess)
            raise base._winerror("ResumeThread")
        return pi


def _wait_exit(pi: base.PROCESS_INFORMATION, milliseconds: int) -> tuple[int, int | None]:
    wait = base.kernel32.WaitForSingleObject(pi.hProcess, milliseconds)
    if wait == base.WAIT_TIMEOUT:
        return wait, None
    if wait != base.WAIT_OBJECT_0:
        raise base._winerror("WaitForSingleObject")
    code = base.DWORD(0)
    if not base.kernel32.GetExitCodeProcess(pi.hProcess, ctypes.byref(code)):
        raise base._winerror("GetExitCodeProcess")
    return wait, int(code.value)


def _close_pi(pi: base.PROCESS_INFORMATION) -> None:
    if pi.hThread:
        base.kernel32.CloseHandle(pi.hThread)
    if pi.hProcess:
        base.kernel32.CloseHandle(pi.hProcess)


def _wait_for_path(path: Path, *, timeout_seconds: float) -> bool:
    """Wait for a child-created marker without conflating startup with timeout."""
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        if path.is_file():
            return True
        time.sleep(0.05)
    return path.is_file()


def main() -> int:
    ctx = None
    result: dict[str, object] = {
        "ok": False,
        "platform": platform.platform(),
        "assertions": {},
    }

    try:
        result["stage"] = "context:init"
        ctx = Context()
        result["moniker"] = ctx.moniker
        result["appcontainer_sid"] = ctx.sid_text

        assertions: dict[str, bool] = {}

        # 1) CPU time: write a marker first, then burn CPU. Job time should end it.
        result["stage"] = "cpu:create-job"
        cpu_started = ctx.workspace / "cpu-started.txt"
        cpu_script = (
            f"Set-Content -LiteralPath '{cpu_started}' -Value started; "
            "while ($true) { [Math]::Sqrt(1234567) | Out-Null }"
        )
        cpu_job = ctx._new_job(
            flags=base.JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE | JOB_OBJECT_LIMIT_JOB_TIME,
            # 1.5 s was too tight on the physical Windows 10 target: PowerShell
            # could consume the entire user-mode budget during startup before the
            # first workspace marker was written.  That made a working Job limit
            # look like a test failure.  Four seconds still fails decisively if
            # JOB_TIME is removed (the infinite loop reaches the 12 s host wait),
            # while giving the command itself time to begin.
            job_time_100ns=40_000_000,  # 4.0 seconds of user-mode CPU time
        )
        result["stage"] = "cpu:start-process"
        cpu_pi = ctx._start(cpu_script, cpu_job)
        result["stage"] = "cpu:wait"
        cpu_t0 = time.monotonic()
        cpu_wait, cpu_code = _wait_exit(cpu_pi, 20_000)
        cpu_elapsed = time.monotonic() - cpu_t0
        cpu_marker = cpu_started.is_file()

        # Wall-clock duration is intentionally NOT the verdict.  A 4 s user-CPU
        # budget can take much longer than 4 s of wall time on a busy/slow host.
        # The physical Windows 10 batch reproduced 11+ s wall time while the Job
        # still terminated the process with the same CPU-limit exit status.
        #
        # Prove causality with a guard-break control: run the same infinite CPU
        # workload in an otherwise identical Job with JOB_TIME removed.  It must
        # still be alive after a bounded observation window.  If removing the
        # control does not change the result, this probe must fail.
        assertions["cpu_job_time_enforced"] = (
            cpu_marker
            and cpu_wait == base.WAIT_OBJECT_0
            and cpu_code is not None
            and cpu_code != 0
        )
        result["cpu_elapsed_seconds"] = round(cpu_elapsed, 3)
        result["cpu_marker_created"] = cpu_marker
        result["cpu_wait_code"] = int(cpu_wait)
        result["cpu_exit_code"] = cpu_code

        result["stage"] = "cpu:guard-break-control"
        control_started = ctx.workspace / "cpu-control-started.txt"
        control_script = (
            f"Set-Content -LiteralPath '{control_started}' -Value started; "
            "while ($true) { [Math]::Sqrt(1234567) | Out-Null }"
        )
        control_job = ctx._new_job(
            flags=base.JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE,
        )
        control_pi = ctx._start(control_script, control_job)
        control_t0 = time.monotonic()
        control_wait, control_code = _wait_exit(control_pi, 6_000)
        control_elapsed = time.monotonic() - control_t0
        control_marker = control_started.is_file()
        control_terminated = False
        if control_wait == base.WAIT_TIMEOUT:
            control_terminated = bool(base.kernel32.TerminateJobObject(control_job, 125))
            control_wait2, control_code2 = _wait_exit(control_pi, 5_000)
        else:
            control_wait2, control_code2 = control_wait, control_code

        assertions["cpu_limit_removed_keeps_workload_running"] = (
            control_marker
            and control_wait == base.WAIT_TIMEOUT
            and control_terminated
            and control_wait2 == base.WAIT_OBJECT_0
        )
        result["cpu_control_elapsed_seconds"] = round(control_elapsed, 3)
        result["cpu_control_marker_created"] = control_marker
        result["cpu_control_initial_wait_code"] = int(control_wait)
        result["cpu_control_exit_code"] = control_code2

        result["stage"] = "cpu:cleanup"
        _close_pi(control_pi)
        base.kernel32.CloseHandle(control_job)
        _close_pi(cpu_pi)
        base.kernel32.CloseHandle(cpu_job)

        # 2) Memory: bounded PowerShell repeatedly allocates 64 MiB chunks.
        result["stage"] = "memory:create-job"
        mem_started = ctx.workspace / "memory-started.txt"
        mem_blocked = ctx.workspace / "memory-blocked.txt"
        mem_script = f"""
Set-Content -LiteralPath '{mem_started}' -Value started
$chunks = @()
try {{
  while ($true) {{
    $chunks += ,(New-Object byte[] 67108864)
  }}
}} catch {{
  Set-Content -LiteralPath '{mem_blocked}' -Value $_.Exception.GetType().FullName
  exit 0
}}
"""
        mem_job = ctx._new_job(
            flags=(
                base.JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
                | base.JOB_OBJECT_LIMIT_PROCESS_MEMORY
                | base.JOB_OBJECT_LIMIT_JOB_MEMORY
            ),
            process_memory=256 * 1024 * 1024,
            job_memory=320 * 1024 * 1024,
        )
        result["stage"] = "memory:start-process"
        mem_pi = ctx._start(mem_script, mem_job)
        result["stage"] = "memory:wait"
        mem_t0 = time.monotonic()
        mem_wait, mem_code = _wait_exit(mem_pi, 12_000)
        mem_elapsed = time.monotonic() - mem_t0
        assertions["memory_limit_enforced"] = (
            mem_started.is_file()
            and mem_wait == base.WAIT_OBJECT_0
            and mem_elapsed < 10.0
            and (mem_blocked.is_file() or (mem_code is not None and mem_code != 0))
        )
        result["memory_elapsed_seconds"] = round(mem_elapsed, 3)
        result["memory_exit_code"] = mem_code
        result["stage"] = "memory:cleanup"
        _close_pi(mem_pi)
        base.kernel32.CloseHandle(mem_job)

        # 3) Active-process limit: parent + at most one live child.
        result["stage"] = "process-limit:create-job"
        proc_result = ctx.workspace / "process-count.txt"
        proc_script = f"""
$alive = @()
for ($i = 0; $i -lt 5; $i++) {{
  try {{
    $p = Start-Process -FilePath "$env:SystemRoot\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -ArgumentList '-NoProfile','-Command','Start-Sleep -Seconds 8' -PassThru -WindowStyle Hidden
    Start-Sleep -Milliseconds 250
    if (-not $p.HasExited) {{ $alive += $p }}
  }} catch {{}}
}}
Set-Content -LiteralPath '{proc_result}' -Value $alive.Count -Encoding ASCII
foreach ($p in $alive) {{ try {{ Stop-Process -Id $p.Id -Force }} catch {{}} }}
"""
        proc_job = ctx._new_job(
            flags=(
                base.JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
                | base.JOB_OBJECT_LIMIT_ACTIVE_PROCESS
            ),
            active_process_limit=2,
        )
        result["stage"] = "process-limit:start-process"
        proc_pi = ctx._start(proc_script, proc_job)
        result["stage"] = "process-limit:wait"
        proc_wait, proc_code = _wait_exit(proc_pi, 15_000)
        count = int(proc_result.read_text(encoding="ascii").strip()) if proc_result.is_file() else 999
        assertions["active_process_limit_enforced"] = (
            proc_wait == base.WAIT_OBJECT_0
            and proc_code == 0
            and count <= 1
        )
        result["max_live_children_observed"] = count
        result["stage"] = "process-limit:cleanup"
        _close_pi(proc_pi)
        base.kernel32.CloseHandle(proc_job)

        # 4) Wall clock: host must be able to terminate the entire job.
        result["stage"] = "wall-clock:create-job"
        wall_started = ctx.workspace / "wall-started.txt"
        wall_script = (
            f"Set-Content -LiteralPath '{wall_started}' -Value started; "
            "Start-Sleep -Seconds 30"
        )
        wall_job = ctx._new_job(flags=base.JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE)
        result["stage"] = "wall-clock:start-process"
        wall_pi = ctx._start(wall_script, wall_job)

        # PowerShell startup time varies substantially on the fresh Windows PC.
        # Start the 2 s wall-clock budget only after the child proves it entered
        # the workload. Otherwise a slow module/runtime startup can make a valid
        # timeout control look broken.
        result["stage"] = "wall-clock:wait-for-marker"
        wall_marker = _wait_for_path(wall_started, timeout_seconds=12.0)

        result["stage"] = "wall-clock:wait"
        if wall_marker:
            wall_wait, _ = _wait_exit(wall_pi, 2_000)
        else:
            wall_wait, _ = _wait_exit(wall_pi, 0)

        terminated = False
        if wall_wait == base.WAIT_TIMEOUT:
            terminated = bool(base.kernel32.TerminateJobObject(wall_job, 124))
            wall_wait2, wall_code2 = _wait_exit(wall_pi, 5_000)
        else:
            wall_wait2, wall_code2 = wall_wait, None
        assertions["wall_clock_job_termination"] = (
            wall_marker
            and wall_wait == base.WAIT_TIMEOUT
            and terminated
            and wall_wait2 == base.WAIT_OBJECT_0
            and wall_code2 == 124
        )
        result["wall_clock_marker_created"] = wall_marker
        result["wall_clock_initial_wait_code"] = int(wall_wait)
        result["wall_clock_terminate_job_succeeded"] = terminated
        result["wall_clock_final_wait_code"] = int(wall_wait2)
        result["wall_clock_exit_code"] = wall_code2
        result["stage"] = "wall-clock:cleanup"
        _close_pi(wall_pi)
        base.kernel32.CloseHandle(wall_job)

        # 5) KILL_ON_JOB_CLOSE: descendant remains alive after parent exits,
        result["stage"] = "kill-on-close:create-job"
        # then closing the job handle must terminate that descendant.
        pid_file = ctx.workspace / "surviving-child.pid"
        child_script = f"""
$p = Start-Process -FilePath "$env:SystemRoot\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -ArgumentList '-NoProfile','-Command','Start-Sleep -Seconds 30' -PassThru -WindowStyle Hidden
Set-Content -LiteralPath '{pid_file}' -Value $p.Id -Encoding ASCII
exit 0
"""
        child_job = ctx._new_job(flags=base.JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE)
        result["stage"] = "kill-on-close:start-process"
        parent_pi = ctx._start(child_script, child_job)
        result["stage"] = "kill-on-close:wait-parent"
        parent_wait, parent_code = _wait_exit(parent_pi, 10_000)
        child_pid = int(pid_file.read_text(encoding="ascii").strip()) if pid_file.is_file() else 0
        result["stage"] = "kill-on-close:open-child"
        child_handle = (
            base.kernel32.OpenProcess(SYNCHRONIZE, False, child_pid)
            if child_pid
            else base.HANDLE()
        )
        child_alive_before_close = bool(
            child_handle
            and base.kernel32.WaitForSingleObject(child_handle, 0) == base.WAIT_TIMEOUT
        )
        result["stage"] = "kill-on-close:close-job"
        base.kernel32.CloseHandle(child_job)
        result["stage"] = "kill-on-close:wait-child"
        child_died_after_close = bool(
            child_handle
            and base.kernel32.WaitForSingleObject(child_handle, 5_000) == base.WAIT_OBJECT_0
        )
        assertions["kill_on_job_close_cleans_descendant"] = (
            parent_wait == base.WAIT_OBJECT_0
            and parent_code == 0
            and child_alive_before_close
            and child_died_after_close
        )
        result["surviving_child_pid"] = child_pid
        if child_handle:
            base.kernel32.CloseHandle(child_handle)
        _close_pi(parent_pi)

        result["stage"] = "final:assertions"
        result["assertions"] = assertions
        failed = [name for name, value in assertions.items() if value is not True]
        if failed:
            raise RuntimeError("resource assertions failed: " + ", ".join(failed))

        result["ok"] = True
        result["stage"] = "complete"
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    except Exception as exc:
        result["error"] = str(exc)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 1

    finally:
        if ctx is not None:
            ctx.close()


if __name__ == "__main__":
    raise SystemExit(main())
