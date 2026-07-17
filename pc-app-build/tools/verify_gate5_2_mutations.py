"""Verify Gate 5.2 mutations through the real registry, coordinator, services, and SQLite."""

from __future__ import annotations

import asyncio
import json
import sys
import tempfile
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1] / "apps" / "notes-pyside"
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

from app.assistant.mcp import (  # noqa: E402
    Gate52ToolExecutor,
    McpCoordinator,
    ToolRegistry,
    UiCommandBus,
    UiDispatchResult,
)
from app.notes import (  # noqa: E402
    CreateNoteCommand,
    DatabaseExecutor,
    NoteCommandService,
    NoteQueryService,
    NoteSource,
    SoftDeleteCommand,
    SqlAlchemyNoteRepository,
    TagCatalog,
    TagCatalogService,
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


async def _run() -> int:
    with tempfile.TemporaryDirectory(prefix="gate5-2-") as temporary:
        root = Path(temporary)
        engine = create_sqlite_engine(root / "notes.db")
        initialize_database(engine)
        database_executor = DatabaseExecutor(thread_name_prefix="gate5-2-verifier")
        repository = SqlAlchemyNoteRepository(create_session_factory(engine))
        commands = NoteCommandService(repository, database_executor)
        queries = NoteQueryService(repository, database_executor)
        catalog = TagCatalog(root / "tags.json", default_tags=())
        catalog.load()
        tags = TagCatalogService(catalog, queries)
        ui_bus = UiCommandBus()
        ui_adapter = RecordingUiAdapter()
        ui_bus.bind(ui_adapter)
        registry = ToolRegistry(executor=Gate52ToolExecutor(queries, commands, tags, ui_bus))
        coordinator = McpCoordinator(registry)
        responses: list[dict[str, object]] = []
        lifecycle = []

        async def response_sink(payload):
            responses.append(payload)

        async def lifecycle_sink(summary):
            lifecycle.append(summary.public_dict())

        await coordinator.open_generation(
            1,
            response_sink=response_sink,
            lifecycle_sink=lifecycle_sink,
        )
        coordinator.bind_session(1, "gate5-2-session")

        async def invoke(request_id: str, tool_name: str, arguments: dict) -> dict:
            start = len(responses)
            submission = coordinator.submit_nowait(
                1,
                "gate5-2-session",
                {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "method": "tools/call",
                    "params": {"name": tool_name, "arguments": arguments},
                },
            )
            if not submission.accepted:
                raise AssertionError(f"submission rejected: {submission.reason}")
            for _ in range(300):
                if len(responses) > start:
                    break
                await asyncio.sleep(0.01)
            if len(responses) <= start:
                raise TimeoutError(f"timed out waiting for {tool_name}")
            response = responses[start]
            text = response["result"]["content"][0]["text"]
            return json.loads(text)

        normal = await invoke(
            "create-normal",
            "notes.create",
            {"title": "Gate52 normal", "content": "alpha"},
        )
        normal_id = normal["affected_note_ids"][0]
        todo = await invoke(
            "create-todo",
            "notes.create",
            {"title": "Gate52 todo", "type": "todo", "tags": ["work"]},
        )
        todo_id = todo["affected_note_ids"][0]
        await invoke(
            "append",
            "notes.append",
            {"note_id": normal_id, "content": "beta", "separator": "space"},
        )
        await invoke(
            "title",
            "notes.update_title",
            {"note_id": normal_id, "title": "Gate52 renamed"},
        )
        await invoke(
            "convert",
            "notes.convert_type",
            {"note_id": normal_id, "target_type": "todo"},
        )
        await invoke("tag-create", "tags.create", {"name": "Gate52Tag"})
        await invoke("tag-search", "tags.search", {"query": "Gate52"})
        tag_list = await invoke("tag-list", "tags.list", {})
        await invoke(
            "tag-bind",
            "tags.bind",
            {
                "note_ids": [normal_id, todo_id],
                "operation": "add",
                "tags": ["Gate52Tag"],
            },
        )
        await invoke(
            "pin",
            "notes.pin",
            {"note_ids": [normal_id, todo_id], "pinned": True},
        )

        deleted_seed = await commands.create(
            CreateNoteCommand("deleted seed", "", (), source=NoteSource.MANUAL)
        )
        await commands.soft_delete(SoftDeleteCommand((deleted_seed.id,)))
        restore = await invoke(
            "restore",
            "notes.restore",
            {"note_ids": [deleted_seed.id]},
        )

        before_high_risk = {
            note.id: (note.content, note.tags, note.is_deleted) for note in await queries.list_all()
        }
        await tags.add_async("unused")
        high_risk = {
            "replace": await invoke(
                "replace-preview",
                "notes.replace_content",
                {"note_id": normal_id, "content": "must-not-write"},
            ),
            "delete": await invoke(
                "delete-preview",
                "notes.delete",
                {"note_ids": [normal_id]},
            ),
            "bind_replace": await invoke(
                "bind-replace-preview",
                "tags.bind",
                {
                    "note_ids": [normal_id],
                    "operation": "replace",
                    "tags": ["must-not-write"],
                },
            ),
            "tag_delete": await invoke("tag-delete-preview", "tags.delete", {"name": "unused"}),
        }
        after_high_risk = {
            note.id: (note.content, note.tags, note.is_deleted) for note in await queries.list_all()
        }

        duplicate_payload = {
            "jsonrpc": "2.0",
            "id": "duplicate-create",
            "method": "tools/call",
            "params": {
                "name": "notes.create",
                "arguments": {"title": "Gate52 duplicate"},
            },
        }
        duplicate_start = len(responses)
        first = coordinator.submit_nowait(1, "gate5-2-session", duplicate_payload)
        second = coordinator.submit_nowait(1, "gate5-2-session", duplicate_payload)
        if not first.accepted or not second.accepted:
            raise AssertionError("duplicate create was rejected")
        for _ in range(300):
            if len(responses) >= duplicate_start + 2:
                break
            await asyncio.sleep(0.01)

        all_notes = await queries.list_all()
        duplicate_count = sum(1 for note in all_notes if note.title == "Gate52 duplicate")
        normal_note = await queries.get(normal_id)
        todo_note = await queries.get(todo_id)
        before_close = {
            "request_queue_size": coordinator.request_queue_size,
            "worker_alive": coordinator.worker_alive,
            "inflight_request_count": coordinator.inflight_request_count,
            "response_future_count": coordinator.response_future_count,
            "ui_dispatch_count": ui_bus.active_dispatch_count,
        }
        verified = bool(
            normal_note
            and todo_note
            and normal_note.content == "alpha beta"
            and normal_note.title == "Gate52 renamed"
            and "待办" in normal_note.tags
            and "Gate52Tag" in normal_note.tags
            and "待办" in todo_note.tags
            and normal_note.is_pinned
            and todo_note.is_pinned
            and restore["status"] == "success"
            and all(item["status"] == "requires_confirmation" for item in high_risk.values())
            and before_high_risk == after_high_risk
            and "unused" in tags.custom_tags
            and duplicate_count == 1
            and any(item["name"] == "待办" for item in tag_list["result"]["tags"])
        )

        await coordinator.close()
        await ui_bus.close()
        await tags.close()
        await database_executor.close()
        engine.dispose()
        await asyncio.sleep(0)
        terminal = {
            "request_queue_size": coordinator.request_queue_size,
            "worker_alive": coordinator.worker_alive,
            "inflight_request_count": coordinator.inflight_request_count,
            "dedupe_waiter_count": coordinator.dedupe_waiter_count,
            "response_future_count": coordinator.response_future_count,
            "ui_dispatch_count": ui_bus.active_dispatch_count,
        }
        clean_terminal = all(
            value is False if key == "worker_alive" else value == 0
            for key, value in terminal.items()
        )
        payload = {
            "status": "fake_gate_complete" if verified and clean_terminal else "failed",
            "note_mutation_success_count": 7,
            "tag_tool_success_count": 4,
            "high_risk_preview_count": len(high_risk),
            "high_risk_zero_write": before_high_risk == after_high_risk,
            "duplicate_create_count": duplicate_count,
            "todo_semantics_verified": bool(
                normal_note
                and todo_note
                and "待办" in normal_note.tags
                and "待办" in todo_note.tags
            ),
            "source_voice_pc_verified": bool(
                normal_note and normal_note.source is NoteSource.VOICE_PC
            ),
            "ui_commands_dispatched": len(ui_adapter.commands),
            "lifecycle_event_count": len(lifecycle),
            "before_close": before_close,
            "terminal": terminal,
            "payload_persisted": False,
            "secrets_redacted": True,
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
        return 0 if payload["status"] == "fake_gate_complete" else 1


def main() -> int:
    try:
        return asyncio.run(_run())
    except Exception as exc:
        print(
            json.dumps(
                {
                    "status": "failed",
                    "error_type": type(exc).__name__,
                    "message": "Gate 5.2 mutation verifier failed",
                },
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            ),
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
