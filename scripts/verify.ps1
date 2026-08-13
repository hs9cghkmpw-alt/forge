#requires -Version 5.1
<#
.SYNOPSIS
    Forge repository standard verification script.

.DESCRIPTION
    Runs Python Test, flutter clean, pub get, analyze, test, build web, and
    flutter devices, in order, and records the outcome of each step. If a
    step fails, the script does not stop; it records that step as FAILED
    and continues to the end, then prints a PASS / FAIL / WARNING summary
    (WARNING = intentionally skipped, for example because -SkipBuild was
    set, or Chrome was not available for -RunChrome).

    This script also checks `flutter devices` before attempting
    `-RunChrome`: if Chrome is not listed, that step is recorded as a
    WARNING (skipped) instead of attempting to launch a browser that is
    not installed.

    This script uses only plain ASCII text (English) for all comments and
    messages. This is intentional: an earlier version of this script used
    Japanese text and was saved without a UTF-8 byte order mark (BOM).
    Windows PowerShell 5.1 does not assume UTF-8 for a .ps1 file that has
    no BOM; on a Japanese-locale Windows machine it falls back to the
    system ANSI code page (Shift_JIS / CP932), which corrupts multi-byte
    UTF-8 text and can break the script parser (missing quote, missing
    brace, missing catch). Using ASCII-only text removes this entire class
    of failure regardless of how the file is saved or read. See README.md
    for the full root-cause writeup.

    This script also carries a UTF-8 byte order mark (BOM) as a second,
    independent safeguard, in case any non-ASCII text is added later.
    Both Windows PowerShell 5.1 and PowerShell 7 (pwsh) read a UTF-8 BOM
    correctly.

    Only plain PowerShell 5.1-compatible syntax is used (no ternary
    operator, no null-coalescing operator, no ForEach-Object -Parallel).

    This script also auto-detects whether to invoke Python as "py" (the
    Windows Python Launcher, registered on PATH by the standard
    python.org installer) or "python" (used as a fallback), instead of
    hardcoding "python". A machine with only "py" available previously
    caused Python Test to fail with exit code 9009 (command not found).

.PARAMETER RunChrome
    After a successful flutter build web, also run `flutter run -d chrome`.

.PARAMETER SkipPython
    Skip Python Test (for example, if no Python environment is available).

.PARAMETER SkipBuild
    Skip `flutter build web --debug` (for a faster check).

.EXAMPLE
    .\scripts\verify.ps1
.EXAMPLE
    .\scripts\verify.ps1 -RunChrome
.EXAMPLE
    .\scripts\verify.ps1 -SkipPython
.EXAMPLE
    .\scripts\verify.ps1 -SkipBuild
#>

[CmdletBinding()]
param(
    [switch]$RunChrome,
    [switch]$SkipPython,
    [switch]$SkipBuild
)

# ---------------------------------------------------------------------------
# Repository root auto-detect: this script is expected to live at
# forge/scripts/verify.ps1, so the parent of scripts/ is the repo root.
# ---------------------------------------------------------------------------
$RepoRoot = Split-Path -Parent $PSScriptRoot
$FrontendDir = Join-Path $RepoRoot "frontend"
$BackendDir = Join-Path $RepoRoot "backend"

Write-Host "==================================================================" -ForegroundColor Cyan
Write-Host " Forge Verify Script" -ForegroundColor Cyan
Write-Host " Repository Root: $RepoRoot" -ForegroundColor Cyan
Write-Host "==================================================================" -ForegroundColor Cyan

