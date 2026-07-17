"""Fake and Real transport adapters that attach the private Gate 5 MCP coordinator."""

from __future__ import annotations

import asyncio
import json

from ..events import ProtocolMessageObserved
from ..network.playback_websocket_transport import (
    RealWebSocketTransport as PlaybackRealWebSocketTransport,
)
from ..protocol.events import ServerHello
from ..testing.scripted_transport import ScriptedFakeTransport
from .constants import MCP_MAX_OUTER_MESSAGE_BYTES
from .contracts import JsonValue, McpLifecycleSummary
from .coordinator import McpCoordinator
from .jsonrpc import error_response
from .router import McpAwareXiaozhiMessageRouter, PrivateMcpEnvelope


class McpRealWebSocketTransport(PlaybackRealWebSocketTransport):
    """Gate 5.0 Real transport preserving the existing single sender queue."""

    def __init__(self, *, mcp_coordinator: McpCoordinator | None = None, **kwargs) -> None:
        kwargs.setdefault("message_router", McpAwareXiaozhiMessageRouter())
        super().__init__(**kwargs)
        self._mcp_coordinator = mcp_coordinator or McpCoordinator()

    @property
    def mcp_coordinator(self) -> McpCoordinator:
        return self._mcp_coordinator

    async def open(self, generation, runtime_mode, event_sink) -> None:
        async def response_sink(payload: dict[str, JsonValue]) -> None:
            await self._send_mcp_response(generation, payload)

        async def lifecycle_sink(summary: McpLifecycleSummary) -> None:
            await event_sink(
                ProtocolMessageObserved(
                    at_ns=self._clock.now_ns(),
                    generation=generation,
                    event_name="McpLifecycleObserved",
                    message_type="mcp",
                    session_id=None,
                    raw_json_redacted=json.dumps(
                        summary.public_dict(),
                        ensure_ascii=False,
                        separators=(",", ":"),
                        sort_keys=True,
                    ),
                )
            )

        await self._mcp_coordinator.open_generation(
            generation,
            response_sink=response_sink,
            lifecycle_sink=lifecycle_sink,
        )
        try:
            await super().open(generation, runtime_mode, event_sink)
        finally:
            await self._mcp_coordinator.close_generation(generation, "transport_generation_closed")

    async def _dispatch_protocol_event(self, active, event) -> None:
        if isinstance(event, PrivateMcpEnvelope):
            if event.preflight_error_code is not None:
                await self._send_mcp_response(
                    active.generation,
                    error_response(
                        None,
                        event.preflight_error_code,
                        event.preflight_error_message or "Invalid MCP request",
                    ),
                )
                return
            session_id = event.session_id or active.session_id or ""
            submission = self._mcp_coordinator.submit_nowait(
                active.generation,
                session_id,
                event.payload,
            )
            await active.event_sink(
                ProtocolMessageObserved(
                    at_ns=self._clock.now_ns(),
                    generation=active.generation,
                    event_name=(
                        "McpEnvelopeAccepted" if submission.accepted else "McpEnvelopeRejected"
                    ),
                    message_type="mcp",
                    session_id=None,
                    raw_json_redacted=json.dumps(
                        {
                            "accepted": submission.accepted,
                            "notification": submission.notification,
                            "reason": submission.reason,
                        },
                        separators=(",", ":"),
                        sort_keys=True,
                    ),
                )
            )
            if submission.immediate_response is not None:
                await self._send_mcp_response(active.generation, submission.immediate_response)
            return
        await super()._dispatch_protocol_event(active, event)
        if isinstance(event, ServerHello) and active.session_id:
            self._mcp_coordinator.bind_session(active.generation, active.session_id)

    async def _send_mcp_response(self, generation: int, payload: dict[str, JsonValue]) -> None:
        active = await self._get_active(generation)
        if active is None or not active.session_id:
            raise RuntimeError("MCP response generation is no longer active")
        wire = self._builder.mcp(active.session_id, payload)
        if len(wire.encode("utf-8")) > MCP_MAX_OUTER_MESSAGE_BYTES:
            raise RuntimeError("MCP response exceeds outer message budget")
        await self._enqueue_and_wait(active, wire)


class McpScriptedFakeTransport(ScriptedFakeTransport):
    """Scripted Fake transport using the exact same registry and coordinator."""

    def __init__(self, *, mcp_coordinator: McpCoordinator | None = None, **kwargs) -> None:
        super().__init__(**kwargs)
        self.mcp_coordinator = mcp_coordinator or McpCoordinator()
        self._mcp_router = McpAwareXiaozhiMessageRouter()
        self.mcp_responses: list[dict[str, JsonValue]] = []
        self.mcp_lifecycle: list[dict[str, JsonValue]] = []
        self._mcp_response_changed = asyncio.Event()

    async def open(self, generation, runtime_mode, event_sink) -> None:
        await super().open(generation, runtime_mode, event_sink)
        if not self.is_open or self.active_generation != generation or not self.session_id:
            return

        async def response_sink(payload: dict[str, JsonValue]) -> None:
            self.mcp_responses.append(payload)
            self._mcp_response_changed.set()

        async def lifecycle_sink(summary: McpLifecycleSummary) -> None:
            public = summary.public_dict()
            self.mcp_lifecycle.append(public)
            await event_sink(
                ProtocolMessageObserved(
                    at_ns=self.clock.now_ns(),
                    generation=generation,
                    event_name="McpLifecycleObserved",
                    message_type="mcp",
                    session_id=None,
                    raw_json_redacted=json.dumps(
                        public,
                        ensure_ascii=False,
                        separators=(",", ":"),
                        sort_keys=True,
                    ),
                )
            )

        await self.mcp_coordinator.open_generation(
            generation,
            response_sink=response_sink,
            lifecycle_sink=lifecycle_sink,
        )
        self.mcp_coordinator.bind_session(generation, self.session_id)

    async def receive_mcp(
        self,
        payload: object,
        *,
        generation: int | None = None,
        session_id: str | None = None,
    ) -> bool:
        active_generation = generation or self.active_generation
        active_session = session_id or self.session_id
        if active_generation is None or active_session is None:
            raise RuntimeError("scripted MCP transport is not open")
        wire = self.message_builder.mcp(active_session, payload)
        event = self._mcp_router.route_text(wire)
        if not isinstance(event, PrivateMcpEnvelope):
            return False
        if event.preflight_error_code is not None:
            self.mcp_responses.append(
                error_response(
                    None,
                    event.preflight_error_code,
                    event.preflight_error_message or "Invalid MCP request",
                )
            )
            self._mcp_response_changed.set()
            return False
        submission = self.mcp_coordinator.submit_nowait(
            active_generation,
            event.session_id or active_session,
            event.payload,
        )
        if submission.immediate_response is not None:
            self.mcp_responses.append(submission.immediate_response)
            self._mcp_response_changed.set()
        return submission.accepted

    async def wait_for_mcp_responses(
        self, count: int, *, timeout_seconds: float = 2.0
    ) -> tuple[dict[str, JsonValue], ...]:
        async def wait() -> None:
            while len(self.mcp_responses) < count:
                self._mcp_response_changed.clear()
                if len(self.mcp_responses) >= count:
                    break
                await self._mcp_response_changed.wait()

        await asyncio.wait_for(wait(), timeout=timeout_seconds)
        return tuple(self.mcp_responses)

    async def close(self, generation: int, reason: str, event_sink) -> None:
        await self.mcp_coordinator.close_generation(generation, reason)
        await super().close(generation, reason, event_sink)
