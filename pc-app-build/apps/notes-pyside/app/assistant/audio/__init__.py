"""Shared Gate 3 audio contracts and deterministic fake adapters."""

from .fake_audio import (
    AudioCaptureBusyError,
    AudioCaptureGenerationError,
    FakeCaptureScript,
    FakeOpusEncoder,
    ScriptedFakeAudioCapture,
    ScriptedVoiceActivityDetector,
)
from .models import (
    DEFAULT_BYTES_PER_FRAME,
    DEFAULT_CHANNELS,
    DEFAULT_FRAME_DURATION_MS,
    DEFAULT_OPUS_BITRATE_BPS,
    DEFAULT_SAMPLE_RATE_HZ,
    DEFAULT_SAMPLES_PER_FRAME,
    AudioCaptureSummary,
    EncodedAudioPacket,
    PcmFrame,
    VoiceActivitySnapshot,
)
from .ports import AudioCapturePort, AudioClock, OpusEncoderPort, VoiceActivityDetectorPort
from .queues import (
    AudioQueueClosed,
    AudioQueueOverflow,
    AudioQueueStats,
    DropOldestAudioQueue,
    FailOnOverflowAudioQueue,
)

__all__ = [
    "AudioCaptureBusyError",
    "AudioCaptureGenerationError",
    "AudioCapturePort",
    "AudioCaptureSummary",
    "AudioClock",
    "AudioQueueClosed",
    "AudioQueueOverflow",
    "AudioQueueStats",
    "DEFAULT_BYTES_PER_FRAME",
    "DEFAULT_CHANNELS",
    "DEFAULT_FRAME_DURATION_MS",
    "DEFAULT_OPUS_BITRATE_BPS",
    "DEFAULT_SAMPLE_RATE_HZ",
    "DEFAULT_SAMPLES_PER_FRAME",
    "DropOldestAudioQueue",
    "EncodedAudioPacket",
    "FailOnOverflowAudioQueue",
    "FakeCaptureScript",
    "FakeOpusEncoder",
    "OpusEncoderPort",
    "PcmFrame",
    "ScriptedFakeAudioCapture",
    "ScriptedVoiceActivityDetector",
    "VoiceActivityDetectorPort",
    "VoiceActivitySnapshot",
]
