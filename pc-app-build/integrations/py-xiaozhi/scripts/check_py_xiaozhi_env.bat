@echo off
setlocal EnableExtensions

set "SCRIPT_DIR=%~dp0"
for %%I in ("%SCRIPT_DIR%..") do set "INTEGRATION_DIR=%%~fI"
for %%I in ("%INTEGRATION_DIR%\..\..") do set "PC_BUILD_ROOT=%%~fI"

if exist "%PC_BUILD_ROOT%\.env" (
  for /f "usebackq tokens=1,* delims==" %%A in ("%PC_BUILD_ROOT%\.env") do (
    if /I "%%A"=="PY_XIAOZHI_ROOT" set "PY_XIAOZHI_ROOT=%%B"
    if /I "%%A"=="PY_XIAOZHI_PYTHON" set "PY_XIAOZHI_PYTHON=%%B"
  )
)

if not defined PY_XIAOZHI_ROOT set "PY_XIAOZHI_ROOT=C:\yuyinzhushou\py-xiaozhi-tao"

if defined PY_XIAOZHI_PYTHON (
  set "PYTHON_EXE=%PY_XIAOZHI_PYTHON%"
) else if exist "%PY_XIAOZHI_ROOT%\.venv\Scripts\python.exe" (
  set "PYTHON_EXE=%PY_XIAOZHI_ROOT%\.venv\Scripts\python.exe"
) else if exist "%PY_XIAOZHI_ROOT%\venv\Scripts\python.exe" (
  set "PYTHON_EXE=%PY_XIAOZHI_ROOT%\venv\Scripts\python.exe"
) else (
  set "PYTHON_EXE=python"
)

echo py-xiaozhi root: %PY_XIAOZHI_ROOT%
echo Python: %PYTHON_EXE%
echo.

if not exist "%PY_XIAOZHI_ROOT%\main.py" (
  echo ERROR: missing %PY_XIAOZHI_ROOT%\main.py
  exit /b 1
)

"%PYTHON_EXE%" --version
if errorlevel 1 (
  echo ERROR: Cannot run Python.
  exit /b 1
)

echo.
echo Checking required Python modules...
"%PYTHON_EXE%" -c "import platformdirs; print('OK platformdirs')"
if errorlevel 1 (
  echo.
  echo ERROR: platformdirs is missing in the Python environment used for py-xiaozhi.
  echo Install py-xiaozhi dependencies in its own environment, for example:
  echo   cd /d %PY_XIAOZHI_ROOT%
  echo   python -m pip install platformdirs
  echo or install the full py-xiaozhi dependency set using that project's instructions.
  exit /b 1
)

echo.
echo OK: py-xiaozhi Python environment passed the minimal check.
exit /b 0
