"""Selected sherpa-onnx adapter behind the framework-neutral KWS port."""

from __future__ import annotations

import time
from typing import Any

from .gate6_contracts import KeywordSpotResult, ProcessedPcmFrame
from .kws_model_registry import KwsModelFiles


class KwsBackendError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(message)


class SherpaOnnxKeywordSpotter:
    """Small synchronous adapter; capture/worker ownership lives elsewhere."""

    def __init__(self, model: KwsModelFiles, *, num_threads: int = 2) -> None:
        if not model.ready:
            raise KwsBackendError("kws_model_invalid", "KWS model files are incomplete")
        try:
            import numpy as np
            import sherpa_onnx
        except ImportError as exc:
            raise KwsBackendError(
                "kws_native_import_failed",
                "sherpa-onnx and numpy are required for offline wake word",
            ) from exc
        try:
            spotter = sherpa_onnx.KeywordSpotter(
                tokens=str(model.tokens),
                encoder=str(model.encoder),
                decoder=str(model.decoder),
                joiner=str(model.joiner),
                keywords_file=str(model.keywords),
                num_threads=max(1, int(num_threads)),
                provider="cpu",
            )
            stream = spotter.create_stream()
        except Exception as exc:
            raise KwsBackendError(
                "kws_model_load_failed",
                f"sherpa KWS model failed to load: {type(exc).__name__}",
            ) from exc
        self._np: Any = np
        self._spotter: Any | None = spotter
        self._stream: Any | None = stream
        self._generation = 0

    def reset(self, generation: int) -> None:
        if generation < 0:
            raise ValueError("KWS generation cannot be negative")
        self._generation = generation
        spotter = self._spotter
        stream = self._stream
        if spotter is not None and stream is not None:
            spotter.reset_stream(stream)

    def accept(self, frame: ProcessedPcmFrame) -> KeywordSpotResult | None:
        spotter = self._spotter
        stream = self._stream
        if spotter is None or stream is None:
            raise KwsBackendError("kws_backend_closed", "KWS backend is closed")
        samples = self._np.frombuffer(frame.pcm16_le, dtype=self._np.int16).astype(self._np.float32)
        samples /= 32768.0
        spotter_stream = stream
        spotter_stream.accept_waveform(frame.source.audio_format.sample_rate_hz, samples)
        result = ""
        while spotter.is_ready(spotter_stream):
            spotter.decode_stream(spotter_stream)
            candidate = str(spotter.get_result(spotter_stream) or "").strip()
            if candidate:
                result = candidate
        if not result:
            return None
        detected_at_ns = time.perf_counter_ns()
        spotter.reset_stream(spotter_stream)
        return KeywordSpotResult(
            generation=self._generation,
            keyword_public_name=result[:120],
            detected_at_ns=detected_at_ns,
        )

    def close(self) -> None:
        self._stream = None
        self._spotter = None
