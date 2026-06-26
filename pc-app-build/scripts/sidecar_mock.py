from __future__ import annotations

import asyncio
import json
import os
import time
from email.utils import formatdate
from typing import Any
from urllib.parse import urlparse

import websockets

WS_HOST = os.getenv("SIDECAR_MOCK_WS_HOST", "127.0.0.1")
WS_PORT = int(os.getenv("SIDECAR_MOCK_WS_PORT", "17890"))
HTTP_HOST = os.getenv("SIDECAR_MOCK_HEALTH_HOST", "127.0.0.1")
HTTP_PORT = int(os.getenv("SIDECAR_MOCK_HEALTH_PORT", "17891"))

CLIENTS: set[Any] = set()
EVENTS: list[dict[str, Any]] = []
MOCK_PID = 99001
SESSION_ID = f"mock-{MOCK_PID}-{int(time.time() * 1000)}"
SCENARIO_INDEX = 0


def now_iso() -> str:
    return formatdate(usegmt=True)


def runtime_config() -> dict[str, Any]:
    root = os.getenv("PY_XIAOZHI_ROOT", r"C:\yuyinzhushou\py-xiaozhi-tao")
    return {
        "type": "runtime_config",
        "env_path": str(os.path.abspath(".env")),
        "settings": {
            "py_xiaozhi_root": root,
            "py_xiaozhi_python": "",
            "py_xiaozhi_runtime_mode": "headless",
            "py_xiaozhi_start_mode": "hidden",
            "py_xiaozhi_window_mode": "hidden",
            "py_xiaozhi_auto_start": False,
        },
    }


def sidecar_status() -> dict[str, Any]:
    return {
        "type": "sidecar_status",
        "sidecar": {
            "ok": True,
            "ws_url": f"ws://{WS_HOST}:{WS_PORT}/assistant",
            "health_url": f"http://{HTTP_HOST}:{HTTP_PORT}/api/health",
            "mock_mode": True,
        },
        "notes_api": {
            "ok": True,
            "url": "http://127.0.0.1:18080/api/health",
            "detail": {"ok": True, "mock": True},
        },
        "py_xiaozhi": {
            "root": os.getenv("PY_XIAOZHI_ROOT", r"C:\yuyinzhushou\py-xiaozhi-tao"),
            "python": "",
            "root_exists": True,
            "main_py_exists": True,
            "notes_tool_installed": True,
            "pc_bridge_installed": True,
            "launchable": True,
            "process_running": True,
            "process_count": 1,
            "process_pids": [MOCK_PID],
            "runtime_mode": "mock",
        },
        "runtime_config": runtime_config(),
    }


def heartbeat(status: str = "idle") -> dict[str, Any]:
    return {
        "type": "assistant_bridge_heartbeat",
        "source": "py-xiaozhi.eventbus_bridge",
        "status": status,
        "pid": MOCK_PID,
        "bridge_session_id": SESSION_ID,
        "message": "mock voice bridge heartbeat",
        "data": {
            "status": status,
            "pid": MOCK_PID,
            "bridge_session_id": SESSION_ID,
        },
    }


async def send(ws, payload: dict[str, Any]) -> None:
    await ws.send(json.dumps(payload, ensure_ascii=False))


async def broadcast(payload: dict[str, Any]) -> None:
    EVENTS.append(payload)
    del EVENTS[:-50]
    raw = json.dumps(payload, ensure_ascii=False)
    closed = []
    for client in list(CLIENTS):
        try:
            await client.send(raw)
        except Exception:
            closed.append(client)
    for client in closed:
        CLIENTS.discard(client)


async def heartbeat_loop() -> None:
    while True:
        await asyncio.sleep(1.0)
        await broadcast(heartbeat("idle"))


