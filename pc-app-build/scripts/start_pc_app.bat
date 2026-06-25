@echo off
setlocal

REM Start the PySide6 + QML desktop application.
REM Phase 8.7:
REM - App-side timeout is long enough for cold py-xiaozhi boot, avoiding false restart.
REM - Background reuse remains enabled; py-xiaozhi is not killed on normal app exit.

set PC_APP_AUTO_START_PY_XIAOZHI=1
set PC_APP_STOP_PY_XIAOZHI_ON_EXIT=0
set PC_APP_STALE_RUNTIME_RESTART_SECONDS=35
set PYTHONIOENCODING=utf-8
set XIAOZHI_EARLY_PC_BRIDGE=1

echo Starting Note Assistant PC App...
cd /d "%~dp0..\apps\notes-pyside"

python main.py
set APP_EXIT_CODE=%ERRORLEVEL%

echo.
echo PC App exited with code %APP_EXIT_CODE%.
exit /b %APP_EXIT_CODE%
