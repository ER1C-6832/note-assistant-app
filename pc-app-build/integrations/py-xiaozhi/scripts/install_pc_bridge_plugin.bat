@echo off
setlocal EnableExtensions

echo Installing py-xiaozhi PC Bridge plugin...
echo.

set "SCRIPT_DIR=%~dp0"

python "%SCRIPT_DIR%patch_pc_bridge_container.py"
exit /b %ERRORLEVEL%
