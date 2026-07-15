"""Raw 20 ms Opus encoder backed by the self-contained PyAV wheel."""

from __future__ import annotations

import time

from .models import (
    DEFAULT_CHANNELS,
    DEFAULT_OPUS_BITRATE_BPS,
    DEFAULT_SAMPLE_RATE_HZ,
    DEFAULT_SAMPLES_PER_FRAME,
    EncodedAudioPacket,
    PcmFrame,
)


class OpusUnavailableError(RuntimeError):
    pass


class PyAvOpusEncoder:
    """Encode one 20 ms PCM16 frame into one raw Opus packet.

    PyAV's Windows wheels carry the FFmpeg/libopus runtime with the Python
    package, so Gate 3.2 does not depend on an unrelated DLL being present on
    PATH. The encoder is created and used only on the audio worker thread.
    """

    def __init__(self) -> None:
        try:
            import av
        except ImportError as exc:
            raise OpusUnavailableError(
                "PyAV is not installed; run pip install -e .[dev] from pc-app-build"
            ) from exc

        try:
            codec = av.CodecContext.create("libopus", "w")
            codec.sample_rate = DEFAULT_SAMPLE_RATE_HZ
            codec.layout = "mono" if DEFAULT_CHANNELS == 1 else "stereo"
            codec.format = "s16"
            codec.bit_rate = DEFAULT_OPUS_BITRATE_BPS
            codec.open()
        except Exception as exc:
            raise OpusUnavailableError(f"PyAV could not initialize libopus: {exc}") from exc

        if codec.frame_size not in (0, DEFAULT_SAMPLES_PER_FRAME):
            raise OpusUnavailableError(
                "libopus reported an incompatible frame size: " f"{codec.frame_size}"
            )
        self._av = av
        self._codec = codec
        self._closed = False

    def encode(self, frame: PcmFrame) -> EncodedAudioPacket:
        frame.validate()
        if self._closed:
            raise RuntimeError("Opus encoder is closed")

        audio_frame = self._av.AudioFrame(
            format="s16",
            layout="mono" if DEFAULT_CHANNELS == 1 else "stereo",
            samples=DEFAULT_SAMPLES_PER_FRAME,
        )
        audio_frame.sample_rate = DEFAULT_SAMPLE_RATE_HZ
        audio_frame.planes[0].update(frame.pcm16_le)
        packets = self._codec.encode(audio_frame)
        if len(packets) != 1:
            raise RuntimeError(
                "libopus must emit exactly one packet per 20 ms frame; "
                f"received {len(packets)} packets"
            )
        payload = bytes(packets[0])
        if not payload:
            raise RuntimeError("libopus returned an empty packet")
        return EncodedAudioPacket(
            generation=frame.generation,
            sequence=frame.sequence,
            encoded_at_ns=time.perf_counter_ns(),
            payload=payload,
        )

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        self._codec = None
