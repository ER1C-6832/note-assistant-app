@echo off
REM Start the PC Assistant Sidecar (WebSocket bridge)
REM Usage: start_sidecar.bat

echo Starting PC Assistant Sidecar...
cd /d "%~dp0.."
python services/pc-assistant-sidecar/main.py
