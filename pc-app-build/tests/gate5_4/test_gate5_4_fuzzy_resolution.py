from __future__ import annotations

import pytest
import pytest_asyncio

from app.assistant.mcp import Gate51ToolExecutor, ToolCall, ToolRegistry, UiCommandBus
from app.notes import (
    CreateNoteCommand,
    DatabaseExecutor,
    NoteCommandService,
    NoteQueryService,
    NoteSource,
    SqlAlchemyNoteRepository,
    create_session_factory,
    create_sqlite_engine,
    initialize_database,
)


@pytest_asyncio.fixture
async def runtime(tmp_path):
    engine = create_sqlite_engine(tmp_path / "gate5-4.db")
    initialize_database(engine)
    database = DatabaseExecutor(thread_name_prefix="gate5-4-intent")
    repository = SqlAlchemyNoteRepository(create_session_factory(engine))
    commands = NoteCommandService(repository, database)
    queries = NoteQueryService(repository, database)
    bus = UiCommandBus()
    registry = ToolRegistry(executor=Gate51ToolExecutor(queries, bus))
    yield registry, commands, queries, bus
    await bus.close()
    await database.close()
    engine.dispose()


async def call(registry, request_id, name, arguments):
    return await registry.call(ToolCall(request_id, name, arguments))


@pytest.mark.asyncio
async def test_verbose_search_and_resolve_find_precise_topic(runtime) -> None:
    registry, commands, _queries, _bus = runtime
    quote = await commands.create(
        CreateNoteCommand(
            "王总报价",
            "游戏手柄样机报价需要周五确认",
            ("客户", "报价"),
            source=NoteSource.MANUAL,
        )
    )
    await commands.create(
        CreateNoteCommand(
            "包装问题",
            "纸箱尺寸需要复核",
            ("包装",),
            source=NoteSource.MANUAL,
        )
    )

    searched = await call(
        registry,
        1,
        "notes.search",
        {"query": "麻烦帮我找一下那个关于王总报价的便签"},
    )
    resolved = await call(
        registry,
        2,
        "notes.resolve",
        {"query": "请帮我定位那个关于王总报价的便签"},
    )

    assert searched.affected_note_ids == (quote.id,)
    assert resolved.result["resolution_status"] == "resolved"
    assert resolved.result["note_id"] == quote.id


@pytest.mark.asyncio
async def test_explicit_id_inside_long_sentence_resolves_exactly(runtime) -> None:
    registry, commands, _queries, _bus = runtime
    first = await commands.create(CreateNoteCommand("第一条", "", (), source=NoteSource.MANUAL))
    await commands.create(CreateNoteCommand("第二条", "", (), source=NoteSource.MANUAL))

    result = await call(
        registry,
        3,
        "notes.resolve",
        {"query": f"麻烦打开编号为 {first.id} 的那条便签"},
    )

    assert result.result["resolution_status"] == "resolved"
    assert result.result["note_id"] == first.id


@pytest.mark.asyncio
async def test_bare_context_reference_never_guesses_among_multiple_notes(
    runtime,
) -> None:
    registry, commands, _queries, _bus = runtime
    await commands.create(CreateNoteCommand("甲", "", (), source=NoteSource.MANUAL))
    await commands.create(CreateNoteCommand("乙", "", (), source=NoteSource.MANUAL))

    result = await call(
        registry,
        4,
        "notes.resolve",
        {"query": "刚才那条便签", "limit": 5},
    )

    assert result.status == "success"
    assert result.result["resolution_status"] == "ambiguous"
    assert result.result["note_id"] is None
    assert len(result.result["candidates"]) == 2


@pytest.mark.asyncio
async def test_numeric_title_is_not_silently_reinterpreted_as_note_id(runtime) -> None:
    registry, commands, _queries, _bus = runtime
    numeric_title = await commands.create(
        CreateNoteCommand("2", "标题就是数字", (), source=NoteSource.MANUAL)
    )
    numeric_id = await commands.create(
        CreateNoteCommand("真正的第二条", "数据库 id 为 2", (), source=NoteSource.MANUAL)
    )
    assert numeric_title.id == 1
    assert numeric_id.id == 2

    by_title = await call(registry, 5, "notes.resolve", {"query": "2"})
    by_id = await call(registry, 6, "notes.resolve", {"query": "编号 2"})

    assert by_title.result["resolution_status"] == "resolved"
    assert by_title.result["note_id"] == numeric_title.id
    assert by_id.result["resolution_status"] == "resolved"
    assert by_id.result["note_id"] == numeric_id.id
