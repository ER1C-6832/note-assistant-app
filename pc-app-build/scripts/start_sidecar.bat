@echo off
setlocal

echo Starting PC Assistant Sidecar...

cd /d "%~dp0.."

if exist "venv\Scripts\activate.bat" (
  call "venv\Scripts\activate.bat"
)

python services\pc-assistant-sidecar\main.py
