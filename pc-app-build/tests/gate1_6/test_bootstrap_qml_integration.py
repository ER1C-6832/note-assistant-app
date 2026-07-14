from __future__ import annotations

import asyncio
from collections.abc import Callable
from pathlib import Path

import pytest

from app.bootstrap import create_application_context
from app.ui import NoteListModel, NotesViewModel


async def _wait_until(
    qapp,
    predicate: Callable[[], bool],
    *,
    timeout_seconds: float = 5.0,
) -> None:
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout_seconds
    while loop.time() < deadline:
        qapp.processEvents()
        if predicate():
            return
        await asyncio.sleep(0.01)
    raise AssertionError("condition was not met before timeout")


async def _close_context(context) -> None:
    for root_object in context.engine.rootObjects():
        root_object.close()
    await context.lifecycle.shutdown(timeout_seconds=3.0)
    context.engine.deleteLater()


@pytest.mark.asyncio
async def test_bootstrap_loads_qml_with_real_gate1_6_objects(qapp, tmp_path: Path) -> None:
    worktree_root = tmp_path / "worktree"
    worktree_root.mkdir()
    context = create_application_context(
        qapp,
        data_root=tmp_path / "runtime",
        worktree_root=worktree_root,
        migration_env={},
    )

    try:
        assert isinstance(context.notes_view_model, NotesViewModel)
        assert isinstance(context.notes_list_model, NoteListModel)
        assert isinstance(context.deleted_notes_list_model, NoteListModel)
        assert context.engine.rootObjects()

        await _wait_until(
            qapp,
            lambda: context.notes_view_model.statusMessage == "全部便签：0 条",
        )
        assert context.notes_view_model.errorMessage == ""
    finally:
        await _close_context(context)

    assert context.database_executor.is_closed is True


@pytest.mark.asyncio
async def test_qml_view_model_runs_todo_crud_and_deleted_flow(qapp, tmp_path: Path) -> None:
    worktree_root = tmp_path / "worktree"
    worktree_root.mkdir()
    context = create_application_context(
        qapp,
        data_root=tmp_path / "runtime",
        worktree_root=worktree_root,
        migration_env={},
    )
    view_model = context.notes_view_model
    created_ids: list[int] = []
    updated_ids: list[int] = []
    deleted_ids: list[list[int]] = []
    restored_ids: list[list[int]] = []
    view_model.noteCreated.connect(created_ids.append)
    view_model.noteUpdated.connect(updated_ids.append)
    view_model.notesSoftDeleted.connect(lambda ids: deleted_ids.append(list(ids)))
    view_model.notesRestored.connect(lambda ids: restored_ids.append(list(ids)))

    try:
        await _wait_until(qapp, lambda: view_model.statusMessage == "全部便签：0 条")

        view_model.requestCreateNote(
            "Gate 1.6 待办",
            "验证正式 QML 接线",
            "待办、测试",
            True,
        )
        await _wait_until(
            qapp,
            lambda: bool(created_ids) and context.notes_list_model.rowCount() == 1,
        )
        note_id = created_ids[0]
        assert view_model.selectedTitle == "Gate 1.6 待办"

        view_model.loadCategory("todo")
        await _wait_until(
            qapp,
            lambda: view_model.activeCategory == "todo"
            and view_model.statusMessage == "待办便签：1 条",
        )
        assert context.notes_list_model.note_ids() == [note_id]

        view_model.requestUpdateSelectedNote(
            "Gate 1.6 已更新",
            "更新后仍属于待办分类",
            "待办、测试",
        )
        await _wait_until(
            qapp,
            lambda: updated_ids == [note_id] and view_model.selectedTitle == "Gate 1.6 已更新",
        )

        view_model.requestDeleteSelectedNote()
        await _wait_until(
            qapp,
            lambda: deleted_ids == [[note_id]] and context.notes_list_model.rowCount() == 0,
        )

        view_model.loadDeleted()
        await _wait_until(
            qapp,
            lambda: view_model.activeCategory == "deleted"
            and context.deleted_notes_list_model.note_ids() == [note_id],
        )

        view_model.requestRestoreDeletedAt(0)
        await _wait_until(
            qapp,
            lambda: restored_ids == [[note_id]]
            and context.deleted_notes_list_model.rowCount() == 0,
        )
        assert view_model.errorMessage == ""
    finally:
        await _close_context(context)
