"""Interactive Gate 5.1 Real Gate using the actual desktop UI and natural language."""

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

from PySide6.QtGui import QGuiApplication  # noqa: E402
from qasync import QEventLoop  # noqa: E402

from app.bootstrap import create_application_context  # noqa: E402
from gate5_1_acceptance import ToolProbeDecision, classify_tool_probe  # noqa: E402

CONNECT_TIMEOUT_SECONDS = 20.0
PROTOCOL_TIMEOUT_SECONDS = 15.0
SCENARIO_TIMEOUT_SECONDS = 90.0


@dataclass(frozen=True, slots=True)
class Scenario:
    name: str
    spoken_command: str
    expected_tool: str
    expected_ui_command: str | None = None
    visual_question: str | None = None


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
            "microphone",
            "audio device",
        )
    )


async def _console_input(prompt: str) -> str:
    return await asyncio.to_thread(input, prompt)


async def _wait_for_protocol_ready(coordinator) -> bool:
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
    coordinator,
    tool_name: str,
    start_index: int,
) -> str | None:
    deadline = time.perf_counter() + SCENARIO_TIMEOUT_SECONDS
    while time.perf_counter() < deadline:
        for summary in coordinator.lifecycle_history[start_index:]:
            if summary.tool_name == tool_name:
                return summary.status
        await asyncio.sleep(0.05)
    return None


async def _wait_for_ui_command(adapter, command: str, start_index: int) -> bool:
    deadline = time.perf_counter() + 5.0
    while time.perf_counter() < deadline:
        if command in adapter.command_history[start_index:]:
            return True
        await asyncio.sleep(0.05)
    return False


async def _ask_yes(prompt: str) -> bool:
    answer = (await _console_input(prompt)).strip().lower()
    return answer in {"y", "yes", "是", "1"}


async def _run_scenario(context, scenario: Scenario) -> tuple[dict[str, object], ToolProbeDecision]:
    coordinator = context.assistant_runtime.mcp_coordinator
    adapter = context.ui_command_adapter
    history_index = len(coordinator.lifecycle_history)
    ui_index = len(adapter.command_history)
    completed_before = (
        context.assistant_controller.state.conversation.last_completed_text_turn_token
    )

    print("\n请在已打开的真实助手 UI 中点击麦克风，并自然说出：")
    print(f"  {scenario.spoken_command}")
    await _console_input("说完后按 Enter；runner 将等待真实 tools/call：")

    tool_status = await _wait_for_tool_status(
        coordinator,
        scenario.expected_tool,
        history_index,
    )
    turn_completed = (
        context.assistant_controller.state.conversation.last_completed_text_turn_token
        > completed_before
    )
    decision = classify_tool_probe(
        protocol_ready=True,
        turn_completed=turn_completed,
        observed_status=tool_status,
        interactive_user_command=True,
    )
    ui_observed = None
    visual_confirmed = None
    if decision.exit_code == 0 and scenario.expected_ui_command is not None:
        ui_observed = await _wait_for_ui_command(
            adapter,
            scenario.expected_ui_command,
            ui_index,
        )
        if not ui_observed:
            decision = ToolProbeDecision(
                "failed",
                1,
                "ui_dispatch",
                f"expected UI command {scenario.expected_ui_command} was not observed",
            )
        elif scenario.visual_question is not None:
            visual_confirmed = await _ask_yes(f"{scenario.visual_question} 输入 y 确认：")
            if not visual_confirmed:
                decision = ToolProbeDecision(
                    "failed",
                    1,
                    "manual_ui_confirmation",
                    "the user did not confirm the visible UI effect",
                )

    return (
        {
            "expected_tool": scenario.expected_tool,
            "tool_status": tool_status,
            "turn_completed": turn_completed,
            "assistant_reply_present": bool(
                context.assistant_controller.state.conversation.last_assistant_text
            ),
            "expected_ui_command": scenario.expected_ui_command,
            "ui_command_observed": ui_observed,
            "visual_confirmed": visual_confirmed,
        },
        decision,
    )


