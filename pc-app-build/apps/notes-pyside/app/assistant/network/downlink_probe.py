"""Metadata-only Gate 4.0 downlink protocol probe.

The probe transiently owns bounded binary packets long enough to validate that the
negotiated Opus stream is decodable. Public snapshots never expose or persist payloads.
"""

from __future__ import annotations

import asyncio
import statistics
from dataclasses import dataclass
from typing import Protocol

from ..protocol.events import DownlinkAudioFormat
from ..protocol.transcript import is_terminal_tts_state


@dataclass(frozen=True, slots=True)
class ProbeDecodeResult:
    sample_rate_hz: int
    channels: int
    sample_count: int


class ProbeDecoder(Protocol):
    def decode(
        self,
        payload: bytes,
        audio_format: DownlinkAudioFormat,
    ) -> ProbeDecodeResult | None: ...

    def close(self) -> None: ...


class PyAvOpusProbeDecoder:
    """Decode only enough audio to prove the real downlink payload is usable."""

    def __init__(self) -> None:
        self._codec = None

    def decode(
        self,
        payload: bytes,
        audio_format: DownlinkAudioFormat,
    ) -> ProbeDecodeResult | None:
        if audio_format.codec != "opus":
            raise ValueError(f"unsupported codec: {audio_format.codec}")
        try:
            import av
        except ImportError as exc:  # pragma: no cover - exercised by real environment
            raise RuntimeError("av is not installed") from exc

        if self._codec is None:
            self._codec = av.CodecContext.create("opus", "r")
        frames = self._codec.decode(av.Packet(payload))
        if not frames:
            return None
        sample_count = sum(int(frame.samples) for frame in frames)
        sample_rate = int(frames[0].sample_rate or audio_format.sample_rate_hz)
        layout = frames[0].layout
        channels = len(layout.channels) if layout is not None else audio_format.channels
        return ProbeDecodeResult(
            sample_rate_hz=sample_rate,
            channels=channels,
            sample_count=sample_count,
        )

    def close(self) -> None:
        self._codec = None


@dataclass(frozen=True, slots=True)
class DownlinkProbeSnapshot:
    generation: int | None
    audio_format: DownlinkAudioFormat | None
    audio_params_error: str | None
    tts_state_sequence: tuple[str, ...]
    observed_terminal: bool
    binary_packet_count: int
    packet_size_min: int | None
    packet_size_max: int | None
    packet_size_median: float | None
    packet_arrival_interval_ms_sample: tuple[float, ...]
    first_binary_relative_to_terminal: str | None
    last_binary_relative_to_terminal: str | None
    decoded: ProbeDecodeResult | None
    decode_error: str | None
    queue_overflow_count: int
    unarmed_binary_count: int
    stale_event_count: int
    payload_persisted: bool
    secrets_redacted: bool
    task_running: bool

    def as_public_dict(self) -> dict[str, object]:
        return {
            "generation": self.generation,
            "server_hello_audio_format": (
                self.audio_format.as_public_dict() if self.audio_format else None
            ),
            "audio_params_error": self.audio_params_error,
            "observed_tts_state_sequence": list(self.tts_state_sequence),
            "observed_terminal": self.observed_terminal,
            "binary_packet_count": self.binary_packet_count,
            "packet_size_bytes": {
                "min": self.packet_size_min,
                "max": self.packet_size_max,
                "median": self.packet_size_median,
            },
            "packet_arrival_interval_ms_sample": list(self.packet_arrival_interval_ms_sample),
            "first_binary_relative_to_tts_terminal": self.first_binary_relative_to_terminal,
            "last_binary_relative_to_tts_terminal": self.last_binary_relative_to_terminal,
            "pyav_decode_success": self.decoded is not None,
            "decoded_sample_rate_hz": (self.decoded.sample_rate_hz if self.decoded else None),
            "decoded_channels": self.decoded.channels if self.decoded else None,
            "decoded_sample_count": self.decoded.sample_count if self.decoded else 0,
            "decode_error": self.decode_error,
            "probe_queue_overflow_count": self.queue_overflow_count,
            "unarmed_binary_count": self.unarmed_binary_count,
            "stale_event_count": self.stale_event_count,
            "payload_persisted": self.payload_persisted,
            "secrets_redacted": self.secrets_redacted,
            "probe_task_running": self.task_running,
        }