# ---------------------------------------------------------------------------
# Python command detection (CEO review: exit code 9009 = command not found).
# On many Windows Python installations (the default from python.org), the
# "py" launcher is registered on PATH but a plain "python" command is not
# (or points to the Microsoft Store stub). Prefer "py" first, then fall
# back to "python". Detected once here and reused everywhere below instead
# of hardcoding either name.
# ---------------------------------------------------------------------------
#
# FORGE-HANDOFF-LOCAL-AI-UX-004 (2026-08-13): version selection, not just
# presence. Picking the first interpreter that exists is not enough. The
# backend pins pydantic 2.7.4 and supabase 2.5.1, neither of which ships
# wheels for Python 3.13; on a machine whose default interpreter is 3.13,
# `pip install -r requirements.txt` tries to build them from source and
# fails. The supported range is Python >= 3.11 and < 3.13 (see
# backend/requirements.txt and GETTING_STARTED.md).
#
# So: enumerate the candidate interpreters, ask each one for its version,
# and use the first one inside the supported range. If only an unsupported
# interpreter is present, say so explicitly rather than running it and
# letting the failure surface as a confusing pip error.
# ---------------------------------------------------------------------------
$PythonMinMinor = 11
$PythonMaxMinorExclusive = 13

function Get-PythonVersionTuple {
    <#
        Returns "major.minor" for a candidate command, or $null if the
        command cannot be run at all. Any failure is treated as "not a
        usable interpreter" rather than an error.
    #>
    param(
        [Parameter(Mandatory = $true)][string]$Command,
        [string[]]$Arguments = @()
    )
    try {
        $VersionArgs = $Arguments + @("-c", "import sys; print('%d.%d' % sys.version_info[:2])")
        $Output = (& $Command @VersionArgs 2>$null | Out-String).Trim()
        if ($LASTEXITCODE -ne 0) { return $null }
        if ($Output -match "^\d+\.\d+$") { return $Output }
        return $null
    }
    catch {
        return $null
    }
}

function Test-PythonVersionSupported {
    param([Parameter(Mandatory = $true)][string]$Version)
    $Parts = $Version.Split(".")
    $Major = [int]$Parts[0]
    $Minor = [int]$Parts[1]
    if ($Major -ne 3) { return $false }
    if ($Minor -lt $PythonMinMinor) { return $false }
    if ($Minor -ge $PythonMaxMinorExclusive) { return $false }
    return $true
}

# Candidates in preference order. The "py -3.12" / "py -3.11" forms let the
# Windows Python Launcher select a specific version even when the default
# one it would pick is unsupported - that is the whole point of trying them
# before falling back to a bare launcher invocation.
$PythonCandidates = @(
    @{ Command = "py"; Arguments = @("-3.12"); Label = "py -3.12" },
    @{ Command = "py"; Arguments = @("-3.11"); Label = "py -3.11" },
    @{ Command = "py"; Arguments = @(); Label = "py" },
    @{ Command = "python3"; Arguments = @(); Label = "python3" },
    @{ Command = "python"; Arguments = @(); Label = "python" }
)

$PythonCmd = $null
$PythonArgs = @()
$PythonLabel = $null
$PythonRejected = @()

foreach ($Candidate in $PythonCandidates) {
    if (-not (Get-Command $Candidate.Command -ErrorAction SilentlyContinue)) { continue }
    $Version = Get-PythonVersionTuple -Command $Candidate.Command -Arguments $Candidate.Arguments
    if ($null -eq $Version) { continue }
    if (Test-PythonVersionSupported -Version $Version) {
        $PythonCmd = $Candidate.Command
        $PythonArgs = $Candidate.Arguments
        $PythonLabel = "$($Candidate.Label) (Python $Version)"
        break
    }
    $PythonRejected += "$($Candidate.Label) = Python $Version"
}

$PythonSkipReason = $null
if ($null -eq $PythonCmd) {
    if ($PythonRejected.Count -gt 0) {
        $PythonSkipReason = "no supported Python found (need >= 3.$PythonMinMinor and < 3.$PythonMaxMinorExclusive); found: " + ($PythonRejected -join ", ")
        Write-Host "[WARN] $PythonSkipReason" -ForegroundColor Yellow
        Write-Host "[WARN] Install Python 3.12 from python.org, then re-run this script." -ForegroundColor Yellow
    }
    else {
        $PythonSkipReason = "no 'py', 'python3' or 'python' command found on PATH"
        Write-Host "[WARN] $PythonSkipReason Python Test steps will be skipped." -ForegroundColor Yellow
    }
}
else {
    Write-Host " Python command detected: $PythonLabel" -ForegroundColor Cyan
}

