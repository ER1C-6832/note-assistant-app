@echo off
setlocal EnableExtensions

set "SCRIPT_DIR=%~dp0"
for %%I in ("%SCRIPT_DIR%..") do set "INTEGRATION_DIR=%%~fI"
for %%I in ("%INTEGRATION_DIR%\..\..") do set "PC_BUILD_ROOT=%%~fI"

if exist "%PC_BUILD_ROOT%\.env" (
  for /f "usebackq tokens=1,* delims==" %%A in ("%PC_BUILD_ROOT%\.env") do (
    if /I "%%A"=="PY_XIAOZHI_ROOT" set "PY_XIAOZHI_ROOT=%%B"
  )
)

if not defined PY_XIAOZHI_ROOT set "PY_XIAOZHI_ROOT=C:\yuyinzhushou\py-xiaozhi-tao"

set "TARGET_DIR=%PY_XIAOZHI_ROOT%\src\mcp\tools\notes"

echo Checking installed notes tool...
echo Target: %TARGET_DIR%
echo.

if not exist "%TARGET_DIR%\_tools.py" (
  echo ERROR: _tools.py not found.
  exit /b 1
)

if not exist "%TARGET_DIR%\notes_api_client.py" (
  echo ERROR: notes_api_client.py not found.
  exit /b 1
)

echo OK: notes tool files exist.
dir "%TARGET_DIR%" /b
exit /b 0
