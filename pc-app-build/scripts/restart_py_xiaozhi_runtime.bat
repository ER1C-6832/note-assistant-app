@echo off
setlocal EnableExtensions
cd /d "%~dp0.."

echo Restarting py-xiaozhi runtime through Sidecar...
echo.

call venv\Scripts\activate.bat
python services\pc-assistant-sidecar\restart_py_xiaozhi_runtime.py
exit /b %ERRORLEVEL%
