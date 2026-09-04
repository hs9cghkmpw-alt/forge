# Windows Home PC Baseline Evidence — 2026-09-04

## Scope

Freshly initialized Windows home PC used as a real portability / distribution check for Forge.

This record is evidence only. It does **not** claim that Windows Sandbox support or TD110 is resolved.

## Environment

- OS: Windows 10 Home 64-bit, 22H2, build 19045.3803
- Python used for Forge: 3.12.10 in repository-local `.venv`
- Flutter: 3.47.2 stable
- Dart: 3.13.2
- Chrome: 152.0.7977.76
- Git: 2.55.0.windows.3
- GitHub CLI: 2.100.0
- Repository branch: `claude/forge-master-handoff-k46jns`
- Tested repository commit after Windows compatibility fixes:
  `fabc32fadba4583052b8e4f965c8665f18abd472`

## Fresh-PC bootstrap issue discovered

Flutter initially failed with:

```text
Error: Unable to determine engine version...
```

Root cause was a broken WindowsApps `pwsh.exe` app execution alias that existed in PATH but could not execute because no applicable app license was available.

A temporary explicit shim to the working Windows PowerShell 5.1 executable allowed Flutter bootstrap to complete.

This demonstrates that Forge's future Windows bootstrap must verify that `pwsh` is actually executable, not merely discoverable on PATH.

## Frontend baseline

Observed on the fresh Windows PC before the Python retest:

- `flutter pub get`: PASS
- `flutter analyze --fatal-infos --fatal-warnings`: PASS
- `flutter test`: 589 tests PASS
- `flutter build web --debug`: PASS

Android SDK and Visual Studio desktop workload were not installed. They were not required for this web/Chrome baseline.

## Backend baseline after CRLF fix

Command:

```powershell
& .\.venv\Scripts\python.exe -m pytest tests -q
```

Result:

```text
2072 passed, 17 skipped, 2 warnings in 67.93s
exit code = 0
```

This confirms the Windows CRLF bug in Flutter generated-workspace materialization was fixed by commit `fabc32f`.

## forge_ai Windows result after POSIX-import compatibility fix

The full `forge_ai` suite now collects and runs on Windows, but 13 execution-path tests fail.

The failures consistently show the same intended fail-closed boundary:

```text
sandbox unavailable, refused to run:
この環境（Windows）には OS 層の隔離手段が無いため、
生成物を実行しない。隔離できないなら動かさない（fail closed）。
```

Affected families include:

- managed build workspace real test/build/runtime probe
- generated Dart real build/probe/promotion
- verified-artifact handoff
- managed BUILD_TIME promotion
- self-extension E2E acquisition/reuse
- generated-source real build/probe

Observed aggregate:

```text
forge_ai exit code = 1
backend exit code = 0
```

Repository working tree remained clean.

## Interpretation

This is **not** a reason to enable `FORGE_SANDBOX_ALLOW_POLICY_ONLY=1` by default.

Doing so would make tests execute under a weaker policy-only mode and would hide the actual Windows product gap.

The result is direct real-Windows evidence for TD110:

> Windows currently has no OS-enforced Sandbox backend for generated BUILD_TIME execution, so Self-Extension correctly fails closed instead of executing generated code with host privileges.

Therefore:

- Windows portability baseline: partially successful
- Backend + Flutter web baseline: successful
- Windows Self-Extension: blocked by TD110
- EXT-08 / SEC-04: remain PARTIAL
- Windows Sandbox completion: **not claimed**

## GitHub CI cross-check

Commit `fabc32fadba4583052b8e4f965c8665f18abd472` also passed GitHub Actions CI:

- Run: `33821012607`
- Conclusion: `success`

The Linux CI success and this Windows failure are both correct: Linux has an OS sandbox backend; Windows does not yet.

## Next engineering action

Implement and break-test a real Windows OS sandbox backend rather than weakening the fail-closed contract.

Minimum proof requirements before closing TD110:

1. network egress blocked by OS boundary
2. host secrets not inherited
3. generated process cannot escape/retain child processes
4. CPU / memory / wall-clock limits enforced
5. workspace/file access boundary is enforced, not merely cwd-pinned
6. harmless test/build/runtime-probe still work
7. escape corpus passes on physical Windows
8. evidence names the exact Windows backend used
9. removing each isolation control makes the corresponding guard-break test fail
10. Self-Extension generate → verify → promote → install → reuse succeeds on Windows only after those gates pass


## TD110 Stage 2 real-Windows isolation boundary probe

Physical Windows 10 Home execution of:

```powershell
py -3.12 scripts\windows_appcontainer_isolation_probe.py
```

at commit `28eb0c68803c0819f66fd567c17fdfacb28fd83f` returned `ok: true`.

Observed OS-backed facts:

```text
profile_created          = true
appcontainer_token       = true
workspace_acl_granted    = true
job_created              = true
job_assigned             = true
process_resumed          = true
process_exit_code         = 0

inside_write              = true
outside_read_blocked      = true
network_blocked           = true
host_secret_absent        = true
minimal_env               = true
child_spawned             = true
```

