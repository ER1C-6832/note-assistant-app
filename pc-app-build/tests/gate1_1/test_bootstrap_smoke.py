from __future__ import annotations

from pathlib import Path

from PySide6.QtGui import QGuiApplication
from qasync import QEventLoop

from app.bootstrap import create_application_context, create_event_loop


def test_qasync_event_loop_can_be_created(qapp) -> None:
    assert isinstance(qapp, QGuiApplication)
    loop = create_event_loop(qapp)
    try:
        assert isinstance(loop, QEventLoop)
    finally:
        loop.close()


def test_qml_loads_with_empty_view_model(qapp, tmp_path: Path) -> None:
    context = create_application_context(qapp, data_root=tmp_path / "runtime")

    assert context.engine.rootObjects()
    assert context.paths.data_dir.is_dir()
    assert context.notes_view_model.resultCount == 0
    assert context.notes_view_model.deletedResultCount == 0

    context.engine.rootObjects()[0].close()
    context.engine.deleteLater()
