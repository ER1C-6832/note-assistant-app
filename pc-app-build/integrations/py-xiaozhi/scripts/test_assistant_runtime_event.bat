@echo off
setlocal EnableExtensions

echo Sending test assistant runtime events to PC Assistant Sidecar...
echo.

set "SCRIPT_DIR=%~dp0"

python "%SCRIPT_DIR%test_assistant_runtime_event.py"
exit /b %ERRORLEVEL%
