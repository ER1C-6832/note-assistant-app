from __future__ import annotations

from app.assistant.mcp.constants import (
    JSONRPC_INVALID_REQUEST,
    JSONRPC_PARSE_ERROR,
    MCP_MAX_OUTER_MESSAGE_BYTES,
)
from app.assistant.mcp.contracts import McpNotification, McpParseFailure, McpRequest
from app.assistant.mcp.jsonrpc import parse_jsonrpc_payload
from app.assistant.mcp.router import McpAwareXiaozhiMessageRouter, PrivateMcpEnvelope


def test_jsonrpc_preserves_string_and_integer_request_ids() -> None:
    integer = parse_jsonrpc_payload(
        {"jsonrpc": "2.0", "id": 3, "method": "tools/list", "params": {}}
    )
    string = parse_jsonrpc_payload(
        {"jsonrpc": "2.0", "id": "3", "method": "tools/list", "params": {}}
    )
    assert isinstance(integer, McpRequest) and integer.request_id == 3
    assert isinstance(string, McpRequest) and string.request_id == "3"
    assert type(integer.request_id) is int
    assert type(string.request_id) is str


def test_jsonrpc_notification_and_failure_contracts() -> None:
    notification = parse_jsonrpc_payload(
        {"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}}
    )
    assert isinstance(notification, McpNotification)
    malformed = parse_jsonrpc_payload("{")
    assert isinstance(malformed, McpParseFailure)
    assert malformed.code == JSONRPC_PARSE_ERROR
    invalid_bool_id = parse_jsonrpc_payload(
        {"jsonrpc": "2.0", "id": True, "method": "tools/list", "params": {}}
    )
    assert isinstance(invalid_bool_id, McpParseFailure)
    assert invalid_bool_id.code == JSONRPC_INVALID_REQUEST
    non_finite = parse_jsonrpc_payload(
        '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{"x":NaN}}'
    )
    assert isinstance(non_finite, McpParseFailure)
    assert non_finite.code == JSONRPC_PARSE_ERROR


def test_private_mcp_event_repr_never_contains_arguments() -> None:
    raw = (
        '{"session_id":"secret-session","type":"mcp","payload":'
        '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":'
        '{"name":"notes.create","arguments":{"title":"private title",'
        '"content":"private body"}}}}'
    )
    event = McpAwareXiaozhiMessageRouter().route_text(raw)
    assert isinstance(event, PrivateMcpEnvelope)
    representation = repr(event)
    assert "private title" not in representation
    assert "private body" not in representation
    assert "secret-session" not in representation
    assert event.raw_json_redacted == f"<mcp-envelope bytes={len(raw.encode('utf-8'))}>"


def test_oversized_mcp_is_rejected_before_handler() -> None:
    padding = "x" * MCP_MAX_OUTER_MESSAGE_BYTES
    raw = (
        '{"session_id":"s","type":"mcp","payload":'
        '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{},'
        f'"padding":"{padding}"}}}}'
    )
    event = McpAwareXiaozhiMessageRouter().route_text(raw)
    assert isinstance(event, PrivateMcpEnvelope)
    assert event.preflight_error_code == JSONRPC_INVALID_REQUEST
    assert event.payload is None


def test_non_mcp_messages_continue_through_the_existing_router() -> None:
    event = McpAwareXiaozhiMessageRouter().route_text(
        '{"type":"hello","session_id":"s","transport":"websocket"}'
    )
    assert not isinstance(event, PrivateMcpEnvelope)
    assert type(event).__name__ == "ServerHello"
