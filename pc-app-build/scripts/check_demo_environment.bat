@echo off
setlocal EnableExtensions
cd /d "%~dp0.."

set ERR=0

echo === 基础路径 ===
echo PC App: %CD%

if exist "venv\Scripts\python.exe" (
  echo OK  pc-app-build venv
) else (
  echo ERR 缺少 pc-app-build\venv\Scripts\python.exe
  set ERR=1
)

if exist "services\notes-api\app\main.py" (
  echo OK  Notes API
) else (
  echo ERR 缺少 services\notes-api\app\main.py
  set ERR=1
)

if exist "services\pc-assistant-sidecar\main.py" (
  echo OK  本地语音桥接服务
) else (
  echo ERR 缺少 services\pc-assistant-sidecar\main.py
  set ERR=1
)

echo.
echo === 语音助手路径 ===
if exist ".env" (
  for /f "tokens=1,* delims==" %%A in ('findstr /B /I "PY_XIAOZHI_ROOT=" ".env"') do set PY_XIAOZHI_ROOT_VALUE=%%B
)

if "%PY_XIAOZHI_ROOT_VALUE%"=="" set PY_XIAOZHI_ROOT_VALUE=C:\yuyinzhushou\py-xiaozhi-tao

echo py-xiaozhi: %PY_XIAOZHI_ROOT_VALUE%
if exist "%PY_XIAOZHI_ROOT_VALUE%\main.py" (
  echo OK  py-xiaozhi main.py
) else (
  echo WARN 未找到 py-xiaozhi main.py；真实语音链路可能无法启动
)

echo.
echo === 端口提示 ===
echo Notes API:      http://127.0.0.1:18080
echo Voice Bridge:   ws://127.0.0.1:17890/assistant
echo Health:         http://127.0.0.1:17891/api/health

exit /b %ERR%
