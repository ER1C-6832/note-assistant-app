from __future__ import annotations

import pytest

from app.assistant.playback import (
    DecodedPcmChunk,
    EncodedDownlinkPacket,
    PcmAudioFormat,
    PlaybackFormatPlanner,
    TtsStreamContext,
)
from app.assistant.protocol import DownlinkAudioFormat


def _wire_format() -> DownlinkAudioFormat:
    return DownlinkAudioFormat(
        codec="opus",
        sample_rate_hz=24_000,
        channels=1,
        frame_duration_ms=20.0,
    )


def test_real_probe_wire_format_is_distinct_from_decoded_pcm_format() -> None:
    wire = _wire_format()
    decoded = PcmAudioFormat(sample_rate_hz=48_000, channels=2)

    assert wire.sample_rate_hz == 24_000
    assert wire.channels == 1
    assert decoded.sample_rate_hz == 48_000
    assert decoded.channels == 2


def test_format_planner_uses_decoded_pcm_not_wire_assumptions() -> None:
    planner = PlaybackFormatPlanner()
    decoded = PcmAudioFormat(48_000, 2)

    native = planner.plan(
        decoded,
        supported_sample_rates_hz=(44_100, 48_000),
        supported_channels=(1, 2),
    )
    assert native.output_format == decoded
    assert native.resample_required is False
    assert native.remix_required is False

    fallback = planner.plan(
        decoded,
        supported_sample_rates_hz=(44_100,),
        supported_channels=(1,),
    )
    assert fallback.output_format == PcmAudioFormat(44_100, 1)
    assert fallback.resample_required is True
    assert fallback.remix_required is True


def test_models_reject_invalid_identity_and_unaligned_pcm() -> None:
    with pytest.raises(ValueError):
        TtsStreamContext(
            connection_generation=0,
            stream_sequence=1,
            playback_generation=1,
            turn_token=1,
            streaming_generation=None,
            wire_format=_wire_format(),
            started_at_ns=1,
        )
    with pytest.raises(ValueError):
        EncodedDownlinkPacket(
            connection_generation=1,
            stream_sequence=1,
            packet_sequence=1,
            received_at_ns=1,
            payload=b"",
        )
    with pytest.raises(ValueError):
        DecodedPcmChunk(
            pcm_format=PcmAudioFormat(48_000, 2),
            payload=b"abc",
            decoded_at_ns=1,
        )
