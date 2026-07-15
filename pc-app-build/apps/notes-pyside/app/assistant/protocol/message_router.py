"""Fail-closed Xiaozhi text and binary message router."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence

from .events import (
    AssistantText,
    BinaryAudio,
    ListenState,
    McpEnvelope,
    ProtocolError,
    ProtocolEvent,
    ServerHello,
    TtsState,
    UnknownJson,
)

_SENSITIVE_KEYS = {
    "authorization",
    "token",
    "access_token",
    "websocket_token",
    "hmac",
    "hmac_key",
    "challenge",
    "secret",
    "password",
}


class XiaozhiMessageRouter:
    """Convert untrusted wire messages into typed protocol events without throwing."""

    def route_text(self, raw: str) -> ProtocolEvent:
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as exc:
            return ProtocolError(
                error=f"invalid_json:{exc.msg}",
                raw_text_redacted=f"<invalid-json chars={len(raw)}>",
            )

        if not isinstance(payload, dict):
            return ProtocolError(
                error="json_root_not_object",
                raw_text_redacted=f"<json-{type(payload).__name__}>",
            )

        redacted = redact_json(payload)
        message_type = _text(payload.get("type"))
        if not message_type and _text(payload.get("method")):
            message_type = "mcp"
        if not message_type:
            return ProtocolError(
                error="missing_type",
                raw_text_redacted=redacted,
                raw_json_redacted=redacted,
            )

        session_id = _optional_text(payload.get("session_id"))
        if message_type == "hello":
            return ServerHello(
                session_id=session_id or "",
                transport=_optional_text(payload.get("transport")),
                raw_json_redacted=redacted,
            )
        if message_type in {"stt", "llm", "text"}:
            text = _text(payload.get("text"))
            if not text:
                return ProtocolError(
                    error="assistant_text_missing_text",
                    raw_text_redacted=redacted,
                    raw_json_redacted=redacted,
                )
            return AssistantText(
                source_type=message_type,
                text=text,
                session_id=session_id,
                raw_json_redacted=redacted,
            )
        if message_type == "tts":
            return TtsState(
                state=_text(payload.get("state")) or "unknown",
                text=_optional_text(payload.get("text")),
                session_id=session_id,
                raw_json_redacted=redacted,
            )
        if message_type == "listen":
            return ListenState(
                state=_text(payload.get("state")) or "unknown",
                session_id=session_id,
                raw_json_redacted=redacted,
            )
        if message_type == "mcp":
            mcp_payload = payload.get("payload")
            if isinstance(mcp_payload, dict):
                redacted_payload = redact_json(mcp_payload)
            elif isinstance(mcp_payload, str) and mcp_payload.strip():
                redacted_payload = _redact_string_payload(mcp_payload)
            elif _text(payload.get("method")):
                redacted_payload = redacted
            else:
                return ProtocolError(
                    error="missing_mcp_payload",
                    raw_text_redacted=redacted,
                    raw_json_redacted=redacted,
                )
            return McpEnvelope(
                payload_json_redacted=redacted_payload,
                session_id=session_id,
                raw_json_redacted=redacted,
            )
        return UnknownJson(
            message_type=message_type,
            session_id=session_id,
            raw_json_redacted=redacted,
        )

    def route_binary(self, data: bytes) -> BinaryAudio:
        return BinaryAudio(size_bytes=len(data))


def redact_json(payload: Mapping[str, object]) -> str:
    """Return compact JSON with secret-bearing fields replaced recursively."""

    return json.dumps(
        _redact_value(payload),
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def _redact_value(value: object) -> object:
    if isinstance(value, Mapping):
        result: dict[str, object] = {}
        for key, item in value.items():
            key_text = str(key)
            result[key_text] = "***" if key_text.lower() in _SENSITIVE_KEYS else _redact_value(item)
        return result
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [_redact_value(item) for item in value]
    return value


def _redact_string_payload(raw: str) -> str:
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return f"<mcp-string chars={len(raw)}>"
    if isinstance(payload, dict):
        return redact_json(payload)
    return f"<mcp-{type(payload).__name__}>"


def _text(value: object) -> str:
    return value.strip() if isinstance(value, str) else ""


def _optional_text(value: object) -> str | None:
    cleaned = _text(value)
    return cleaned or None
