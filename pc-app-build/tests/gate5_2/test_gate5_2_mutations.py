from __future__ import annotations

import asyncio

import pytest
import pytest_asyncio

from app.assistant.mcp import (
    Gate52ToolExecutor,
    McpCoordinator,
    ToolCall,
    ToolRegistry,
    UiCommandBus,
    UiDispatchResult,
)
from app.notes import (
    CreateNoteCommand,
    DatabaseExecutor,
    NoteCommandService,
    NoteQueryService,
    NoteSource,
    SqlAlchemyNoteRepository,
    TagCatalog,
    TagCatalogService,
    create_session_factory,
    create_sqlite_engine,
    initialize_database,
)


class RecordingUiAdapter:
    def __init__(self, *, accepted: bool = True) -> None:
        self.accepted = accepted
        self.commands: list[str] = []

    async def dispatch(self, command):
        self.commands.append(command.kind.value)
        return UiDispatchResult(
            self.accepted,
            "ok" if self.accepted else "unavailable",
            None if self.accepted else "ui_unavailable",
        )


@pytest_asyncio.fixture
async def runtime(tmp_path):
    engine = create_sqlite_engine(tmp_path / "notes.db")
    initialize_database(engine)
    db = DatabaseExecutor(thread_name_prefix="gate5-2-test")
    repository = SqlAlchemyNoteRepository(create_session_factory(engine))
    commands = NoteCommandService(repository, db)
    queries = NoteQueryService(repository, db)
    catalog = TagCatalog(tmp_path / "tags.json", default_tags=())
    catalog.load()
    tags = TagCatalogService(catalog, queries)
    ui_bus = UiCommandBus()
    adapter = RecordingUiAdapter()
    ui_bus.bind(adapter)
    registry = ToolRegistry(executor=Gate52ToolExecutor(queries, commands, tags, ui_bus))
    yield registry, commands, queries, tags, ui_bus, adapter
    await ui_bus.close()
    await tags.close()
    await db.close()
    engine.dispose()


async def call(registry, request_id, name, arguments):
    return await registry.call(ToolCall(request_id, name, arguments))


@pytest.mark.asyncio
async def test_low_risk_note_mutations_use_services_and_voice_pc_source(
    runtime,
) -> None:
    registry, _commands, queries, _tags, _bus, adapter = runtime
    created = await call(
        registry,
        1,
        "notes.create",
        {
            "title": "Gate52",
            "content": "first",
            "type": "todo",
            "tags": ["客户"],
        },
    )
    assert created.status == "success"
    note_id = created.affected_note_ids[0]
    note = await queries.get(note_id)
    assert note is not None
    assert note.source is NoteSource.VOICE_PC
    assert note.tags == ("客户", "待办")

    appended = await call(
        registry,
        2,
        "notes.append",
        {"note_id": note_id, "content": "second", "separator": "space"},
    )
    titled = await call(
        registry,
        3,
        "notes.update_title",
        {"note_id": note_id, "title": "Renamed"},
    )
    converted = await call(
        registry,
        4,
        "notes.convert_type",
        {"note_id": note_id, "target_type": "normal"},
    )
    pinned = await call(
        registry,
        5,
        "notes.pin",
        {"note_ids": [note_id], "pinned": True},
    )

    assert {appended.status, titled.status, converted.status, pinned.status} == {"success"}
    final = await queries.get(note_id)
    assert final is not None
    assert final.title == "Renamed"
    assert final.content == "first second"
    assert "待办" not in final.tags
    assert final.is_pinned is True
    assert adapter.commands.count("refresh_current") >= 5


@pytest.mark.asyncio
async def test_high_risk_gate52_previews_are_zero_write(runtime) -> None:
    registry, commands, queries, tags, _bus, _adapter = runtime
    note = await commands.create(
        CreateNoteCommand("original", "body", ("base",), source=NoteSource.MANUAL)
    )
    before = await queries.get(note.id)
    await tags.add_async("unused")

    results = (
        await call(
            registry,
            10,
            "notes.replace_content",
            {"note_id": note.id, "content": "replacement"},
        ),
        await call(registry, 11, "notes.delete", {"note_ids": [note.id]}),
        await call(
            registry,
            12,
            "tags.bind",
            {"note_ids": [note.id], "operation": "replace", "tags": ["other"]},
        ),
        await call(registry, 13, "tags.delete", {"name": "unused"}),
    )

    assert all(result.status == "requires_confirmation" for result in results)
    assert all(result.confirmation_id is None for result in results)
    assert all(result.result["confirmation_available"] is False for result in results)
    assert await queries.get(note.id) == before
    assert "unused" in tags.custom_tags


