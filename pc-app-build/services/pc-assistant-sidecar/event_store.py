from __future__ import annotations

import asyncio
from collections import deque
from datetime import datetime, timezone
from typing import Any


class SidecarEventHub:
    """In-memory event hub shared by HTTP event intake and WebSocket broadcast."""

    def __init__(self, max_events: int = 200) -> None:
        self._events: deque[dict[str, Any]] = deque(maxlen=max_events)
        self._subscribers: set[asyncio.Queue] = set()
        self._next_id = 1

    def recent_events(self, limit: int = 20) -> list[dict[str, Any]]:
        limit = max(1, min(int(limit or 20), 200))
        return list(self._events)[-limit:]

    async def publish(self, event: dict[str, Any]) -> dict[str, Any]:
        normalized = dict(event)
        normalized.setdefault("type", "sidecar_event")
        normalized.setdefault("source", "unknown")
        normalized.setdefault("created_at", datetime.now(timezone.utc).isoformat())
        normalized["event_id"] = self._next_id
        self._next_id += 1

        self._events.append(normalized)

        for queue in list(self._subscribers):
            try:
                queue.put_nowait(normalized)
            except asyncio.QueueFull:
                pass

        return normalized

    def subscribe(self) -> asyncio.Queue:
        queue: asyncio.Queue = asyncio.Queue(maxsize=200)
        self._subscribers.add(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue) -> None:
        self._subscribers.discard(queue)