The AppContainer LocalAppData path was resolved by Windows through
`GetAppContainerFolderPath`, rather than guessed.

This closes an important uncertainty: **Windows 10 Home on the actual distribution
target can enforce the core AppContainer boundary while a Job Object is attached
before execution begins.**

It still does **not** close TD110.  Remaining proof includes resource limits
(CPU / memory / wall-clock), child-process cleanup, real Python/Dart/Flutter
toolchain execution, mutation/guard-break tests, production runner wiring, and
the full Self-Extension generate → verify → promote → install → reuse path.

### Probe defect found and corrected

The first Stage 2 attempts failed at `CreateProcessW` with Win32 error 203
(`ERROR_ENVVAR_NOT_FOUND`).  The AppContainer profile itself was healthy.

The defect was in the probe's custom minimal environment: AppContainer launch on
this Windows 10 machine required the profile-specific `LOCALAPPDATA` and
`TEMP`/`TMP` paths.  The probe now obtains the profile path from Windows and
constructs the child environment from that path.  This is relevant to the
production backend: **AppContainer environment paths must be resolved from the OS,
not inferred from the host user's normal environment.**


## TD110 Stage 3 real-Windows Job Object resource proof

Physical Windows 10 Home execution of:

```powershell
py -3.12 scripts\windows_job_resource_probe.py
```

at commit `0c7ef87028c198c894fb5320227874fa815e0e87` returned `ok: true`.

Observed assertions:

```text
cpu_job_time_enforced                    = true
memory_limit_enforced                    = true
active_process_limit_enforced            = true
wall_clock_job_termination               = true
kill_on_job_close_cleans_descendant      = true
```

Observed measurements:

```text
cpu_elapsed_seconds        = 4.859
cpu_marker_created         = true
cpu_wait_code              = 0
cpu_exit_code              = 3221225540
memory_elapsed_seconds     = 2.797
memory_exit_code           = 0
max_live_children_observed = 1
wall_clock_exit_code       = 124
```

The CPU process was terminated by the Job Object CPU-time limit after it had
actually entered the workload.  The wall-clock path separately terminated the
whole Job with exit code 124.  The process-count probe observed at most one live
child with the configured parent+one-child limit.  A descendant deliberately
left alive after its parent exited was terminated when the Job handle closed.

This is direct physical-machine evidence that AppContainer + Job Object can
supply both the security boundary and resource/lifetime controls needed by the
Windows backend on Windows 10 Home.

TD110 remains open until the real Forge runner uses this backend, real Python
and Dart/Flutter toolchains execute inside it, guard-break tests fail when
controls are removed, and the Self-Extension promotion/reuse path passes.


## TD110 Stage 4 partial: real Python passes; dartdev CLI hits AppContainer path-canonicalization limit

Physical Windows 10 Home batch at commit `0447c0d17529f22a5edaab877e5d495a0a2d2562` observed:

- isolation boundary: PASS
- Job Object resource/lifetime controls: PASS
- Python 3.12.10 direct AppContainer smoke: PASS
- Python generated test / compileall / runtime probe: PASS
- Dart 3.13.2 direct AppContainer smoke (`--version`): PASS
- Dart `run` / `analyze`: FAIL with exit 255 before generated source runs
- ACL cleanup: PASS

The Dart failure stack is:

```text
type 'Null' is not a subtype of type 'String'
_Platform.resolvedExecutable
Sdk._createSingleton
VmInteropHandler.initialize
```

This distinguishes executable viability from dartdev viability: `dart.exe` itself
starts successfully as an AppContainer process, while dartdev initialization fails
when it asks Dart for a canonical resolved executable path.

Current investigation therefore keeps the AppContainer boundary intact and probes a
Dart VM route using `--disable-dart-dev` plus kernel snapshot generation. We will
not weaken the sandbox or grant broad Windows object-manager permissions merely to
make dartdev pass.

TD110 remains open until the chosen Dart route passes physical Windows mutation
tests and is integrated into the production sandbox runner / Self-Extension path.


### Dart Windows launcher follow-up

A subsequent physical Windows run showed that the first proposed
`dart --disable-dart-dev` workaround is not sufficient. On Windows, the
distributed `dart.exe` launcher still transitions to `dartvm.exe`. In this
AppContainer, Dart's Windows launcher cannot resolve its DOS canonical executable
path and constructs an empty `--resolved_executable_name=` argument. The child
then exits before generated Dart executes.

Observed evidence:

```text
dart-vm-test/build/runtime exit = 0xC0000008
Empty value for option resolved_executable_name
Setting VM flags failed: Unrecognized flags: resolved_executable_name
```

The next probe therefore bypasses `dart.exe` entirely and launches the SDK's
`bin\\dartvm.exe` directly, supplying explicit executable and resolved-executable
identity. This keeps the AppContainer boundary unchanged and tests the primitive
that a production Windows runner could actually use.
