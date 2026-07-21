"""Real WebSocket transport with private bounded TTS payload delivery."""

from __future__ import annotations

import asyncio

from ..events import TransportFailed
from ..playback.coordinator import PlaybackCoordinator
from ..playback.runtime_events import TtsPlaybackInputEnded, TtsPlaybackStreamStarted
from ..protocol import is_terminal_tts_state
from ..protocol.events import ServerHello, TtsState
from .websocket_transport import (
    RealWebSocketTransport as BaseRealWebSocketTransport,
    WebSocketClosed,
    _safe_error_text,
)


class RealWebSocketTransport(BaseRealWebSocketTransport):
    """Gate 4.2 transport: binary payload bypasses the Runtime event queue."""

    def __init__(
        self, *, playback_coordinator: PlaybackCoordinator | None = None, **kwargs
    ) -> None:
        super().__init__(**kwargs)
        self._playback_coordinator = playback_coordinator or PlaybackCoordinator(
            clock_ns=self._clock.now_ns
        )
        self._downlink_formats = {}
        self._stream_sequences: dict[int, int] = {}
        self._current_streams: dict[int, tuple[int, int, int]] = {}

    @property
    def playback_coordinator(self) -> PlaybackCoordinator:
        return self._playback_coordinator

    async def open(self, generation, runtime_mode, event_sink) -> None:
        await self._playback_coordinator.open_generation(generation, event_sink)
        try:
            await super().open(generation, runtime_mode, event_sink)
        finally:
            await self._playback_coordinator.close_generation(
                generation, "transport_generation_closed"
            )
            self._downlink_formats.pop(generation, None)
            self._stream_sequences.pop(generation, None)
            self._current_streams.pop(generation, None)

    async def _receiver_loop(self, active) -> None:
        try:
            while True:
                message = await active.connection.recv()
                if isinstance(message, str):
                    await self._dispatch_protocol_event(active, self._router.route_text(message))
                    continue
                payload = bytes(message)
                current = self._current_streams.get(active.generation)
                if current is not None:
                    stream_sequence, _playback_generation, _turn_token = current
                    self._playback_coordinator.offer_payload_nowait(
                        connection_generation=active.generation,
                        stream_sequence=stream_sequence,
                        payload=payload,
                        received_at_ns=self._clock.now_ns(),
                    )
                # Runtime receives size metadata only. Raw Opus never enters its queue.
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
            if event.audio_format is not None and event.audio_params_error is None:
                self._downlink_formats[active.generation] = event.audio_format
        elif isinstance(event, TtsState):
            normalized = event.state.strip().lower()
            # Xiaozhi sends `start` before LLM/TTS generation.  Only
            # `sentence_start` is the media boundary immediately preceding the
            # first Opus packet, so the short no-binary watchdog starts here.
            if normalized == "sentence_start" and active.generation not in self._current_streams:
                await self._begin_tts_stream(active, event, now)
            elif is_terminal_tts_state(normalized):
                await self._end_tts_stream(active, normalized, now)
        await super()._dispatch_protocol_event(active, event)

    async def _begin_tts_stream(self, active, event: TtsState, now: int) -> None:
        wire_format = self._downlink_formats.get(active.generation)
        turn_token = active.active_voice_turn_token or active.active_text_turn_token
        if wire_format is None or turn_token is None:
            return
        stream_sequence = self._stream_sequences.get(active.generation, 0) + 1
        self._stream_sequences[active.generation] = stream_sequence
        context = await self._playback_coordinator.begin_stream(
            connection_generation=active.generation,
            stream_sequence=stream_sequence,
            turn_token=turn_token,
            streaming_generation=(
                self._playback_coordinator.streaming_generation_for_turn(turn_token)
            ),
            wire_format=wire_format,
            session_id=event.session_id or active.session_id,
            started_at_ns=now,
        )
        if context is None:
            return
        self._current_streams[active.generation] = (
            context.stream_sequence,
            context.playback_generation,
            context.turn_token,
        )
        await active.event_sink(
            TtsPlaybackStreamStarted(
                at_ns=now,
                connection_generation=active.generation,
                stream_sequence=context.stream_sequence,
                playback_generation=context.playback_generation,
                turn_token=context.turn_token,
                wire_format=context.wire_format,
                streaming_generation=context.streaming_generation,
            )
        )

    async def _end_tts_stream(self, active, state: str, now: int) -> None:
        current = self._current_streams.pop(active.generation, None)
        if current is None:
            return
        stream_sequence, playback_generation, turn_token = current
        accepted = self._playback_coordinator.end_stream_nowait(
            connection_generation=active.generation,
            stream_sequence=stream_sequence,
            reason=f"tts_{state}",
            at_ns=now,
        )
        if not accepted:
            return
        await active.event_sink(
            TtsPlaybackInputEnded(
                at_ns=now,
                connection_generation=active.generation,
                stream_sequence=stream_sequence,
                playback_generation=playback_generation,
                turn_token=turn_token,
                reason=f"tts_{state}",
            )
        )