if (-not (Test-Path $FrontendDir)) {
    Write-Host "[FATAL] frontend/ not found: $FrontendDir" -ForegroundColor Red
    Write-Host "This script expects to be placed at forge/scripts/verify.ps1" -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}

# ---------------------------------------------------------------------------
# Log file: use a timestamped file name on every run so old logs are never
# overwritten or locked by a previous run. Start-Transcript is the only
# logging mechanism used here; Tee-Object is not combined with it (writing
# to the same file with both at once is a known source of file-handle
# conflicts).
# ---------------------------------------------------------------------------
$LogDir = Join-Path $RepoRoot "verify_logs"
if (-not (Test-Path $LogDir)) {
    New-Item -ItemType Directory -Path $LogDir | Out-Null
}
$Timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$LogPath = Join-Path $LogDir "verify_$Timestamp.log"

try {
    Start-Transcript -Path $LogPath -Append | Out-Null
}
catch {
    Write-Host "[WARN] Start-Transcript failed, continuing without a log file: $_" -ForegroundColor Yellow
}

# Step results (PowerShell 5.1-compatible ordered hashtable).
$Results = [ordered]@{}

function Invoke-Step {
    <#
        Runs one step and records its exit code in $Results. If the step
        throws, the exception is caught and recorded as a failure; the
        overall script keeps going instead of stopping.
    #>
    param(
        [Parameter(Mandatory = $true)][string]$Name,
        [Parameter(Mandatory = $true)][scriptblock]$Action
    )

    Write-Host ""
    Write-Host "------------------------------------------------------------------" -ForegroundColor DarkGray
    Write-Host ">> $Name" -ForegroundColor Cyan
    Write-Host "------------------------------------------------------------------" -ForegroundColor DarkGray

    try {
        & $Action
        $ExitCode = $LASTEXITCODE
        if ($null -eq $ExitCode) {
            # Commands that do not set $LASTEXITCODE (for example New-Item)
            # are treated as successful.
            $ExitCode = 0
        }
    }
    catch {
        Write-Host "[EXCEPTION] $Name : $_" -ForegroundColor Red
        $ExitCode = 1
    }

    $Passed = ($ExitCode -eq 0)
    $Results[$Name] = @{ Status = "PASS"; ExitCode = $ExitCode }
    if (-not $Passed) {
        $Results[$Name] = @{ Status = "FAIL"; ExitCode = $ExitCode }
    }

    if ($Passed) {
        Write-Host "[OK] $Name (exit code $ExitCode)" -ForegroundColor Green
    }
    else {
        Write-Host "[FAILED] $Name (exit code $ExitCode)" -ForegroundColor Red
    }
}

function Skip-Step {
    <#
        Records a step as intentionally skipped (WARNING in the final
        summary), instead of leaving it silently absent from $Results.
        CEO review: the final PASS/FAIL summary should also surface
        anything that was NOT run, so a reader cannot mistake "not run"
        for "passed".
    #>
    param(
        [Parameter(Mandatory = $true)][string]$Name,
        [Parameter(Mandatory = $true)][string]$Reason
    )
    Write-Host "[SKIP] $Name : $Reason" -ForegroundColor Yellow
    $Results[$Name] = @{ Status = "WARNING"; ExitCode = $null; Reason = $Reason }
}

