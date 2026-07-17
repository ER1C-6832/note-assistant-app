"""Run the canonical Gate 5.1 Fake read/resolve and UI-navigation acceptance."""

from __future__ import annotations

import asyncio
import json
import sys
import tempfile
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1] / "apps" / "notes-pyside"
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

from app.assistant import AssistantRuntimeMode  # noqa: E402
from app.assistant.mcp import (  # noqa: E402
    Gate51ToolExecutor,
    McpCoordinator,
    McpScriptedFakeTransport,
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
    SetPinnedCommand,
    SoftDeleteCommand,
    SqlAlchemyNoteRepository,
    create_session_factory,
    create_sqlite_engine,
    initialize_database,
)


class RecordingUiAdapter:
    def __init__(self) -> None:
        self.commands = []
        self.closed = False

    async def dispatch(self, command):
        self.commands.append(command)
        return UiDispatchResult(True, "桌面 UI 已切换")

    async def close(self) -> None:
        self.closed = True


async def _run() -> int:
    with tempfile.TemporaryDirectory(prefix="gate5-1-") as temp_dir:
        engine = create_sqlite_engine(Path(temp_dir) / "notes.db")
        initialize_database(engine)
        session_factory = create_session_factory(engine)
        repository = SqlAlchemyNoteRepository(session_factory)
        database_executor = DatabaseExecutor(thread_name_prefix="gate5-1-db")
        commands = NoteCommandService(repository, database_executor)
        queries = NoteQueryService(repository, database_executor)

        first = await commands.create(
            CreateNoteCommand(
                title="Gate51 北京行程",
                content="周末去故宫",
                tags=("旅行",),
                is_pinned=False,
                source=NoteSource.VOICE_PC,
            )
        )
        todo = await commands.create(
            CreateNoteCommand(
                title="Gate51 采购清单",
                content="牛奶和咖啡",
                tags=("待办", "生活"),
                source=NoteSource.VOICE_PC,
            )
        )
        deleted = await commands.create(
            CreateNoteCommand(
                title="Gate51 已删除样本",
                content="只用于读取验收",
                tags=("测试",),
                source=NoteSource.VOICE_PC,
            )
        )
        await commands.set_pinned(SetPinnedCommand((first.id,), True))
        await commands.soft_delete(SoftDeleteCommand((deleted.id,)))

        ui_bus = UiCommandBus()
        ui_adapter = RecordingUiAdapter()
        ui_bus.bind(ui_adapter)
        registry = ToolRegistry(executor=Gate51ToolExecutor(queries, ui_bus))
        coordinator = McpCoordinator(registry)
        transport = McpScriptedFakeTransport(mcp_coordinator=coordinator)
        events = []

        async def event_sink(event) -> None:
            events.append(type(event).__name__)

        await transport.open(1, AssistantRuntimeMode.FAKE, event_sink)
        requests = (
            (1, "notes.resolve", {"exact_title": first.title}),
            (2, "notes.search", {"query": "Gate51", "limit": 10}),
            (3, "notes.list_recent", {"limit": 5}),
            (4, "notes.get", {"note_id": todo.id}),
            (5, "notes.list_by_tag", {"tag": "旅行"}),
            (6, "notes.list_deleted", {"limit": 20}),
            (7, "notes.list_todos", {"limit": 20}),
            (8, "notes.list_pinned", {"limit": 20}),
            (9, "ui.open_note", {"note_id": first.id}),
            (10, "ui.show_search", {"query": "Gate51"}),
            (11, "ui.show_note_list", {}),
            (12, "ui.show_tag", {"tag": "旅行"}),
            (13, "ui.show_trash", {}),
            (14, "ui.show_pinned", {}),
            (15, "ui.show_todos", {}),
            (16, "ui.show_confirmation", {"confirmation_id": "not-created-yet"}),
        )

        for request_id, name, arguments in requests:
            accepted = await transport.receive_mcp(
                {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "method": "tools/call",
                    "params": {"name": name, "arguments": arguments},
                }
            )
            if not accepted:
                raise RuntimeError(f"Fake MCP request was rejected: {name}")

        responses = await transport.wait_for_mcp_responses(len(requests), timeout_seconds=5.0)
        results = {}
        for response in responses:
            request_id = response.get("id")
            result = response.get("result")
            if not isinstance(result, dict):
                raise RuntimeError(f"missing tools/call result for request {request_id}")
            content = result.get("content")
            if not isinstance(content, list) or not content:
                raise RuntimeError(f"missing tool content for request {request_id}")
            tool_payload = json.loads(content[0]["text"])
            results[int(request_id)] = tool_payload

        read_statuses = [results[index]["status"] for index in range(1, 9)]
        ui_statuses = [results[index]["status"] for index in range(9, 16)]
        confirmation = results[16]
        active_after = await queries.list_all()
        deleted_after = await queries.list_deleted()
        before_close = {
            "request_queue_size": coordinator.request_queue_size,
            "worker_alive": coordinator.worker_alive,
            "inflight_request_count": coordinator.inflight_request_count,
            "dedupe_waiter_count": coordinator.dedupe_waiter_count,
            "response_future_count": coordinator.response_future_count,
            "ui_dispatch_count": ui_bus.active_dispatch_count,
        }
        verified = bool(
            all(status == "success" for status in read_statuses)
            and all(status == "success" for status in ui_statuses)
            and confirmation["status"] == "blocked"
            and confirmation.get("error_code") == "confirmation_not_ready"
            and len(ui_adapter.commands) == 7
            and {note.id for note in active_after} == {first.id, todo.id}
            and {note.id for note in deleted_after} == {deleted.id}
        )

        await transport.close(1, "gate5_1_fake_complete", event_sink)
        await ui_bus.close()
        await database_executor.close()
        engine.dispose()
        terminal = {
            "request_queue_size": coordinator.request_queue_size,
            "worker_alive": coordinator.worker_alive,
            "inflight_request_count": coordinator.inflight_request_count,
            "dedupe_entry_count": coordinator.dedupe_entry_count,
            "dedupe_waiter_count": coordinator.dedupe_waiter_count,
            "response_future_count": coordinator.response_future_count,
            "ui_dispatch_count": ui_bus.active_dispatch_count,
        }
        verified = verified and all(
            value is False if key == "worker_alive" else value == 0
            for key, value in terminal.items()
        )
        print(
            json.dumps(
                {
                    "status": "fake_gate_complete" if verified else "failed",
                    "read_tool_count": 8,
                    "ui_tool_success_count": 7,
                    "confirmation_display_status": confirmation["status"],
                    "resolved_note_id": results[1]["result"]["note_id"],
                    "todo_note_ids": results[7]["affected_note_ids"],
                    "deleted_note_ids": results[6]["affected_note_ids"],
                    "ui_commands_dispatched": len(ui_adapter.commands),
                    "protocol_observation_count": len(events),
                    "before_close": before_close,
                    "terminal": terminal,
                    "payload_persisted": False,
                    "secrets_redacted": True,
                },
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
        )
        return 0 if verified else 1


def main() -> int:
    try:
        return asyncio.run(_run())
    except Exception as exc:
        print(
            json.dumps(
                {
                    "status": "failed",
                    "error_type": type(exc).__name__,
                    "message": str(exc)[:240],
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
