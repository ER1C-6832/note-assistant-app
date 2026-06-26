@echo off
setlocal EnableExtensions
cd /d "%~dp0.."

echo ==========================================
echo  Note Assistant Real Demo Preflight
echo ==========================================
echo.

echo [1/2] Environment check
call scripts\check_demo_environment.bat
if errorlevel 1 (
  echo.
  echo Preflight failed at environment check.
  exit /b 1
)

echo.
echo [2/2] Done
echo Use scripts\start_all_integrated.bat to start the real demo.
exit /b 0