@dataclass(frozen=True, slots=True)
class _ProbePacket:
    generation: int
    stream_sequence: int
    packet_sequence: int
    received_at_ns: int
    payload: bytes


_STOP = object()


class MetadataOnlyDownlinkProbe:
    """Bounded non-blocking sink for Gate 4.0 protocol observations."""

    def __init__(
        self,
        *,
        decoder: ProbeDecoder | None = None,
        packet_capacity: int = 128,
        close_timeout_seconds: float = 3.0,
    ) -> None:
        if packet_capacity <= 0:
            raise ValueError("packet_capacity must be positive")
        self._decoder = decoder or PyAvOpusProbeDecoder()
        self._packet_capacity = packet_capacity
        self._close_timeout_seconds = close_timeout_seconds
        self._queue: asyncio.Queue[_ProbePacket | object] | None = None
        self._worker: asyncio.Task[None] | None = None
        self._generation: int | None = None
        self._accepting = False
        self._audio_format: DownlinkAudioFormat | None = None
        self._audio_params_error: str | None = None
        self._stream_sequence = 0
        self._active_stream_sequence: int | None = None
        self._active_stream_terminal_seen = False
        self._packet_sequence = 0
        self._tts_states: list[str] = []
        self._terminal_at_ns: int | None = None
        self._binary_times_ns: list[int] = []
        self._packet_sizes: list[int] = []
        self._arrival_intervals_ms: list[float] = []
        self._decoded: ProbeDecodeResult | None = None
        self._decode_error: str | None = None
        self._queue_overflow_count = 0
        self._unarmed_binary_count = 0
        self._stale_event_count = 0

    @property
    def task_running(self) -> bool:
        return self._worker is not None and not self._worker.done()

    async def open_generation(self, generation: int) -> None:
        if generation <= 0:
            raise ValueError("generation must be positive")
        if self.task_running:
            raise RuntimeError("downlink probe generation already active")
        self._reset(generation)
        self._queue = asyncio.Queue(maxsize=self._packet_capacity)
        self._accepting = True
        self._worker = asyncio.create_task(
            self._worker_loop(),
            name=f"assistant-downlink-probe-{generation}",
        )

    async def close_generation(self, generation: int) -> None:
        if generation != self._generation:
            self._stale_event_count += 1
            return
        self._accepting = False
        queue = self._queue
        worker = self._worker
        if queue is not None and worker is not None:
            try:
                await asyncio.wait_for(queue.join(), timeout=self._close_timeout_seconds)
                await queue.put(_STOP)
                await asyncio.wait_for(worker, timeout=self._close_timeout_seconds)
            except TimeoutError:
                worker.cancel()
                await asyncio.gather(worker, return_exceptions=True)
            finally:
                self._decoder.close()
        self._worker = None
        self._queue = None

    def observe_server_hello(
        self,
        generation: int,
        audio_format: DownlinkAudioFormat | None,
        audio_params_error: str | None,
    ) -> None:
        if generation != self._generation:
            self._stale_event_count += 1
            return
        self._audio_format = audio_format
        self._audio_params_error = audio_params_error

    def observe_tts_state(self, generation: int, state: str, at_ns: int) -> None:
        if generation != self._generation:
            self._stale_event_count += 1
            return
        normalized = state.strip().lower() or "unknown"
        terminal = is_terminal_tts_state(normalized)
        if not terminal and (
            self._active_stream_sequence is None or self._active_stream_terminal_seen
        ):
            self._stream_sequence += 1
            self._active_stream_sequence = self._stream_sequence
            self._active_stream_terminal_seen = False
            self._packet_sequence = 0
        stream_sequence = self._active_stream_sequence or self._stream_sequence
        self._tts_states.append(f"{stream_sequence}:{normalized}")
        if terminal and self._active_stream_sequence is not None:
            self._terminal_at_ns = at_ns
            self._active_stream_terminal_seen = True

    def offer_packet_nowait(self, generation: int, payload: bytes, at_ns: int) -> bool:
        if generation != self._generation:
            self._stale_event_count += 1
            return False
        if not self._accepting:
            self._unarmed_binary_count += 1
            return False

        # Count all wire binary observations, including fail-closed unarmed packets,
        # without exposing their contents. This preserves the terminal ordering sample.
        self._packet_sizes.append(len(payload))
        if self._binary_times_ns:
            self._arrival_intervals_ms.append(
                max(0.0, (at_ns - self._binary_times_ns[-1]) / 1_000_000)
            )
        self._binary_times_ns.append(at_ns)

        if self._active_stream_sequence is None:
            self._unarmed_binary_count += 1
            return False
        queue = self._queue
        if queue is None:
            self._unarmed_binary_count += 1
            return False

        self._packet_sequence += 1
        packet = _ProbePacket(
            generation=generation,
            stream_sequence=self._active_stream_sequence,
            packet_sequence=self._packet_sequence,
            received_at_ns=at_ns,
            payload=bytes(payload),
        )
        try:
            queue.put_nowait(packet)
        except asyncio.QueueFull:
            self._queue_overflow_count += 1
            return False
        return True

    def snapshot(self) -> DownlinkProbeSnapshot:
        packet_size_min = min(self._packet_sizes) if self._packet_sizes else None
        packet_size_max = max(self._packet_sizes) if self._packet_sizes else None
        packet_size_median = (
            float(statistics.median(self._packet_sizes)) if self._packet_sizes else None
        )
        first_relative = self._relative_to_terminal(
            self._binary_times_ns[0] if self._binary_times_ns else None
        )
        last_relative = self._relative_to_terminal(
            self._binary_times_ns[-1] if self._binary_times_ns else None
        )
        return DownlinkProbeSnapshot(
            generation=self._generation,
            audio_format=self._audio_format,
            audio_params_error=self._audio_params_error,
            tts_state_sequence=tuple(self._tts_states),
            observed_terminal=self._terminal_at_ns is not None,
            binary_packet_count=len(self._packet_sizes),
            packet_size_min=packet_size_min,
            packet_size_max=packet_size_max,
            packet_size_median=packet_size_median,
            packet_arrival_interval_ms_sample=tuple(self._arrival_intervals_ms[:16]),
            first_binary_relative_to_terminal=first_relative,
            last_binary_relative_to_terminal=last_relative,
            decoded=self._decoded,
            decode_error=self._decode_error,
            queue_overflow_count=self._queue_overflow_count,
            unarmed_binary_count=self._unarmed_binary_count,
            stale_event_count=self._stale_event_count,
            payload_persisted=False,
            secrets_redacted=True,
            task_running=self.task_running,
        )

    async def _worker_loop(self) -> None:
        assert self._queue is not None
        queue = self._queue
        while True:
            item = await queue.get()
            try:
                if item is _STOP:
                    return
                assert isinstance(item, _ProbePacket)
                if self._decoded is not None or self._audio_format is None:
                    continue
                try:
                    result = await asyncio.to_thread(
                        self._decoder.decode,
                        item.payload,
                        self._audio_format,
                    )
                except Exception as exc:
                    # Decoder failure is probe metadata, not a transport crash.
                    self._decode_error = _safe_error_text(exc)
                    continue
                if result is not None:
                    self._decoded = result
                    self._decode_error = None
            finally:
                queue.task_done()

    def _relative_to_terminal(self, at_ns: int | None) -> str | None:
        if at_ns is None or self._terminal_at_ns is None:
            return None
        return "before" if at_ns <= self._terminal_at_ns else "after"

    def _reset(self, generation: int) -> None:
        self._generation = generation
        self._audio_format = None
        self._audio_params_error = None
        self._stream_sequence = 0
        self._active_stream_sequence = None
        self._active_stream_terminal_seen = False
        self._packet_sequence = 0
        self._tts_states.clear()
        self._terminal_at_ns = None
        self._binary_times_ns.clear()
        self._packet_sizes.clear()
        self._arrival_intervals_ms.clear()
        self._decoded = None
        self._decode_error = None
        self._queue_overflow_count = 0
        self._unarmed_binary_count = 0
        self._stale_event_count = 0


def _safe_error_text(exc: Exception) -> str:
    text = str(exc).strip() or type(exc).__name__
    text = text.replace("\r", " ").replace("\n", " ")
    return text[:240]
