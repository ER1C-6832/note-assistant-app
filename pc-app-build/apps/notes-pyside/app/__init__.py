"""
PySide6 + QML application bootstrap.
"""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine


def run_app() -> int:
    """Create the Qt application, load QML, and start the event loop."""

    app = QGuiApplication(sys.argv)
    app.setApplicationDisplayName("小智便签")
    app.setOrganizationName("NoteAssistant")

    engine = QQmlApplicationEngine()
    qml_path = Path(__file__).resolve().parent / "qml" / "Main.qml"
    engine.load(qml_path.as_uri())

    if not engine.rootObjects():
        return 1

    return app.exec()
