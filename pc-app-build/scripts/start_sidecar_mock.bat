@echo off
setlocal EnableExtensions
cd /d "%~dp0.."
set PYTHONIOENCODING=utf-8
if exist "venv\Scripts\activate.bat" call "venv\Scripts\activate.bat"
python scripts\sidecar_mock.py
exit /b %ERRORLEVEL%
