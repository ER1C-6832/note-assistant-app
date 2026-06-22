@echo off
REM Start the Notes API (FastAPI + uvicorn)
REM Usage: start_notes_api.bat

echo Starting Notes API...
cd /d "%~dp0.."
python -m uvicorn services.notes-api.app.main:app --host 127.0.0.1 --port 18080 --reload
