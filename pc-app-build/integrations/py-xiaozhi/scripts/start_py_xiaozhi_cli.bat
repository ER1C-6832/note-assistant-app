@echo off
setlocal EnableExtensions

set "SCRIPT_DIR=%~dp0"
for %%I in ("%SCRIPT_DIR%..") do set "INTEGRATION_DIR=%%~fI"
for %%I in ("%INTEGRATION_DIR%\..\..") do set "PC_BUILD_ROOT=%%~fI"

if exist "%PC_BUILD_ROOT%\.env" (
  for /f "usebackq tokens=1,* delims==" %%A in ("%PC_BUILD_ROOT%\.env") do (
    if /I "%%A"=="NOTES_API_BASE_URL" set "NOTES_API_BASE_URL=%%B"
    if /I "%%A"=="PY_XIAOZHI_ROOT" set "PY_XIAOZHI_ROOT=%%B"
    if /I "%%A"=="PY_XIAOZHI_PROTOCOL" set "PY_XIAOZHI_PROTOCOL=%%B"
    if /I "%%A"=="PY_XIAOZHI_PYTHON" set "PY_XIAOZHI_PYTHON=%%B"
    if /I "%%A"=="PY_XIAOZHI_SKIP_ACTIVATION" set "PY_XIAOZHI_SKIP_ACTIVATION=%%B"
  )
)

if not defined NOTES_API_BASE_URL set "NOTES_API_BASE_URL=http://127.0.0.1:18080"
if not defined PY_XIAOZHI_ROOT set "PY_XIAOZHI_ROOT=C:\yuyinzhushou\py-xiaozhi-tao"
if not defined PY_XIAOZHI_PROTOCOL set "PY_XIAOZHI_PROTOCOL=websocket"
if not defined PY_XIAOZHI_SKIP_ACTIVATION set "PY_XIAOZHI_SKIP_ACTIVATION=0"

if defined PY_XIAOZHI_PYTHON (
  set "PYTHON_EXE=%PY_XIAOZHI_PYTHON%"
) else if exist "%PY_XIAOZHI_ROOT%\.venv\Scripts\python.exe" (
  set "PYTHON_EXE=%PY_XIAOZHI_ROOT%\.venv\Scripts\python.exe"
) else if exist "%PY_XIAOZHI_ROOT%\venv\Scripts\python.exe" (
  set "PYTHON_EXE=%PY_XIAOZHI_ROOT%\venv\Scripts\python.exe"
) else (
  set "PYTHON_EXE=python"
)

echo Starting py-xiaozhi in CLI mode...
echo PC build root: %PC_BUILD_ROOT%
echo Root: %PY_XIAOZHI_ROOT%
echo Python: %PYTHON_EXE%
echo Notes API: %NOTES_API_BASE_URL%
echo Protocol: %PY_XIAOZHI_PROTOCOL%
echo.

if not exist "%PY_XIAOZHI_ROOT%\main.py" (
  echo ERROR: PY_XIAOZHI_ROOT does not look like a py-xiaozhi repo.
  echo Missing: %PY_XIAOZHI_ROOT%\main.py
  exit /b 1
)

"%PYTHON_EXE%" -c "import platformdirs" >nul 2>nul
if errorlevel 1 (
  echo ERROR: The selected py-xiaozhi Python environment is missing platformdirs.
  echo.
  echo This is not a Note Assistant venv problem. py-xiaozhi needs its own dependencies.
  echo Try:
  echo   cd /d %PY_XIAOZHI_ROOT%
  echo   python -m pip install platformdirs
  echo.
  echo If py-xiaozhi has a requirements or uv workflow, install its full dependencies there.
  echo You can also set PY_XIAOZHI_PYTHON in pc-app-build\.env to its venv python.exe.
  exit /b 1
)

cd /d "%PY_XIAOZHI_ROOT%"

set "EXTRA_ARGS="
if "%PY_XIAOZHI_SKIP_ACTIVATION%"=="1" set "EXTRA_ARGS=--skip-activation"

"%PYTHON_EXE%" main.py --mode cli --protocol %PY_XIAOZHI_PROTOCOL% %EXTRA_ARGS%
exit /b %ERRORLEVEL%
