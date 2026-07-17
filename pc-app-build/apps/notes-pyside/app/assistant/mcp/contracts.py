"""Private typed contracts for the in-process Gate 5 MCP runtime."""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass, field
from enum import Enum
from typing import Protocol, TypeAlias

JsonScalar: TypeAlias = str | int | float | bool | None
JsonValue: TypeAlias = JsonScalar | list["JsonValue"] | dict[str, "JsonValue"]
RequestId: TypeAlias = str | int


class ToolRisk(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    HIGH_GATEWAY = "high_gateway"


class ConfirmationPolicy(str, Enum):
    NEVER = "never"
    CONDITIONAL = "conditional"
    ALWAYS = "always"
    PENDING_ID = "pending_id"


@dataclass(frozen=True, slots=True)
class ToolDescriptor:
    name: str
    description: str
    input_schema: Mapping[str, JsonValue]
    risk: ToolRisk
    mutates: bool
    confirmation: ConfirmationPolicy

    def public_dict(self) -> dict[str, JsonValue]:
        return {
            "name": self.name,
            "description": self.description,
            "inputSchema": dict(self.input_schema),
            "risk": self.risk.value,
            "mutates": self.mutates,
            "confirmation": self.confirmation.value,
        }


@dataclass(frozen=True, slots=True)
class McpRequest:
    request_id: RequestId
    method: str
    params: Mapping[str, JsonValue] = field(repr=False)


@dataclass(frozen=True, slots=True)
class McpNotification:
    method: str
    params: Mapping[str, JsonValue] = field(repr=False)


@dataclass(frozen=True, slots=True)
class McpParseFailure:
    code: int
    message: str
    request_id: RequestId | None = None


@dataclass(frozen=True, slots=True)
class ToolCall:
    request_id: RequestId
    tool_name: str
    arguments: Mapping[str, JsonValue] = field(repr=False)


@dataclass(frozen=True, slots=True)
class ToolResult:
    status: str
    message: str
    tool_name: str
    risk: ToolRisk
    requires_confirmation: bool = False
    confirmation_id: str | None = None
    affected_note_ids: tuple[int, ...] = ()
    affected_tags: tuple[str, ...] = ()
    result: Mapping[str, JsonValue] = field(default_factory=dict, repr=False)
    error_code: str | None = None

    def public_dict(self) -> dict[str, JsonValue]:
        payload: dict[str, JsonValue] = {
            "status": self.status,
            "message": self.message,
            "tool_name": self.tool_name,
            "risk": self.risk.value,
            "requires_confirmation": self.requires_confirmation,
            "confirmation_id": self.confirmation_id,
            "affected_note_ids": list(self.affected_note_ids),
            "affected_tags": list(self.affected_tags),
            "result": dict(self.result),
        }
        if self.error_code is not None:
            payload["error_code"] = self.error_code
        return payload


@dataclass(frozen=True, slots=True)
class McpLifecycleSummary:
    request_id_hash: str
    method: str
    tool_name: str | None
    status: str
    risk: str | None
    duration_ms: float

    def public_dict(self) -> dict[str, JsonValue]:
        return {
            "request_id_hash": self.request_id_hash,
            "method": self.method,
            "tool_name": self.tool_name,
            "status": self.status,
            "risk": self.risk,
            "duration_ms": self.duration_ms,
        }


McpResponseSink: TypeAlias = Callable[[dict[str, JsonValue]], Awaitable[None]]
McpLifecycleSink: TypeAlias = Callable[[McpLifecycleSummary], Awaitable[None]]


class ToolExecutor(Protocol):
    async def execute(self, call: ToolCall, descriptor: ToolDescriptor) -> ToolResult: ...
