# Phase 5.1.1 Hotfix Report — PC App Startup and Duplicate Sidecar Guard

> **Project:** Note Assistant  
> **Patch:** Phase 5.1.1 Hotfix  
> **Status:** ✅ Delivered

## 1. Fixed Issues

### 1.1 Qt Quick Controls style warnings

The PC App did not set `QT_QUICK_CONTROLS_STYLE=Basic` before creating
`QGuiApplication`, so the native Windows style rejected customized controls such
as TextField background and ScrollBar contentItem.

### 1.2 Missing QML context aliases

Some QML files still use the old context names:

```text
notesModel
deletedNotesModel
```

The previous bootstrap only exposed:

```text
notesListModel
deletedNotesListModel
```

The hotfix exposes both old and new names.

### 1.3 QML null guards

TopBar, Sidebar, and HomePage now use explicit object properties and null guards
to avoid `Cannot read property ... of null` during early QML initialization.

### 1.4 Duplicate Sidecar process

Starting Sidecar twice caused:

```text
OSError: [WinError 10048] address already in use
```

The hotfix checks the health endpoint before binding ports. If a Sidecar is
already running, the second process exits cleanly.

## 2. Files Included

```text
pc-app-build/apps/notes-pyside/app/__init__.py
pc-app-build/apps/notes-pyside/app/services/sidecar_client.py
pc-app-build/apps/notes-pyside/app/qml/Main.qml
pc-app-build/apps/notes-pyside/app/qml/components/TopBar.qml
pc-app-build/apps/notes-pyside/app/qml/components/Sidebar.qml
pc-app-build/apps/notes-pyside/app/qml/pages/HomePage.qml
pc-app-build/services/pc-assistant-sidecar/main.py
pc-app-build/services/pc-assistant-sidecar/app_ws_server.py
pc-app-build/DELIVERY_REPORT_PHASE_5_1_1_HOTFIX.md
```

## 3. Verification

Start only one Sidecar process:

```bat
scripts\start_notes_api.bat
scripts\start_sidecar.bat
scripts\start_pc_app.bat
```

Expected:

```text
1. PC App starts without QML null errors.
2. Sidecar terminal shows Client connected when the PC App opens.
3. Starting start_sidecar.bat again prints that Sidecar is already running.
4. Creating a note through py-xiaozhi triggers notes_changed and PC App refresh.
```

*End of Phase 5.1.1 Hotfix Report*
