"""Manual Real Gate 5.4 recorder for user-authored natural-language commands.

This runner intentionally does not send scripted text to the assistant.  It opens
the production desktop composition root, displays the frozen tool checklist and
observes sanitized MCP lifecycle summaries while the user speaks or types any
natural wording they prefer in the visible UI.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP_ROOT = ROOT / "apps" / "notes-pyside"
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))
if str(Path(__file__).resolve().parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parent))

from PySide6.QtGui import QGuiApplication  # noqa: E402
from qasync import QEventLoop  # noqa: E402

from app.bootstrap import create_application_context  # noqa: E402
from gate5_4_acceptance_catalog import (  # noqa: E402
    GATE5_4_ACCEPTANCE_CASES,
    format_command,
    format_verbose_command,
)

CONNECT_TIMEOUT_SECONDS = 20.0
PROTOCOL_TIMEOUT_SECONDS = 15.0
TOOL_TIMEOUT_SECONDS = 90.0
_ACCEPTED_TOOL_STATUSES = {"success", "requires_confirmation", "partial_success"}


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
            "microphone",
            "audio device",
        )
    )


async def _console(prompt: str) -> str:
    return await asyncio.to_thread(input, prompt)


async def _wait_protocol(coordinator) -> bool:
    deadline = time.perf_counter() + PROTOCOL_TIMEOUT_SECONDS
    while time.perf_counter() < deadline:
        successful = {
            item.method for item in coordinator.lifecycle_history if item.status == "success"
        }
        if {"initialize", "tools/list"}.issubset(successful):
            return True
        await asyncio.sleep(0.05)
    return False


async def _wait_tool(coordinator, tool_name: str, start: int) -> str | None:
    deadline = time.perf_counter() + TOOL_TIMEOUT_SECONDS
    while time.perf_counter() < deadline:
        for item in coordinator.lifecycle_history[start:]:
            if item.tool_name == tool_name:
                return item.status
        await asyncio.sleep(0.05)
    return None


def _print_catalog(group: str | None = None) -> None:
    for index, case in enumerate(GATE5_4_ACCEPTANCE_CASES, start=1):
        if group and case.group != group:
            continue
        print(f"{index:02d}. [{case.group}] {case.tool_name}")
        print(f"    简洁：{case.command}")
        print(f"    口语：{case.verbose_command}")
        print(f"    期望：{case.expected}")


async def _run(context, args: argparse.Namespace) -> int:
    controller = context.assistant_controller
    coordinator = context.assistant_runtime.mcp_coordinator

    results: list[dict[str, object]] = []
    aborted = False
    try:
        await controller.start()
        await controller.use_real_runtime()
        await controller.enable_assistant()
        await controller.ensure_device_identity()
        await controller.connect()
        state = await controller.wait_for_state(
            lambda value: value.is_connected or value.error is not None,
            timeout_seconds=CONNECT_TIMEOUT_SECONDS,
        )
        if not state.is_connected:
            message = state.error.message if state.error else "真实 WebSocket 未连接"
            print(
                json.dumps(
                    {
                        "status": (
                            "real_gate_blocked" if _environment_blocked(message) else "failed"
                        ),
                        "failure_stage": "connect",
                        "message": message[:240],
                    },
                    ensure_ascii=False,
                    indent=2,
                    sort_keys=True,
                )
            )
            return 2 if _environment_blocked(message) else 1

        if not await _wait_protocol(coordinator):
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

        active = await context.note_query_service.list_recent(1)
        deleted = await context.note_query_service.list_deleted_bounded(1)
        active_id: int | str = active[0].id if active else "<活动便签ID>"
        deleted_id: int | str = deleted[0].id if deleted else "<已删除便签ID>"

        print("\nGate 5.4 Real 手工验收记录器已启动。")
        print("请在可见助手 UI 中使用你自己的自然语言；下面句子只是参考，不会自动发送。")
        print("每一步输入 Enter 后说话，完成后再按 Enter。输入 s 跳过，q 结束。")

        selected = tuple(
            case
            for case in GATE5_4_ACCEPTANCE_CASES
            if args.group is None or case.group == args.group
        )
        for case in selected:
            print(f"\n[{case.group}] {case.tool_name}")
            print("参考：" + format_command(case, active_id=active_id, deleted_id=deleted_id))
            print(
                "口语：" + format_verbose_command(case, active_id=active_id, deleted_id=deleted_id)
            )
            print(f"前置：{case.prerequisite}")
            choice = (await _console("Enter 开始，s 跳过，q 结束：")).strip().lower()
            if choice == "q":
                aborted = True
                break
            if choice == "s":
                results.append(
                    {
                        "tool_name": case.tool_name,
                        "status": "skipped",
                        "observed": False,
                    }
                )
                continue

            start = len(coordinator.lifecycle_history)
            await _console("请现在说出或输入你自己的命令，完成后按 Enter：")
            status = await _wait_tool(coordinator, case.tool_name, start)
            observed = status is not None
            accepted = status in _ACCEPTED_TOOL_STATUSES
            visually_confirmed: bool | None = None
            if observed and args.confirm_effects:
                answer = (
                    (await _console("数据库或界面效果是否符合期望？输入 y 确认：")).strip().lower()
                )
                visually_confirmed = answer in {"y", "yes", "是", "1"}
                accepted = accepted and visually_confirmed
            results.append(
                {
                    "tool_name": case.tool_name,
                    "status": status,
                    "observed": observed,
                    "accepted": accepted,
                    "effect_confirmed": visually_confirmed,
                }
            )
            print(f"观察结果：{status or '未观察到 tools/call'}")

        before_shutdown = {
            "request_queue_size": coordinator.request_queue_size,
            "worker_alive": coordinator.worker_alive,
            "inflight_request_count": coordinator.inflight_request_count,
            "response_future_count": coordinator.response_future_count,
            "pending_confirmation_count": coordinator.pending_confirmation_count,
            "ui_dispatch_count": context.ui_command_bus.active_dispatch_count,
        }
    finally:
        await context.lifecycle.shutdown(timeout_seconds=10.0)
        await asyncio.sleep(0)

    terminal = {
        "request_queue_size": coordinator.request_queue_size,
        "worker_alive": coordinator.worker_alive,
        "inflight_request_count": coordinator.inflight_request_count,
        "dedupe_waiter_count": coordinator.dedupe_waiter_count,
        "response_future_count": coordinator.response_future_count,
        "pending_confirmation_count": coordinator.pending_confirmation_count,
        "ui_dispatch_count": context.ui_command_bus.active_dispatch_count,
    }
    selected_names = {
        case.tool_name
        for case in GATE5_4_ACCEPTANCE_CASES
        if args.group is None or case.group == args.group
    }
    passed_names = {str(item["tool_name"]) for item in results if item.get("accepted") is True}
    missing = sorted(selected_names - passed_names)
    terminal_clean = all(
        value is False if key == "worker_alive" else value == 0 for key, value in terminal.items()
    )
    complete = not aborted and not missing and terminal_clean
    print(
        json.dumps(
            {
                "status": "real_gate_complete" if complete else "incomplete",
                "real_ui_used": True,
                "natural_language_user_authored": True,
                "selected_tool_count": len(selected_names),
                "passed_tool_count": len(passed_names),
                "missing_tools": missing,
                "results": results,
                "before_shutdown": before_shutdown,
                "terminal": terminal,
                "payload_persisted": False,
                "secrets_redacted": True,
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if complete else 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--list", action="store_true", help="仅列出 31 个验收案例")
    parser.add_argument(
        "--group",
        choices=("读取/解析", "便签写入", "标签", "界面", "确认"),
        help="只记录一个工具分组",
    )
    parser.add_argument(
        "--confirm-effects",
        action="store_true",
        help="每次工具调用后要求人工确认数据库或 UI 效果",
    )
    args = parser.parse_args()
    if args.list:
        _print_catalog(args.group)
        return 0
    if os.environ.get("QT_QPA_PLATFORM") == "offscreen":
        print("真实 UI 验收不能使用 QT_QPA_PLATFORM=offscreen", file=sys.stderr)
        return 2

    app = QGuiApplication.instance()
    owns_app = app is None
    if app is None:
        app = QGuiApplication(sys.argv)
    if not isinstance(app, QGuiApplication):
        raise RuntimeError("existing Qt application is not a QGuiApplication")
    app.setApplicationName("NoteAssistant Gate 5.4 Real Manual")
    app.setQuitOnLastWindowClosed(True)
    loop = QEventLoop(app)
    asyncio.set_event_loop(loop)
    data_root = os.environ.get("NOTE_ASSISTANT_DATA_ROOT", "").strip() or None
    context = create_application_context(app, data_root=data_root)
    app.aboutToQuit.connect(loop.stop)
    try:
        with loop:
            try:
                exit_code = loop.run_until_complete(_run(context, args))
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
