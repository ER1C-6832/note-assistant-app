@echo off
REM One-click launcher — starts all backend services and the PC app.
REM
REM This script opens three separate terminal windows:
REM   1. Notes API (FastAPI + SQLite)
REM   2. PC Assistant Sidecar (WebSocket bridge)
REM   3. PySide6 Note Assistant desktop app
REM
REM Usage: start_all.bat

echo ========================================
echo  Note Assistant — Starting All Services
echo ========================================
echo.

start "Notes API" cmd /c "%~dp0start_notes_api.bat"
echo [OK] Notes API starting on port 18080...

timeout /t 2 /nobreak >nul

start "Sidecar" cmd /c "%~dp0start_sidecar.bat"
echo [OK] PC Assistant Sidecar starting on port 17890...

timeout /t 2 /nobreak >nul

start "Note Assistant" cmd /c "%~dp0start_pc_app.bat"
echo [OK] Note Assistant desktop app starting...

echo.
echo All services launched. Close each terminal window to stop.
echo.
pause
