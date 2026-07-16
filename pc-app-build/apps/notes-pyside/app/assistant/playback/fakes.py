"""Deterministic fake decoder and output for Gate 4.1 acceptance."""

from __future__ import annotations

import asyncio
from collections.abc import Callable

from .models import (
    DecodedPcmChunk,
    EncodedDownlinkPacket,
    PcmAudioFormat,
    TtsStreamContext,
)
from .ports import ConsumedCallback, DrainedCallback, PcmPlaybackSource


class DeterministicFakeOpusDecoder:
    def __init__(
        self,
        *,
        pcm_format: PcmAudioFormat | None = None,
        sample_frames_per_packet: int = 960,
        corrupt_prefix: bytes = b"CORRUPT",
        emit_audio: bool = True,
        clock_ns: Callable[[], int] | None = None,
    ) -> None:
        self.pcm_format = pcm_format or PcmAudioFormat(48_000, 2)
        self.sample_frames_per_packet = sample_frames_per_packet
        self.corrupt_prefix = corrupt_prefix
        self.emit_audio = emit_audio
        self._clock_ns = clock_ns or (lambda: 0)
        self.closed = False

    def decode(self, packet: EncodedDownlinkPacket) -> tuple[DecodedPcmChunk, ...]:
        if self.closed:
            raise RuntimeError("decoder is closed")
        if packet.payload.startswith(self.corrupt_prefix):
            raise ValueError("corrupt opus packet")
        if not self.emit_audio:
            return ()
        frame_size = self.pcm_format.frame_size_bytes
        byte_count = self.sample_frames_per_packet * frame_size
        seed = packet.packet_sequence % 251 + 1
        payload = bytes([seed]) * byte_count
        return (
            DecodedPcmChunk(
                pcm_format=self.pcm_format,
                payload=payload,
                decoded_at_ns=self._clock_ns(),
            ),
        )

    def flush(self) -> tuple[DecodedPcmChunk, ...]:
        if self.closed:
            return ()
        return ()

    def close(self) -> None:
        self.closed = True


class GateControlledFakeAudioOutput:
    """Fake callback output that consumes exact PCM and reports physical drain."""

    def __init__(
        self,
        *,
        chunk_bytes: int = 3_840,
        consume_gate: asyncio.Event | None = None,
        device_public_name: str = "Fake output",
    ) -> None:
        if chunk_bytes <= 0:
            raise ValueError("chunk_bytes must be positive")
        self._chunk_bytes = chunk_bytes
        self._consume_gate = consume_gate
        self._device_public_name = device_public_name
        self._source: PcmPlaybackSource | None = None
        self._consumed_callback: ConsumedCallback | None = None
        self._drained_callback: DrainedCallback | None = None
        self._task: asyncio.Task[None] | None = None
        self._stopping = False
        self.open_calls = 0
        self.start_calls = 0
        self.stop_calls = 0
        self.close_calls = 0
        self.consumed_bytes = 0

    @property
    def device_public_name(self) -> str | None:
        return self._device_public_name

    @property
    def running(self) -> bool:
        return self._task is not None and not self._task.done()

    async def open(
        self,
        context: TtsStreamContext,
        source: PcmPlaybackSource,
        consumed_callback: ConsumedCallback,
        drained_callback: DrainedCallback,
    ) -> None:
        del context
        if self._source is not None:
            raise RuntimeError("fake output already open")
        self.open_calls += 1
        self._source = source
        self._consumed_callback = consumed_callback
        self._drained_callback = drained_callback

    async def start(self) -> None:
        if self._source is None:
            raise RuntimeError("fake output is not open")
        if self.running:
            return
        self.start_calls += 1
        self._stopping = False
        self._task = asyncio.create_task(self._pump(), name="assistant-fake-playback-output")

    async def stop(self) -> None:
        self.stop_calls += 1
        self._stopping = True
        task = self._task
        if task is not None and not task.done() and task is not asyncio.current_task():
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
        self._task = None

    async def close(self) -> None:
        self.close_calls += 1
        await self.stop()
        self._source = None
        self._consumed_callback = None
        self._drained_callback = None

    async def _pump(self) -> None:
        assert self._source is not None
        assert self._consumed_callback is not None
        assert self._drained_callback is not None
        try:
            while not self._stopping:
                if self._consume_gate is not None:
                    await self._consume_gate.wait()
                payload = self._source.consume(self._chunk_bytes)
                if payload:
                    self.consumed_bytes += len(payload)
                    sample_frames = len(payload) // self._source.pcm_format.frame_size_bytes
                    self._consumed_callback(len(payload), sample_frames)
                    await asyncio.sleep(0)
                    continue
                if self._source.terminal_and_empty:
                    self._drained_callback()
                    return
                await asyncio.sleep(0)
        except asyncio.CancelledError:
            raise
