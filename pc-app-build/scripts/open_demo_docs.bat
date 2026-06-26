@echo off
setlocal EnableExtensions
cd /d "%~dp0.."

if exist "docs\demo\README_DEMO_PHASE_9_2.md" start "" "docs\demo\README_DEMO_PHASE_9_2.md"
if exist "docs\demo\DEMO_RUNBOOK_PHASE_9_2.md" start "" "docs\demo\DEMO_RUNBOOK_PHASE_9_2.md"
if exist "docs\demo\DEMO_CHECKLIST_PHASE_9_2.md" start "" "docs\demo\DEMO_CHECKLIST_PHASE_9_2.md"

exit /b 0
