"""
Note Assistant — PySide6 + QML Application Package

This package contains the main application bootstrap and all UI-related
modules: QML pages and components, Python controllers, service clients,
and data models.
"""

import sys
import os

# Ensure subpackages are resolvable
_PKG_DIR = os.path.dirname(os.path.abspath(__file__))
if _PKG_DIR not in sys.path:
    sys.path.insert(0, _PKG_DIR)


def run_app():
    """Launch the PySide6 desktop application.

    Initializes the QML engine, loads the main window, and enters
    the Qt event loop. This function blocks until the window is closed.
    """
    from PySide6.QtGui import QGuiApplication
    from PySide6.QtQml import QQmlApplicationEngine

    app = QGuiApplication(sys.argv)
    app.setApplicationName("Note Assistant")
    app.setOrganizationName("NoteAssistant")

    engine = QQmlApplicationEngine()

    # Resolve the main QML file relative to this package
    qml_path = os.path.join(os.path.dirname(__file__), "qml", "Main.qml")
    engine.load(qml_path)

    if not engine.rootObjects():
        sys.exit(-1)

    sys.exit(app.exec())
