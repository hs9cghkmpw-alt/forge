param(
    [string]$BaseUrl = 'http://localhost:7358',
    [string]$OutputDirectory = ''
)

$repoRoot = Split-Path -Parent $PSScriptRoot
if (-not $OutputDirectory) { $OutputDirectory = Join-Path $repoRoot 'docs\visual-evidence\FORGE-019' }
New-Item -ItemType Directory -Force -Path $OutputDirectory | Out-Null
$edge = 'C:\Program Files\Google\Chrome\Application\chrome.exe'
if (-not (Test-Path -LiteralPath $edge)) { $edge = 'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe' }
if (-not (Test-Path -LiteralPath $edge)) { throw 'Chrome or Edge is required for deterministic capture.' }
$beforePath = Join-Path $OutputDirectory 'finance-before.png'
$afterPath = Join-Path $OutputDirectory 'finance-after-balance-emphasis.png'
$captureNonce = [DateTimeOffset]::UtcNow.ToUnixTimeMilliseconds()
$beforeProfile = Join-Path $env:TEMP "forge-019-headless-before-$captureNonce"
$afterProfile = Join-Path $env:TEMP "forge-019-headless-after-$captureNonce"
New-Item -ItemType Directory -Force -Path $beforeProfile | Out-Null
New-Item -ItemType Directory -Force -Path $afterProfile | Out-Null
& $edge --headless=new --no-sandbox --use-gl=swiftshader --enable-unsafe-swiftshader --hide-scrollbars --window-size=390,844 --virtual-time-budget=15000 "--user-data-dir=$beforeProfile" "--screenshot=$beforePath" "$BaseUrl/?state=before"
for ($attempt = 0; $attempt -lt 20 -and -not (Test-Path -LiteralPath $beforePath); $attempt++) { Start-Sleep -Milliseconds 250 }
if (-not (Test-Path -LiteralPath $beforePath)) { throw 'Before route capture failed.' }
& $edge --headless=new --no-sandbox --use-gl=swiftshader --enable-unsafe-swiftshader --hide-scrollbars --window-size=390,844 --virtual-time-budget=15000 "--user-data-dir=$afterProfile" "--screenshot=$afterPath" "$BaseUrl/?state=after"
for ($attempt = 0; $attempt -lt 20 -and -not (Test-Path -LiteralPath $afterPath); $attempt++) { Start-Sleep -Milliseconds 250 }
if (-not (Test-Path -LiteralPath $afterPath)) { throw 'After route capture failed.' }
