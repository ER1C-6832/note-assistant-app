"""Playback ports separating decode, buffering, and output ownership."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Protocol

from .models import (
    DecodedPcmChunk,
    EncodedDownlinkPacket,
    PcmAudioFormat,
    PlaybackSignal,
    TtsStreamContext,
)

PlaybackEventSink = Callable[[PlaybackSignal], Awaitable[None]]
ConsumedCallback = Callable[[int, int], None]
DrainedCallback = Callable[[], None]
RenderReferenceCallback = Callable[[int, PcmAudioFormat, bytes, int], None]


class OpusDecoderPort(Protocol):
    @property
    def pcm_format(self) -> PcmAudioFormat: ...

    def decode(self, packet: EncodedDownlinkPacket) -> tuple[DecodedPcmChunk, ...]: ...

    def flush(self) -> tuple[DecodedPcmChunk, ...]: ...

    def close(self) -> None: ...


class PcmPlaybackSource(Protocol):
    @property
    def pcm_format(self) -> PcmAudioFormat: ...

    @property
    def terminal_and_empty(self) -> bool: ...

    @property
    def buffered_bytes(self) -> int: ...

    @property
    def underflow_count(self) -> int: ...

    def consume(self, maximum_bytes: int) -> bytes: ...


class AudioOutputPort(Protocol):
    @property
    def device_public_name(self) -> str | None: ...

    @property
    def running(self) -> bool: ...

    async def open(
        self,
        context: TtsStreamContext,
        source: PcmPlaybackSource,
        consumed_callback: ConsumedCallback,
        drained_callback: DrainedCallback,
    ) -> None: ...

    async def start(self) -> None: ...

    async def stop(self) -> None: ...

    async def close(self) -> None: ...
