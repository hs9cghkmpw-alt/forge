param(
    [switch]$SkipPull
)

$ErrorActionPreference = "Stop"

$Repo = Split-Path -Parent $PSScriptRoot
$Branch = "claude/forge-master-handoff-k46jns"
Set-Location $Repo

Write-Host ""
Write-Host "=== Repository ===" -ForegroundColor Cyan
Write-Host ("Repo   : " + $Repo)
Write-Host ("Branch : " + $Branch)

$Dirty = git status --porcelain
if ($LASTEXITCODE -ne 0) {
    Write-Host "git status failed." -ForegroundColor Red
    exit 2
}

if ($Dirty -and -not $SkipPull) {
    Write-Host "Working tree is dirty; refusing automatic pull." -ForegroundColor Yellow
    $Dirty | ForEach-Object { Write-Host $_ }
    Write-Host "Commit/stash the changes, or rerun with -SkipPull." -ForegroundColor Yellow
    exit 3
}

if (-not $SkipPull) {
    Write-Host ""
    Write-Host "=== Git pull ===" -ForegroundColor Cyan
    git pull --ff-only origin $Branch
    if ($LASTEXITCODE -ne 0) {
        Write-Host "git pull failed." -ForegroundColor Red
        exit 4
    }
}

Write-Host ""
git log -1 --oneline

$Batch = Join-Path $Repo "scripts\windows_td110_batch.py"
$VenvPython = Join-Path $Repo ".venv\Scripts\python.exe"

Write-Host ""
Write-Host "=== Batch ===" -ForegroundColor Cyan

if (Test-Path $VenvPython) {
    & $VenvPython $Batch
    exit $LASTEXITCODE
}

$Py = Get-Command py -ErrorAction SilentlyContinue
if ($null -eq $Py) {
    Write-Host "Python 3.12 is unavailable." -ForegroundColor Red
    exit 5
}

& $Py.Source -3.12 $Batch
exit $LASTEXITCODE
