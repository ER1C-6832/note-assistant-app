# PC Setup Guide

## Start Notes API

```bat
cd /d C:\yuyinzhushou\note-assistant-app\pc-app-build
venv\Scripts\activate
scripts\start_notes_api.bat
```

Health:

```text
http://127.0.0.1:18080/api/health
```

## Start Sidecar

```bat
cd /d C:\yuyinzhushou\note-assistant-app\pc-app-build
venv\Scripts\activate
scripts\start_sidecar.bat
```

Health:

```text
http://127.0.0.1:17891/api/health
```

WebSocket:

```text
ws://127.0.0.1:17890/assistant
```

## Start PC App

```bat
cd /d C:\yuyinzhushou\note-assistant-app\pc-app-build
venv\Scripts\activate
scripts\start_pc_app.bat
```

## One-click start

```bat
scripts\start_all.bat
```
