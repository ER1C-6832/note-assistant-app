@echo off
setlocal

REM Phase 8.8 Windows login prewarm entry.
REM Keeps Sidecar running and lets Sidecar auto-start py-xiaozhi in the background.

cd /d "%~dp0.."

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

set PC_BRIDGE_HEARTBEAT_SECONDS=1.0
set PC_BRIDGE_SUPPRESS_STARTUP_AUTO_LISTEN=1
set PC_BRIDGE_STARTUP_GUARD_SECONDS=10

if exist "venv\Scripts\activate.bat" (
  call "venv\Scripts\activate.bat"
)

python services\pc-assistant-sidecar\main.py
