"""PyAudio callback output with non-blocking PCM consumption and physical drain."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from .models import PcmAudioFormat, TtsStreamContext
from .ports import ConsumedCallback, DrainedCallback, PcmPlaybackSource


@dataclass(frozen=True, slots=True)
class PyAudioOutputPlan:
    device_index: int
    device_public_name: str
    pcm_format: PcmAudioFormat
    frames_per_buffer: int


def probe_default_output_plan(
    *,
    preferred_formats: tuple[PcmAudioFormat, ...] | None = None,
    pyaudio_factory: Callable[[], Any] | None = None,
) -> PyAudioOutputPlan:
    """Select a supported public default-output format without opening a stream."""

    try:
        import pyaudio
    except ImportError as exc:  # pragma: no cover - real dependency boundary
        raise RuntimeError("pyaudio is not installed") from exc

    factory = pyaudio_factory or pyaudio.PyAudio
    manager = factory()
    try:
        info = manager.get_default_output_device_info()
        device_index = int(info["index"])
        device_name = str(info.get("name") or "Default output")[:120]
        candidates = preferred_formats or (
            PcmAudioFormat(48_000, 2),
            PcmAudioFormat(48_000, 1),
            PcmAudioFormat(24_000, 1),
            PcmAudioFormat(44_100, 2),
            PcmAudioFormat(44_100, 1),
        )
        for pcm_format in candidates:
            try:
                supported = manager.is_format_supported(
                    pcm_format.sample_rate_hz,
                    output_device=device_index,
                    output_channels=pcm_format.channels,
                    output_format=pyaudio.paInt16,
                )
            except (ValueError, OSError):
                continue
            if supported:
                frames_per_buffer = max(240, pcm_format.sample_rate_hz // 50)
                return PyAudioOutputPlan(
                    device_index=device_index,
                    device_public_name=device_name,
                    pcm_format=pcm_format,
                    frames_per_buffer=frames_per_buffer,
                )
        raise RuntimeError("default output device has no supported Gate 4 PCM16 format")
    finally:
        manager.terminate()


class PyAudioOutputAdapter:
    """Own one PortAudio output stream and report drain after the final buffer plays."""

    def __init__(
        self,
        plan: PyAudioOutputPlan,
        *,
        pyaudio_factory: Callable[[], Any] | None = None,
        close_timeout_seconds: float = 2.0,
        poll_interval_seconds: float = 0.01,
    ) -> None:
        if close_timeout_seconds <= 0 or poll_interval_seconds <= 0:
            raise ValueError("output timeouts must be positive")
        self._plan = plan
        self._pyaudio_factory = pyaudio_factory
        self._close_timeout_seconds = close_timeout_seconds
        self._poll_interval_seconds = poll_interval_seconds
        self._manager: Any | None = None
        self._stream: Any | None = None
        self._source: PcmPlaybackSource | None = None
        self._consumed_callback: ConsumedCallback | None = None
        self._drained_callback: DrainedCallback | None = None
        self._monitor_task: asyncio.Task[None] | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._running = False
        self._terminal_submitted = False
        self._drain_reported = False
        self._closed = False
        self._callback_status_error_count = 0

    @property
    def device_public_name(self) -> str | None:
        return self._plan.device_public_name

    @property
    def running(self) -> bool:
        return self._running

    @property
    def callback_status_error_count(self) -> int:
        return self._callback_status_error_count

    async def open(
        self,
        context: TtsStreamContext,
        source: PcmPlaybackSource,
        consumed_callback: ConsumedCallback,
        drained_callback: DrainedCallback,
    ) -> None:
        del context
        if self._stream is not None or self._closed:
            raise RuntimeError("PyAudio output is already open or closed")
        if source.pcm_format != self._plan.pcm_format:
            raise ValueError("PCM source format does not match output plan")
        self._loop = asyncio.get_running_loop()
        self._source = source
        self._consumed_callback = consumed_callback
        self._drained_callback = drained_callback
        await asyncio.to_thread(self._open_sync)

    async def start(self) -> None:
        if self._stream is None:
            raise RuntimeError("PyAudio output is not open")
        if self._running:
            return
        await asyncio.to_thread(self._stream.start_stream)
        self._running = True
        self._monitor_task = asyncio.create_task(
            self._monitor_physical_drain(),
            name="assistant-pyaudio-output-drain",
        )

    async def stop(self) -> None:
        self._running = False
        task = self._monitor_task
        self._monitor_task = None
        if task is not None and not task.done() and task is not asyncio.current_task():
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
        stream = self._stream
        if stream is None:
            return
        try:
            if await asyncio.to_thread(stream.is_active):
                await asyncio.wait_for(
                    asyncio.to_thread(stream.stop_stream),
                    timeout=self._close_timeout_seconds,
                )
        except (OSError, asyncio.TimeoutError):
            pass

    async def close(self) -> None:
        if self._closed:
            return
        await self.stop()
        stream = self._stream
        manager = self._manager
        self._stream = None
        self._manager = None
        try:
            if stream is not None:
                await asyncio.wait_for(
                    asyncio.to_thread(stream.close),
                    timeout=self._close_timeout_seconds,
                )
        finally:
            if manager is not None:
                try:
                    await asyncio.wait_for(
                        asyncio.to_thread(manager.terminate),
                        timeout=self._close_timeout_seconds,
                    )
                except asyncio.TimeoutError:
                    pass
        self._source = None
        self._consumed_callback = None
        self._drained_callback = None
        self._closed = True

    def _open_sync(self) -> None:
        try:
            import pyaudio
        except ImportError as exc:  # pragma: no cover - real dependency boundary
            raise RuntimeError("pyaudio is not installed") from exc
        factory = self._pyaudio_factory or pyaudio.PyAudio
        manager = factory()
        try:
            stream = manager.open(
                format=pyaudio.paInt16,
                channels=self._plan.pcm_format.channels,
                rate=self._plan.pcm_format.sample_rate_hz,
                output=True,
                output_device_index=self._plan.device_index,
                frames_per_buffer=self._plan.frames_per_buffer,
                stream_callback=self._callback,
                start=False,
            )
        except Exception:
            manager.terminate()
            raise
        self._manager = manager
        self._stream = stream

    def _callback(self, _in_data, frame_count: int, _time_info, status_flags: int):
        import pyaudio

        source = self._source
        consumed_callback = self._consumed_callback
        if source is None or consumed_callback is None or frame_count <= 0:
            return (b"", pyaudio.paAbort)
        if status_flags:
            self._callback_status_error_count += 1
        byte_count = frame_count * source.pcm_format.frame_size_bytes
        payload = source.consume(byte_count)
        real_bytes = len(payload)
        if real_bytes:
            consumed_callback(
                real_bytes,
                real_bytes // source.pcm_format.frame_size_bytes,
            )
        if real_bytes < byte_count:
            payload += b"\x00" * (byte_count - real_bytes)
        terminal = source.terminal_and_empty
        if terminal:
            self._terminal_submitted = True
            return (payload, pyaudio.paComplete)
        return (payload, pyaudio.paContinue)

    async def _monitor_physical_drain(self) -> None:
        try:
            while self._running:
                stream = self._stream
                if stream is None:
                    return
                active = await asyncio.to_thread(stream.is_active)
                if self._terminal_submitted and not active:
                    self._running = False
                    self._report_drain_once()
                    return
                await asyncio.sleep(self._poll_interval_seconds)
        except asyncio.CancelledError:
            raise
        except (OSError, RuntimeError):
            # The engine drain watchdog owns conversion of output failures into a
            # visible RuntimePlaybackFailed event. The callback task must not leak
            # an unhandled exception.
            self._running = False

    def _report_drain_once(self) -> None:
        if self._drain_reported:
            return
        self._drain_reported = True
        callback = self._drained_callback
        loop = self._loop
        if callback is not None and loop is not None:
            loop.call_soon_threadsafe(callback)
