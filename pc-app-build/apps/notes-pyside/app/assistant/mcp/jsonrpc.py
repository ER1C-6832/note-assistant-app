"""Typed JSON-RPC parsing and response helpers for Gate 5.0."""

from __future__ import annotations

import json
from collections.abc import Mapping

from .constants import (
    JSONRPC_INTERNAL_ERROR,
    JSONRPC_INVALID_PARAMS,
    JSONRPC_INVALID_REQUEST,
    JSONRPC_METHOD_NOT_FOUND,
    JSONRPC_PARSE_ERROR,
)
from .contracts import (
    JsonValue,
    McpNotification,
    McpParseFailure,
    McpRequest,
    RequestId,
)


def parse_jsonrpc_payload(
    payload: object,
) -> McpRequest | McpNotification | McpParseFailure:
    if isinstance(payload, str):
        try:
            payload = json.loads(payload, parse_constant=_reject_json_constant)
        except (json.JSONDecodeError, ValueError):
            return McpParseFailure(JSONRPC_PARSE_ERROR, "Parse error")
    if not isinstance(payload, Mapping):
        return McpParseFailure(JSONRPC_INVALID_REQUEST, "Invalid Request")
    if payload.get("jsonrpc") != "2.0":
        return McpParseFailure(
            JSONRPC_INVALID_REQUEST, "Invalid Request", _safe_id(payload.get("id"))
        )
    method = payload.get("method")
    if not isinstance(method, str) or not method.strip():
        return McpParseFailure(
            JSONRPC_INVALID_REQUEST, "Invalid Request", _safe_id(payload.get("id"))
        )
    params = payload.get("params", {})
    if not isinstance(params, Mapping):
        return McpParseFailure(
            JSONRPC_INVALID_PARAMS, "Invalid params", _safe_id(payload.get("id"))
        )
    if "id" not in payload:
        return McpNotification(method=method, params=dict(params))
    request_id = payload.get("id")
    if not _valid_id(request_id):
        return McpParseFailure(JSONRPC_INVALID_REQUEST, "Invalid Request")
    return McpRequest(request_id=request_id, method=method, params=dict(params))


def success_response(
    request_id: RequestId, result: Mapping[str, JsonValue]
) -> dict[str, JsonValue]:
    return {"jsonrpc": "2.0", "id": request_id, "result": dict(result)}


def error_response(
    request_id: RequestId | None,
    code: int,
    message: str,
    *,
    data: Mapping[str, JsonValue] | None = None,
) -> dict[str, JsonValue]:
    error: dict[str, JsonValue] = {"code": code, "message": message}
    if data:
        error["data"] = dict(data)
    return {"jsonrpc": "2.0", "id": request_id, "error": error}


def method_not_found(
    request_id: RequestId, message: str = "Method not found"
) -> dict[str, JsonValue]:
    return error_response(request_id, JSONRPC_METHOD_NOT_FOUND, message)


def invalid_params(request_id: RequestId, message: str = "Invalid params") -> dict[str, JsonValue]:
    return error_response(request_id, JSONRPC_INVALID_PARAMS, message)


def internal_error(request_id: RequestId, message: str = "Internal error") -> dict[str, JsonValue]:
    return error_response(request_id, JSONRPC_INTERNAL_ERROR, message)


def _valid_id(value: object) -> bool:
    return (isinstance(value, int) and not isinstance(value, bool)) or isinstance(value, str)


def _safe_id(value: object) -> RequestId | None:
    return value if _valid_id(value) else None


def _reject_json_constant(value: str) -> None:
    raise ValueError(f"invalid JSON constant: {value}")
