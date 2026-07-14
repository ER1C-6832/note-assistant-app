"""Composition root for the single-process desktop application."""

from __future__ import annotations

import asyncio
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from PySide6.QtCore import QTimer, QUrl
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine
from qasync import QEventLoop

from .app_paths import AppPaths
from .lifecycle import ApplicationLifecycle
from .ui.empty_notes_view_model import EmptyNoteListModel, EmptyNotesViewModel


@dataclass(slots=True)
class ApplicationContext:
    app: QGuiApplication
    engine: QQmlApplicationEngine
    paths: AppPaths
    lifecycle: ApplicationLifecycle
    notes_view_model: EmptyNotesViewModel
    notes_list_model: EmptyNoteListModel
    deleted_notes_list_model: EmptyNoteListModel


def create_event_loop(app: QGuiApplication) -> QEventLoop:
    return QEventLoop(app)


def create_application_context(
    app: QGuiApplication,
    *,
    data_root: str | Path | None = None,
) -> ApplicationContext:
    paths = AppPaths.resolve(root_override=data_root)
    paths.ensure_directories()

    lifecycle = ApplicationLifecycle()
    notes_list_model = EmptyNoteListModel()
    deleted_notes_list_model = EmptyNoteListModel()
    notes_view_model = EmptyNotesViewModel()

    engine = QQmlApplicationEngine()
    context = engine.rootContext()
    context.setContextProperty("notesViewModel", notes_view_model)
    context.setContextProperty("notesListModel", notes_list_model)
    context.setContextProperty("deletedNotesListModel", deleted_notes_list_model)

    qml_file = Path(__file__).resolve().parent / "qml" / "Main.qml"
    engine.load(QUrl.fromLocalFile(str(qml_file)))
    if not engine.rootObjects():
        raise RuntimeError(f"QML failed to load: {qml_file}")

    engine.quit.connect(app.quit)
    QTimer.singleShot(0, notes_view_model.loadAll)

    return ApplicationContext(
        app=app,
        engine=engine,
        paths=paths,
        lifecycle=lifecycle,
        notes_view_model=notes_view_model,
        notes_list_model=notes_list_model,
        deleted_notes_list_model=deleted_notes_list_model,
    )


def run_application(
    argv: Sequence[str] | None = None,
    *,
    data_root: str | Path | None = None,
) -> int:
    arguments = list(sys.argv if argv is None else argv)
    existing = QGuiApplication.instance()
    owns_app = existing is None
    app = existing if existing is not None else QGuiApplication(arguments)
    if not isinstance(app, QGuiApplication):
        raise RuntimeError("The existing Qt application is not a QGuiApplication.")

    app.setApplicationName("NoteAssistant")
    app.setOrganizationName("EHOME")
    app.setQuitOnLastWindowClosed(True)

    loop = create_event_loop(app)
    asyncio.set_event_loop(loop)

    try:
        context = create_application_context(app, data_root=data_root)
    except Exception:
        loop.close()
        asyncio.set_event_loop(None)
        raise

    app.aboutToQuit.connect(loop.stop)

    try:
        with loop:
            loop.run_forever()
            loop.run_until_complete(context.lifecycle.shutdown(timeout_seconds=1.0))
    finally:
        asyncio.set_event_loop(None)
        if owns_app:
            context.engine.deleteLater()

    return 0
