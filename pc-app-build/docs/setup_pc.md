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

## One-click start

```bat
scripts\start_all.bat
```

## Phase 5.1.1 verification

```text
1. Start Notes API.
2. Start Sidecar.
3. Start PC App.
4. Open the Voice Assistant page or Settings page.
5. Confirm Sidecar shows connected.
6. Use py-xiaozhi GUI to create or update a note.
7. Keep PC App open. The note list should refresh automatically after Sidecar emits notes_changed.
```
