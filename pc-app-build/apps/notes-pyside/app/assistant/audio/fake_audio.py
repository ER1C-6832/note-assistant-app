"""Scriptable fake audio adapters used before real PyAudio is activated."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from ..state import VoiceActivityState
from .models import EncodedAudioPacket, PcmFrame, VoiceActivitySnapshot
from .ports import PcmFrameSink


class AudioCaptureBusyError(RuntimeError):
    pass


class AudioCaptureGenerationError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class FakeCaptureScript:
    frames: tuple[bytes, ...]
    first_timestamp_ns: int = 0
    frame_interval_ns: int = 20_000_000
    fail_on_start: bool = False

    @classmethod
    def from_frames(cls, frames: Iterable[bytes]) -> "FakeCaptureScript":
        return cls(tuple(bytes(frame) for frame in frames))


class ScriptedFakeAudioCapture:
    """A deterministic callback-style capture adapter with generation guards."""

    def __init__(self, script: FakeCaptureScript) -> None:
        self._script = script
        self._active_generation: int | None = None
        self._frame_sink: PcmFrameSink | None = None
        self._next_sequence = 0
        self._closed = False
        self.stale_frame_count = 0

    @property
    def input_device_public_name(self) -> str | None:
        return "Scripted Fake Microphone"

    @property
    def active_generation(self) -> int | None:
        return self._active_generation

    @property
    def is_active(self) -> bool:
        return self._active_generation is not None

    def start(self, generation: int, frame_sink: PcmFrameSink) -> None:
        if self._closed:
            raise RuntimeError("fake capture is closed")
        if self.is_active:
            raise AudioCaptureBusyError("one capture generation is already active")
        if generation < 0:
            raise ValueError("generation cannot be negative")
        if self._script.fail_on_start:
            raise RuntimeError("scripted device open failure")
        self._active_generation = generation
        self._frame_sink = frame_sink
        self._next_sequence = 0

    def emit_next(self) -> bool:
        generation = self._active_generation
        sink = self._frame_sink
        if generation is None or sink is None:
            return False
        if self._next_sequence >= len(self._script.frames):
            return False
        sequence = self._next_sequence
        self._next_sequence += 1
        frame = PcmFrame(
            generation=generation,
            sequence=sequence,
            captured_at_ns=(
                self._script.first_timestamp_ns + sequence * self._script.frame_interval_ns
            ),
            pcm16_le=self._script.frames[sequence],
        )
        return bool(sink(frame))

    def emit_all(self) -> int:
        emitted = 0
        while self.emit_next():
            emitted += 1
        return emitted

    def emit_stale(self, generation: int, payload: bytes = b"stale") -> bool:
        if generation == self._active_generation:
            raise AudioCaptureGenerationError("stale generation must differ from active generation")
        self.stale_frame_count += 1
        return False

    def stop(self, generation: int) -> None:
        if self._active_generation is None:
            return
        if generation != self._active_generation:
            raise AudioCaptureGenerationError("stop generation does not own the active capture")
        self._active_generation = None
        self._frame_sink = None

    def close(self) -> None:
        self._active_generation = None
        self._frame_sink = None
        self._closed = True


class FakeOpusEncoder:
    def __init__(self, *, fail_sequences: Iterable[int] = ()) -> None:
        self._fail_sequences = frozenset(fail_sequences)
        self._closed = False

    def encode(self, frame: PcmFrame) -> EncodedAudioPacket:
        if self._closed:
            raise RuntimeError("fake encoder is closed")
        frame.validate()
        if frame.sequence in self._fail_sequences:
            raise RuntimeError(f"scripted encode failure at frame {frame.sequence}")
        payload = b"FAKE-OPUS\x00" + frame.pcm16_le
        packet = EncodedAudioPacket(
            generation=frame.generation,
            sequence=frame.sequence,
            encoded_at_ns=frame.captured_at_ns + 1,
            payload=payload,
        )
        packet.validate()
        return packet

    def close(self) -> None:
        self._closed = True


class ScriptedVoiceActivityDetector:
    def __init__(self, states: Iterable[VoiceActivityState]) -> None:
        self._states = tuple(states)
        self._index = 0
        self._generation = 0

    def reset(self, generation: int) -> None:
        self._generation = generation
        self._index = 0

    def observe(self, frame: PcmFrame) -> VoiceActivitySnapshot:
        if frame.generation != self._generation:
            raise AudioCaptureGenerationError("VAD received a stale capture generation")
        if not self._states:
            state = VoiceActivityState.WAITING_FOR_SPEECH
        else:
            state = self._states[min(self._index, len(self._states) - 1)]
        self._index += 1
        return VoiceActivitySnapshot(
            generation=frame.generation,
            frame_sequence=frame.sequence,
            state=state,
            peak_abs=max(frame.pcm16_le, default=0),
            rms=float(sum(frame.pcm16_le)) / max(1, len(frame.pcm16_le)),
            elapsed_ms=frame.sequence * 20,
        )
