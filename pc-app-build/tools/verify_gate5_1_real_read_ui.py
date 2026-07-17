"""Verify real Gate 5.1 read tools and typed UI dispatch over Xiaozhi MCP."""

from __future__ import annotations

import asyncio
import json
import os
import re
import sys
import time
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1] / "apps" / "notes-pyside"
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

from app.app_paths import AppPaths  # noqa: E402
from app.assistant import (  # noqa: E402
    AssistantController,
    DeviceIdentityManager,
    DeviceIdentityStore,
    McpCoordinator,
    McpScriptedFakeTransport,
    PersistedConnectionConfigProvider,
    RealWebSocketTransport,
    RuntimeConfigStore,
    RuntimeTransportRouter,
    ToolRegistry,
)
from app.assistant.identity import LegacyPyXiaozhiIdentitySource  # noqa: E402
from app.assistant.mcp import (  # noqa: E402
    Gate51ToolExecutor,
    UiCommandBus,
    UiDispatchResult,
)
from app.notes import (  # noqa: E402
    DatabaseExecutor,
    NoteQueryService,
    SqlAlchemyNoteRepository,
    create_session_factory,
    create_sqlite_engine,
    initialize_database,
)

CONNECT_TIMEOUT_SECONDS = 20.0
TOOL_TIMEOUT_SECONDS = 60.0


class MonotonicClock:
    def now_ns(self) -> int:
        return time.perf_counter_ns()


class RecordingUiAdapter:
    def __init__(self) -> None:
        self.commands = []

    async def dispatch(self, command):
        self.commands.append(command.kind.value)
        return UiDispatchResult(True, "桌面 UI 已切换")


async def _wait_for_tool(coordinator, tool_name: str, start_index: int) -> bool:
    deadline = time.perf_counter() + TOOL_TIMEOUT_SECONDS
    while time.perf_counter() < deadline:
        for summary in coordinator.lifecycle_history[start_index:]:
            if summary.tool_name == tool_name and summary.status == "success":
                return True
        await asyncio.sleep(0.05)
    return False


async def _run_prompt(controller, coordinator, prompt: str, tool_name: str) -> bool:
    history_index = len(coordinator.lifecycle_history)
    await controller.send_text(prompt)
    turn_token = controller.state.conversation.active_text_turn_token
    if turn_token is None:
        return False
    tool_task = asyncio.create_task(
        _wait_for_tool(coordinator, tool_name, history_index),
        name=f"gate5-1-wait-{tool_name}",
    )
    try:
        await controller.wait_for_state(
            lambda state: state.error is not None
            or state.conversation.last_completed_text_turn_token >= turn_token,
            timeout_seconds=TOOL_TIMEOUT_SECONDS,
        )
        return await tool_task
    finally:
        if not tool_task.done():
            tool_task.cancel()
            await asyncio.gather(tool_task, return_exceptions=True)


def _optional_env(name: str) -> str | None:
    value = os.environ.get(name, "").strip()
    return value or None


def _mask(value: str | None) -> str | None:
    if not value:
        return None
    if len(value) <= 8:
        return "*" * len(value)
    return f"{value[:4]}***{value[-4:]}"


def _environment_blocked(message: str) -> bool:
    lowered = message.lower()
    return any(
        marker in lowered
        for marker in (
            "token 未配置",
            "websocket url 未配置",
            "activation",
            "network",
            "dns",
            "connection refused",
            "service unavailable",
            "ssl",
            "urlopen error",
        )
    )


def _safe_query(title: str) -> str:
    words = re.findall(r"[\w\u4e00-\u9fff]+", title)
    return (words[0] if words else "便签")[:12]


