@echo off
setlocal

REM Start the PySide6 + QML desktop application.
REM Phase 8.2: keep this terminal open after the window closes, and allow quick restart.

cd /d "%~dp0..\apps\notes-pyside"

:RUN_APP
echo.
echo Starting Note Assistant PC App...
python main.py
set APP_EXIT_CODE=%ERRORLEVEL%

echo.
echo PC App exited with code %APP_EXIT_CODE%.
echo.

choice /C RQ /N /M "Press R to restart PC App, or Q to quit: "
if errorlevel 2 goto END
goto RUN_APP

:END
exit /b %APP_EXIT_CODE%
