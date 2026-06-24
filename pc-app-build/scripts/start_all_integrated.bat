@echo off
setlocal EnableExtensions
cd /d "%~dp0.."

echo Starting Note Assistant integrated dev environment...
echo.

if not exist "venv\Scripts\activate.bat" (
  echo ERROR: venv not found. Please create/install pc-app-build venv first.
  pause
  exit /b 1
)

start "Note Assistant - Notes API" cmd /k "cd /d %CD% && call venv\Scripts\activate.bat && scripts\start_notes_api.bat"
timeout /t 2 /nobreak >nul

start "Note Assistant - Sidecar" cmd /k "cd /d %CD% && call venv\Scripts\activate.bat && scripts\start_sidecar.bat"
timeout /t 2 /nobreak >nul

echo Starting PC App in this terminal...
call venv\Scripts\activate.bat
call scripts\start_pc_app.bat
exit /b %ERRORLEVEL%
