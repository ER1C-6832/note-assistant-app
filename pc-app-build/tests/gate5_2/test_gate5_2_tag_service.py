from __future__ import annotations

import asyncio

import pytest

from app.notes import (
    DatabaseExecutor,
    NoteQueryService,
    SqlAlchemyNoteRepository,
    TagCatalog,
    TagCatalogService,
    create_session_factory,
    create_sqlite_engine,
    initialize_database,
)


@pytest.mark.asyncio
async def test_concurrent_catalog_adds_do_not_overwrite_each_other(tmp_path) -> None:
    engine = create_sqlite_engine(tmp_path / "notes.db")
    initialize_database(engine)
    db = DatabaseExecutor(thread_name_prefix="gate5-2-tags")
    queries = NoteQueryService(SqlAlchemyNoteRepository(create_session_factory(engine)), db)
    catalog = TagCatalog(tmp_path / "tags.json", default_tags=())
    catalog.load()
    service = TagCatalogService(catalog, queries)

    await asyncio.gather(
        service.add_async("one"),
        service.add_async("two"),
        service.add_async("three"),
    )

    assert set(service.custom_tags) == {"one", "two", "three"}
    await service.close()
    await db.close()
    engine.dispose()
