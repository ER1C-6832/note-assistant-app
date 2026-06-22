@echo off
REM Start the PySide6 + QML desktop application.

echo Starting Note Assistant PC App...
cd /d "%~dp0..\apps\notes-pyside"

python main.py

pause
