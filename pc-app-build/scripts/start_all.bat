@echo off
setlocal

echo ========================================
echo Note Assistant - Starting All Services
echo ========================================
echo.

start "Notes API" cmd /k "%~dp0start_notes_api.bat"
echo [OK] Notes API starting on port 18080...

timeout /t 2 /nobreak >nul

start "PC Assistant Sidecar" cmd /k "%~dp0start_sidecar.bat"
echo [OK] PC Assistant Sidecar starting on ports 17890 / 17891...

timeout /t 2 /nobreak >nul

start "Note Assistant" cmd /k "%~dp0start_pc_app.bat"
echo [OK] Note Assistant desktop app starting...

echo.
echo All services launched.
echo Close each opened terminal window to stop its process.
echo.
pause
