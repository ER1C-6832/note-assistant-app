from __future__ import annotations

import asyncio
import json
import logging
from typing import Callable, Awaitable

from config import SidecarConfig
from status_checker import collect_status

logger = logging.getLogger("sidecar.health")


async def start_health_server(config: SidecarConfig) -> None:
    server = await asyncio.start_server(
        lambda reader, writer: _handle_http(reader, writer, config),
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
) -> None:
    try:
        request_line = await reader.readline()
        request = request_line.decode("utf-8", errors="ignore").strip()
        path = request.split(" ")[1] if " " in request else "/"

        while True:
            line = await reader.readline()
            if line in {b"\r\n", b"\n", b""}:
                break

        if path not in {"/api/health", "/health", "/"}:
            await _write_json(writer, 404, {"ok": False, "error": "not found"})
            return

        status = await collect_status(config)
        await _write_json(writer, 200, {
            "ok": True,
            "type": "sidecar_health",
            "status": status,
        })
    except Exception as exc:
        await _write_json(writer, 500, {"ok": False, "error": str(exc)})
    finally:
        writer.close()
        await writer.wait_closed()


async def _write_json(
    writer: asyncio.StreamWriter,
    status_code: int,
    payload: dict,
) -> None:
    reason = {
        200: "OK",
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
