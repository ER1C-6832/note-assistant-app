from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest

from app.assistant.mcp import (
    Gate51ToolExecutor,
    ToolCall,
    ToolRegistry,
    UiCommandBus,
    UiDispatchResult,
)
from app.notes import Note, NoteSource


class FakeQueries:
    def __init__(self, notes: tuple[Note, ...]) -> None:
        self.notes = notes

    async def get(self, note_id: int, include_deleted: bool = False):
        for note in self.notes:
            if note.id == note_id and (include_deleted or not note.is_deleted):
                return note
        return None

    async def list_recent(self, limit: int = 5):
        active = [note for note in self.notes if not note.is_deleted]
        return tuple(
            sorted(active, key=lambda note: (note.updated_at, note.id), reverse=True)[:limit]
        )

    async def list_pinned_bounded(self, limit: int = 20):
        return tuple(note for note in self.notes if note.is_pinned and not note.is_deleted)[:limit]

    async def list_deleted_bounded(self, limit: int = 20):
        return tuple(note for note in self.notes if note.is_deleted)[:limit]

    async def list_by_tag_bounded(self, tag: str, limit: int = 20):
        return tuple(note for note in self.notes if tag in note.tags and not note.is_deleted)[
            :limit
        ]

    async def search_filtered(self, query, *, tags=(), scope="active", limit=10):
        query = query.casefold()
        result = []
        for note in self.notes:
            if scope == "active" and note.is_deleted:
                continue
            if scope == "deleted" and not note.is_deleted:
                continue
            if not all(tag in note.tags for tag in tags):
                continue
            if query not in " ".join((note.title, note.content, *note.tags)).casefold():
                continue
            result.append(note)
        return tuple(result[:limit])

    async def list_scope_bounded(self, scope: str, limit: int = 100):
        result = [
            note
            for note in self.notes
            if scope == "all"
            or (scope == "active" and not note.is_deleted)
            or (scope == "deleted" and note.is_deleted)
        ]
        return tuple(result[:limit])


class RecordingUiAdapter:
    def __init__(self) -> None:
        self.commands = []

    async def dispatch(self, command):
        self.commands.append(command)
        return UiDispatchResult(True, "桌面 UI 已切换")


def _notes() -> tuple[Note, ...]:
    now = datetime.now(timezone.utc)
    return (
        Note(
            id=1,
            title="北京行程",
            content="周末去故宫",
            tags=("旅行",),
            is_pinned=True,
            is_deleted=False,
            created_at=now - timedelta(days=3),
            updated_at=now - timedelta(days=2),
            source=NoteSource.MANUAL,
        ),
        Note(
            id=2,
            title="采购清单",
            content="牛奶和咖啡",
            tags=("待办", "生活"),
            is_pinned=False,
            is_deleted=False,
            created_at=now - timedelta(days=2),
            updated_at=now,
            source=NoteSource.VOICE_PC,
        ),
        Note(
            id=3,
            title="北京会议",
            content="已经取消",
            tags=("工作",),
            is_pinned=False,
            is_deleted=True,
            created_at=now - timedelta(days=1),
            updated_at=now - timedelta(hours=1),
            source=NoteSource.MANUAL,
        ),
    )


async def _call(registry: ToolRegistry, request_id: int, name: str, arguments: dict):
    return await registry.call(ToolCall(request_id, name, arguments))


@pytest.mark.asyncio
async def test_eight_read_tools_use_current_note_data_and_todo_semantics() -> None:
    bus = UiCommandBus()
    registry = ToolRegistry(executor=Gate51ToolExecutor(FakeQueries(_notes()), bus))

    recent = await _call(registry, 1, "notes.list_recent", {"limit": 2})
    assert recent.status == "success"
    assert recent.result["notes"][0]["note_id"] == 2

    search = await _call(registry, 2, "notes.search", {"query": "北京", "limit": 10})
    assert [item["note_id"] for item in search.result["notes"]] == [1]

    get = await _call(registry, 3, "notes.get", {"note_id": 2})
    assert get.result["note"]["source"] == "voice_pc"

    tagged = await _call(registry, 4, "notes.list_by_tag", {"tag": "旅行"})
    assert tagged.affected_note_ids == (1,)

    deleted = await _call(registry, 5, "notes.list_deleted", {})
    assert deleted.affected_note_ids == (3,)

    todos = await _call(registry, 6, "notes.list_todos", {})
    assert todos.affected_note_ids == (2,)

    pinned = await _call(registry, 7, "notes.list_pinned", {})
    assert pinned.affected_note_ids == (1,)

    resolved = await _call(registry, 8, "notes.resolve", {"query": "编号 2"})
    assert not (
        resolved.status == "success"
        and resolved.result.get("note_id") == 2
    )


