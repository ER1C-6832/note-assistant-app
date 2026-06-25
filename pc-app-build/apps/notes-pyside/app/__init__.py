"""
PySide6 + QML application bootstrap.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

_PKG_DIR = os.path.dirname(os.path.abspath(__file__))
if _PKG_DIR not in sys.path:
    sys.path.insert(0, _PKG_DIR)


def _load_env_file(path: Path) -> None:
    if not path.exists():
        return

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def _request_stop_py_xiaozhi_fire_and_forget() -> None:
    """Ask Sidecar to stop py-xiaozhi without blocking the Qt close path."""
    enabled = os.getenv("PC_APP_STOP_PY_XIAOZHI_ON_EXIT", "0").strip().lower()
    if enabled in {"0", "false", "no", "off"}:
        return

    host = os.getenv("SIDECAR_HEALTH_HOST", "127.0.0.1")
    port = os.getenv("SIDECAR_HEALTH_PORT", "17891")
    url = f"http://{host}:{port}/api/runtime/py-xiaozhi/stop"

    try:
        import subprocess

        command = (
            "$ProgressPreference='SilentlyContinue'; "
            f"try {{ Invoke-WebRequest -UseBasicParsing -Method POST -ContentType 'application/json' -Body '{{}}' '{url}' | Out-Null }} catch {{ }}"
        )
        creationflags = 0
        creationflags |= getattr(subprocess, "CREATE_NO_WINDOW", 0)
        creationflags |= getattr(subprocess, "DETACHED_PROCESS", 0)
        creationflags |= getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)

        subprocess.Popen(
            ["powershell", "-NoProfile", "-WindowStyle", "Hidden", "-Command", command],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=creationflags,
        )
    except Exception:
        pass


def run_app() -> int:
    """Create the Qt application, load QML, and start the event loop."""

    os.environ.setdefault("QT_QUICK_CONTROLS_STYLE", "Basic")
    os.environ.setdefault("QT_API", "pyside6")

    pc_build_root = Path(__file__).resolve().parents[3]
    _load_env_file(pc_build_root / ".env")

    from PySide6.QtGui import QGuiApplication
    from PySide6.QtQml import QQmlApplicationEngine

    from app.controllers.notes_controller import NotesController
    from app.services.sidecar_client import SidecarClient
    from app.services.login_prewarm import LoginPrewarmController

    app = QGuiApplication(sys.argv)
    app.setQuitOnLastWindowClosed(True)
    app.setApplicationDisplayName("小智便签")
    app.setOrganizationName("NoteAssistant")

    notes_controller = NotesController()
    sidecar_client = SidecarClient()
    login_prewarm_controller = LoginPrewarmController(pc_build_root)

    sidecar_client.notesChanged.connect(notes_controller.refresh)
    sidecar_client.start()
    app.aboutToQuit.connect(_request_stop_py_xiaozhi_fire_and_forget)
    app.aboutToQuit.connect(sidecar_client.stop)

    engine = QQmlApplicationEngine()
    context = engine.rootContext()

    context.setContextProperty("notesController", notes_controller)
    context.setContextProperty("notesModel", notes_controller.notes_model)
    context.setContextProperty("deletedNotesModel", notes_controller.deleted_notes_model)
    context.setContextProperty("notesListModel", notes_controller.notes_model)
    context.setContextProperty("deletedNotesListModel", notes_controller.deleted_notes_model)
    context.setContextProperty("sidecarClient", sidecar_client)
    context.setContextProperty("loginPrewarmController", login_prewarm_controller)

    engine.notes_controller = notes_controller  # type: ignore[attr-defined]
    engine.sidecar_client = sidecar_client  # type: ignore[attr-defined]
    engine.login_prewarm_controller = login_prewarm_controller  # type: ignore[attr-defined]

    qml_path = Path(__file__).resolve().parent / "qml" / "Main.qml"
    engine.load(qml_path.as_uri())

    if not engine.rootObjects():
        sidecar_client.stop()
        return 1

    exit_code = app.exec()
    sidecar_client.stop()
    return int(exit_code)
