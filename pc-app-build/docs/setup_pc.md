# PC Setup Guide

## Start Notes API

```bat
cd /d C:\yuyinzhushou\note-assistant-app\pc-app-build
venv\Scripts\activate
scripts\start_notes_api.bat
```

## Start Sidecar

```bat
cd /d C:\yuyinzhushou\note-assistant-app\pc-app-build
venv\Scripts\activate
scripts\start_sidecar.bat
```

Check:

```bat
scripts\check_sidecar.bat
```

## Start PC App

```bat
cd /d C:\yuyinzhushou\note-assistant-app\pc-app-build
venv\Scripts\activate
scripts\start_pc_app.bat
```

## Install py-xiaozhi notes MCP tool

```bat
integrations\py-xiaozhi\scripts\install_notes_tool.bat
```

Restart py-xiaozhi after installing the tool.

## Phase 5.2 event bridge test

Start Notes API, Sidecar, and PC App, then run:

```bat
integrations\py-xiaozhi\scripts\test_sidecar_event.bat
```

The PC App Voice Assistant panel should show the test tool result.
