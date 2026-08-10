@echo off
REM Forge Repository 標準検証スクリプト起動用バッチファイル(FORGE-MILESTONE-003.1 PHASE12)。
REM
REM verify.ps1 をダブルクリックだけでは実行できない場合がある
REM (Windowsの既定ではPowerShellスクリプトの直接実行がブロックされているため)。
REM このバッチファイルは、実行ポリシーを「このプロセス内でだけ」一時的に
REM 緩和して verify.ps1 を呼び出す(システム全体の実行ポリシーは変更しない)。
REM
REM 使い方:
REM   scripts\verify.bat
REM   scripts\verify.bat -RunChrome
REM   scripts\verify.bat -SkipPython
REM   scripts\verify.bat -SkipBuild

setlocal

set SCRIPT_DIR=%~dp0
set PS1_PATH=%SCRIPT_DIR%verify.ps1

if not exist "%PS1_PATH%" (
    echo [FATAL] verify.ps1 が見つかりません: %PS1_PATH%
    pause
    exit /b 1
)

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%PS1_PATH%" %*

endlocal
