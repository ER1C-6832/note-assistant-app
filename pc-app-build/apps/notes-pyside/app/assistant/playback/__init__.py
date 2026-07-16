"""Gate 4 playback foundation with bounded queues and deterministic Fake output."""

from .engine import AssistantPlaybackEngine
from .fakes import DeterministicFakeOpusDecoder, GateControlledFakeAudioOutput
from .format_planner import PlaybackFormatPlanner, PlaybackOutputPlan
from .ingress import DownlinkAudioIngress, IngressOfferStatus
from .models import (
    DecodedPcmChunk,
    EncodedDownlinkPacket,
    PcmAudioFormat,
    PlaybackCancelledSignal,
    PlaybackEndedSignal,
    PlaybackFailedSignal,
    PlaybackLifecycleState,
    PlaybackMetrics,
    PlaybackSignal,
    PlaybackStartedSignal,
    PlaybackSummary,
    TtsStreamContext,
)
from .opus_decoder import PyAvOpusDecoder
from .ports import AudioOutputPort, OpusDecoderPort, PlaybackEventSink
from .pyaudio_output import PyAudioOutputAdapter
from .queues import BoundedEncodedDownlinkQueue, EncodedInputTerminal, PcmPlaybackBuffer

__all__ = [
    "AssistantPlaybackEngine",
    "AudioOutputPort",
    "BoundedEncodedDownlinkQueue",
    "DecodedPcmChunk",
    "DownlinkAudioIngress",
    "DeterministicFakeOpusDecoder",
    "EncodedDownlinkPacket",
    "EncodedInputTerminal",
    "GateControlledFakeAudioOutput",
    "IngressOfferStatus",
    "OpusDecoderPort",
    "PcmAudioFormat",
    "PcmPlaybackBuffer",
    "PlaybackCancelledSignal",
    "PlaybackEndedSignal",
    "PlaybackEventSink",
    "PlaybackFailedSignal",
    "PlaybackFormatPlanner",
    "PlaybackLifecycleState",
    "PlaybackMetrics",
    "PlaybackOutputPlan",
    "PlaybackSignal",
    "PlaybackStartedSignal",
    "PlaybackSummary",
    "PyAudioOutputAdapter",
    "PyAvOpusDecoder",
    "TtsStreamContext",
]