# ---------------------------------------------------------------------------
# Python Test
# ---------------------------------------------------------------------------
if (-not $SkipPython) {
    if ($null -eq $PythonCmd) {
        Skip-Step -Name "Python Test (backend)" -Reason $PythonSkipReason
        Skip-Step -Name "Python Test (forge_ai)" -Reason $PythonSkipReason
    }
    else {
        if (Test-Path $BackendDir) {
            # FORGE-MILESTONE-005: backend/tests/test_http_api.py needs fastapi/pydantic
            # to actually run (it self-skips gracefully otherwise, per its own
            # _FASTAPI_AVAILABLE check). Installing requirements.txt here means the
            # CEO's real environment actually exercises those tests instead of
            # silently skipping them for a missing-dependency reason.
            $InstallStepName = "pip install -r requirements.txt (backend)"
            Invoke-Step -Name $InstallStepName -Action {
                Push-Location $BackendDir
                try {
                    & $PythonCmd @PythonArgs -m pip install -r requirements.txt
                }
                finally {
                    Pop-Location
                }
            }

            # FORGE-HANDOFF-LOCAL-AI-UX-004 (2026-08-13): do NOT run the
            # backend tests when the install failed. Previously the script
            # continued regardless, so a dependency problem surfaced as a
            # wall of import errors from the test run - which reads like a
            # code failure and buries the actual cause several screens up.
            # One failing step, named for what actually broke, is clearer.
            if ($Results[$InstallStepName].Status -eq "PASS") {
                Invoke-Step -Name "Python Test (backend)" -Action {
                    Push-Location $BackendDir
                    try {
                        & $PythonCmd @PythonArgs -m unittest discover -s tests -p "test_*.py"
                    }
                    finally {
                        Pop-Location
                    }
                }
            }
            else {
                Skip-Step -Name "Python Test (backend)" -Reason "dependency install failed; fix that first (see the step above)"
            }
        }
        else {
            Skip-Step -Name "Python Test (backend)" -Reason "backend/ not found"
        }

        $ForgeAiDir = Join-Path $RepoRoot "forge_ai"
        if (Test-Path $ForgeAiDir) {
            # forge_ai has no third-party dependencies (standard library
            # only), so it runs even when the backend install failed.
            Invoke-Step -Name "Python Test (forge_ai)" -Action {
                Push-Location $RepoRoot
                try {
                    & $PythonCmd @PythonArgs -m unittest discover -s forge_ai/tests -p "test_*.py"
                }
                finally {
                    Pop-Location
                }
            }
        }
        else {
            Skip-Step -Name "Python Test (forge_ai)" -Reason "forge_ai/ not found"
        }
    }
}
else {
    Skip-Step -Name "Python Test (backend)" -Reason "-SkipPython was set"
    Skip-Step -Name "Python Test (forge_ai)" -Reason "-SkipPython was set"
}

