@echo off
setlocal EnableExtensions

cd /d "%~dp0.."

echo Verifying py-xiaozhi runtime manager...
echo.

python services\pc-assistant-sidecar\verify_py_xiaozhi_runtime_manager.py
exit /b %ERRORLEVEL%
