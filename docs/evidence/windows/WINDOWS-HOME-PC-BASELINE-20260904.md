# Windows Home PC Baseline Evidence — 2026-09-04

## Scope

Freshly initialized Windows home PC used as a real portability / distribution check for Forge.

This record began as evidence-only while the Windows backend was incomplete. The final section records the physical production-validation run that closes the **Windows portion** of TD110. macOS remains a separate unimplemented backend.

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


### Dart direct-VM file path still blocked by AppContainer DOS canonicalization

Physical Windows 10 Home run after `c2c7091` confirmed that bypassing
`dart.exe` and invoking `dartvm.exe` directly is necessary but not sufficient.

Observed:

```text
dartvm direct --version: PASS
generated Python test/build/runtime: PASS
dartvm generated source by ordinary C:\\... path: exit 255
Failed to canonicalize path '...capability_test.dart'. OS error: '(null)' (5).
```

This is not a workspace file-ACL failure. Dart's Windows runtime canonicalizes a
script path through `GetFinalPathNameByHandleW(..., VOLUME_NAME_DOS)`.
AppContainer denies the DOS-volume translation path even when the file itself is
readable. Microsoft has separately reproduced the same Win32 behavior and notes
that `VOLUME_NAME_NT` succeeds where `VOLUME_NAME_DOS` returns
`ERROR_ACCESS_DENIED`.

The probe now tests two non-weakened alternatives in the same physical batch:

1. `package:` URI with a sandbox-local package_config, retaining ordinary
   multi-file generated Dart and relative imports.
2. self-contained `data:` URI as a control that removes main-script filesystem
   canonicalization entirely.

The package route is the quality gate because it scales beyond command-line-sized
single-file source. The data route is diagnostic evidence only if package routing
still fails.


## TD110 Stage 4 complete: real Python + Dart package route inside AppContainer

Physical Windows 10 Home batch at commit
`1a3acee2b0315bda0f1055a3f2ba38e0042c8224` returned:

```text
01-isolation-boundary      PASS
02-job-resource-limits     PASS
03-real-toolchains         PASS
TD110 probe batch: ALL PASS
```

The real-toolchain evidence included:

```text
python_smoke         = true
python_test          = true
python_build         = true
python_runtime       = true

dartvm_visible       = true
dart_package_test    = true
dart_package_build   = true
dart_package_runtime = true

host_secret_absent   = true
acl_cleanup          = true
direct_smoke_ok      = true
```

The ordinary Windows `dart run` / `dart analyze` and direct file-path
`dartvm.exe` routes remain incompatible with AppContainer because Dart asks
Windows for a DOS-canonical path. That incompatibility is preserved as diagnostic
evidence rather than hidden.

The successful production candidate is:

```text
AppContainer + Job Object
  -> dartvm.exe directly
  -> explicit executable identity
  -> sandbox-local package_config
  -> package:forge_extension/<entry.dart>
  -> kernel snapshot generation for build/type-check gate
```

This route keeps multi-file generated Dart and relative imports, does not grant
network capabilities, and does not broaden host filesystem ACLs beyond temporary
RX grants on the exact toolchain roots plus non-inheriting ancestor traversal.

Stage 4 is complete. TD110 itself remains open until the production
`forge_ai.core.sandbox` backend passes the physical full escape corpus and the
previously failing Self-Extension generate -> verify -> promote -> install -> reuse
tests on this machine.


## TD110 production integration attempt: foundation defects found

Physical Windows 10 Home production-validation run at commit
`4f7aa31626a981989d5923ca60131b1dfb106588` produced:

```text
PASS  01 TD110 physical probes
FAIL  02 production escape corpus
FAIL  03 full forge_ai Self-Extension suite
PASS  04 backend regression
working tree clean = true
policy-only fallback = disabled
```

This was valuable: the probe implementation was healthy, while the first
production backend wiring exposed defects that the isolated probes could not see.

Root causes identified from the physical run:

1. the production execution timeout began **before** first-use recursive toolchain
   ACL projection. On the fresh PC that projection consumed tens of seconds, so
   some commands entered the AppContainer with almost no execution budget left.
   This explained false wall-clock failures, empty network/write output, and
   Self-Extension commands stopping before runtime-probe evidence.
2. production Job Object CPU policy used only per-job user time. The backend now
   additionally applies `JOB_OBJECT_LIMIT_PROCESS_TIME` with the same bounded
   budget to make the Python workload limit explicit.
