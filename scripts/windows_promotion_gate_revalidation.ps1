# FORGE-PROMOTION-HARD-GATE-001A — Windows 実機 再試験（1 本で完結）
#
# Promotion の**本番配線**を変えたので、Windows 実機で Self-Extension の
# Promotion 経路だけを確かめる。**TD110 physical probes の全再実行は不要。**
#
# 使い方（PowerShell を管理者で開かなくてよい）:
#
#     cd <forge を clone した場所>
#     powershell -ExecutionPolicy Bypass -File scripts\windows_promotion_gate_revalidation.ps1
#
# 出力の最後に PASS / FAIL が 1 行で出る。その行を貼ってください。

$ErrorActionPreference = "Stop"
$repo = Split-Path -Parent $PSScriptRoot
Set-Location $repo

# **policy-only を絶対に使わない。** これを立てると OS 隔離を通らずに
# 通ってしまい、実機で確かめた意味が消える。
Remove-Item Env:FORGE_SANDBOX_ALLOW_POLICY_ONLY -ErrorAction SilentlyContinue

$python = if (Test-Path ".venv\Scripts\python.exe") { ".venv\Scripts\python.exe" } else { "python" }

Write-Host "== Forge Promotion Gate — Windows 実機 再試験 ==" -ForegroundColor Cyan
Write-Host "repo   : $repo"
Write-Host "python : $python"
Write-Host ""

$results = [ordered]@{}

function Invoke-Step($name, $arguments) {
    Write-Host "-- $name" -ForegroundColor Yellow
    & $python @arguments
    $ok = ($LASTEXITCODE -eq 0)
    $script:results[$name] = $ok
    if ($ok) { Write-Host "   PASS`n" -ForegroundColor Green }
    else     { Write-Host "   FAIL`n" -ForegroundColor Red }
}

# 1. Sandbox backend が Windows 実機で OS 隔離を名乗ること
Write-Host "-- 00 sandbox backend の実測" -ForegroundColor Yellow
& $python -c @"
import json, sys
sys.path.insert(0, '.')
from forge_ai.core.sandbox.runner import describe_environment
info = describe_environment()
print(json.dumps(info, ensure_ascii=False))
if info.get('policy_only_allowed'):
    print('policy-only が許可されている。実機証拠にならない'); raise SystemExit(1)
if not info.get('os_isolation'):
    print('OS 隔離が使えない'); raise SystemExit(1)
"@
$results["00 sandbox backend"] = ($LASTEXITCODE -eq 0)
Write-Host ""

# 2. Promotion Gate 本体
Invoke-Step "01 promotion gate" @("-m","pytest","forge_ai/tests/test_promotion_gate.py","-q")

# 3. 偽造 PROMOTED の拒否（今回の Major 1）
Invoke-Step "02 forged promotion" @("-m","pytest","forge_ai/tests/test_promotion_forgery.py","-q")

# 4. Gate の本番配線
Invoke-Step "03 gate wiring" @("-m","pytest","forge_ai/tests/test_promotion_gate_wiring.py","-q")

# 5. 生成 Source の Effect 検査
Invoke-Step "04 effect corpus" @("-m","pytest","forge_ai/tests/test_generated_source_effect_corpus.py","-q")

# 6. Self-Extension の本番経路（実 Dart / 実 build）
Invoke-Step "05 self-extension build path" @(
    "-m","pytest",
    "forge_ai/tests/test_dart_build_plan.py",
    "forge_ai/tests/test_synthesizing_build_time_implementer.py",
    "forge_ai/tests/test_managed_build_time_implementer.py",
    "forge_ai/tests/test_self_extension_e2e_real_build.py",
    "-q"
)

# 7. Registry / Store の再検証
Invoke-Step "06 registry and store" @(
    "-m","pytest",
    "forge_ai/tests/test_extension_registry.py",
    "forge_ai/tests/test_extension_store.py",
    "-q"
)

# 8. Critical Gate 全数破壊試験
Invoke-Step "07 mutation (all critical gates)" @("scripts/promotion_mutation_runner.py")

Write-Host "== 結果 ==" -ForegroundColor Cyan
$failed = @()
foreach ($key in $results.Keys) {
    $state = if ($results[$key]) { "PASS" } else { "FAIL"; }
    Write-Host ("  {0,-34} {1}" -f $key, $state)
    if (-not $results[$key]) { $failed += $key }
}

Write-Host ""
if ($failed.Count -eq 0) {
    Write-Host "RESULT: ALL PASS (Windows Promotion Gate revalidation)" -ForegroundColor Green
    exit 0
} else {
    Write-Host ("RESULT: FAIL ({0}) -> {1}" -f $failed.Count, ($failed -join ", ")) -ForegroundColor Red
    exit 1
}
