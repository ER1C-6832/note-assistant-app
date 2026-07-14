from __future__ import annotations

import asyncio
import sqlite3
from collections.abc import Callable
from contextlib import closing
from pathlib import Path

import pytest

from app.bootstrap import create_application_context


async def _wait_until(
    qapp,
    predicate: Callable[[], bool],
    *,
    timeout_seconds: float = 8.0,
) -> None:
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout_seconds
    while loop.time() < deadline:
        qapp.processEvents()
        if predicate():
            return
        await asyncio.sleep(0.01)
    raise AssertionError("condition was not met before timeout")


async def _close_context(context, qapp) -> None:
    for root_object in context.engine.rootObjects():
        root_object.close()
    await context.lifecycle.shutdown(timeout_seconds=5.0)
    context.engine.deleteLater()
    qapp.processEvents()


def _write_legacy_database(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(path)) as connection:
        connection.execute(
            """
            CREATE TABLE notes (
                id INTEGER PRIMARY KEY,
                title VARCHAR(200) NOT NULL,
                content TEXT NOT NULL DEFAULT '',
                tags TEXT NOT NULL DEFAULT '[]',
                is_pinned BOOLEAN NOT NULL DEFAULT 0,
                is_deleted BOOLEAN NOT NULL DEFAULT 0,
                created_at DATETIME NOT NULL,
                updated_at DATETIME NOT NULL,
                source VARCHAR(50) NOT NULL DEFAULT 'manual'
            )
            """
        )
        connection.execute(
            """
            INSERT INTO notes (
                id, title, content, tags, is_pinned, is_deleted,
                created_at, updated_at, source
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                1,
                "legacy gate 1.7",
                "legacy migration smoke",
                '["客户", "待办"]',
                1,
                0,
                "2026-07-14 00:00:00",
                "2026-07-14 00:00:00",
                "imported",
            ),
        )
        connection.commit()


@pytest.mark.asyncio
async def test_real_qml_sqlite_crud_survives_restart_and_hard_delete(
    qapp,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "runtime"
    worktree_root = tmp_path / "worktree"
    worktree_root.mkdir()

    first = create_application_context(
        qapp,
        data_root=data_root,
        worktree_root=worktree_root,
        migration_env={},
    )
    created_ids: list[int] = []
    updated_ids: list[int] = []
    first.notes_view_model.noteCreated.connect(created_ids.append)
    first.notes_view_model.noteUpdated.connect(updated_ids.append)

    try:
        await _wait_until(
            qapp,
            lambda: first.notes_view_model.statusMessage == "全部便签：0 条",
        )

        first.notes_view_model.requestCreateNote(
            "Gate 1.7 持久化",
            "跨重启 CRUD 回归",
            "待办、回归",
            True,
        )
        await _wait_until(
            qapp,
            lambda: bool(created_ids) and first.notes_list_model.rowCount() == 1,
        )
        note_id = created_ids[0]

        first.notes_view_model.loadCategory("todo")
        await _wait_until(
            qapp,
            lambda: first.notes_view_model.activeCategory == "todo"
            and first.notes_list_model.note_ids() == [note_id],
        )

        first.notes_view_model.loadTag("回归")
        await _wait_until(
            qapp,
            lambda: first.notes_view_model.activeCategory == "tag:回归"
            and first.notes_list_model.note_ids() == [note_id],
        )

        first.notes_view_model.searchNotes("跨重启")
        await _wait_until(
            qapp,
            lambda: first.notes_view_model.activeCategory == "search"
            and first.notes_list_model.note_ids() == [note_id],
        )

        first.notes_view_model.requestUpdateSelectedNote(
            "Gate 1.7 已更新",
            "持久化内容已更新",
            "待办、回归、已更新",
        )
        await _wait_until(
            qapp,
            lambda: updated_ids == [note_id] and not first.notes_view_model.isBusy,
        )
        updated = await first.note_query_service.get(note_id)
        assert updated is not None
        assert updated.title == "Gate 1.7 已更新"
        assert updated.content == "持久化内容已更新"
        assert updated.tags == ("待办", "回归", "已更新")

        # The current search no longer matches after the edit, so keeping the current
        # query correctly removes the note from the visible model and clears selection.
        assert first.notes_view_model.activeCategory == "search"
        assert first.notes_list_model.rowCount() == 0
        assert first.notes_view_model.selectedIndex == -1

        first.notes_view_model.requestAddCustomTag("自定义回归")
        await _wait_until(
            qapp,
            lambda: "自定义回归" in first.tag_catalog.custom_tags
            and not first.notes_view_model.mutationBusy,
        )
    finally:
        await _close_context(first, qapp)

    second = create_application_context(
        qapp,
        data_root=data_root,
        worktree_root=worktree_root,
        migration_env={},
    )
    soft_deleted: list[list[int]] = []
    hard_deleted: list[list[int]] = []
    second.notes_view_model.notesSoftDeleted.connect(
        lambda ids: soft_deleted.append(list(ids))
    )
    second.notes_view_model.notesHardDeleted.connect(
        lambda ids: hard_deleted.append(list(ids))
    )

    try:
        assert second.migration_result.status == "existing"
        await _wait_until(
            qapp,
            lambda: second.notes_list_model.note_ids() == [note_id],
        )
        assert second.notes_view_model.selectedTitle == "Gate 1.7 已更新"
        assert "自定义回归" in second.tag_catalog.custom_tags

        second.notes_view_model.requestDeleteSelectedNote()
        await _wait_until(
            qapp,
            lambda: soft_deleted == [[note_id]]
            and second.notes_list_model.rowCount() == 0,
        )

        second.notes_view_model.loadDeleted()
        await _wait_until(
            qapp,
            lambda: second.deleted_notes_list_model.note_ids() == [note_id],
        )

        second.notes_view_model.requestBulkHardDeleteDeleted([note_id])
        await _wait_until(
            qapp,
            lambda: hard_deleted == [[note_id]]
            and second.deleted_notes_list_model.rowCount() == 0,
        )
    finally:
        await _close_context(second, qapp)

    third = create_application_context(
        qapp,
        data_root=data_root,
        worktree_root=worktree_root,
        migration_env={},
    )
    try:
        await _wait_until(
            qapp,
            lambda: third.notes_view_model.statusMessage == "全部便签：0 条",
        )
        assert await third.note_query_service.list_all() == ()
        assert await third.note_query_service.list_deleted() == ()
    finally:
        await _close_context(third, qapp)


@pytest.mark.asyncio
async def test_legacy_database_migrates_through_bootstrap_and_renders(
    qapp,
    tmp_path: Path,
) -> None:
    worktree_root = tmp_path / "worktree"
    legacy_db = (
        worktree_root / "pc-app-build" / "services" / "notes-api" / "data" / "notes.db"
    )
    _write_legacy_database(legacy_db)
    source_bytes = legacy_db.read_bytes()

    context = create_application_context(
        qapp,
        data_root=tmp_path / "runtime",
        worktree_root=worktree_root,
        migration_env={},
    )
    try:
        assert context.migration_result.status == "migrated"
        assert context.migration_result.source_db == legacy_db.resolve()
        await _wait_until(
            qapp,
            lambda: context.notes_list_model.note_ids() == [1],
        )
        assert context.notes_view_model.selectedTitle == "legacy gate 1.7"
        assert context.notes_view_model.selectedIsPinned is True
        assert legacy_db.read_bytes() == source_bytes
        assert context.paths.notes_db.resolve() != legacy_db.resolve()
    finally:
        await _close_context(context, qapp)
