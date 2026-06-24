from __future__ import annotations

from collections import deque
from datetime import datetime, timezone
from typing import Any


class ControlCommandHub:
    """In-memory command queue for PC App -> Sidecar -> py-xiaozhi control."""

    def __init__(self, max_commands: int = 200) -> None:
        self._commands: deque[dict[str, Any]] = deque(maxlen=max_commands)
        self._next_id = 1

    async def publish(self, command: dict[str, Any]) -> dict[str, Any]:
        normalized = dict(command)
        normalized.setdefault("source", "unknown")
        normalized.setdefault("created_at", datetime.now(timezone.utc).isoformat())
        normalized["command_id"] = self._next_id
        self._next_id += 1

        # Canonical command field.
        if "command" not in normalized:
            normalized["command"] = normalized.get("type", "unknown")

        self._commands.append(normalized)
        return normalized

    def recent(self, after: int = 0, limit: int = 20) -> list[dict[str, Any]]:
        after = int(after or 0)
        limit = max(1, min(int(limit or 20), 100))
        items = [item for item in self._commands if int(item.get("command_id", 0)) > after]
        return items[:limit]

    def latest_id(self) -> int:
        if not self._commands:
            return 0
        return int(self._commands[-1].get("command_id", 0))