def scenario_payload(index: int) -> dict[str, Any]:
    mode = index % 4
    if mode == 0:
        return {
            "title": "已新增便签",
            "message": "演示：已创建“明天十点项目例会”。",
            "action": "voice_result",
            "data": {
                "title": "已新增便签",
                "message": "已创建演示便签：明天十点项目例会。",
                "success": True,
            },
        }
    if mode == 1:
        return {
            "title": "请选择一条便签",
            "message": "演示：找到多条和“周五例会”相关的便签，请选择要操作的一条。",
            "action": "voice_candidates",
            "data": {
                "title": "请选择一条便签",
                "message": "找到多条可能匹配的便签，请选择要操作的那一条。",
                "action_type": "update",
                "candidates": [
                    {"id": 101, "title": "周五项目例会", "content": "周五上午十点讨论阶段 9 Demo 包装。", "tags": ["演示", "会议"]},
                    {"id": 102, "title": "周五例会纪要", "content": "用于测试多候选选择第一条、第二条。", "tags": ["演示", "会议"]},
                ],
            },
        }
    if mode == 2:
        return {
            "title": "确认删除便签",
            "message": "演示：删除前必须二次确认，且必须基于明确 note_id。",
            "action": "voice_confirm_delete",
            "data": {
                "note_id": 103,
                "title": "临时删除测试便签",
                "content": "这是防误删策略演示便签。",
                "message": "为了防止误删，请确认是否删除这条便签。",
                "action_type": "delete",
            },
        }
    return {
        "title": "操作失败",
        "message": "演示：未找到明确便签，请换一种说法或先打开搜索结果。",
        "action": "voice_failure",
        "data": {
            "title": "操作失败",
            "message": "未找到明确便签，请换一种说法或先打开搜索结果。",
            "success": False,
        },
    }


async def simulate_voice_result() -> None:
    global SCENARIO_INDEX
    current = SCENARIO_INDEX
    SCENARIO_INDEX += 1

    await asyncio.sleep(0.6)
    await broadcast({
        "type": "assistant_transcript",
        "source": "py-xiaozhi.eventbus_bridge",
        "text": "演示语音命令",
        "message": "mock transcript",
    })
    await broadcast({
        "type": "tool_call",
        "source": "py-xiaozhi.eventbus_bridge",
        "tool_name": "notes.demo",
        "message": "mock: calling notes demo tool",
    })

    scenario = scenario_payload(current)
    await asyncio.sleep(0.6)
    await broadcast({
        "type": "tool_result",
        "source": "py-xiaozhi.eventbus_bridge",
        "tool_name": "notes.demo",
        "status": "success" if scenario["action"] != "voice_failure" else "error",
        "message": scenario["message"],
        "note_changed": scenario["action"] == "voice_result",
        "ui_action": {
            "action": scenario["action"],
            "data": scenario["data"],
            "message": scenario["message"],
        },
    })

    await broadcast({
        "type": "assistant_reply",
        "source": "py-xiaozhi.eventbus_bridge",
        "text": scenario["message"],
        "message": "mock assistant reply",
    })
    await broadcast({
        "type": "assistant_state",
        "source": "py-xiaozhi.eventbus_bridge",
        "status": "speaking",
        "message": "语音助手正在播报",
    })
    await broadcast(heartbeat("speaking"))
    await asyncio.sleep(0.8)
    await broadcast({
        "type": "assistant_state",
        "source": "py-xiaozhi.eventbus_bridge",
        "status": "idle",
        "message": "语音助手空闲",
    })
    await broadcast(heartbeat("idle"))
    if scenario["action"] == "voice_result":
        await broadcast({"type": "notes_changed", "reason": "mock_voice_demo"})


async def handle_control(message: dict[str, Any], ws) -> None:
    command = str(message.get("type", ""))
    if command == "abort_speaking":
        command = "abort"

    await send(ws, {
        "type": "control_accepted",
        "command": command,
        "command_id": int(time.time() * 1000),
        "message": f"Mock accepted voice command: {command}",
    })
    await broadcast({
        "type": "assistant_control",
        "source": "pc_app.websocket",
        "command": command,
        "message": f"mock received command: {command}",
    })
    await broadcast({
        "type": "assistant_control_received",
        "source": "py-xiaozhi.eventbus_bridge",
        "command": command,
        "message": f"mock runtime received command: {command}",
    })

    if command == "start_listen":
        await broadcast({"type": "audio_channel", "source": "py-xiaozhi.eventbus_bridge", "state": "opened", "message": "mock audio channel opened"})
        await broadcast({"type": "assistant_state", "source": "py-xiaozhi.eventbus_bridge", "status": "listening", "message": "语音助手正在聆听"})
        await broadcast({
            "type": "assistant_control_result",
            "source": "py-xiaozhi.eventbus_bridge",
            "command": "start_listen",
            "message": "mock start_listen done",
        })
        asyncio.create_task(simulate_voice_result())
    elif command in {"stop_listen", "abort"}:
        await broadcast({"type": "assistant_state", "source": "py-xiaozhi.eventbus_bridge", "status": "idle", "message": "语音助手空闲"})
        await broadcast({
            "type": "assistant_control_result",
            "source": "py-xiaozhi.eventbus_bridge",
            "command": command,
            "message": f"mock {command} done",
        })


