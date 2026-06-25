@echo off
setlocal EnableExtensions
cd /d "%~dp0.."

echo ==========================================
echo  小智便签 Demo 一键启动
echo ==========================================
echo.

if not exist "venv\Scripts\activate.bat" (
  echo ERROR: pc-app-build\venv 不存在。请先安装 PC App 依赖。
  echo.
  pause
  exit /b 1
)

echo [1/4] 检查演示环境...
call scripts\check_demo_environment.bat
if errorlevel 1 (
  echo.
  echo 环境检查未通过，请按上方提示修复后重试。
  pause
  exit /b 1
)

echo.
echo [2/4] 启动便签服务 Notes API...
start "Note Assistant - Notes API" cmd /k "cd /d %CD% && call venv\Scripts\activate.bat && scripts\start_notes_api.bat"
timeout /t 2 /nobreak >nul

echo [3/4] 启动本地语音桥接服务...
start "Note Assistant - Voice Bridge" cmd /k "cd /d %CD% && call venv\Scripts\activate.bat && scripts\start_sidecar.bat"
timeout /t 2 /nobreak >nul

echo [4/4] 启动桌面应用...
call venv\Scripts\activate.bat
call scripts\start_pc_app.bat
exit /b %ERRORLEVEL%
