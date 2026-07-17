"""Registry and Gate 5.0 fail-closed executor."""

from __future__ import annotations

from collections.abc import Iterable

from .contracts import ToolCall, ToolDescriptor, ToolExecutor, ToolResult
from .descriptors import GATE5_TOOL_DESCRIPTORS
from .validation import SchemaValidationError, validate_arguments


class GateNotReadyExecutor:
    """Gate 5.0 executor: descriptors are discoverable but business handlers are blocked."""

    async def execute(self, call: ToolCall, descriptor: ToolDescriptor) -> ToolResult:
        return ToolResult(
            status="blocked",
            message="该工具已注册，但业务处理器将在后续 Gate 接入",
            tool_name=call.tool_name,
            risk=descriptor.risk,
            error_code="gate_not_ready",
        )


class ToolRegistry:
    def __init__(
        self,
        descriptors: Iterable[ToolDescriptor] = GATE5_TOOL_DESCRIPTORS,
        *,
        executor: ToolExecutor | None = None,
    ) -> None:
        descriptor_map: dict[str, ToolDescriptor] = {}
        for descriptor in descriptors:
            if descriptor.name in descriptor_map:
                raise ValueError(f"duplicate MCP tool descriptor: {descriptor.name}")
            descriptor_map[descriptor.name] = descriptor
        self._descriptors = descriptor_map
        self._executor = executor or GateNotReadyExecutor()

    @property
    def names(self) -> tuple[str, ...]:
        return tuple(self._descriptors)

    @property
    def descriptors(self) -> tuple[ToolDescriptor, ...]:
        return tuple(self._descriptors.values())

    @property
    def pending_confirmation_count(self) -> int:
        return int(getattr(self._executor, "pending_confirmation_count", 0))

    def get(self, name: str) -> ToolDescriptor | None:
        return self._descriptors.get(name)

    def public_tools(self) -> list[dict[str, object]]:
        return [descriptor.public_dict() for descriptor in self._descriptors.values()]

    async def call(self, call: ToolCall) -> ToolResult:
        descriptor = self.get(call.tool_name)
        if descriptor is None:
            raise KeyError(call.tool_name)
        validate_arguments(call.arguments, descriptor.input_schema)
        return await self._executor.execute(call, descriptor)

    async def close_generation(self, generation: int, reason: str) -> None:
        handler = getattr(self._executor, "close_generation", None)
        if handler is None:
            return
        result = handler(generation, reason)
        if hasattr(result, "__await__"):
            await result

    async def close(self) -> None:
        handler = getattr(self._executor, "close", None)
        if handler is None:
            return
        result = handler()
        if hasattr(result, "__await__"):
            await result


__all__ = [
    "GateNotReadyExecutor",
    "SchemaValidationError",
    "ToolRegistry",
]
