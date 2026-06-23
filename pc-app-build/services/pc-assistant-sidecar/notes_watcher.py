from __future__ import annotations

import hashlib
import json
from typing import Any

import httpx

from config import SidecarConfig


class NotesSnapshotWatcher:
    def __init__(self, config: SidecarConfig) -> None:
        self.config = config
        self._last_signature = ""

    async def fetch_signature(self) -> tuple[str, dict[str, Any]]:
        url = f"{self.config.notes_api_base_url}/api/notes"

        async with httpx.AsyncClient(timeout=3.0, trust_env=False) as client:
            response = await client.get(
                url,
                params={
                    "include_deleted": "true",
                    "limit": 200,
                },
            )
            response.raise_for_status()
            notes = response.json()

        compact = [
            {
                "id": item.get("id"),
                "title": item.get("title"),
                "updated_at": item.get("updated_at"),
                "is_deleted": item.get("is_deleted"),
                "is_pinned": item.get("is_pinned"),
                "tags": item.get("tags"),
            }
            for item in notes
        ]

        raw = json.dumps(compact, ensure_ascii=False, sort_keys=True)
        signature = hashlib.sha256(raw.encode("utf-8")).hexdigest()

        payload = {
            "count": len(notes),
            "signature": signature,
        }
        return signature, payload

    async def check_changed(self) -> dict[str, Any] | None:
        signature, payload = await self.fetch_signature()

        if not self._last_signature:
            self._last_signature = signature
            return None

        if signature == self._last_signature:
            return None

        self._last_signature = signature
        return {
            "type": "notes_changed",
            "reason": "snapshot_changed",
            **payload,
        }
