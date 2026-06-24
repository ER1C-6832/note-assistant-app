@echo off
setlocal

REM Start the PySide6 + QML desktop application.
REM Hotfix: do not enter a CHOICE restart loop after the Qt window exits.
REM Let the terminal return normally after a simple pause.

echo Starting Note Assistant PC App...
cd /d "%~dp0..\apps\notes-pyside"

python main.py
set APP_EXIT_CODE=%ERRORLEVEL%

echo.
echo PC App exited with code %APP_EXIT_CODE%.
echo Press any key to return to the terminal...
pause >nul

exit /b %APP_EXIT_CODE%
