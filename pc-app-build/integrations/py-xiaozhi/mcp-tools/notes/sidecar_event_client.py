from __future__ import annotations

import json
import os
from typing import Any
from urllib.request import Request, urlopen


def sidecar_event_url() -> str:
    return os.getenv("SIDECAR_EVENT_URL", "http://127.0.0.1:17891/api/events")


def emit_sidecar_event(event: dict[str, Any], timeout: float = 0.6) -> None:
    """Best-effort event emit. Never raise into MCP tool execution."""

    payload = dict(event)
    payload.setdefault("source", "py-xiaozhi.notes_mcp")

    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = Request(
        sidecar_event_url(),
        data=data,
        method="POST",
        headers={
            "Content-Type": "application/json; charset=utf-8",
            "Accept": "application/json",
        },
    )

    try:
        with urlopen(request, timeout=timeout) as response:
            response.read()
    except Exception:
        return


def preview_text(text: object, max_len: int = 80) -> str:
    value = "" if text is None else str(text)
    value = value.replace("\r", " ").replace("\n", " ").strip()
    if len(value) <= max_len:
        return value
    return value[:max_len] + "..."
