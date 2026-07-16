"""Output format planning kept separate from wire negotiation and decode."""

from __future__ import annotations

from dataclasses import dataclass

from .models import PcmAudioFormat


@dataclass(frozen=True, slots=True)
class PlaybackOutputPlan:
    decoded_format: PcmAudioFormat
    output_format: PcmAudioFormat
    resample_required: bool
    remix_required: bool


class PlaybackFormatPlanner:
    """Choose an explicit device format from decoded PCM capabilities."""

    def plan(
        self,
        decoded_format: PcmAudioFormat,
        *,
        supported_sample_rates_hz: tuple[int, ...],
        supported_channels: tuple[int, ...],
    ) -> PlaybackOutputPlan:
        rates = tuple(sorted({rate for rate in supported_sample_rates_hz if rate > 0}))
        channels = tuple(sorted({value for value in supported_channels if value > 0}))
        if not rates:
            raise ValueError("no supported output sample rates")
        if not channels:
            raise ValueError("no supported output channel counts")

        output_rate = (
            decoded_format.sample_rate_hz
            if decoded_format.sample_rate_hz in rates
            else min(rates, key=lambda rate: abs(rate - decoded_format.sample_rate_hz))
        )
        output_channels = (
            decoded_format.channels
            if decoded_format.channels in channels
            else (1 if 1 in channels else channels[0])
        )
        output_format = PcmAudioFormat(
            sample_rate_hz=output_rate,
            channels=output_channels,
            sample_width_bytes=decoded_format.sample_width_bytes,
        )
        return PlaybackOutputPlan(
            decoded_format=decoded_format,
            output_format=output_format,
            resample_required=output_rate != decoded_format.sample_rate_hz,
            remix_required=output_channels != decoded_format.channels,
        )
