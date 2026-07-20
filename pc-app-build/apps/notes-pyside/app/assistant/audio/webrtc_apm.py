"""Production WebRTC APM adapter selected by the Windows Gate 6 evidence."""

from __future__ import annotations

from dataclasses import replace

from .gate6_contracts import (
    AudioProcessingMetrics,
    ProcessedPcmFrame,
    ProcessingState,
    TimedPcmFrame,
)


class AudioProcessingUnavailable(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(message)


class WebRtcApmAudioProcessor:
    """AEC-first, AGC-off processor; NS stays off after the Windows double-talk evidence."""

    def __init__(
        self,
        *,
        sample_rate_hz: int = 16_000,
        channels: int = 1,
        stream_delay_ms: int = 120,
        enable_ns: bool = False,
    ) -> None:
        try:
            from aec_audio_processing import AudioProcessor
        except ImportError as exc:
            raise AudioProcessingUnavailable(
                "aec_audio_processing_not_installed",
                "安装 aec-audio-processing 后才能启用扬声器播放期声学插话",
            ) from exc
        try:
            processor = AudioProcessor(
                enable_aec=True,
                enable_ns=enable_ns,
                enable_agc=False,
                enable_vad=False,
            )
            try:
                processor.set_stream_format(
                    sample_rate_in=sample_rate_hz,
                    channel_count_in=channels,
                    sample_rate_out=sample_rate_hz,
                    channel_count_out=channels,
                )
            except TypeError:
                processor.set_stream_format(sample_rate_hz, channels)
            processor.set_reverse_stream_format(sample_rate_hz, channels)
            processor.set_stream_delay(max(0, min(500, int(stream_delay_ms))))
        except Exception as exc:
            raise AudioProcessingUnavailable(
                "aec_backend_create_failed",
                f"WebRTC APM 初始化失败：{type(exc).__name__}",
            ) from exc
        reverse = next(
            (
                getattr(processor, name)
                for name in (
                    "process_reverse_stream",
                    "process_reverse",
                    "analyze_reverse_stream",
                    "process_render",
                )
                if callable(getattr(processor, name, None))
            ),
            None,
        )
        if reverse is None:
            close = getattr(processor, "close", None)
            if callable(close):
                close()
            raise AudioProcessingUnavailable(
                "aec_reverse_stream_api_missing",
                "WebRTC APM 缺少 render reference 接口",
            )
        self._processor = processor
        self._reverse = reverse
        self._enable_ns = bool(enable_ns)
        self._closed = False
        self._metrics = AudioProcessingMetrics(
            backend_public_name="aec-audio-processing/WebRTC APM",
            state=ProcessingState.WARMING,
            aec_available=True,
            aec_effective=True,
            ns_available=True,
            ns_effective=self._enable_ns,
            agc_available=True,
            agc_effective=False,
            estimated_delay_ms=float(max(0, min(500, int(stream_delay_ms)))),
        )

    def process_render(self, frame: TimedPcmFrame) -> None:
        self._require_open()
        self._reverse(frame.pcm16_le)
        self._metrics = replace(
            self._metrics,
            render_frames=self._metrics.render_frames + 1,
            state=(
                ProcessingState.READY
                if self._metrics.capture_frames > 0
                else ProcessingState.WARMING
            ),
        )

    def process_capture(self, frame: TimedPcmFrame) -> ProcessedPcmFrame:
        self._require_open()
        try:
            payload = bytes(self._processor.process_stream(frame.pcm16_le))
        except Exception as exc:
            self._metrics = replace(
                self._metrics,
                state=ProcessingState.FAILED,
                error_code="aec_process_capture_failed",
            )
            raise AudioProcessingUnavailable(
                "aec_process_capture_failed",
                f"WebRTC APM capture 处理失败：{type(exc).__name__}",
            ) from exc
        if len(payload) != len(frame.pcm16_le):
            self._metrics = replace(
                self._metrics,
                state=ProcessingState.FAILED,
                error_code="aec_output_size_mismatch",
            )
            raise AudioProcessingUnavailable(
                "aec_output_size_mismatch",
                "WebRTC APM 返回了错误长度的 PCM block",
            )
        capture_frames = self._metrics.capture_frames + 1
        ready = self._metrics.render_frames >= 20 and capture_frames >= 20
        self._metrics = replace(
            self._metrics,
            capture_frames=capture_frames,
            processed_frames=self._metrics.processed_frames + 1,
            state=ProcessingState.READY if ready else ProcessingState.WARMING,
        )
        return ProcessedPcmFrame(
            source=frame,
            pcm16_le=payload,
            processing_state=self._metrics.state,
            backend_public_name=self._metrics.backend_public_name,
        )

    def metrics(self) -> AudioProcessingMetrics:
        return self._metrics

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        close = getattr(self._processor, "close", None)
        if callable(close):
            close()

    def _require_open(self) -> None:
        if self._closed:
            raise RuntimeError("audio processor is closed")
