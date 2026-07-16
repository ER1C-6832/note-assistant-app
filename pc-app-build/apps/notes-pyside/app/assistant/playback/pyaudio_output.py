"""PyAudio output adapter scaffold; real device activation belongs to Gate 4.2."""

from __future__ import annotations

from .models import TtsStreamContext
from .ports import ConsumedCallback, DrainedCallback, PcmPlaybackSource


class PyAudioOutputAdapter:
    """Fail-closed scaffold that never opens a device during Gate 4.1 tests."""

    def __init__(self) -> None:
        self._running = False
        self._device_public_name: str | None = None

    @property
    def device_public_name(self) -> str | None:
        return self._device_public_name

    @property
    def running(self) -> bool:
        return self._running

    async def open(
        self,
        context: TtsStreamContext,
        source: PcmPlaybackSource,
        consumed_callback: ConsumedCallback,
        drained_callback: DrainedCallback,
    ) -> None:
        del context, source, consumed_callback, drained_callback
        raise RuntimeError("PyAudio output is not activated before Gate 4.2")

    async def start(self) -> None:
        raise RuntimeError("PyAudio output is not activated before Gate 4.2")

    async def stop(self) -> None:
        self._running = False

    async def close(self) -> None:
        self._running = False
