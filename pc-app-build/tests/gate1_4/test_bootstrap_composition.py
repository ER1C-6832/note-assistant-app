from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QUICK_CONTROLS_STYLE", "Basic")

APP_ROOT = Path(__file__).resolve().parents[2] / "apps" / "notes-pyside"
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

from app.bootstrap import (  # noqa: E402
    create_application_context,
    resolve_worktree_root,
)
from app.notes import (  # noqa: E402
    CreateNoteCommand,
    NoteServiceUnavailableError,
)


def test_explicit_worktree_root_is_resolved(tmp_path: Path) -> None:
    root = tmp_path / "worktree"
    assert resolve_worktree_root(root) == root.resolve()


@pytest.mark.asyncio
async def test_bootstrap_composes_notes_runtime_and_shutdown(qapp, tmp_path: Path) -> None:
    worktree_root = tmp_path / "worktree"
    worktree_root.mkdir()
    context = create_application_context(
        qapp,
        data_root=tmp_path / "runtime",
        worktree_root=worktree_root,
        migration_env={},
    )

    try:
        assert context.migration_result.status == "created_empty"
        assert context.paths.notes_db.is_file()
        assert context.tag_catalog.custom_tags
        assert context.engine.rootObjects()

        note = await context.note_command_service.create(
            CreateNoteCommand("bootstrap", "content", ("测试",))
        )
        assert note.id > 0
        assert await context.note_query_service.get(note.id) == note
    finally:
        for root_object in context.engine.rootObjects():
            root_object.close()
        await context.lifecycle.shutdown(timeout_seconds=3.0)
        context.engine.deleteLater()

    assert context.database_executor.is_closed is True
    with pytest.raises(NoteServiceUnavailableError):
        await context.note_query_service.list_all()


@pytest.mark.asyncio
async def test_shutdown_closes_executor_before_database_engine(
    qapp,
    tmp_path: Path,
    monkeypatch,
) -> None:
    import app.bootstrap as bootstrap

    holder = {}
    dispose_calls = []

    async def recording_dispose(database_engine) -> None:
        context = holder["context"]
        assert context.database_executor.is_closed is True
        dispose_calls.append(database_engine)
        database_engine.dispose()

    monkeypatch.setattr(bootstrap, "dispose_database_engine", recording_dispose)

    worktree_root = tmp_path / "worktree"
    worktree_root.mkdir()
    context = create_application_context(
        qapp,
        data_root=tmp_path / "runtime",
        worktree_root=worktree_root,
        migration_env={},
    )
    holder["context"] = context

    for root_object in context.engine.rootObjects():
        root_object.close()
    await context.lifecycle.shutdown(timeout_seconds=3.0)
    context.engine.deleteLater()

    assert dispose_calls == [context.database_engine]
