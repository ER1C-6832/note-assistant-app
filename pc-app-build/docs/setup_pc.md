# PC Setup Guide

## Start Notes API

```bat
cd /d C:\yuyinzhushou\note-assistant-app\pc-app-build
venv\Scripts\activate
scripts\start_notes_api.bat
```

Health check:

```text
http://127.0.0.1:18080/api/health
```

## Start PC App

```bat
cd /d C:\yuyinzhushou\note-assistant-app\pc-app-build
venv\Scripts\activate
scripts\start_pc_app.bat
```

## Phase 5.0 py-xiaozhi feasibility

Copy env:

```bat
copy .env.example .env
```

Edit `.env`:

```env
PY_XIAOZHI_ROOT=C:\yuyinzhushou\py-xiaozhi-tao
```

Install MCP notes tool:

```bat
integrations\py-xiaozhi\scripts\install_notes_tool.bat
```

Check py-xiaozhi Python environment:

```bat
integrations\py-xiaozhi\scripts\check_py_xiaozhi_env.bat
```

Start py-xiaozhi CLI:

```bat
integrations\py-xiaozhi\scripts\start_py_xiaozhi_cli.bat
```
