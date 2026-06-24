from __future__ import annotations

import json
import os
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


class NotesApiClient:
    def __init__(self, base_url: str | None = None, timeout: float = 5.0) -> None:
        self.base_url = (
            base_url or os.getenv("NOTES_API_BASE_URL") or "http://127.0.0.1:18080"
        ).rstrip("/")
        self.timeout = timeout

    def create_note(
        self,
        title: str,
        content: str = "",
        tags: list[str] | None = None,
        is_pinned: bool = False,
    ) -> dict[str, Any]:
        return self._request(
            "POST",
            "/api/notes",
            {
                "title": title,
                "content": content,
                "tags": tags or [],
                "is_pinned": bool(is_pinned),
                "source": "voice_pc",
            },
        )

    def get_note(self, note_id: int, include_deleted: bool = False) -> dict[str, Any]:
        note_id = int(note_id)
        qs = "?include_deleted=true" if include_deleted else ""

        try:
            return self._request("GET", f"/api/notes/{note_id}{qs}")
        except Exception as first_exc:
            items = self.list_notes(limit=500, include_deleted=True)
            for item in items:
                if int(item.get("id", -1)) == note_id:
                    if include_deleted or not bool(item.get("is_deleted")):
                        return item
            raise RuntimeError(f"Note not found: {note_id}") from first_exc

    def search_notes(self, query: str, limit: int = 10) -> dict[str, Any]:
        qs = urlencode({"q": query, "limit": max(1, min(int(limit or 10), 100))})
        return self._request("GET", f"/api/notes/search?{qs}")

    def list_notes(
        self,
        limit: int = 10,
        include_deleted: bool = False,
    ) -> list[dict[str, Any]]:
        qs = urlencode({
            "limit": max(1, min(int(limit or 10), 500)),
            "include_deleted": "true" if include_deleted else "false",
        })
        return self._request("GET", f"/api/notes?{qs}")

    def list_deleted_notes(self, limit: int = 50) -> list[dict[str, Any]]:
        items = self.list_notes(limit=max(1, min(int(limit or 50), 500)), include_deleted=True)
        return [item for item in items if bool(item.get("is_deleted"))]

    def update_note(
        self,
        note_id: int,
        title: str | None = None,
        content: str | None = None,
        tags: list[str] | None = None,
        is_pinned: bool | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {}

        if title is not None and title != "":
            payload["title"] = title
        if content is not None:
            payload["content"] = content
        if tags is not None:
            payload["tags"] = tags
        if is_pinned is not None:
            payload["is_pinned"] = bool(is_pinned)

        if not payload:
            raise RuntimeError("No fields to update")

        return self._request("PATCH", f"/api/notes/{int(note_id)}", payload)

    def pin_note(self, note_id: int) -> dict[str, Any]:
        return self.update_note(note_id, is_pinned=True)

    def unpin_note(self, note_id: int) -> dict[str, Any]:
        return self.update_note(note_id, is_pinned=False)

    def delete_note(self, note_id: int) -> dict[str, Any]:
        return self._request("DELETE", f"/api/notes/{int(note_id)}")

    def restore_note(self, note_id: int) -> dict[str, Any]:
        return self._request("POST", f"/api/notes/{int(note_id)}/restore")

    def hard_delete_note(self, note_id: int) -> dict[str, Any]:
        return self._request("DELETE", f"/api/notes/{int(note_id)}/hard")

    def list_tags(self, include_deleted: bool = True) -> list[dict[str, Any]]:
        items = self.list_notes(limit=500, include_deleted=include_deleted)
        stats: dict[str, dict[str, Any]] = {}

        for item in items:
            is_deleted = bool(item.get("is_deleted"))
            for raw_tag in item.get("tags", []) or []:
                tag = str(raw_tag).strip()
                if not tag:
                    continue
                entry = stats.setdefault(tag, {
                    "name": tag,
                    "count": 0,
                    "active_count": 0,
                    "deleted_count": 0,
                })
                entry["count"] += 1
                if is_deleted:
                    entry["deleted_count"] += 1
                else:
                    entry["active_count"] += 1

        return [stats[name] for name in sorted(stats.keys())]

    def tag_has_notes(self, tag: str) -> bool:
        clean = (tag or "").strip()
        if not clean:
            return False
        for item in self.list_notes(limit=500, include_deleted=True):
            tags = [str(value).strip() for value in item.get("tags", []) or []]
            if clean in tags:
                return True
        return False

    def _request(self, method: str, path: str, payload: dict[str, Any] | None = None) -> Any:
        url = self.base_url + path
        data = None
        headers = {"Accept": "application/json"}

        if payload is not None:
            data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            headers["Content-Type"] = "application/json"

        request = Request(url, data=data, headers=headers, method=method)

        try:
            with urlopen(request, timeout=self.timeout) as response:
                raw = response.read().decode("utf-8")
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Notes API HTTP {exc.code}: {detail}") from exc
        except URLError as exc:
            raise RuntimeError(f"Cannot connect to Notes API at {self.base_url}: {exc}") from exc

        return json.loads(raw) if raw else None


def parse_tags(tags: str | list[str] | None) -> list[str]:
    if not tags:
        return []

    if isinstance(tags, list):
        return [str(item).strip() for item in tags if str(item).strip()]

    normalized = str(tags)
    for sep in ["，", "、", "；", ";", "|", " "]:
        normalized = normalized.replace(sep, ",")

    return [item.strip() for item in normalized.split(",") if item.strip()]


def parse_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() in {"1", "true", "yes", "y", "是", "置顶", "pin", "pinned"}
