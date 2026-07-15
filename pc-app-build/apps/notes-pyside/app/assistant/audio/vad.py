"""Local energy-based VAD used by Gate 3.3 streaming conversation."""

from __future__ import annotations

import math
import struct
from dataclasses import dataclass

from ..state import VoiceActivityState
from .models import DEFAULT_FRAME_DURATION_MS, PcmFrame, VoiceActivitySnapshot


@dataclass(frozen=True, slots=True)
class EnergyVadConfig:
    warmup_ms: int = 300
    min_speech_ms: int = 240
    end_silence_ms: int = 700
    no_speech_timeout_ms: int = 8_000
    min_rms_threshold: float = 180.0
    min_peak_threshold: int = 700
    rms_noise_multiplier: float = 2.5
    peak_noise_multiplier: float = 2.0
    speech_trigger_frames: int = 3

    def validate(self) -> None:
        if self.warmup_ms < 0:
            raise ValueError("warmup_ms cannot be negative")
        if self.min_speech_ms <= 0 or self.end_silence_ms <= 0:
            raise ValueError("speech and silence windows must be positive")
        if self.no_speech_timeout_ms < self.warmup_ms + DEFAULT_FRAME_DURATION_MS:
            raise ValueError("no_speech_timeout_ms is too small")
        if self.speech_trigger_frames <= 0:
            raise ValueError("speech_trigger_frames must be positive")


class EnergyVoiceActivityDetector:
    """Adaptive RMS/peak VAD with deterministic frame-based state transitions."""

    def __init__(self, config: EnergyVadConfig | None = None) -> None:
        self._config = config or EnergyVadConfig()
        self._config.validate()
        self._generation = 0
        self._frame_count = 0
        self._warmup_rms_total = 0.0
        self._warmup_peak = 0
        self._warmup_frames = max(0, self._config.warmup_ms // DEFAULT_FRAME_DURATION_MS)
        self._min_speech_frames = max(1, self._config.min_speech_ms // DEFAULT_FRAME_DURATION_MS)
        self._end_silence_frames = max(1, self._config.end_silence_ms // DEFAULT_FRAME_DURATION_MS)
        self._timeout_frames = max(
            1, self._config.no_speech_timeout_ms // DEFAULT_FRAME_DURATION_MS
        )
        self._candidate_frames = 0
        self._speech_frames = 0
        self._silence_frames = 0
        self._speech_started = False
        self._terminal_state: VoiceActivityState | None = None

    def reset(self, generation: int) -> None:
        if generation < 0:
            raise ValueError("VAD generation cannot be negative")
        self._generation = generation
        self._frame_count = 0
        self._warmup_rms_total = 0.0
        self._warmup_peak = 0
        self._candidate_frames = 0
        self._speech_frames = 0
        self._silence_frames = 0
        self._speech_started = False
        self._terminal_state = None

    def observe(self, frame: PcmFrame) -> VoiceActivitySnapshot:
        if frame.generation != self._generation:
            raise ValueError("VAD received a stale capture generation")
        frame.validate()
        peak, rms = _measure_pcm16(frame.pcm16_le)
        self._frame_count += 1
        elapsed_ms = self._frame_count * DEFAULT_FRAME_DURATION_MS

        if self._terminal_state is not None:
            return self._snapshot(frame, self._terminal_state, peak, rms, elapsed_ms)

        if self._frame_count <= self._warmup_frames:
            self._warmup_rms_total += rms
            self._warmup_peak = max(self._warmup_peak, peak)
            return self._snapshot(frame, VoiceActivityState.WARMUP, peak, rms, elapsed_ms)

        noise_rms = self._warmup_rms_total / max(1, self._warmup_frames)
        rms_threshold = max(
            self._config.min_rms_threshold,
            noise_rms * self._config.rms_noise_multiplier,
        )
        peak_threshold = max(
            self._config.min_peak_threshold,
            int(self._warmup_peak * self._config.peak_noise_multiplier),
        )
        speech_like = rms >= rms_threshold or peak >= peak_threshold

        if not self._speech_started:
            if self._frame_count >= self._timeout_frames:
                self._terminal_state = VoiceActivityState.NO_SPEECH_TIMEOUT
                return self._snapshot(frame, self._terminal_state, peak, rms, elapsed_ms)
            if speech_like:
                self._candidate_frames += 1
            else:
                self._candidate_frames = 0
            if self._candidate_frames >= self._config.speech_trigger_frames:
                self._speech_started = True
                self._speech_frames = self._candidate_frames
                self._silence_frames = 0
                return self._snapshot(
                    frame, VoiceActivityState.SPEECH_DETECTED, peak, rms, elapsed_ms
                )
            return self._snapshot(
                frame, VoiceActivityState.WAITING_FOR_SPEECH, peak, rms, elapsed_ms
            )

        if speech_like:
            self._speech_frames += 1
            self._silence_frames = 0
        else:
            self._silence_frames += 1

        if (
            self._speech_frames >= self._min_speech_frames
            and self._silence_frames >= self._end_silence_frames
        ):
            self._terminal_state = VoiceActivityState.END_OF_SPEECH
            return self._snapshot(frame, self._terminal_state, peak, rms, elapsed_ms)
        return self._snapshot(frame, VoiceActivityState.SPEECH_ACTIVE, peak, rms, elapsed_ms)

    def _snapshot(
        self,
        frame: PcmFrame,
        state: VoiceActivityState,
        peak: int,
        rms: float,
        elapsed_ms: int,
    ) -> VoiceActivitySnapshot:
        return VoiceActivitySnapshot(
            generation=frame.generation,
            frame_sequence=frame.sequence,
            state=state,
            peak_abs=peak,
            rms=rms,
            elapsed_ms=elapsed_ms,
        )


def _measure_pcm16(payload: bytes) -> tuple[int, float]:
    count = len(payload) // 2
    if count <= 0:
        return 0, 0.0
    peak = 0
    sum_squares = 0
    for (sample,) in struct.iter_unpack("<h", payload):
        absolute = abs(sample)
        peak = max(peak, absolute)
        sum_squares += sample * sample
    return peak, math.sqrt(sum_squares / count)
