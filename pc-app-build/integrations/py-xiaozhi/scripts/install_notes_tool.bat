@echo off
setlocal EnableExtensions

echo Installing Note Assistant MCP notes tool...

set "SCRIPT_DIR=%~dp0"
for %%I in ("%SCRIPT_DIR%..") do set "INTEGRATION_DIR=%%~fI"
for %%I in ("%INTEGRATION_DIR%\..\..") do set "PC_BUILD_ROOT=%%~fI"

if exist "%PC_BUILD_ROOT%\.env" (
  for /f "usebackq tokens=1,* delims==" %%A in ("%PC_BUILD_ROOT%\.env") do (
    if /I "%%A"=="PY_XIAOZHI_ROOT" set "PY_XIAOZHI_ROOT=%%B"
  )
)

if not defined PY_XIAOZHI_ROOT set "PY_XIAOZHI_ROOT=C:\yuyinzhushou\py-xiaozhi-tao"

set "SOURCE_DIR=%INTEGRATION_DIR%\mcp-tools\notes"
set "TARGET_DIR=%PY_XIAOZHI_ROOT%\src\mcp\tools\notes"

echo PC build root: %PC_BUILD_ROOT%
echo Source: %SOURCE_DIR%
echo Target: %TARGET_DIR%
echo.

if not exist "%SOURCE_DIR%\_tools.py" (
  echo ERROR: Source folder not found or incomplete.
  echo Expected: %SOURCE_DIR%\_tools.py
  exit /b 1
)

if not exist "%PY_XIAOZHI_ROOT%\main.py" (
  echo ERROR: PY_XIAOZHI_ROOT does not look like a py-xiaozhi repo.
  echo Missing: %PY_XIAOZHI_ROOT%\main.py
  exit /b 1
)

if exist "%TARGET_DIR%" rmdir /s /q "%TARGET_DIR%"
mkdir "%TARGET_DIR%" >nul 2>nul

xcopy "%SOURCE_DIR%\*" "%TARGET_DIR%\" /E /I /Y >nul
if errorlevel 1 (
  echo ERROR: Failed to copy notes tool.
  exit /b 1
)

echo.
echo Installed files:
dir "%TARGET_DIR%" /b
echo.
echo OK: notes MCP tool installed.
echo Restart py-xiaozhi and check logs for:
echo   Add tool: notes.create
echo   Add tool: notes.search
exit /b 0
