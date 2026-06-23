@echo off
setlocal EnableExtensions

set "LOG_FILE=%LOCALAPPDATA%\py-xiaozhi\py-xiaozhi\logs\app.log"

echo Checking py-xiaozhi log for notes tool registration...
echo Log: %LOG_FILE%
echo.

if not exist "%LOG_FILE%" (
  echo ERROR: app.log not found. Start py-xiaozhi once first.
  exit /b 1
)

findstr /C:"Add tool: notes.create" "%LOG_FILE%" >nul
if errorlevel 1 (
  echo ERROR: notes.create was not registered.
  echo.
  echo Recent notes-related log lines:
  findstr /I "notes" "%LOG_FILE%"
  exit /b 1
)

findstr /C:"Add tool: notes.search" "%LOG_FILE%" >nul
if errorlevel 1 (
  echo ERROR: notes.search was not registered.
  echo.
  echo Recent notes-related log lines:
  findstr /I "notes" "%LOG_FILE%"
  exit /b 1
)

echo OK: notes.create and notes.search are registered.
findstr /C:"Add tool: notes." "%LOG_FILE%"
exit /b 0
