from __future__ import annotations

import asyncio
import json

import pytest
import pytest_asyncio

from app.assistant.mcp import (
    Gate53ToolExecutor,
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
    UpdateNoteCommand,
    create_session_factory,
    create_sqlite_engine,
    initialize_database,
)


class RecordingUiAdapter:
    def __init__(self) -> None:
        self.commands: list[str] = []

    async def dispatch(self, command):
        self.commands.append(command.kind.value)
        return UiDispatchResult(True, "ok")


@pytest_asyncio.fixture
async def runtime(tmp_path):
    engine = create_sqlite_engine(tmp_path / "notes.db")
    initialize_database(engine)
    db = DatabaseExecutor(thread_name_prefix="gate5-3-test")
    repository = SqlAlchemyNoteRepository(create_session_factory(engine))
    commands = NoteCommandService(repository, db)
    queries = NoteQueryService(repository, db)
    catalog = TagCatalog(tmp_path / "tags.json", default_tags=())
    catalog.load()
    tags = TagCatalogService(catalog, queries)
    bus = UiCommandBus()
    adapter = RecordingUiAdapter()
    bus.bind(adapter)
    executor = Gate53ToolExecutor(queries, commands, tags, bus)
    registry = ToolRegistry(executor=executor)
    yield registry, executor, commands, queries, tags, bus, adapter
    await executor.close()
    await bus.close()
    await tags.close()
    await db.close()
    engine.dispose()


async def call(registry, request_id, name, arguments, *, generation=1, session="s"):
    return await registry.call(ToolCall(request_id, name, arguments, generation, session))


@pytest.mark.asyncio
async def test_delete_reject_then_confirm_is_exactly_once(runtime) -> None:
    registry, executor, commands, queries, _tags, _bus, _adapter = runtime
    note = await commands.create(CreateNoteCommand("delete", "body", (), source=NoteSource.MANUAL))

    first = await call(registry, 1, "notes.delete", {"note_ids": [note.id]})
    assert first.status == "requires_confirmation"
    assert first.confirmation_id
    assert (await queries.get(note.id, include_deleted=True)).is_deleted is False

    listed = await call(registry, 2, "assistant.list_pending_confirmations", {})
    assert listed.result["count"] == 1
    rejected = await call(
        registry,
        3,
        "assistant.reject",
        {"confirmation_id": first.confirmation_id},
    )
    assert rejected.status == "success"
    assert (await queries.get(note.id, include_deleted=True)).is_deleted is False

    second = await call(registry, 4, "notes.delete", {"note_ids": [note.id]})
    confirmed = await call(
        registry,
        5,
        "assistant.confirm",
        {"confirmation_id": second.confirmation_id},
    )
    assert confirmed.status == "success"
    assert (await queries.get(note.id, include_deleted=True)).is_deleted is True
    repeated = await call(
        registry,
        6,
        "assistant.confirm",
        {"confirmation_id": second.confirmation_id},
    )
    assert repeated.error_code == "confirmation_consumed"
    assert executor.pending_confirmation_count == 0


@pytest.mark.asyncio
async def test_confirm_revalidates_target_version(runtime) -> None:
    registry, _executor, commands, queries, _tags, _bus, _adapter = runtime
    note = await commands.create(CreateNoteCommand("replace", "old", (), source=NoteSource.MANUAL))
    pending = await call(
        registry,
        10,
        "notes.replace_content",
        {"note_id": note.id, "content": "dangerous replacement"},
    )
    await commands.update(UpdateNoteCommand(note.id, note.title, "newer", note.tags))

    result = await call(
        registry,
        11,
        "assistant.confirm",
        {"confirmation_id": pending.confirmation_id},
    )
    assert result.status == "failed"
    assert result.error_code == "stale_confirmation_target"
    assert (await queries.get(note.id)).content == "newer"


@pytest.mark.asyncio
async def test_large_pin_and_tag_replace_complete_after_confirmation(runtime) -> None:
    registry, _executor, commands, queries, _tags, _bus, _adapter = runtime
    notes = [
        await commands.create(CreateNoteCommand(f"n-{index}", "", (), source=NoteSource.MANUAL))
        for index in range(6)
    ]
    note_ids = [note.id for note in notes]

    pin = await call(registry, 20, "notes.pin", {"note_ids": note_ids, "pinned": True})
    assert pin.status == "requires_confirmation"
    pin_result = await call(
        registry,
        21,
        "assistant.confirm",
        {"confirmation_id": pin.confirmation_id},
    )
    assert pin_result.status == "success"
    pinned_snapshots = await asyncio.gather(*(queries.get(note_id) for note_id in note_ids))
    assert all(note.is_pinned for note in pinned_snapshots)

    bind = await call(
        registry,
        22,
        "tags.bind",
        {"note_ids": note_ids, "operation": "replace", "tags": ["批量"]},
    )
    bind_result = await call(
        registry,
        23,
        "assistant.confirm",
        {"confirmation_id": bind.confirmation_id},
    )
    assert bind_result.status == "success"
    snapshots = await asyncio.gather(*(queries.get(note_id) for note_id in note_ids))
    assert all(note.tags == ("批量",) for note in snapshots)


@pytest.mark.asyncio
async def test_show_confirmation_and_disconnect_invalidation(runtime) -> None:
    registry, executor, commands, _queries, _tags, _bus, adapter = runtime
    note = await commands.create(CreateNoteCommand("show", "", (), source=NoteSource.MANUAL))
    pending = await call(registry, 30, "notes.delete", {"note_ids": [note.id]})
    shown = await call(
        registry,
        31,
        "ui.show_confirmation",
        {"confirmation_id": pending.confirmation_id},
    )
    assert shown.status == "success"
    assert adapter.commands[-1] == "show_confirmation"

    await registry.close_generation(1, "disconnect")
    assert executor.pending_confirmation_count == 0
    blocked = await call(
        registry,
        32,
        "assistant.confirm",
        {"confirmation_id": pending.confirmation_id},
    )
    assert blocked.error_code == "confirmation_consumed"


@pytest.mark.asyncio
async def test_coordinator_disconnect_invalidates_session_pending(runtime) -> None:
    registry, executor, commands, _queries, _tags, _bus, _adapter = runtime
    note = await commands.create(CreateNoteCommand("disconnect", "", (), source=NoteSource.MANUAL))
    coordinator = McpCoordinator(registry)
    responses = []

    async def response_sink(payload):
        responses.append(payload)

    async def lifecycle_sink(_summary):
        return None

    await coordinator.open_generation(7, response_sink=response_sink, lifecycle_sink=lifecycle_sink)
    assert coordinator.bind_session(7, "session-7")
    submission = coordinator.submit_nowait(
        7,
        "session-7",
        {
            "jsonrpc": "2.0",
            "id": "pending-delete",
            "method": "tools/call",
            "params": {
                "name": "notes.delete",
                "arguments": {"note_ids": [note.id]},
            },
        },
    )
    assert submission.accepted
    for _ in range(100):
        if responses:
            break
        await asyncio.sleep(0.01)
    assert len(responses) == 1
    content = json.loads(responses[0]["result"]["content"][0]["text"])
    assert content["status"] == "requires_confirmation"
    assert executor.pending_confirmation_count == 1

    await coordinator.close_generation(7, "disconnect")
    assert executor.pending_confirmation_count == 0
    assert coordinator.worker_alive is False
    assert coordinator.request_queue_size == 0
    assert coordinator.inflight_request_count == 0
    assert coordinator.response_future_count == 0