async def _run(context) -> int:
    controller = context.assistant_controller
    coordinator = context.assistant_runtime.mcp_coordinator
    await controller.start()
    await controller.use_real_runtime()
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
        print(
            json.dumps(
                {
                    "status": "real_gate_blocked" if blocked else "failed",
                    "failure_stage": "connect",
                    "message": message[:240],
                },
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
        )
        return 2 if blocked else 1

    protocol_ready = await _wait_for_protocol_ready(coordinator)
    if not protocol_ready:
        print(
            json.dumps(
                {
                    "status": "real_gate_blocked",
                    "failure_stage": "mcp_capability_handshake",
                    "message": "未观察到 initialize + tools/list 成功闭环",
                },
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
        )
        return 2

    recent = await context.note_query_service.list_recent(1)
    if not recent:
        print(
            json.dumps(
                {
                    "status": "real_gate_blocked",
                    "failure_stage": "seed_data",
                    "message": "真实数据库没有活动便签",
                },
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
        )
        return 2
    target_note_id = recent[0].id

    print("\nGate 5.1 真实 UI 自然语言验收已启动。")
    print("窗口会保持打开；请不要在 runner 完成前关闭应用。")
    print("命令必须通过窗口中的真实助手输入，优先使用麦克风说话。")

    scenarios = (
        Scenario(
            "recent",
            "请告诉我最近三条便签。",
            "notes.list_recent",
        ),
        Scenario(
            "search",
            "请搜索关键词便签，最多返回五条结果。",
            "notes.search",
        ),
        Scenario(
            "get",
            f"请读取编号为 {target_note_id} 的便签。",
            "notes.get",
        ),
        Scenario(
            "open_note",
            f"请打开编号为 {target_note_id} 的便签。",
            "ui.open_note",
            "open_note",
            "是否看到桌面界面切换并选中了该便签？",
        ),
        Scenario(
            "show_note_list",
            "请回到全部便签列表。",
            "ui.show_note_list",
            "show_note_list",
            "是否看到桌面界面回到全部便签列表？",
        ),
    )

    scenario_results: dict[str, dict[str, object]] = {}
    decision = ToolProbeDecision("real_gate_complete", 0, None, None)
    for scenario in scenarios:
        result, step_decision = await _run_scenario(context, scenario)
        scenario_results[scenario.name] = result
        if step_decision.exit_code != 0:
            decision = step_decision
            break

    before_shutdown = {
        "request_queue_size": coordinator.request_queue_size,
        "worker_alive": coordinator.worker_alive,
        "inflight_request_count": coordinator.inflight_request_count,
        "response_future_count": coordinator.response_future_count,
        "ui_dispatch_count": context.ui_command_bus.active_dispatch_count,
    }
    await context.lifecycle.shutdown(timeout_seconds=10.0)
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
        "ui_dispatch_count": context.ui_command_bus.active_dispatch_count,
    }
    terminal_clean = pending == [] and all(
        value is False if key == "worker_alive" else value == 0 for key, value in terminal.items()
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
                "protocol_ready": protocol_ready,
                "scenario_results": scenario_results,
                "ui_command_history": list(context.ui_command_adapter.command_history),
                "target_note_id": target_note_id,
                "connection_generation": connected.connection.connection_generation,
                "session_id_masked": _mask(connected.connection.session_id),
                "websocket_url": connected.connection.websocket_url_public,
                "before_shutdown": before_shutdown,
                "terminal": terminal,
                "pending_assistant_tasks": pending,
                "payload_persisted": False,
                "secrets_redacted": True,
                "real_ui_used": True,
                "natural_language_used": True,
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )
    return decision.exit_code


def main() -> int:
    app = QGuiApplication.instance()
    owns_app = app is None
    if app is None:
        app = QGuiApplication(sys.argv)
    if not isinstance(app, QGuiApplication):
        raise RuntimeError("existing Qt application is not a QGuiApplication")
    app.setApplicationName("NoteAssistant Gate 5.1 Real UI")
    app.setQuitOnLastWindowClosed(True)

    loop = QEventLoop(app)
    asyncio.set_event_loop(loop)
    context = create_application_context(
        app,
        data_root=_optional_env("NOTE_ASSISTANT_DATA_ROOT"),
    )
    app.aboutToQuit.connect(loop.stop)
    try:
        with loop:
            try:
                exit_code = loop.run_until_complete(_run(context))
            finally:
                if not context.lifecycle.is_closed:
                    loop.run_until_complete(context.lifecycle.shutdown(timeout_seconds=10.0))
            app.quit()
            return exit_code
    except Exception as exc:
        message = str(exc) or type(exc).__name__
        blocked = _environment_blocked(message)
        print(
            json.dumps(
                {
                    "status": "real_gate_blocked" if blocked else "failed",
                    "failure_stage": "runner",
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
    finally:
        asyncio.set_event_loop(None)
        if owns_app:
            context.engine.deleteLater()


if __name__ == "__main__":
    raise SystemExit(main())
