@echo off
setlocal EnableExtensions
cd /d "%~dp0.."

echo Cleaning abandoned Phase 9.1 mock/demo-seed files...

del /f /q "scripts\seed_demo_notes.py" 2>nul
del /f /q "scripts\reset_demo_data.py" 2>nul
del /f /q "scripts\sidecar_mock.py" 2>nul
del /f /q "scripts\seed_demo_notes.bat" 2>nul
del /f /q "scripts\reset_demo_data.bat" 2>nul
del /f /q "scripts\start_sidecar_mock.bat" 2>nul
del /f /q "scripts\start_demo_mock_mode.bat" 2>nul

del /f /q "docs\demo\README_DEMO_PHASE_9_1.md" 2>nul
del /f /q "docs\demo\DEMO_SCRIPT_PHASE_9_1.md" 2>nul
del /f /q "docs\demo\KNOWN_ISSUES_PHASE_9_1.md" 2>nul
del /f /q "docs\demo\FALLBACK_DEMO_PATH_PHASE_9_1.md" 2>nul
del /f /q "DELIVERY_REPORT_PHASE_9_1.md" 2>nul

echo Done.
exit /b 0
