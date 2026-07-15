"""Platform-neutral audio ports for the Gate 3 shared pipeline."""

from __future__ import annotations

from collections.abc import Callable
from typing import Protocol

from .models import EncodedAudioPacket, PcmFrame, VoiceActivitySnapshot

PcmFrameSink = Callable[[PcmFrame], bool]


class AudioCapturePort(Protocol):
    def start(self, generation: int, frame_sink: PcmFrameSink) -> None: ...

    def stop(self, generation: int) -> None: ...

    def close(self) -> None: ...


class OpusEncoderPort(Protocol):
    def encode(self, frame: PcmFrame) -> EncodedAudioPacket: ...

    def close(self) -> None: ...


class VoiceActivityDetectorPort(Protocol):
    def observe(self, frame: PcmFrame) -> VoiceActivitySnapshot: ...

    def reset(self, generation: int) -> None: ...


class AudioClock(Protocol):
    def now_ns(self) -> int: ...