async def _run() -> int:
    paths = AppPaths.resolve(root_override=_optional_env("NOTE_ASSISTANT_DATA_ROOT"))
    paths.ensure_directories()
    engine = create_sqlite_engine(paths.notes_db)
    initialize_database(engine)
    database_executor = DatabaseExecutor(thread_name_prefix="gate5-1-real-db")
    queries = NoteQueryService(
        SqlAlchemyNoteRepository(create_session_factory(engine)), database_executor
    )
    active_notes = await queries.list_recent(1)
    if not active_notes:
        print(
            json.dumps(
                {
                    "status": "real_gate_blocked",
                    "failure_stage": "seed_data",
                    "message": "真实数据库没有活动便签，无法执行 search/get/open_note 验收",
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        await database_executor.close()
        engine.dispose()
        return 2

    target = active_notes[0]
    query = _safe_query(target.title)
    ui_bus = UiCommandBus()
    ui_adapter = RecordingUiAdapter()
    ui_bus.bind(ui_adapter)
    registry = ToolRegistry(executor=Gate51ToolExecutor(queries, ui_bus))
    coordinator = McpCoordinator(registry)

    config_store = RuntimeConfigStore(paths.assistant_runtime_config)
    identity_manager = DeviceIdentityManager(
        DeviceIdentityStore(config_store),
        legacy_identity=LegacyPyXiaozhiIdentitySource.from_local_app_data().load,
    )
    identity = await identity_manager.ensure_identity()
    clock = MonotonicClock()
    provider = PersistedConnectionConfigProvider(
        config_store=config_store,
        identity_manager=identity_manager,
    )
    real_transport = RealWebSocketTransport(
        config_provider=provider,
        clock=clock,
        mcp_coordinator=coordinator,
    )
    transport = RuntimeTransportRouter(
        fake_transport=McpScriptedFakeTransport(mcp_coordinator=coordinator),
        real_transport=real_transport,
    )
    controller = AssistantController(
        transport=transport,
        clock=clock,
        identity_manager=identity_manager,
    )

    observed = {}
    failure_stage = "connect"
    try:
        await controller.enable_assistant()
        await controller.ensure_device_identity()
        await controller.connect()
        connected = await controller.wait_for_state(
            lambda state: state.is_connected or state.error is not None,
            timeout_seconds=CONNECT_TIMEOUT_SECONDS,
        )
        if not connected.is_connected:
            message = connected.error.message if connected.error else "真实 WebSocket 未连接"
            print(
                json.dumps(
                    {
                        "status": (
                            "real_gate_blocked" if _environment_blocked(message) else "failed"
                        ),
                        "failure_stage": failure_stage,
                        "message": message[:240],
                    },
                    ensure_ascii=False,
                    indent=2,
                    sort_keys=True,
                )
            )
            return 2 if _environment_blocked(message) else 1

        scenarios = (
            (
                "notes.list_recent",
                "请调用 notes.list_recent 工具读取最近三条便签，然后简短回复完成。",
            ),
            (
                "notes.search",
                f"请调用 notes.search 工具搜索关键词“{query}”，limit 为 5，然后简短回复完成。",
            ),
            (
                "notes.get",
                f"请调用 notes.get 工具读取 note_id={target.id}，然后简短回复完成。",
            ),
            (
                "ui.open_note",
                f"请调用 ui.open_note 工具打开 note_id={target.id}，然后简短回复完成。",
            ),
            (
                "ui.show_note_list",
                "请调用 ui.show_note_list 工具切换到全部便签列表，然后简短回复完成。",
            ),
        )
        for tool_name, prompt in scenarios:
            failure_stage = tool_name
            observed[tool_name] = await _run_prompt(controller, coordinator, prompt, tool_name)
            if not observed[tool_name]:
                break

        verified_before_shutdown = all(observed.values()) and {
            "open_note",
            "show_note_list",
        }.issubset(set(ui_adapter.commands))
        before_disconnect = {
            "request_queue_size": coordinator.request_queue_size,
            "worker_alive": coordinator.worker_alive,
            "inflight_request_count": coordinator.inflight_request_count,
            "response_future_count": coordinator.response_future_count,
            "ui_dispatch_count": ui_bus.active_dispatch_count,
        }
        await controller.disconnect("gate5_1_real_read_ui_complete")
        await controller.shutdown()
        await ui_bus.close()
        await database_executor.close()
        engine.dispose()
        await asyncio.sleep(0)
        pending = sorted(
            task.get_name()
            for task in asyncio.all_tasks()
            if task is not asyncio.current_task()
            and not task.done()
            and task.get_name().startswith("assistant-")
        )
        terminal = {
            "request_queue_size": coordinator.request_queue_size,
            "worker_alive": coordinator.worker_alive,
            "inflight_request_count": coordinator.inflight_request_count,
            "dedupe_waiter_count": coordinator.dedupe_waiter_count,
            "response_future_count": coordinator.response_future_count,
            "ui_dispatch_count": ui_bus.active_dispatch_count,
        }
        verified = (
            verified_before_shutdown
            and pending == []
            and all(
                value is False if key == "worker_alive" else value == 0
                for key, value in terminal.items()
            )
        )
        print(
            json.dumps(
                {
                    "status": "real_gate_complete" if verified else "failed",
                    "failure_stage": None if verified else failure_stage,
                    "observed_tools": observed,
                    "ui_commands": ui_adapter.commands,
                    "target_note_id": target.id,
                    "connection_generation": connected.connection.connection_generation,
                    "session_id_masked": _mask(connected.connection.session_id),
                    "device_id_masked": identity.device_id_masked,
                    "client_id_masked": identity.client_id_masked,
                    "websocket_url": connected.connection.websocket_url_public,
                    "before_disconnect": before_disconnect,
                    "terminal": terminal,
                    "pending_assistant_tasks": pending,
                    "payload_persisted": False,
                    "secrets_redacted": True,
                },
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
        )
        return 0 if verified else 1
    finally:
        if not controller.closed:
            await controller.shutdown()
        await ui_bus.close()
        if not database_executor.is_closed:
            await database_executor.close()
        engine.dispose()


def main() -> int:
    try:
        return asyncio.run(_run())
    except TimeoutError:
        print(
            json.dumps(
                {
                    "status": "failed",
                    "failure_stage": "timeout",
                    "message": "等待 Gate 5.1 Real 工具调用超时",
                },
                ensure_ascii=False,
                indent=2,
            ),
            file=sys.stderr,
        )
        return 1
    except Exception as exc:
        message = str(exc) or type(exc).__name__
        blocked = _environment_blocked(message)
        print(
            json.dumps(
                {
                    "status": "real_gate_blocked" if blocked else "failed",
                    "error_type": type(exc).__name__,
                    "message": message[:240],
                },
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            ),
            file=sys.stderr,
        )
        return 2 if blocked else 1


if __name__ == "__main__":
    raise SystemExit(main())
