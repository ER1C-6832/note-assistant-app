@echo off
setlocal EnableExtensions

set "SCRIPT_DIR=%~dp0"

echo Sending Phase 6 voice control verification commands...
echo.

python "%SCRIPT_DIR%verify_voice_control_bridge.py"
exit /b %ERRORLEVEL%
