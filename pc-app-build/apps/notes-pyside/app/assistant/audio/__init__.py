"""Shared Gate 3 audio contracts and adapters."""

from .engine import (
    AssistantAudioEngine,
    AudioEngineBusyError,
    AudioEngineFailure,
    AudioEngineGenerationError,
    MicrophoneLeaseCoordinator,
)
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
    ENCODED_PACKET_CAPACITY,
    PCM_INGRESS_CAPACITY,
    AudioCaptureSummary,
    EncodedAudioPacket,
    PcmFrame,
    VoiceActivitySnapshot,
)
from .opus_codec import OpusUnavailableError, PyAvOpusEncoder
from .ports import AudioCapturePort, AudioClock, OpusEncoderPort, VoiceActivityDetectorPort
from .pyaudio_adapter import PyAudioCaptureAdapter, PyAudioUnavailableError
from .vad import EnergyVadConfig, EnergyVoiceActivityDetector
from .queues import (
    AudioQueueClosed,
    AudioQueueOverflow,
    AudioQueueStats,
    DropOldestAudioQueue,
    FailOnOverflowAudioQueue,
)

__all__ = [
    "AssistantAudioEngine",
    "AudioCaptureBusyError",
    "AudioCaptureGenerationError",
    "AudioCapturePort",
    "AudioCaptureSummary",
    "AudioClock",
    "AudioEngineBusyError",
    "AudioEngineFailure",
    "AudioEngineGenerationError",
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
    "EnergyVadConfig",
    "EnergyVoiceActivityDetector",
    "ENCODED_PACKET_CAPACITY",
    "EncodedAudioPacket",
    "FailOnOverflowAudioQueue",
    "FakeCaptureScript",
    "FakeOpusEncoder",
    "MicrophoneLeaseCoordinator",
    "OpusEncoderPort",
    "OpusUnavailableError",
    "PCM_INGRESS_CAPACITY",
    "PcmFrame",
    "PyAudioCaptureAdapter",
    "PyAudioUnavailableError",
    "PyAvOpusEncoder",
    "ScriptedFakeAudioCapture",
    "ScriptedVoiceActivityDetector",
    "VoiceActivityDetectorPort",
    "VoiceActivitySnapshot",
]
