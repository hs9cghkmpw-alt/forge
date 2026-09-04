param()

$ErrorActionPreference = "Stop"
$Repo = Split-Path -Parent $PSScriptRoot
$Branch = "claude/forge-master-handoff-k46jns"
Set-Location $Repo

Write-Host ""
Write-Host "=== Forge TD110 final Windows batch ===" -ForegroundColor Cyan

# This validation never shuts Windows down or restarts it.
# RAM values are diagnostic only. An 8 GB machine often reports about 7.9 GB
# because of hardware reservation; that must not be treated as "insufficient".
try {
    $Computer = Get-CimInstance Win32_ComputerSystem
    $OS = Get-CimInstance Win32_OperatingSystem
    $TotalRamGB = [math]::Round($Computer.TotalPhysicalMemory / 1GB, 2)
    $FreeRamGB = [math]::Round(($OS.FreePhysicalMemory * 1KB) / 1GB, 2)
    $PageFiles = @(Get-CimInstance Win32_PageFileUsage -ErrorAction SilentlyContinue)
    $PageFileGB = if ($PageFiles.Count -gt 0) {
        [math]::Round((($PageFiles | Measure-Object -Property AllocatedBaseSize -Sum).Sum) / 1024, 2)
    } else {
        0
    }

    Write-Host "RAM installed : $TotalRamGB GB"
    Write-Host "RAM free      : $FreeRamGB GB"
    Write-Host "Page file     : $PageFileGB GB"

    if ($FreeRamGB -lt 1.5) {
        Write-Host "WARNING: free RAM is low. The test will continue; closing heavy apps may improve stability." -ForegroundColor Yellow
    }
} catch {
    Write-Host "WARNING: RAM/page-file diagnostics failed; validation will continue." -ForegroundColor Yellow
}

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
