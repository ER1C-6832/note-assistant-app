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


def run_app() -> int:
    """Create the Qt application, load QML, and start the event loop."""

    os.environ.setdefault("QT_QUICK_CONTROLS_STYLE", "Basic")
    os.environ.setdefault("QT_API", "pyside6")

    from PySide6.QtGui import QGuiApplication
    from PySide6.QtQml import QQmlApplicationEngine

    from app.controllers.notes_controller import NotesController
    from app.services.sidecar_client import SidecarClient

    pc_build_root = Path(__file__).resolve().parents[3]
    _load_env_file(pc_build_root / ".env")

    app = QGuiApplication(sys.argv)
    app.setApplicationDisplayName("小智便签")
    app.setOrganizationName("NoteAssistant")

    notes_controller = NotesController()
    sidecar_client = SidecarClient()

    sidecar_client.notesChanged.connect(notes_controller.refresh)
    sidecar_client.start()
    app.aboutToQuit.connect(sidecar_client.stop)

    engine = QQmlApplicationEngine()
    context = engine.rootContext()

    context.setContextProperty("notesController", notes_controller)
    context.setContextProperty("notesModel", notes_controller.notes_model)
    context.setContextProperty("deletedNotesModel", notes_controller.deleted_notes_model)
    context.setContextProperty("notesListModel", notes_controller.notes_model)
    context.setContextProperty("deletedNotesListModel", notes_controller.deleted_notes_model)
    context.setContextProperty("sidecarClient", sidecar_client)

    engine.notes_controller = notes_controller  # type: ignore[attr-defined]
    engine.sidecar_client = sidecar_client  # type: ignore[attr-defined]

    qml_path = Path(__file__).resolve().parent / "qml" / "Main.qml"
    engine.load(qml_path.as_uri())

    if not engine.rootObjects():
        sidecar_client.stop()
        return 1

    exit_code = app.exec()
    sidecar_client.stop()
    return int(exit_code)
