# PC Setup Guide

## Start services

```bat
cd /d C:\yuyinzhushou\note-assistant-app\pc-app-build
venv\Scripts\activate
scripts\start_notes_api.bat
scripts\start_sidecar.bat
scripts\start_pc_app.bat
```

Start py-xiaozhi GUI separately.

## Phase 5.3 test

```bat
integrations\py-xiaozhi\scripts\test_assistant_runtime_event.bat
```

The Voice Assistant panel should show transcript / reply / runtime state test
events.

## Optional log path override

Edit `.env`:

```text
PY_XIAOZHI_LOG_PATH=C:\Users\111\AppData\Local\py-xiaozhi\py-xiaozhi\logs\app.log
```
