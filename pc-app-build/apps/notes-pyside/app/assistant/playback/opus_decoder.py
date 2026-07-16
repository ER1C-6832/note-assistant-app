"""PyAV Opus decoder boundary prepared for Gate 4.2 device wiring."""

from __future__ import annotations

from collections.abc import Callable, Iterable

from .models import DecodedPcmChunk, EncodedDownlinkPacket, PcmAudioFormat


class PyAvOpusDecoder:
    """Decode Opus and normalize it to explicit packed PCM16 output."""

    def __init__(
        self,
        output_format: PcmAudioFormat,
        *,
        clock_ns: Callable[[], int],
    ) -> None:
        try:
            import av
        except ImportError as exc:  # pragma: no cover - real dependency boundary
            raise RuntimeError("av is not installed") from exc
        self._av = av
        self._pcm_format = output_format
        self._codec = av.CodecContext.create("opus", "r")
        layout = "mono" if output_format.channels == 1 else "stereo"
        self._resampler = av.AudioResampler(
            format="s16",
            layout=layout,
            rate=output_format.sample_rate_hz,
        )
        self._clock_ns = clock_ns
        self._closed = False

    @property
    def pcm_format(self) -> PcmAudioFormat:
        return self._pcm_format

    def decode(self, packet: EncodedDownlinkPacket) -> tuple[DecodedPcmChunk, ...]:
        if self._closed:
            raise RuntimeError("decoder is closed")
        frames = self._codec.decode(self._av.Packet(packet.payload))
        return self._convert(frames)

    def flush(self) -> tuple[DecodedPcmChunk, ...]:
        if self._closed:
            return ()
        decoded = self._codec.decode(None)
        chunks = list(self._convert(decoded))
        chunks.extend(self._convert(self._normalize_frames(self._resampler.resample(None))))
        return tuple(chunks)

    def close(self) -> None:
        self._closed = True
        self._codec = None
        self._resampler = None

    def _convert(self, frames: Iterable[object]) -> tuple[DecodedPcmChunk, ...]:
        chunks: list[DecodedPcmChunk] = []
        for frame in frames:
            resampled = self._normalize_frames(self._resampler.resample(frame))
            for output_frame in resampled:
                expected_bytes = output_frame.samples * self._pcm_format.frame_size_bytes
                payload = bytes(output_frame.planes[0])[:expected_bytes]
                if not payload:
                    continue
                chunks.append(
                    DecodedPcmChunk(
                        pcm_format=self._pcm_format,
                        payload=payload,
                        decoded_at_ns=self._clock_ns(),
                    )
                )
        return tuple(chunks)

    @staticmethod
    def _normalize_frames(value) -> tuple[object, ...]:
        if value is None:
            return ()
        if isinstance(value, list):
            return tuple(value)
        if isinstance(value, tuple):
            return value
        return (value,)
