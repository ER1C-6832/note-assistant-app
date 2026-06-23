"""
Note Assistant — PySide6 + QML Application Package.
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


def run_app() -> int:
    """Launch the PySide6 desktop application."""

    from PySide6.QtGui import QGuiApplication
    from PySide6.QtQml import QQmlApplicationEngine

    from app.controllers.notes_controller import NotesController
    from app.services.sidecar_client import SidecarClient

    pc_build_root = Path(__file__).resolve().parents[3]
    _load_env_file(pc_build_root / ".env")

    app = QGuiApplication(sys.argv)
    app.setApplicationName("Note Assistant")
    app.setOrganizationName("NoteAssistant")

    notes_controller = NotesController()
    sidecar_client = SidecarClient()

    sidecar_client.notesChanged.connect(notes_controller.refresh)
    sidecar_client.start()
    app.aboutToQuit.connect(sidecar_client.stop)

    engine = QQmlApplicationEngine()
    context = engine.rootContext()
    context.setContextProperty("notesController", notes_controller)
    context.setContextProperty("notesListModel", notes_controller.notes_model)
    context.setContextProperty("deletedNotesListModel", notes_controller.deleted_notes_model)
    context.setContextProperty("sidecarClient", sidecar_client)

    qml_path = os.path.join(os.path.dirname(__file__), "qml", "Main.qml")
    engine.load(qml_path)

    if not engine.rootObjects():
        return -1

    return app.exec()
