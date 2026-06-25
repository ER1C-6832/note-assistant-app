@echo off
setlocal EnableExtensions
cd /d "%~dp0.."

set ERR=0
set PY_XIAOZHI_ROOT_VALUE=

echo === Basic paths ===
echo PC App: %CD%

if exist "venv\Scripts\python.exe" (
  echo OK  pc-app-build venv
) else (
  echo ERR missing pc-app-build\venv\Scripts\python.exe
  set ERR=1
)

if exist "services\notes-api\app\main.py" (
  echo OK  Notes API
) else (
  echo ERR missing services\notes-api\app\main.py
  set ERR=1
)

if exist "services\pc-assistant-sidecar\main.py" (
  echo OK  local voice bridge
) else (
  echo ERR missing services\pc-assistant-sidecar\main.py
  set ERR=1
)

echo.
echo === Voice assistant path ===
if exist ".env" (
  for /f "usebackq tokens=1,* delims==" %%A in (`findstr /B /I "PY_XIAOZHI_ROOT=" ".env"`) do set "PY_XIAOZHI_ROOT_VALUE=%%B"
)

if "%PY_XIAOZHI_ROOT_VALUE%"=="" set "PY_XIAOZHI_ROOT_VALUE=C:\yuyinzhushou\py-xiaozhi-tao"

echo py-xiaozhi root: %PY_XIAOZHI_ROOT_VALUE%
if exist "%PY_XIAOZHI_ROOT_VALUE%\main.py" (
  echo OK  py-xiaozhi main.py
) else (
  echo WARN py-xiaozhi main.py not found. Real voice runtime may not start.
)

echo.
echo === Ports ===
echo Notes API:    http://127.0.0.1:18080
echo Voice bridge: ws://127.0.0.1:17890/assistant
echo Health:       http://127.0.0.1:17891/api/health

exit /b %ERR%
