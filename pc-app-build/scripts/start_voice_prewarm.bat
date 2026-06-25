@echo off
setlocal

REM Phase 8.9 Windows login prewarm entry.
REM This script is safe to keep in Task Scheduler because it only starts Sidecar
REM when pc-app-build\.env contains PC_APP_LOGIN_PREWARM_ENABLED=1.

cd /d "%~dp0.."

powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$envPath = Join-Path (Resolve-Path '.') '.env';" ^
  "$enabled = $false;" ^
  "if (Test-Path $envPath) {" ^
  "  foreach ($line in Get-Content $envPath -Encoding UTF8) {" ^
  "    if ($line -match '^\s*PC_APP_LOGIN_PREWARM_ENABLED\s*=\s*(1|true|yes|on)\s*$') { $enabled = $true; break }" ^
  "  }" ^
  "}" ^
  "if (-not $enabled) { exit 2 }"

if errorlevel 2 (
  echo Login prewarm is disabled by .env. Exit.
  exit /b 0
)

set PYTHONIOENCODING=utf-8
set PY_XIAOZHI_AUTO_START=1
set PY_XIAOZHI_RUNTIME_MODE=headless
set PY_XIAOZHI_START_MODE=hidden
set PY_XIAOZHI_WINDOW_MODE=hidden
set PY_XIAOZHI_SKIP_ACTIVATION=1

set XIAOZHI_PC_MANAGED_MODE=1
set XIAOZHI_EARLY_PC_BRIDGE=1
set XIAOZHI_DISABLE_WAKE_WORD=1
set XIAOZHI_DISABLE_SHORTCUTS=1
set XIAOZHI_MCP_TOOL_ALLOWLIST=notes
set XIAOZHI_AUDIO_LAZY_INIT=1

set PC_BRIDGE_HEARTBEAT_SECONDS=1.0
set PC_BRIDGE_SUPPRESS_STARTUP_AUTO_LISTEN=1
set PC_BRIDGE_STARTUP_GUARD_SECONDS=10

if exist "venv\Scripts\activate.bat" (
  call "venv\Scripts\activate.bat"
)

python services\pc-assistant-sidecar\main.py
