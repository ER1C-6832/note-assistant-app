"""Real WebSocket transport variant that exposes raw downlink only to a bounded probe."""

from __future__ import annotations

import asyncio

from ..events import TransportFailed
from ..protocol.events import ServerHello, TtsState
from .downlink_probe import MetadataOnlyDownlinkProbe
from .websocket_transport import (
    RealWebSocketTransport,
    WebSocketClosed,
    _safe_error_text,
)


class ProbingRealWebSocketTransport(RealWebSocketTransport):
    """Gate 4.0 transport: normal Runtime events plus a private binary probe sink."""

    def __init__(self, *, downlink_probe: MetadataOnlyDownlinkProbe, **kwargs) -> None:
        super().__init__(**kwargs)
        self._downlink_probe = downlink_probe

    @property
    def downlink_probe(self) -> MetadataOnlyDownlinkProbe:
        return self._downlink_probe

    async def open(self, generation, runtime_mode, event_sink) -> None:
        await self._downlink_probe.open_generation(generation)
        try:
            await super().open(generation, runtime_mode, event_sink)
        finally:
            await self._downlink_probe.close_generation(generation)

    async def _receiver_loop(self, active) -> None:
        try:
            while True:
                message = await active.connection.recv()
                if isinstance(message, str):
                    await self._dispatch_protocol_event(active, self._router.route_text(message))
                else:
                    payload = bytes(message)
                    self._downlink_probe.offer_packet_nowait(
                        active.generation,
                        payload,
                        self._clock.now_ns(),
                    )
                    # Runtime receives metadata only. Raw payload remains private to the
                    # bounded probe queue and is released after decode observation.
                    await self._dispatch_protocol_event(
                        active,
                        self._router.route_binary(payload),
                    )
        except asyncio.CancelledError:
            raise
        except WebSocketClosed as exc:
            active.close_started = True
            await self._emit_close(
                active,
                code=exc.code,
                reason=exc.reason,
                expected=active.expected_close or exc.code in {1000, 1001},
            )
        except Exception as exc:
            if active.expected_close:
                await self._emit_close(active, code=1000, reason="client_close", expected=True)
                return
            await active.event_sink(
                TransportFailed(
                    at_ns=self._clock.now_ns(),
                    generation=active.generation,
                    message=_safe_error_text(exc),
                )
            )

    async def _dispatch_protocol_event(self, active, event) -> None:
        now = self._clock.now_ns()
        if isinstance(event, ServerHello):
            self._downlink_probe.observe_server_hello(
                active.generation,
                event.audio_format,
                event.audio_params_error,
            )
        elif isinstance(event, TtsState):
            self._downlink_probe.observe_tts_state(
                active.generation,
                event.state,
                now,
            )
        await super()._dispatch_protocol_event(active, event)
