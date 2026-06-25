@echo off
setlocal EnableExtensions
cd /d "%~dp0.."

echo ==========================================
echo  准备语音助手运行环境
echo ==========================================
echo.

if exist ".env" (
  for /f "tokens=1,* delims==" %%A in ('findstr /B /I "PY_XIAOZHI_ROOT=" ".env"') do set PY_XIAOZHI_ROOT_VALUE=%%B
)

if "%PY_XIAOZHI_ROOT_VALUE%"=="" set PY_XIAOZHI_ROOT_VALUE=C:\yuyinzhushou\py-xiaozhi-tao

echo py-xiaozhi root: %PY_XIAOZHI_ROOT_VALUE%

if not exist "%PY_XIAOZHI_ROOT_VALUE%\main.py" (
  echo ERROR: 未找到 py-xiaozhi main.py
  echo 请在 pc-app-build\.env 中设置 PY_XIAOZHI_ROOT
  pause
  exit /b 1
)

if exist "%PY_XIAOZHI_ROOT_VALUE%\.venv\Scripts\python.exe" (
  echo OK: 找到 .venv Python
  "%PY_XIAOZHI_ROOT_VALUE%\.venv\Scripts\python.exe" -V
) else (
  echo WARN: 未找到 .venv Python，将依赖系统 Python 或设置页配置。
)

echo.
echo 推荐 .env：
echo PY_XIAOZHI_ROOT=%PY_XIAOZHI_ROOT_VALUE%
echo PY_XIAOZHI_RUNTIME_MODE=headless
echo PY_XIAOZHI_START_MODE=hidden
echo PY_XIAOZHI_SKIP_ACTIVATION=1
echo XIAOZHI_MCP_TOOL_ALLOWLIST=notes
echo.
pause
