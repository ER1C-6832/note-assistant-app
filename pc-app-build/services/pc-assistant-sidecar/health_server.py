from __future__ import annotations

import asyncio
import json
import logging
from urllib.parse import parse_qs, urlparse

from config import SidecarConfig, load_config
from control_store import ControlCommandHub
from event_store import SidecarEventHub
from py_xiaozhi_process_manager import PyXiaozhiProcessManager
from runtime_config_store import get_runtime_config, save_runtime_config
from status_checker import collect_status

logger = logging.getLogger("sidecar.health")


async def start_health_server(
    config: SidecarConfig,
    event_hub: SidecarEventHub | None = None,
    control_hub: ControlCommandHub | None = None,
    runtime_manager: PyXiaozhiProcessManager | None = None,
) -> None:
    if event_hub is None:
        event_hub = SidecarEventHub()
    if control_hub is None:
        control_hub = ControlCommandHub()
    if runtime_manager is None:
        runtime_manager = PyXiaozhiProcessManager(config)

    server = await asyncio.start_server(
        lambda reader, writer: _handle_http(reader, writer, config, event_hub, control_hub, runtime_manager),
        config.health_host,
        config.health_port,
    )

    logger.info("Starting health server on %s", config.health_url)

    async with server:
        await server.serve_forever()


