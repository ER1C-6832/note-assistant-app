@echo off
REM Start the Notes API (FastAPI + uvicorn)
REM Usage:
REM   scripts\start_notes_api.bat
REM
REM This script intentionally enters services\notes-api first because the
REM directory name "notes-api" contains a hyphen and cannot be imported as
REM a Python dotted package path.

echo Starting Notes API...
cd /d "%~dp0..\services\notes-api"

python -m uvicorn app.main:app --host 127.0.0.1 --port 18080 --reload

pause
