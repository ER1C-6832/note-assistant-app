@echo off
setlocal

echo === .env ===
type "%~dp0..\.env"

echo.
echo === Effective PC_APP_STOP_PY_XIAOZHI_ON_EXIT from .env ===
powershell -NoProfile -Command "$p=Join-Path (Resolve-Path '%~dp0..') '.env'; if (Test-Path $p) { Select-String -Path $p -Pattern '^\s*PC_APP_STOP_PY_XIAOZHI_ON_EXIT\s*=' }"
