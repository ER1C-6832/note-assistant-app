@echo off
setlocal

REM Start the PySide6 + QML desktop application.
REM Phase 8.8.2:
REM - Do not hard-code PC_APP_* or XIAOZHI_* product settings here.
REM - The app bootstrap loads pc-app-build\.env, and .env should be the primary config source.
REM - This script only keeps console encoding stable.

set PYTHONIOENCODING=utf-8

echo Starting Note Assistant PC App...
cd /d "%~dp0..\apps\notes-pyside"

python main.py
set APP_EXIT_CODE=%ERRORLEVEL%

echo.
echo PC App exited with code %APP_EXIT_CODE%.
exit /b %APP_EXIT_CODE%
