@echo off
setlocal

REM Start the PySide6 + QML desktop application.
REM Phase 8.4.1: return to the shell normally after the Qt window exits.

echo Starting Note Assistant PC App...
cd /d "%~dp0..\apps\notes-pyside"

python main.py
set APP_EXIT_CODE=%ERRORLEVEL%

echo.
echo PC App exited with code %APP_EXIT_CODE%.
exit /b %APP_EXIT_CODE%
