from __future__ import annotations

import struct

from app.assistant import VoiceActivityState
from app.assistant.audio import EnergyVadConfig, EnergyVoiceActivityDetector, PcmFrame


def _frame(sequence: int, sample: int) -> PcmFrame:
    return PcmFrame(
        generation=7,
        sequence=sequence,
        captured_at_ns=sequence * 20_000_000,
        pcm16_le=struct.pack("<320h", *([sample] * 320)),
    )


def test_energy_vad_warmup_speech_and_end_of_speech() -> None:
    vad = EnergyVoiceActivityDetector(
        EnergyVadConfig(
            warmup_ms=40,
            min_speech_ms=40,
            end_silence_ms=60,
            no_speech_timeout_ms=1_000,
            min_rms_threshold=300.0,
            min_peak_threshold=900,
            speech_trigger_frames=1,
        )
    )
    vad.reset(7)
    states = [
        vad.observe(_frame(0, 0)).state,
        vad.observe(_frame(1, 0)).state,
        vad.observe(_frame(2, 1600)).state,
        vad.observe(_frame(3, 1600)).state,
        vad.observe(_frame(4, 1600)).state,
        vad.observe(_frame(5, 0)).state,
        vad.observe(_frame(6, 0)).state,
        vad.observe(_frame(7, 0)).state,
    ]

    assert VoiceActivityState.WARMUP in states
    assert VoiceActivityState.SPEECH_DETECTED in states
    assert VoiceActivityState.SPEECH_ACTIVE in states
    assert states[-1] is VoiceActivityState.END_OF_SPEECH


def test_energy_vad_emits_no_speech_timeout() -> None:
    vad = EnergyVoiceActivityDetector(
        EnergyVadConfig(
            warmup_ms=20,
            min_speech_ms=40,
            end_silence_ms=60,
            no_speech_timeout_ms=100,
            speech_trigger_frames=1,
        )
    )
    vad.reset(7)
    states = [vad.observe(_frame(index, 0)).state for index in range(7)]
    assert states[-1] is VoiceActivityState.NO_SPEECH_TIMEOUT
