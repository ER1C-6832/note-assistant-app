@echo off
setlocal EnableExtensions
cd /d "%~dp0.."

echo ==========================================
echo  Note Assistant Demo Start
echo ==========================================
echo.

if not exist "venv\Scripts\activate.bat" (
  echo ERROR: pc-app-build venv not found.
  echo Please install PC App dependencies first.
  echo.
  pause
  exit /b 1
)

echo [1/4] Checking demo environment...
call scripts\check_demo_environment.bat
if errorlevel 1 (
  echo.
  echo Environment check failed. Please fix the issues above and retry.
  pause
  exit /b 1
)

echo.
echo [2/4] Starting Notes API...
start "Note Assistant - Notes API" cmd /k "cd /d %CD% && call venv\Scripts\activate.bat && scripts\start_notes_api.bat"
timeout /t 2 /nobreak >nul

echo [3/4] Starting local voice bridge...
start "Note Assistant - Voice Bridge" cmd /k "cd /d %CD% && call venv\Scripts\activate.bat && scripts\start_sidecar.bat"
timeout /t 2 /nobreak >nul

echo [4/4] Starting desktop app...
call venv\Scripts\activate.bat
call scripts\start_pc_app.bat
exit /b %ERRORLEVEL%
