param()

$ErrorActionPreference = "Stop"
$Repo = Split-Path -Parent $PSScriptRoot
$Branch = "claude/forge-master-handoff-k46jns"
Set-Location $Repo

Write-Host ""
Write-Host "=== Forge TD110 final Windows batch ===" -ForegroundColor Cyan

$Dirty = git status --porcelain
if ($LASTEXITCODE -ne 0) {
    Write-Host "git status failed." -ForegroundColor Red
    exit 2
}
if ($Dirty) {
    Write-Host "Working tree is dirty; refusing automatic pull." -ForegroundColor Yellow
    $Dirty | ForEach-Object { Write-Host $_ }
    exit 3
}

git pull --ff-only origin $Branch
if ($LASTEXITCODE -ne 0) {
    Write-Host "git pull failed." -ForegroundColor Red
    exit 4
}

git log -1 --oneline

$Python = Join-Path $Repo ".venv\Scripts\python.exe"
if (-not (Test-Path $Python)) {
    Write-Host "Forge .venv Python is missing: $Python" -ForegroundColor Red
    exit 5
}

Remove-Item Env:FORGE_SANDBOX_ALLOW_POLICY_ONLY -ErrorAction SilentlyContinue

& $Python (Join-Path $Repo "scripts\windows_td110_production_validation.py")
exit $LASTEXITCODE
