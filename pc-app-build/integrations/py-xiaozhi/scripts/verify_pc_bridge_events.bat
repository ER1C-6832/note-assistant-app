@echo off
setlocal EnableExtensions

echo Sending Phase 5.4 bridge verification events...
echo.

set "SCRIPT_DIR=%~dp0"

python "%SCRIPT_DIR%verify_pc_bridge_events.py"
exit /b %ERRORLEVEL%

