"""Privacy-preserving Xiaozhi router extension for private MCP payload delivery."""

from __future__ import annotations

import json
from dataclasses import dataclass, field

from ..protocol.events import ProtocolEvent
from ..protocol.message_router import XiaozhiMessageRouter
from .constants import JSONRPC_INVALID_REQUEST, MCP_MAX_OUTER_MESSAGE_BYTES


@dataclass(frozen=True, slots=True)
class PrivateMcpEnvelope(ProtocolEvent):
    """MCP payload retained only on the private transport-to-coordinator path."""

    payload: object = field(default=None, repr=False)
    session_id: str | None = field(default=None, repr=False)
    preflight_error_code: int | None = None
    preflight_error_message: str | None = None


class McpAwareXiaozhiMessageRouter(XiaozhiMessageRouter):
    """Parse MCP outer JSON once while delegating all non-MCP messages unchanged."""

    def route_text(self, raw: str) -> ProtocolEvent:
        try:
            outer = json.loads(raw, parse_constant=_reject_json_constant)
        except (json.JSONDecodeError, ValueError):
            return super().route_text(raw)
        if not isinstance(outer, dict):
            return super().route_text(raw)
        message_type = outer.get("type")
        is_mcp = message_type == "mcp" or (
            not message_type and isinstance(outer.get("method"), str)
        )
        if not is_mcp:
            return super().route_text(raw)

        size_bytes = len(raw.encode("utf-8"))
        session_id = outer.get("session_id")
        clean_session = (
            session_id.strip() if isinstance(session_id, str) and session_id.strip() else None
        )
        safe_marker = f"<mcp-envelope bytes={size_bytes}>"
        if size_bytes > MCP_MAX_OUTER_MESSAGE_BYTES:
            return PrivateMcpEnvelope(
                session_id=clean_session,
                preflight_error_code=JSONRPC_INVALID_REQUEST,
                preflight_error_message="MCP envelope exceeds the 64 KiB input budget",
                raw_json_redacted=safe_marker,
            )

        if "payload" in outer:
            payload = outer.get("payload")
            if not isinstance(payload, (dict, str)) or (
                isinstance(payload, str) and not payload.strip()
            ):
                return PrivateMcpEnvelope(
                    session_id=clean_session,
                    preflight_error_code=JSONRPC_INVALID_REQUEST,
                    preflight_error_message="Invalid MCP payload",
                    raw_json_redacted=safe_marker,
                )
        else:
            payload = {
                key: value for key, value in outer.items() if key not in {"session_id", "type"}
            }
        return PrivateMcpEnvelope(
            payload=payload,
            session_id=clean_session,
            raw_json_redacted=safe_marker,
        )


def _reject_json_constant(value: str) -> None:
    raise ValueError(f"invalid JSON constant: {value}")
