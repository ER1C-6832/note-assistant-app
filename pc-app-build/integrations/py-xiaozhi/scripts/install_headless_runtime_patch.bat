@echo off
setlocal EnableExtensions

set "SCRIPT_DIR=%~dp0"
for %%I in ("%SCRIPT_DIR%..\") do set "INTEGRATION_ROOT=%%~fI"
for %%I in ("%INTEGRATION_ROOT%..\..\") do set "PC_BUILD_ROOT=%%~fI"

if "%PY_XIAOZHI_ROOT%"=="" set "PY_XIAOZHI_ROOT=C:\yuyinzhushou\py-xiaozhi-tao"

set "PATCH_ROOT=%INTEGRATION_ROOT%headless-runtime"
set "MAIN_SRC=%PATCH_ROOT%\main.py"
set "UI_SRC=%PATCH_ROOT%\src\plugins\ui.py"
set "MAIN_DST=%PY_XIAOZHI_ROOT%\main.py"
set "UI_DST=%PY_XIAOZHI_ROOT%\src\plugins\ui.py"

if not exist "%PY_XIAOZHI_ROOT%" (
  echo ERROR: py-xiaozhi root not found: %PY_XIAOZHI_ROOT%
  exit /b 1
)

if not exist "%MAIN_SRC%" (
  echo ERROR: missing source file: %MAIN_SRC%
  exit /b 1
)

if not exist "%UI_SRC%" (
  echo ERROR: missing source file: %UI_SRC%
  exit /b 1
)

echo Installing py-xiaozhi headless runtime patch...
echo py-xiaozhi root: %PY_XIAOZHI_ROOT%
echo.

if exist "%MAIN_DST%" (
  copy /Y "%MAIN_DST%" "%MAIN_DST%.phase7_2_backup" >nul
)
if exist "%UI_DST%" (
  copy /Y "%UI_DST%" "%UI_DST%.phase7_2_backup" >nul
)

copy /Y "%MAIN_SRC%" "%MAIN_DST%" >nul
if errorlevel 1 exit /b 1

copy /Y "%UI_SRC%" "%UI_DST%" >nul
if errorlevel 1 exit /b 1

echo OK: installed headless runtime patch.
echo.
echo Recommended .env:
echo   PY_XIAOZHI_RUNTIME_MODE=headless
echo   PY_XIAOZHI_START_MODE=hidden
echo   PY_XIAOZHI_WINDOW_MODE=hidden
echo.
echo Restart Sidecar and start py-xiaozhi from PC App settings page.
exit /b 0
