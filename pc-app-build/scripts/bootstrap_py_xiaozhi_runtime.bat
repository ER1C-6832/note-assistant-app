@echo off
setlocal EnableExtensions
cd /d "%~dp0.."

set PY_XIAOZHI_ROOT_VALUE=

echo ==========================================
echo  Bootstrap py-xiaozhi runtime
echo ==========================================
echo.

if exist ".env" (
  for /f "usebackq tokens=1,* delims==" %%A in (`findstr /B /I "PY_XIAOZHI_ROOT=" ".env"`) do set "PY_XIAOZHI_ROOT_VALUE=%%B"
)

if "%PY_XIAOZHI_ROOT_VALUE%"=="" set "PY_XIAOZHI_ROOT_VALUE=C:\yuyinzhushou\py-xiaozhi-tao"

echo py-xiaozhi root: %PY_XIAOZHI_ROOT_VALUE%

if not exist "%PY_XIAOZHI_ROOT_VALUE%\main.py" (
  echo ERROR: py-xiaozhi main.py not found.
  echo Set PY_XIAOZHI_ROOT in pc-app-build\.env or update the Settings page.
  pause
  exit /b 1
)

if exist "%PY_XIAOZHI_ROOT_VALUE%\.venv\Scripts\python.exe" (
  echo OK: found .venv Python
  "%PY_XIAOZHI_ROOT_VALUE%\.venv\Scripts\python.exe" -V
) else (
  echo WARN: .venv Python not found. The app will use configured Python or system Python.
)

echo.
echo Recommended env values:
echo PY_XIAOZHI_ROOT=%PY_XIAOZHI_ROOT_VALUE%
echo PY_XIAOZHI_RUNTIME_MODE=headless
echo PY_XIAOZHI_START_MODE=hidden
echo PY_XIAOZHI_SKIP_ACTIVATION=1
echo XIAOZHI_MCP_TOOL_ALLOWLIST=notes
echo.
pause
