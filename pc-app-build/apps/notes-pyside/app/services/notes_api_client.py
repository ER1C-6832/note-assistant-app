"""
HTTP client for the Notes API.

Localhost requests must not use system proxy settings. Some Windows proxy/VPN
setups route 127.0.0.1 through the proxy and can return intermittent 502.
"""

from __future__ import annotations

import os
from typing import Any
from urllib.parse import urljoin

import httpx


class NotesApiError(RuntimeError):
    """Base error for Notes API communication."""


class NotesApiConnectionError(NotesApiError):
    """Raised when the app cannot connect to the Notes API."""


class NotesApiHttpError(NotesApiError):
    """Raised when the Notes API returns a non-2xx response."""


class NotesApiClient:
    """Synchronous HTTP client used by the PySide6 controller."""

    def __init__(self, base_url: str | None = None, timeout: float = 4.0) -> None:
        self.base_url = (base_url or os.getenv("NOTES_API_BASE_URL") or "http://127.0.0.1:18080").rstrip("/")
        self.timeout = timeout

    def health(self) -> dict[str, Any]:
        return self._request("GET", "/api/health")

    def list_notes(
        self,
        *,
        include_deleted: bool = False,
        tag: str | None = None,
        limit: int = 200,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        params: dict[str, Any] = {
            "include_deleted": include_deleted,
            "limit": limit,
            "offset": offset,
        }

        if tag:
            params["tag"] = tag

        return self._request("GET", "/api/notes", params=params)

    def create_note(self, *, title: str, content: str, tags: list[str], source: str = "manual") -> dict[str, Any]:
        payload = {
            "title": title,
            "content": content,
            "tags": tags,
            "is_pinned": False,
            "source": source,
        }
        return self._request("POST", "/api/notes", json=payload)

    def update_note(
        self,
        note_id: int,
        *,
        title: str | None = None,
        content: str | None = None,
        tags: list[str] | None = None,
        is_pinned: bool | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {}

        if title is not None:
            payload["title"] = title
        if content is not None:
            payload["content"] = content
        if tags is not None:
            payload["tags"] = tags
        if is_pinned is not None:
            payload["is_pinned"] = is_pinned

        return self._request("PATCH", f"/api/notes/{note_id}", json=payload)

    def delete_note(self, note_id: int) -> dict[str, Any]:
        return self._request("DELETE", f"/api/notes/{note_id}")

    def restore_note(self, note_id: int) -> dict[str, Any]:
        return self._request("POST", f"/api/notes/{note_id}/restore")

    def hard_delete_note(self, note_id: int) -> dict[str, Any]:
        return self._request("DELETE", f"/api/notes/{note_id}/hard")

    def search_notes(self, *, query: str, limit: int = 100) -> dict[str, Any]:
        return self._request("GET", "/api/notes/search", params={"q": query, "limit": limit})

    def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        url = urljoin(self.base_url + "/", path.lstrip("/"))

        try:
            with httpx.Client(timeout=self.timeout, trust_env=False) as client:
                response = client.request(method, url, **kwargs)
                response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            detail = _safe_response_text(exc.response.text)
            raise NotesApiHttpError(f"Notes API returned {exc.response.status_code}: {detail}") from exc
        except httpx.RequestError as exc:
            raise NotesApiConnectionError(f"无法连接 Notes API：{self.base_url}") from exc

        if response.content:
            return response.json()

        return None


def _safe_response_text(text: str) -> str:
    clean = (text or "").strip()
    if not clean:
        return "请求失败"
    return clean[:240]
