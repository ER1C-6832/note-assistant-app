@echo off
setlocal EnableExtensions
cd /d "%~dp0.."

echo ==========================================
echo  Note Assistant Demo Mock Mode
echo ==========================================
echo.

if not exist "venv\Scripts\activate.bat" (
  echo ERROR: pc-app-build venv not found.
  pause
  exit /b 1
)

echo [1/4] Starting Notes API...
start "Note Assistant - Notes API" cmd /k "cd /d %CD% && call venv\Scripts\activate.bat && scripts\start_notes_api.bat"
timeout /t 2 /nobreak >nul

echo [2/4] Seeding demo notes...
call venv\Scripts\activate.bat
call scripts\seed_demo_notes.bat

echo [3/4] Starting mock voice bridge...
start "Note Assistant - Mock Voice Bridge" cmd /k "cd /d %CD% && call venv\Scripts\activate.bat && scripts\start_sidecar_mock.bat"
timeout /t 2 /nobreak >nul

echo [4/4] Starting desktop app...
call scripts\start_pc_app.bat
exit /b %ERRORLEVEL%