async def _handle_http(
    reader: asyncio.StreamReader,
    writer: asyncio.StreamWriter,
    config: SidecarConfig,
    event_hub: SidecarEventHub,
    control_hub: ControlCommandHub,
    runtime_manager: PyXiaozhiProcessManager,
) -> None:
    try:
        request_line = await reader.readline()
        request = request_line.decode("utf-8", errors="ignore").strip()

        if not request:
            await _write_json(writer, 400, {"ok": False, "error": "empty request"})
            return

        parts = request.split(" ")
        method = parts[0].upper() if parts else "GET"
        raw_path = parts[1] if len(parts) > 1 else "/"
        parsed = urlparse(raw_path)
        path = parsed.path
        query = parse_qs(parsed.query)

        headers: dict[str, str] = {}
        while True:
            line = await reader.readline()
            if line in {b"\r\n", b"\n", b""}:
                break

            decoded = line.decode("utf-8", errors="ignore")
            if ":" in decoded:
                key, value = decoded.split(":", 1)
                headers[key.strip().lower()] = value.strip()

        if method == "GET" and path in {"/api/health", "/health", "/"}:
            status = await collect_status(config)
            status.setdefault("sidecar", {})
            status["sidecar"]["control_latest_id"] = control_hub.latest_id()
            fresh = load_config()
            if hasattr(fresh, "py_xiaozhi_log_path"):
                status["py_xiaozhi"]["log_path"] = str(fresh.py_xiaozhi_log_path or "")
                status["py_xiaozhi"]["log_path_exists"] = bool(
                    fresh.py_xiaozhi_log_path and fresh.py_xiaozhi_log_path.exists()
                )
            await _write_json(writer, 200, {
                "ok": True,
                "type": "sidecar_health",
                "status": status,
            })
            return

        if method == "GET" and path == "/api/runtime/config":
            await _write_json(writer, 200, {
                "ok": True,
                **get_runtime_config(load_config()),
            })
            return

        if method == "POST" and path == "/api/runtime/config":
            payload = await _read_json_body(reader, headers)
            if not isinstance(payload, dict):
                await _write_json(writer, 400, {"ok": False, "error": "runtime config payload must be an object"})
                return
            result = await asyncio.to_thread(save_runtime_config, payload, load_config())
            runtime_manager.reload_config()
            await _write_json(writer, 200, result)
            return

        if method == "GET" and path == "/api/events":
            limit = int((query.get("limit") or ["20"])[0])
            await _write_json(writer, 200, {
                "ok": True,
                "type": "sidecar_events",
                "items": event_hub.recent_events(limit=limit),
            })
            return

        if method == "POST" and path == "/api/events":
            payload = await _read_json_body(reader, headers)
            if not isinstance(payload, dict):
                await _write_json(writer, 400, {"ok": False, "error": "event payload must be an object"})
                return

            stored = await event_hub.publish(payload)
            await _write_json(writer, 200, {
                "ok": True,
                "type": "sidecar_event_accepted",
                "event": stored,
            })
            return

        if method == "GET" and path == "/api/control":
            after = int((query.get("after") or ["0"])[0] or 0)
            limit = int((query.get("limit") or ["20"])[0] or 20)
            await _write_json(writer, 200, {
                "ok": True,
                "type": "assistant_control_commands",
                "latest_id": control_hub.latest_id(),
                "items": control_hub.recent(after=after, limit=limit),
            })
            return

        if method == "POST" and path == "/api/control":
            payload = await _read_json_body(reader, headers)
            if not isinstance(payload, dict):
                await _write_json(writer, 400, {"ok": False, "error": "control payload must be an object"})
                return

            command = await control_hub.publish(payload)
            await event_hub.publish({
                "type": "assistant_control",
                "source": payload.get("source", "sidecar.http"),
                "command": command.get("command"),
                "command_id": command.get("command_id"),
                "message": f"收到语音控制命令：{command.get('command')}",
                "data": command,
            })
            await _write_json(writer, 200, {
                "ok": True,
                "type": "assistant_control_accepted",
                "command": command,
            })
            return

        if method == "GET" and path == "/api/runtime/py-xiaozhi/status":
            runtime_manager.reload_config()
            await _write_json(writer, 200, {
                "ok": True,
                "type": "py_xiaozhi_runtime_status",
                "status": runtime_manager.status(),
                "config": get_runtime_config(runtime_manager.config),
            })
            return

        if method == "POST" and path in {
            "/api/runtime/py-xiaozhi/start",
            "/api/runtime/py-xiaozhi/stop",
            "/api/runtime/py-xiaozhi/restart",
        }:
            payload = await _read_json_body(reader, headers)
            mode = ""
            if isinstance(payload, dict):
                mode = str(payload.get("mode", "") or "")

            runtime_manager.reload_config()
            if path.endswith("/start"):
                result = await asyncio.to_thread(runtime_manager.start, mode or None)
            elif path.endswith("/stop"):
                result = await asyncio.to_thread(runtime_manager.stop)
            else:
                result = await asyncio.to_thread(runtime_manager.restart, mode or None)

            event = {
                "type": "runtime_action_result",
                "source": "sidecar.runtime_manager",
                "action": path.rsplit("/", 1)[-1],
                "success": bool(result.get("ok")),
                "message": result.get("message", ""),
                "data": result,
            }
            await event_hub.publish(event)

            await _write_json(writer, 200 if result.get("ok") else 500, {
                "ok": bool(result.get("ok")),
                "type": "py_xiaozhi_runtime_action_result",
                "result": result,
            })
            return

        await _write_json(writer, 404, {"ok": False, "error": "not found"})

    except Exception as exc:
        await _write_json(writer, 500, {"ok": False, "error": str(exc)})
    finally:
        writer.close()
        await writer.wait_closed()


async def _read_json_body(reader: asyncio.StreamReader, headers: dict[str, str]) -> object:
    content_length = int(headers.get("content-length") or "0")
    raw_body = await reader.readexactly(content_length) if content_length > 0 else b"{}"

    try:
        return json.loads(raw_body.decode("utf-8"))
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"invalid json: {exc}") from exc


async def _write_json(writer: asyncio.StreamWriter, status_code: int, payload: dict) -> None:
    reason = {
        200: "OK",
        400: "Bad Request",
        404: "Not Found",
        500: "Internal Server Error",
    }.get(status_code, "OK")

    body = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
    headers = (
        f"HTTP/1.1 {status_code} {reason}\r\n"
        "Content-Type: application/json; charset=utf-8\r\n"
        f"Content-Length: {len(body)}\r\n"
        "Connection: close\r\n"
        "\r\n"
    ).encode("utf-8")

    writer.write(headers + body)
    await writer.drain()
