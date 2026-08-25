param(
    [int]$BackendPort = 8000,
    [int]$FlutterPort = 7357
)

$repoRoot = Split-Path -Parent $PSScriptRoot
Start-Process powershell -WindowStyle Hidden -ArgumentList '-NoProfile', '-Command', "Set-Location '$repoRoot\backend'; python -m uvicorn app.main:app --port $BackendPort"
Start-Process powershell -WindowStyle Hidden -ArgumentList '-NoProfile', '-Command', "Set-Location '$repoRoot\frontend'; flutter run -d web-server --web-port $FlutterPort"
Write-Host "Forge backend: http://localhost:$BackendPort"
Write-Host "Forge Flutter: http://localhost:$FlutterPort"