# ---------------------------------------------------------------------------
# Flutter steps (all run inside frontend/)
# ---------------------------------------------------------------------------
Push-Location $FrontendDir
try {
    Invoke-Step -Name "flutter clean" -Action { flutter clean }
    Invoke-Step -Name "flutter pub get" -Action { flutter pub get }
    Invoke-Step -Name "flutter analyze" -Action { flutter analyze }
    Invoke-Step -Name "flutter test" -Action { flutter test --reporter expanded }

    if (-not $SkipBuild) {
        Invoke-Step -Name "flutter build web --debug" -Action { flutter build web --debug }
    }
    else {
        Skip-Step -Name "flutter build web --debug" -Reason "-SkipBuild was set"
    }

    # CEO review: not everyone running this script has Chrome installed.
    # `flutter devices` is informational and always runs (cheap, fast); its
    # output is also used to decide whether -RunChrome can actually proceed,
    # instead of blindly invoking `flutter run -d chrome` and failing or
    # hanging on a machine without Chrome.
    #
    # Implementation note: the output is captured directly in this scope
    # (not inside a scriptblock passed to Invoke-Step) because a scriptblock
    # invoked via the `&` call operator runs in a child scope, and an
    # assignment to an outer-scope variable from inside it would not
    # reliably propagate back out. Capturing here first, then recording the
    # PASS/FAIL result separately, avoids that risk entirely.
    Write-Host ""
    Write-Host "------------------------------------------------------------------" -ForegroundColor DarkGray
    Write-Host ">> flutter devices" -ForegroundColor Cyan
    Write-Host "------------------------------------------------------------------" -ForegroundColor DarkGray
    $DevicesOutput = ""
    $DevicesExitCode = 0
    try {
        $DevicesOutput = (flutter devices 2>&1 | Out-String)
        $DevicesExitCode = $LASTEXITCODE
        if ($null -eq $DevicesExitCode) { $DevicesExitCode = 0 }
        Write-Host $DevicesOutput
    }
    catch {
        Write-Host "[EXCEPTION] flutter devices : $_" -ForegroundColor Red
        $DevicesExitCode = 1
    }
    if ($DevicesExitCode -eq 0) {
        $Results["flutter devices"] = @{ Status = "PASS"; ExitCode = $DevicesExitCode }
        Write-Host "[OK] flutter devices (exit code $DevicesExitCode)" -ForegroundColor Green
    }
    else {
        $Results["flutter devices"] = @{ Status = "FAIL"; ExitCode = $DevicesExitCode }
        Write-Host "[FAILED] flutter devices (exit code $DevicesExitCode)" -ForegroundColor Red
    }

    if ($RunChrome) {
        $ChromeAvailable = $false
        if ($DevicesOutput -match "(?i)chrome") {
            $ChromeAvailable = $true
        }

        if ($ChromeAvailable) {
            Write-Host ""
            Write-Host "------------------------------------------------------------------" -ForegroundColor DarkGray
            Write-Host ">> flutter run -d chrome (manual check, close Chrome or press 'q' to stop)" -ForegroundColor Cyan
            Write-Host "------------------------------------------------------------------" -ForegroundColor DarkGray
            # flutter run stays in the foreground until the user stops it, so it
            # is not tracked in $Results the way the other steps are.
            flutter run -d chrome
        }
        else {
            Skip-Step -Name "flutter run -d chrome" -Reason "Chrome not found in 'flutter devices' output; run 'flutter config --enable-web' and install Chrome, or verify manually"
        }
    }
    else {
        Skip-Step -Name "flutter run -d chrome" -Reason "-RunChrome was not set"
    }
}
finally {
    Pop-Location
}

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
Write-Host ""
Write-Host "==================================================================" -ForegroundColor Cyan
Write-Host " SUMMARY" -ForegroundColor Cyan
Write-Host "==================================================================" -ForegroundColor Cyan

$AnyFailed = $false
$AnyWarning = $false
foreach ($Key in $Results.Keys) {
    $Entry = $Results[$Key]
    if ($Entry.Status -eq "PASS") {
        Write-Host ("  [PASS]    {0} (exit {1})" -f $Key, $Entry.ExitCode) -ForegroundColor Green
    }
    elseif ($Entry.Status -eq "WARNING") {
        Write-Host ("  [WARNING] {0} - {1}" -f $Key, $Entry.Reason) -ForegroundColor Yellow
        $AnyWarning = $true
    }
    else {
        Write-Host ("  [FAIL]    {0} (exit {1})" -f $Key, $Entry.ExitCode) -ForegroundColor Red
        $AnyFailed = $true
    }
}

Write-Host ""
if ($AnyFailed) {
    Write-Host "One or more steps FAILED. Check the summary above and the log file." -ForegroundColor Red
}
elseif ($AnyWarning) {
    Write-Host "All executed steps PASSED, but one or more steps were SKIPPED (see WARNING above)." -ForegroundColor Yellow
}
else {
    Write-Host "All steps PASSED." -ForegroundColor Green
}
Write-Host "Log file: $LogPath" -ForegroundColor DarkGray

try {
    Stop-Transcript | Out-Null
}
catch {
    # If Start-Transcript failed earlier, Stop-Transcript will also fail; ignore.
}

Write-Host ""
Read-Host "Press Enter to close this window"