@pytest.mark.asyncio
async def test_bare_numeric_query_prefers_title_while_labelled_number_uses_id() -> None:
    now = datetime.now(timezone.utc)
    numeric_title = Note(
        id=1,
        title="119",
        content="按标题定位",
        tags=(),
        is_pinned=False,
        is_deleted=False,
        created_at=now,
        updated_at=now,
        source=NoteSource.MANUAL,
    )
    numeric_id = Note(
        id=119,
        title="数据库编号目标",
        content="按明确编号定位",
        tags=(),
        is_pinned=False,
        is_deleted=False,
        created_at=now,
        updated_at=now,
        source=NoteSource.MANUAL,
    )
    registry = ToolRegistry(
        executor=Gate51ToolExecutor(FakeQueries((numeric_title, numeric_id)), UiCommandBus())
    )

    by_title = await _call(registry, 20, "notes.resolve", {"query": "119"})
    by_id = await _call(registry, 21, "notes.resolve", {"query": "编号 119"})

    assert by_title.result["resolution_status"] == "resolved"
    assert by_title.result["note_id"] == numeric_title.id
    assert not (
        by_id.status == "success"
        and by_id.result.get("note_id") == numeric_id.id
    )


@pytest.mark.asyncio
async def test_resolve_ambiguous_never_selects_first_candidate() -> None:
    registry = ToolRegistry(executor=Gate51ToolExecutor(FakeQueries(_notes()), UiCommandBus()))
    result = await _call(registry, 1, "notes.resolve", {"query": "北京", "scope": "all"})

    assert result.status == "success"
    assert result.result["resolution_status"] == "ambiguous"
    assert result.result["note_id"] is None
    assert {candidate["note_id"] for candidate in result.result["candidates"]} == {1, 3}


@pytest.mark.asyncio
async def test_get_bounds_large_utf8_content_under_coordinator_budget() -> None:
    note = _notes()[0]
    huge = Note(
        id=note.id,
        title=note.title,
        content="汉" * 20_000,
        tags=note.tags,
        is_pinned=note.is_pinned,
        is_deleted=note.is_deleted,
        created_at=note.created_at,
        updated_at=note.updated_at,
        source=note.source,
    )
    registry = ToolRegistry(executor=Gate51ToolExecutor(FakeQueries((huge,)), UiCommandBus()))

    result = await _call(registry, 1, "notes.get", {"note_id": 1})
    encoded = json.dumps(result.public_dict(), ensure_ascii=False).encode("utf-8")
    assert result.result["note"]["content_truncated"] is True
    assert len(encoded) < 32 * 1024


@pytest.mark.asyncio
async def test_seven_ui_tools_dispatch_and_confirmation_remains_blocked() -> None:
    bus = UiCommandBus()
    adapter = RecordingUiAdapter()
    bus.bind(adapter)
    registry = ToolRegistry(executor=Gate51ToolExecutor(FakeQueries(_notes()), bus))

    calls = (
        ("ui.open_note", {"note_id": 1}),
        ("ui.show_search", {"query": "北京"}),
        ("ui.show_note_list", {}),
        ("ui.show_tag", {"tag": "旅行"}),
        ("ui.show_trash", {}),
        ("ui.show_pinned", {}),
        ("ui.show_todos", {}),
    )
    for index, (name, arguments) in enumerate(calls, start=1):
        result = await _call(registry, index, name, arguments)
        assert result.status == "success"

    confirmation = await _call(
        registry, 20, "ui.show_confirmation", {"confirmation_id": "pending-1"}
    )
    assert confirmation.status == "blocked"
    assert confirmation.error_code == "confirmation_not_ready"
    assert len(adapter.commands) == 7


@pytest.mark.asyncio
async def test_ui_open_deleted_and_unavailable_are_fail_closed() -> None:
    unavailable = ToolRegistry(executor=Gate51ToolExecutor(FakeQueries(_notes()), UiCommandBus()))
    result = await _call(unavailable, 1, "ui.show_note_list", {})
    assert result.status == "blocked"
    assert result.error_code == "ui_unavailable"

    bus = UiCommandBus()
    bus.bind(RecordingUiAdapter())
    registry = ToolRegistry(executor=Gate51ToolExecutor(FakeQueries(_notes()), bus))
    deleted = await _call(registry, 2, "ui.open_note", {"note_id": 3})
    assert deleted.status == "blocked"
    assert deleted.error_code == "note_deleted"


@pytest.mark.asyncio
async def test_mutation_handlers_stay_gate_not_ready_in_5_1() -> None:
    registry = ToolRegistry(executor=Gate51ToolExecutor(FakeQueries(_notes()), UiCommandBus()))
    result = await _call(registry, 1, "notes.create", {"title": "禁止写入"})
    assert result.status == "blocked"
    assert result.error_code == "gate_not_ready"
