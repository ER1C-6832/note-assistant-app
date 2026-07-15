from __future__ import annotations

import pytest

from app.assistant.audio import (
    AudioCaptureBusyError,
    AudioCaptureGenerationError,
    AudioQueueOverflow,
    DropOldestAudioQueue,
    FailOnOverflowAudioQueue,
    FakeCaptureScript,
    FakeOpusEncoder,
    ScriptedFakeAudioCapture,
    ScriptedVoiceActivityDetector,
)
from app.assistant.state import VoiceActivityState


def test_pcm_queue_drops_oldest_without_blocking() -> None:
    queue = DropOldestAudioQueue[int](capacity=2)
    assert queue.put(1) is None
    assert queue.put(2) is None
    assert queue.put(3) == 1
    assert queue.get() == 2
    assert queue.get() == 3
    assert queue.stats.dropped_oldest == 1


def test_encoded_queue_fails_current_turn_on_overflow() -> None:
    queue = FailOnOverflowAudioQueue[int](capacity=2)
    queue.put(1)
    queue.put(2)
    with pytest.raises(AudioQueueOverflow):
        queue.put(3)
    assert queue.stats.overflow_failures == 1
    assert queue.drain() == (1, 2)


def test_scripted_capture_encoder_vad_share_generation() -> None:
    capture = ScriptedFakeAudioCapture(FakeCaptureScript.from_frames((b"a", b"b")))
    encoder = FakeOpusEncoder()
    vad = ScriptedVoiceActivityDetector(
        (VoiceActivityState.SPEECH_DETECTED, VoiceActivityState.END_OF_SPEECH)
    )
    accepted = []
    snapshots = []

    vad.reset(7)

    def on_frame(frame):
        accepted.append(encoder.encode(frame))
        snapshots.append(vad.observe(frame))
        return True

    capture.start(7, on_frame)
    with pytest.raises(AudioCaptureBusyError):
        capture.start(8, on_frame)
    assert capture.emit_all() == 2
    capture.stop(7)
    assert [item.generation for item in accepted] == [7, 7]
    assert [item.state for item in snapshots] == [
        VoiceActivityState.SPEECH_DETECTED,
        VoiceActivityState.END_OF_SPEECH,
    ]
    assert capture.emit_stale(7) is False
    assert capture.stale_frame_count == 1

    capture.start(8, on_frame)
    with pytest.raises(AudioCaptureGenerationError):
        capture.stop(7)
    capture.stop(8)