@pytest.mark.asyncio
async def test_tag_tools_and_batch_bind_are_atomic(runtime) -> None:
    registry, commands, queries, _tags, _bus, _adapter = runtime
    first = await commands.create(CreateNoteCommand("first", "", (), source=NoteSource.MANUAL))
    second = await commands.create(CreateNoteCommand("second", "", (), source=NoteSource.MANUAL))

    created = await call(registry, 20, "tags.create", {"name": "项目"})
    duplicate = await call(registry, 21, "tags.create", {"name": "项目"})
    bound = await call(
        registry,
        22,
        "tags.bind",
        {
            "note_ids": [first.id, second.id],
            "operation": "add",
            "tags": ["项目"],
        },
    )
    listed = await call(registry, 23, "tags.list", {})
    searched = await call(registry, 24, "tags.search", {"query": "项"})

    assert created.result["created"] is True
    assert duplicate.result["created"] is False
    assert bound.status == "success"
    assert "项目" in (await queries.get(first.id)).tags
    assert "项目" in (await queries.get(second.id)).tags
    assert any(item["name"] == "待办" for item in listed.result["tags"])
    assert searched.result["count"] == 1

    rolled_back = await call(
        registry,
        25,
        "tags.bind",
        {
            "note_ids": [first.id, 999999],
            "operation": "add",
            "tags": ["should-not-commit"],
        },
    )
    assert rolled_back.status == "failed"
    assert "should-not-commit" not in (await queries.get(first.id)).tags


@pytest.mark.asyncio
async def test_large_conditional_batches_escalate_without_write(runtime) -> None:
    registry, commands, queries, _tags, _bus, _adapter = runtime
    notes = [
        await commands.create(CreateNoteCommand(f"n-{index}", "", (), source=NoteSource.MANUAL))
        for index in range(6)
    ]
    note_ids = [note.id for note in notes]

    pin = await call(
        registry,
        30,
        "notes.pin",
        {"note_ids": note_ids, "pinned": True},
    )
    bind = await call(
        registry,
        31,
        "tags.bind",
        {"note_ids": note_ids, "operation": "add", "tags": ["bulk"]},
    )

    assert pin.status == "requires_confirmation"
    assert bind.status == "requires_confirmation"

    persisted = await asyncio.gather(*(queries.get(note_id) for note_id in note_ids))
    assert all(note is not None and not note.is_pinned for note in persisted)
    assert all(note is not None and "bulk" not in note.tags for note in persisted)


@pytest.mark.asyncio
async def test_committed_mutation_reports_ui_failure_as_partial_success(
    tmp_path,
) -> None:
    engine = create_sqlite_engine(tmp_path / "partial.db")
    initialize_database(engine)
    db = DatabaseExecutor(thread_name_prefix="gate5-2-partial")
    repository = SqlAlchemyNoteRepository(create_session_factory(engine))
    commands = NoteCommandService(repository, db)
    queries = NoteQueryService(repository, db)
    catalog = TagCatalog(tmp_path / "partial-tags.json", default_tags=())
    catalog.load()
    tags = TagCatalogService(catalog, queries)
    bus = UiCommandBus()
    bus.bind(RecordingUiAdapter(accepted=False))
    registry = ToolRegistry(executor=Gate52ToolExecutor(queries, commands, tags, bus))

    result = await call(registry, 40, "notes.create", {"title": "committed"})

    assert result.status == "partial_success"
    assert result.error_code == "ui_refresh_failed"
    assert result.result["committed"] is True
    assert len(await queries.list_all()) == 1

    await bus.close()
    await tags.close()
    await db.close()
    engine.dispose()


@pytest.mark.asyncio
async def test_duplicate_create_request_mutates_once(runtime) -> None:
    registry, _commands, queries, _tags, _bus, _adapter = runtime
    coordinator = McpCoordinator(registry)
    responses = []

    async def response_sink(payload):
        responses.append(payload)

    async def lifecycle_sink(_summary):
        return None

    await coordinator.open_generation(1, response_sink=response_sink, lifecycle_sink=lifecycle_sink)
    coordinator.bind_session(1, "session")
    payload = {
        "jsonrpc": "2.0",
        "id": "duplicate-create",
        "method": "tools/call",
        "params": {"name": "notes.create", "arguments": {"title": "only once"}},
    }
    assert coordinator.submit_nowait(1, "session", payload).accepted
    assert coordinator.submit_nowait(1, "session", payload).accepted

    for _ in range(100):
        if len(responses) == 2:
            break
        await asyncio.sleep(0.01)

    assert len(responses) == 2
    assert len(await queries.list_all()) == 1
    await coordinator.close()
