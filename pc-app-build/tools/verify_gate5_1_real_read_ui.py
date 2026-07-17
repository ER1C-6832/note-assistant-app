"""Probe Gate 5.1 natural-language tool selection over the real Xiaozhi endpoint."""

from __future__ import annotations

import asyncio
import json
import os
import sys
import time
from dataclasses import dataclass
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
from gate5_1_acceptance import ToolProbeDecision, classify_tool_probe  # noqa: E402

CONNECT_TIMEOUT_SECONDS = 20.0
PROTOCOL_TIMEOUT_SECONDS = 15.0
TOOL_TIMEOUT_SECONDS = 45.0


class MonotonicClock:
    def now_ns(self) -> int:
        return time.perf_counter_ns()


class RecordingUiAdapter:
    def __init__(self) -> None:
        self.commands: list[str] = []

    async def dispatch(self, command):
        self.commands.append(command.kind.value)
        return UiDispatchResult(True, "桌面 UI 已切换")


@dataclass(frozen=True, slots=True)
class PromptOutcome:
    tool_status: str | None
    turn_completed: bool
    assistant_reply_present: bool


async def _wait_for_protocol_ready(coordinator: McpCoordinator) -> bool:
    deadline = time.perf_counter() + PROTOCOL_TIMEOUT_SECONDS
    while time.perf_counter() < deadline:
        methods = {
            summary.method
            for summary in coordinator.lifecycle_history
            if summary.status == "success"
        }
        if {"initialize", "tools/list"}.issubset(methods):
            return True
        await asyncio.sleep(0.05)
    return False


async def _wait_for_tool_status(
    coordinator: McpCoordinator,
    tool_name: str,
    start_index: int,
    timeout_seconds: float,
) -> str | None:
    deadline = time.perf_counter() + max(timeout_seconds, 0.01)
    while time.perf_counter() < deadline:
        for summary in coordinator.lifecycle_history[start_index:]:
            if summary.tool_name == tool_name:
                return summary.status
        await asyncio.sleep(0.05)
    return None


async def _run_prompt(
    controller: AssistantController,
    coordinator: McpCoordinator,
    prompt: str,
    tool_name: str,
) -> PromptOutcome:
    history_index = len(coordinator.lifecycle_history)
    deadline = time.perf_counter() + TOOL_TIMEOUT_SECONDS
    await controller.send_text(prompt)
    turn_token = controller.state.conversation.active_text_turn_token
    if turn_token is None:
        return PromptOutcome(None, False, False)

    try:
        final_state = await controller.wait_for_state(
            lambda state: state.error is not None
            or state.conversation.last_completed_text_turn_token >= turn_token,
            timeout_seconds=TOOL_TIMEOUT_SECONDS,
        )
    except TimeoutError:
        final_state = controller.state

    remaining = max(0.01, deadline - time.perf_counter())
    tool_status = await _wait_for_tool_status(
        coordinator,
        tool_name,
        history_index,
        remaining,
    )
    return PromptOutcome(
        tool_status=tool_status,
        turn_completed=(final_state.conversation.last_completed_text_turn_token >= turn_token),
        assistant_reply_present=bool(final_state.conversation.last_assistant_text),
    )


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
            "unexpected_eof_while_reading",
            "eof occurred in violation",
        )
    )


def _protocol_statuses(coordinator: McpCoordinator) -> dict[str, str]:
    result: dict[str, str] = {}
    for summary in coordinator.lifecycle_history:
        if summary.method in {"initialize", "tools/list"}:
            result[summary.method] = summary.status
    return result


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
                    "message": "真实数据库没有活动便签，无法执行 read/UI 验收",
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        await database_executor.close()
        engine.dispose()
        return 2

    target = active_notes[0]
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

    observed: dict[str, bool] = {}
    prompt_outcomes: dict[str, dict[str, object]] = {}
    protocol_ready = False
    decision = ToolProbeDecision("failed", 1, "connect", "not connected")
    blocked_tool: str | None = None
    connected = controller.state
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
            blocked = _environment_blocked(message)
            decision = ToolProbeDecision(
                "real_gate_blocked" if blocked else "failed",
                2 if blocked else 1,
                "connect",
                message[:240],
            )
        else:
            protocol_ready = await _wait_for_protocol_ready(coordinator)
            if not protocol_ready:
                decision = classify_tool_probe(
                    protocol_ready=False,
                    turn_completed=True,
                    observed_status=None,
                    interactive_user_command=False,
                )
            else:
                scenarios = (
                    ("notes.list_recent", "请告诉我最近三条便签，简短回答即可。"),
                    ("notes.search", "请搜索关键词“便签”，最多返回五条结果。"),
                    ("notes.get", f"请读取编号为 {target.id} 的便签。"),
                    ("ui.open_note", f"请打开编号为 {target.id} 的便签。"),
                    ("ui.show_note_list", "请回到全部便签列表。"),
                )
                decision = ToolProbeDecision("real_gate_complete", 0, None, None)
                for tool_name, prompt in scenarios:
                    outcome = await _run_prompt(controller, coordinator, prompt, tool_name)
                    prompt_outcomes[tool_name] = {
                        "tool_status": outcome.tool_status,
                        "turn_completed": outcome.turn_completed,
                        "assistant_reply_present": outcome.assistant_reply_present,
                    }
                    observed[tool_name] = outcome.tool_status == "success"
                    step_decision = classify_tool_probe(
                        protocol_ready=protocol_ready,
                        turn_completed=outcome.turn_completed,
                        observed_status=outcome.tool_status,
                        interactive_user_command=False,
                    )
                    if step_decision.exit_code != 0:
                        decision = step_decision
                        blocked_tool = tool_name
                        break

                if decision.exit_code == 0 and not {
                    "open_note",
                    "show_note_list",
                }.issubset(set(ui_adapter.commands)):
                    decision = ToolProbeDecision(
                        "failed",
                        1,
                        "ui_dispatch",
                        "tool call succeeded but expected typed UI command was not dispatched",
                    )

        before_disconnect = {
            "request_queue_size": coordinator.request_queue_size,
            "worker_alive": coordinator.worker_alive,
            "inflight_request_count": coordinator.inflight_request_count,
            "response_future_count": coordinator.response_future_count,
            "ui_dispatch_count": ui_bus.active_dispatch_count,
        }
        if connected.is_connected:
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
        terminal_clean = pending == [] and all(
            value is False if key == "worker_alive" else value == 0
            for key, value in terminal.items()
        )
        if not terminal_clean and decision.exit_code == 0:
            decision = ToolProbeDecision(
                "failed",
                1,
                "resource_closeout",
                "MCP/UI resources were not fully released",
            )

        print(
            json.dumps(
                {
                    "status": decision.status,
                    "failure_stage": decision.failure_stage,
                    "failure_reason": decision.reason,
                    "blocked_tool": blocked_tool,
                    "protocol_ready": protocol_ready,
                    "protocol_statuses": _protocol_statuses(coordinator),
                    "observed_tools": observed,
                    "prompt_outcomes": prompt_outcomes,
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
        return decision.exit_code
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
