param(
    [switch]$SkipPull
)

$ErrorActionPreference = "Continue"

$Repo = Split-Path -Parent $PSScriptRoot
$Branch = "claude/forge-master-handoff-k46jns"
$Stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$RunDir = Join-Path $env:TEMP ("forge-td110-" + $Stamp)
New-Item -ItemType Directory -Force -Path $RunDir | Out-Null

function Write-Section([string]$Title) {
    Write-Host ""
    Write-Host ("=== " + $Title + " ===") -ForegroundColor Cyan
}

function Run-Step(
    [string]$Name,
    [string]$Command,
    [string[]]$Arguments
) {
    Write-Section $Name
    $Log = Join-Path $RunDir (($Name -replace '[^A-Za-z0-9_-]', '_') + ".log")

    & $Command @Arguments 2>&1 | Tee-Object -FilePath $Log
    $Code = $LASTEXITCODE

    if ($Code -eq 0) {
        Write-Host ("PASS: " + $Name) -ForegroundColor Green
    } else {
        Write-Host ("FAIL: " + $Name + " (exit " + $Code + ")") -ForegroundColor Red
    }

    return [pscustomobject]@{
        Name = $Name
        ExitCode = $Code
        Log = $Log
    }
}

Set-Location $Repo

Write-Section "Repository"
Write-Host ("Repo   : " + $Repo)
Write-Host ("Branch : " + $Branch)
Write-Host ("RunDir : " + $RunDir)

$Dirty = git status --porcelain
if ($LASTEXITCODE -ne 0) {
    Write-Host "git status failed." -ForegroundColor Red
    exit 2
}

if ($Dirty) {
    Write-Host "Working tree is dirty. Refusing automatic pull." -ForegroundColor Yellow
    $Dirty | ForEach-Object { Write-Host $_ }
    Write-Host "Fix/commit/stash the changes, or run manually with -SkipPull." -ForegroundColor Yellow
    if (-not $SkipPull) {
        exit 3
    }
}

if (-not $SkipPull) {
    Write-Section "Git pull"
    git pull --ff-only origin $Branch
    if ($LASTEXITCODE -ne 0) {
        Write-Host "git pull failed." -ForegroundColor Red
        exit 4
    }
}

Write-Host ""
git log -1 --oneline

$Python = Join-Path $Repo ".venv\Scripts\python.exe"
$PyArgsPrefix = @()

if (-not (Test-Path $Python)) {
    $PyLauncher = Get-Command py -ErrorAction SilentlyContinue
    if ($null -eq $PyLauncher) {
        Write-Host "Python 3.12 is unavailable." -ForegroundColor Red
        exit 5
    }
    $Python = $PyLauncher.Source
    $PyArgsPrefix = @("-3.12")
}

Write-Section "Python"
& $Python @PyArgsPrefix --version
if ($LASTEXITCODE -ne 0) {
    Write-Host "Python check failed." -ForegroundColor Red
    exit 6
}

$Steps = @(
    @{
        Name = "01-isolation-boundary"
        Script = "scripts\windows_appcontainer_isolation_probe.py"
    },
    @{
        Name = "02-job-resource-limits"
        Script = "scripts\windows_job_resource_probe.py"
    },
    @{
        Name = "03-real-toolchains"
        Script = "scripts\windows_toolchain_probe.py"
    }
)

$Results = @()

foreach ($Step in $Steps) {
    $Args = @()
    $Args += $PyArgsPrefix
    $Args += (Join-Path $Repo $Step.Script)

    $Result = Run-Step -Name $Step.Name -Command $Python -Arguments $Args
    $Results += $Result
}

Write-Section "Summary"
$Results | Format-Table Name, ExitCode, Log -AutoSize

$Failed = @($Results | Where-Object { $_.ExitCode -ne 0 })

Write-Host ""
Write-Host ("HEAD   : " + (git rev-parse --short HEAD))
Write-Host ("Logs   : " + $RunDir)
Write-Host ("Failed : " + $Failed.Count)

if ($Failed.Count -gt 0) {
    Write-Host ""
    Write-Host "=== COPY FROM HERE ===" -ForegroundColor Yellow
    foreach ($Item in $Failed) {
        Write-Host ""
        Write-Host ("--- " + $Item.Name + " ---")
        Get-Content $Item.Log
    }
    Write-Host ""
    Write-Host "=== COPY TO HERE ===" -ForegroundColor Yellow
    exit 1
}

Write-Host ""
Write-Host "TD110 probe batch: ALL PASS" -ForegroundColor Green
exit 0