3. the production backend recreated a new AppContainer SID and recursively
   rewrote Python/Dart toolchain ACLs for every command. This made the complete
   suite take roughly 95 minutes. The backend now reuses one random ephemeral
   AppContainer identity per host Python process, caches exact toolchain RX
   projection for that SID, and still grants/removes each generated workspace
   independently.
4. the Windows escape corpus contained Linux-specific resource expectations and
   platform guards that were not yet production-grade. Windows now has explicit
   Job Object process-limit coverage and Windows memory-limit semantics.

The next production run is gated: the expensive full suite executes only after
the physical probes, production escape corpus, and the previously failing
Self-Extension regression files pass.


### Production escape corpus follow-up: 27/28 effective checks, memory verdict fixed

Physical Windows 10 Home run from branch HEAD `d805b3c` showed that the
production escape corpus was down to one reported failure:

```text
network deny                     PASS
DNS deny                         PASS
wall-clock timeout               PASS
CPU limit                        PASS
workspace write                  PASS
workspace max-file monitor       PASS
secret/env scrub                 PASS
Windows child-process limit      PASS
memory bomb                      reported FAIL
Linux-only PID/fork checks        SKIP (expected)
```

The memory result itself was not an escape. The child returned:

```text
exit_code       = 0
timed_out       = false
stdout_bytes    = 22
```

On Windows Job Object memory enforcement, Python can receive an allocation
failure, raise `MemoryError`, let the test program catch it, print
`blocked: MemoryError`, and then exit 0. The previous Windows assertion
incorrectly required a non-zero process exit for every valid memory-limit
outcome. The corpus now accepts either:

1. handled `MemoryError` with the explicit blocked marker, or
2. hard Job/process termination with a non-zero exit,

while still rejecting wall-clock timeout as proof of memory enforcement.

The next rerun also contains production integration fixes not present in this
physical result: one AppContainer SID per host test process, cached toolchain RX
projection, command timeout starting after isolation setup, and explicit
per-process CPU time enforcement.


## FINAL — Windows 10 Home production validation: ALL PASS

Physical Windows 10 Home execution on 2026-09-04 at repository commit
`7f8e000ce53165512c66132018a888c560c61ca4` completed the one-shot production
validation with `FORGE_SANDBOX_ALLOW_POLICY_ONLY` explicitly disabled.

Observed host resources at launch:

```text
RAM installed : 7.92 GB
RAM free      : 2.76 GB
Page file     : 1.88 GB
```

Observed result:

```text
PASS  01 production escape corpus             exit=0   169.8s
PASS  02 TD110 physical probes                exit=0   239.3s
PASS  03 targeted Self-Extension regressions  exit=0   218.5s
PASS  04 full forge_ai Self-Extension suite   exit=0   257.1s
PASS  05 backend regression                   exit=0    74.2s

Working tree clean: True
Policy-only fallback: DISABLED

TD110 production validation: ALL PASS
```

This run is the first complete physical-Windows proof of the production backend,
not merely the isolated probe implementation.

The evidence now establishes, on the actual Windows 10 Home distribution target:

- AppContainer no-capability OS boundary is active.
- outbound network and DNS escape tests are blocked.
- host secrets and host environment are not inherited.
- workspace write is allowed while host/outside access remains denied.
- Job Object wall-clock, CPU, memory and active-process controls are exercised by
  the production runner.
- oversized workspace file growth is stopped.
- real Python test/build/runtime execution succeeds in the sandbox.
- real Dart execution succeeds through the AppContainer-safe
  `dartvm.exe + package:` route, including kernel build/type-check gate.
- the production escape corpus passes; Linux-only PID namespace / `os.fork`
  observations are intentionally skipped on Windows and replaced by Windows Job
  Object process-limit coverage.
- the previously failing Self-Extension regression families pass.
- the complete `forge_ai` Self-Extension suite passes.
- backend regression passes.
- generated execution does not rely on the weaker `policy-only` fallback.
- the repository remains clean after validation.

### Closure decision

**Windows portion of TD110: RESOLVED on Windows 10 Home.**

The tested production backend is:

```text
windows-appcontainer+job
```

and the Windows Self-Extension path now reaches the intended
generate -> verify -> promote -> install/reuse behavior under OS isolation.

This does **not** prove macOS sandbox support, Android/iOS device behavior,
all 121 capabilities at 99%, or the global Security/Sandbox hard gate across
every target OS. macOS remains unimplemented and must stay explicit in the
capability matrix / tech-debt ledger rather than being hidden by the Windows pass.
