@echo off
setlocal EnableExtensions
cd /d "%~dp0.."

echo Checking Note Assistant runtime diagnostics...
echo.

call venv\Scripts\activate.bat
python services\pc-assistant-sidecar\inspect_runtime_diagnostics.py
exit /b %ERRORLEVEL%
