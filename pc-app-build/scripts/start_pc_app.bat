@echo off
REM Start the PySide6 Note Assistant desktop application
REM Usage: start_pc_app.bat

echo Starting Note Assistant PC App...
cd /d "%~dp0.."
python apps/notes-pyside/main.py
