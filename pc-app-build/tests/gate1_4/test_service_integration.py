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

from app.notes import (  # noqa: E402
    CreateNoteCommand,
    DatabaseExecutor,
    HardDeleteCommand,
    NoteCommandService,
    NoteQueryService,
    RestoreCommand,
    SetPinnedCommand,
    SoftDeleteCommand,
    SqlAlchemyNoteRepository,
    UpdateNoteCommand,
    create_session_factory,
    create_sqlite_engine,
    initialize_database,
)


@pytest.mark.asyncio
async def test_services_use_real_repository_and_single_executor(tmp_path: Path) -> None:
    engine = create_sqlite_engine(tmp_path / "notes.db")
    initialize_database(engine)
    repository = SqlAlchemyNoteRepository(create_session_factory(engine))
    executor = DatabaseExecutor(thread_name_prefix="gate1-4-db")
    commands = NoteCommandService(repository, executor)
    queries = NoteQueryService(repository, executor)

    try:
        created = await commands.create(
            CreateNoteCommand(
                title=" first ",
                content="content\n",
                tags=("客户", "客户", "跟进"),
            )
        )
        assert created.title == "first"
        assert created.tags == ("客户", "跟进")

        updated = await commands.update(
            UpdateNoteCommand(
                note_id=created.id,
                title="updated",
                content="new content",
                tags=("测试",),
            )
        )
        assert updated.title == "updated"

        pinned = await commands.set_pinned(SetPinnedCommand((created.id,), True))
        assert pinned[0].is_pinned is True
        assert await queries.list_pinned() == pinned
        assert await queries.search("new content") == pinned
        assert await queries.list_by_tag("测试") == pinned

        assert await commands.soft_delete(SoftDeleteCommand((created.id,))) == 1
        deleted = await queries.list_deleted()
        assert len(deleted) == 1
        assert deleted[0].is_deleted is True

        assert await commands.restore(RestoreCommand((created.id,))) == 1
        restored = await queries.get(created.id)
        assert restored is not None
        assert restored.is_deleted is False

        assert await commands.soft_delete(SoftDeleteCommand((created.id,))) == 1
        assert await commands.hard_delete(HardDeleteCommand((created.id,))) == 1
        assert await queries.get(created.id, include_deleted=True) is None
    finally:
        await executor.close()
        engine.dispose()

    assert executor.is_closed is True
