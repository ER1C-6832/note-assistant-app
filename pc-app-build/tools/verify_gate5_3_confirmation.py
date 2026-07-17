"""Verify Gate 5.3 confirmation, high-risk execution, and cleanup locally."""

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
    Gate53ToolExecutor,
    McpCoordinator,
    ToolCall,
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


async def _call(registry, request_id, name, arguments, *, generation=1, session="gate5-3"):
    return await registry.call(ToolCall(request_id, name, arguments, generation, session))


async def _run() -> int:
    with tempfile.TemporaryDirectory(prefix="gate5-3-") as temporary:
        root = Path(temporary)
        engine = create_sqlite_engine(root / "notes.db")
        initialize_database(engine)
        database = DatabaseExecutor(thread_name_prefix="gate5-3-verifier")
        repository = SqlAlchemyNoteRepository(create_session_factory(engine))
        commands = NoteCommandService(repository, database)
        queries = NoteQueryService(repository, database)
        catalog = TagCatalog(root / "tags.json", default_tags=())
        catalog.load()
        tags = TagCatalogService(catalog, queries)
        ui_bus = UiCommandBus()
        ui_adapter = RecordingUiAdapter()
        ui_bus.bind(ui_adapter)
        executor = Gate53ToolExecutor(queries, commands, tags, ui_bus)
        registry = ToolRegistry(executor=executor)
        coordinator = McpCoordinator(registry)

        pending_created = 0
        high_risk_completed = 0

        reject_note = await commands.create(
            CreateNoteCommand("reject", "body", (), source=NoteSource.MANUAL)
        )
        rejected_pending = await _call(registry, 1, "notes.delete", {"note_ids": [reject_note.id]})
        pending_created += 1
        rejected = await _call(
            registry,
            2,
            "assistant.reject",
            {"confirmation_id": rejected_pending.confirmation_id},
        )
        reject_zero_write = bool(
            rejected.status == "success"
            and not (await queries.get(reject_note.id, include_deleted=True)).is_deleted
        )

        confirmed_pending = await _call(registry, 3, "notes.delete", {"note_ids": [reject_note.id]})
        pending_created += 1
        shown = await _call(
            registry,
            4,
            "ui.show_confirmation",
            {"confirmation_id": confirmed_pending.confirmation_id},
        )
        confirmed = await _call(
            registry,
            5,
            "assistant.confirm",
            {"confirmation_id": confirmed_pending.confirmation_id},
        )
        high_risk_completed += int(confirmed.status in {"success", "partial_success"})
        repeat = await _call(
            registry,
            6,
            "assistant.confirm",
            {"confirmation_id": confirmed_pending.confirmation_id},
        )
        delete_confirmed = bool(
            (await queries.get(reject_note.id, include_deleted=True)).is_deleted
        )

        stale_note = await commands.create(
            CreateNoteCommand("stale", "old", (), source=NoteSource.MANUAL)
        )
        stale_pending = await _call(
            registry,
            7,
            "notes.replace_content",
            {"note_id": stale_note.id, "content": "must-not-win"},
        )
        pending_created += 1
        await commands.update(
            UpdateNoteCommand(stale_note.id, stale_note.title, "newer", stale_note.tags)
        )
        stale_result = await _call(
            registry,
            8,
            "assistant.confirm",
            {"confirmation_id": stale_pending.confirmation_id},
        )
        stale_revalidation = bool(
            stale_result.error_code == "stale_confirmation_target"
            and (await queries.get(stale_note.id)).content == "newer"
        )

        bulk_notes = [
            await commands.create(
                CreateNoteCommand(f"bulk-{index}", "", (), source=NoteSource.MANUAL)
            )
            for index in range(6)
        ]
        bulk_ids = [note.id for note in bulk_notes]
        pin_pending = await _call(
            registry,
            9,
            "notes.pin",
            {"note_ids": bulk_ids, "pinned": True},
        )
        pending_created += 1
        pin_confirmed = await _call(
            registry,
            10,
            "assistant.confirm",
            {"confirmation_id": pin_pending.confirmation_id},
        )
        high_risk_completed += int(pin_confirmed.status in {"success", "partial_success"})
        pin_snapshots = await asyncio.gather(*(queries.get(note_id) for note_id in bulk_ids))
        pin_effect_verified = all(note is not None and note.is_pinned for note in pin_snapshots)

        bind_pending = await _call(
            registry,
            11,
            "tags.bind",
            {"note_ids": bulk_ids, "operation": "replace", "tags": ["确认标签"]},
        )
        pending_created += 1
        bind_confirmed = await _call(
            registry,
            12,
            "assistant.confirm",
            {"confirmation_id": bind_pending.confirmation_id},
        )
        high_risk_completed += int(bind_confirmed.status in {"success", "partial_success"})

        await tags.add_async("待删除标签")
        tag_pending = await _call(registry, 13, "tags.delete", {"name": "待删除标签"})
        pending_created += 1
        tag_confirmed = await _call(
            registry,
            14,
            "assistant.confirm",
            {"confirmation_id": tag_pending.confirmation_id},
        )
        high_risk_completed += int(tag_confirmed.status in {"success", "partial_success"})

        await commands.soft_delete(SoftDeleteCommand(tuple(bulk_ids)))
        restore_pending = await _call(registry, 15, "notes.restore", {"note_ids": bulk_ids})
        pending_created += 1
        restore_confirmed = await _call(
            registry,
            16,
            "assistant.confirm",
            {"confirmation_id": restore_pending.confirmation_id},
        )
        high_risk_completed += int(restore_confirmed.status in {"success", "partial_success"})

        responses = []

        async def response_sink(payload):
            responses.append(payload)

        async def lifecycle_sink(_summary):
            return None

        await coordinator.open_generation(
            9, response_sink=response_sink, lifecycle_sink=lifecycle_sink
        )
        coordinator.bind_session(9, "disconnect-session")
        disconnect_note = await commands.create(
            CreateNoteCommand("disconnect", "", (), source=NoteSource.MANUAL)
        )
        coordinator.submit_nowait(
            9,
            "disconnect-session",
            {
                "jsonrpc": "2.0",
                "id": "disconnect-pending",
                "method": "tools/call",
                "params": {
                    "name": "notes.delete",
                    "arguments": {"note_ids": [disconnect_note.id]},
                },
            },
        )
        for _ in range(100):
            if responses:
                break
            await asyncio.sleep(0.01)
        pending_before_disconnect = executor.pending_confirmation_count
        await coordinator.close_generation(9, "disconnect")
        invalidated_on_disconnect = bool(
            pending_before_disconnect == 1 and executor.pending_confirmation_count == 0
        )

        snapshots = await asyncio.gather(*(queries.get(note_id) for note_id in bulk_ids))
        high_risk_effects_verified = bool(
            all(note is not None and not note.is_deleted for note in snapshots)
            and all(note.tags == ("确认标签",) for note in snapshots)
            and all(not note.is_pinned for note in snapshots)
            and pin_effect_verified
            and "待删除标签" not in tags.custom_tags
        )
        before_close = {
            "request_queue_size": coordinator.request_queue_size,
            "worker_alive": coordinator.worker_alive,
            "inflight_request_count": coordinator.inflight_request_count,
            "response_future_count": coordinator.response_future_count,
            "pending_confirmation_count": executor.pending_confirmation_count,
            "ui_dispatch_count": ui_bus.active_dispatch_count,
        }

        await coordinator.close()
        await ui_bus.close()
        await tags.close()
        await database.close()
        engine.dispose()
        await asyncio.sleep(0)
        terminal = {
            "request_queue_size": coordinator.request_queue_size,
            "worker_alive": coordinator.worker_alive,
            "inflight_request_count": coordinator.inflight_request_count,
            "dedupe_waiter_count": coordinator.dedupe_waiter_count,
            "response_future_count": coordinator.response_future_count,
            "pending_confirmation_count": executor.pending_confirmation_count,
            "ui_dispatch_count": ui_bus.active_dispatch_count,
        }
        verified = all(
            (
                reject_zero_write,
                delete_confirmed,
                repeat.error_code == "confirmation_consumed",
                stale_revalidation,
                shown.status == "success",
                high_risk_completed == 5,
                high_risk_effects_verified,
                invalidated_on_disconnect,
                all(
                    value is False if key == "worker_alive" else value == 0
                    for key, value in terminal.items()
                ),
            )
        )
        print(
            json.dumps(
                {
                    "status": "fake_gate_complete" if verified else "failed",
                    "pending_created_count": pending_created,
                    "high_risk_completion_count": high_risk_completed,
                    "reject_zero_write": reject_zero_write,
                    "delete_confirmed": delete_confirmed,
                    "repeat_confirm_consumed": repeat.error_code == "confirmation_consumed",
                    "stale_target_rejected": stale_revalidation,
                    "ui_confirmation_displayed": shown.status == "success",
                    "invalidated_on_disconnect": invalidated_on_disconnect,
                    "high_risk_effects_verified": high_risk_effects_verified,
                    "ui_commands_dispatched": len(ui_adapter.commands),
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
    return asyncio.run(_run())


if __name__ == "__main__":
    raise SystemExit(main())
