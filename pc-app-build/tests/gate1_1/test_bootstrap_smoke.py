from __future__ import annotations

from pathlib import Path

import pytest
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


@pytest.mark.asyncio
async def test_qml_loads_with_composed_notes_runtime(qapp, tmp_path: Path) -> None:
    worktree_root = tmp_path / "worktree"
    worktree_root.mkdir()
    context = create_application_context(
        qapp,
        data_root=tmp_path / "runtime",
        worktree_root=worktree_root,
        migration_env={},
    )

    try:
        assert context.engine.rootObjects()
        assert context.paths.data_dir.is_dir()
        assert context.paths.notes_db.is_file()
        assert context.migration_result.status == "created_empty"
        assert context.notes_view_model.resultCount == 0
        assert context.notes_view_model.deletedResultCount == 0
    finally:
        for root_object in context.engine.rootObjects():
            root_object.close()
        await context.lifecycle.shutdown(timeout_seconds=3.0)
        context.engine.deleteLater()

    assert context.database_executor.is_closed is True