async def handle_runtime(message: dict[str, Any], ws) -> None:
    action = str(message.get("type", ""))
    await send(ws, {"type": "runtime_action_accepted", "action": action, "message": f"Mock accepted runtime action: {action}"})
    await asyncio.sleep(0.2)
    event = {
        "type": "runtime_action_result",
        "source": "sidecar.runtime_manager",
        "action": action,
        "success": True,
        "message": f"Mock runtime action completed: {action}",
        "data": {"ok": True, "action": action, "status": sidecar_status()["py_xiaozhi"]},
    }
    await send(ws, event)
    await send(ws, sidecar_status())
    await broadcast(heartbeat("idle"))


async def ws_handler(ws) -> None:
    CLIENTS.add(ws)
    try:
        await send(ws, {"type": "sidecar_connected", "message": "Mock Sidecar connected", "ws_url": f"ws://{WS_HOST}:{WS_PORT}/assistant"})
        await send(ws, runtime_config())
        await send(ws, sidecar_status())
        await send(ws, {"type": "sidecar_events", "items": []})
        await send(ws, heartbeat("idle"))

        async for raw in ws:
            try:
                message = json.loads(raw)
            except Exception:
                await send(ws, {"type": "error", "message": "invalid json"})
                continue

            message_type = str(message.get("type", ""))
            if message_type == "ping":
                await send(ws, {"type": "pong"})
            elif message_type == "refresh_status":
                await send(ws, sidecar_status())
            elif message_type == "get_runtime_config":
                await send(ws, runtime_config())
            elif message_type == "refresh_events":
                await send(ws, {"type": "sidecar_events", "items": EVENTS[-20:]})
            elif message_type in {"start_listen", "stop_listen", "toggle_listen", "abort", "abort_speaking"}:
                await handle_control(message, ws)
            elif message_type in {"start_py_xiaozhi", "stop_py_xiaozhi", "restart_py_xiaozhi"}:
                await handle_runtime(message, ws)
            elif message_type == "refresh_notes":
                await broadcast({"type": "notes_changed", "reason": "mock_refresh"})
            else:
                await send(ws, {"type": "error", "message": f"unknown message type: {message_type}"})
    finally:
        CLIENTS.discard(ws)


async def handle_http(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
    try:
        line = await reader.readline()
        request = line.decode("utf-8", errors="ignore").strip()
        parts = request.split(" ")
        method = parts[0].upper() if parts else "GET"
        path = urlparse(parts[1] if len(parts) > 1 else "/").path

        headers = {}
        while True:
            h = await reader.readline()
            if h in {b"\r\n", b"\n", b""}:
                break
            decoded = h.decode("utf-8", errors="ignore")
            if ":" in decoded:
                k, v = decoded.split(":", 1)
                headers[k.strip().lower()] = v.strip()

        if method == "GET" and path in {"/", "/health", "/api/health"}:
            payload = {"ok": True, "type": "sidecar_health", "status": sidecar_status(), "mock": True}
        elif method == "GET" and path == "/api/events":
            payload = {"ok": True, "type": "sidecar_events", "items": EVENTS[-20:]}
        elif method == "POST" and path.startswith("/api/runtime/py-xiaozhi/"):
            payload = {"ok": True, "type": "py_xiaozhi_runtime_action_result", "result": {"ok": True, "mock": True}}
        else:
            payload = {"ok": False, "error": "not found", "path": path}

        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        status = "200 OK" if payload.get("ok") else "404 Not Found"
        writer.write(
            f"HTTP/1.1 {status}\r\nContent-Type: application/json; charset=utf-8\r\nContent-Length: {len(body)}\r\nConnection: close\r\n\r\n".encode("utf-8") + body
        )
        await writer.drain()
    finally:
        writer.close()
        await writer.wait_closed()


async def main() -> None:
    print(f"Mock Sidecar WS: ws://{WS_HOST}:{WS_PORT}/assistant")
    print(f"Mock Sidecar HTTP: http://{HTTP_HOST}:{HTTP_PORT}/api/health")
    http_server = await asyncio.start_server(handle_http, HTTP_HOST, HTTP_PORT)
    async with http_server, websockets.serve(ws_handler, WS_HOST, WS_PORT, ping_interval=20, ping_timeout=20):
        asyncio.create_task(heartbeat_loop())
        await asyncio.Future()


if __name__ == "__main__":
    asyncio.run(main())
