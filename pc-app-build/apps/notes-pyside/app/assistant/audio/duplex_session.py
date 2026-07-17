"""PortAudio duplex session used by later AEC/barge-in product stages."""

from __future__ import annotations

import threading
import time
from collections.abc import Callable
from typing import Any

from .device_registry import PyAudioDeviceRegistry
from .gate6_contracts import (
    DeviceDirection,
    DuplexAudioPlan,
    DuplexCallbacks,
    ResolvedAudioRoute,
    TimedPcmFrame,
)

RouteProvider = Callable[[], ResolvedAudioRoute]


class PyAudioDuplexSession:
    """Own one input/output pair; callbacks only move bounded public frames."""

    def __init__(
        self,
        registry: PyAudioDeviceRegistry,
        route_provider: RouteProvider,
        *,
        pyaudio_factory: Callable[[], Any] | None = None,
        pyaudio_module: Any | None = None,
    ) -> None:
        self._registry = registry
        self._route_provider = route_provider
        self._factory = pyaudio_factory
        self._module = pyaudio_module
        self._lock = threading.RLock()
        self._manager: Any | None = None
        self._input_stream: Any | None = None
        self._output_stream: Any | None = None
        self._plan: DuplexAudioPlan | None = None
        self._callbacks: DuplexCallbacks | None = None
        self._stream_generation = 0
        self._capture_sequence = 0
        self._running = False
        self._closed = False

    @property
    def running(self) -> bool:
        with self._lock:
            return self._running

    @property
    def open_stream_count(self) -> int:
        with self._lock:
            return int(self._input_stream is not None) + int(self._output_stream is not None)

    def open(self, plan: DuplexAudioPlan, callbacks: DuplexCallbacks) -> None:
        with self._lock:
            if self._closed:
                raise RuntimeError("duplex session is closed")
            if self._manager is not None:
                raise RuntimeError("duplex session is already open")
        route = self._route_provider()
        if route.route_generation != plan.route_generation:
            raise RuntimeError("stale route generation cannot open duplex audio")
        if route.input_device is None or route.output_device is None:
            raise RuntimeError("duplex route is unavailable")
        module = self._pyaudio_module()
        factory = self._factory or module.PyAudio
        manager = factory()
        input_index = self._registry.device_index(
            route.input_device.opaque_device_id, DeviceDirection.INPUT
        )
        output_index = self._registry.device_index(
            route.output_device.opaque_device_id, DeviceDirection.OUTPUT
        )
        with self._lock:
            self._plan = plan
            self._callbacks = callbacks
            self._stream_generation += 1
            self._capture_sequence = 0
        try:
            input_stream = manager.open(
                format=module.paInt16,
                channels=plan.capture_format.channels,
                rate=plan.capture_format.sample_rate_hz,
                input=True,
                input_device_index=input_index,
                frames_per_buffer=plan.capture_format.samples_per_frame,
                stream_callback=self._capture_callback,
                start=False,
            )
            output_stream = manager.open(
                format=module.paInt16,
                channels=plan.render_format.channels,
                rate=plan.render_format.sample_rate_hz,
                output=True,
                output_device_index=output_index,
                frames_per_buffer=plan.render_format.samples_per_frame,
                stream_callback=self._render_callback,
                start=False,
            )
        except Exception:
            for stream in (
                locals().get("input_stream"),
                locals().get("output_stream"),
            ):
                if stream is not None:
                    stream.close()
            manager.terminate()
            with self._lock:
                self._plan = None
                self._callbacks = None
            raise
        with self._lock:
            self._manager = manager
            self._input_stream = input_stream
            self._output_stream = output_stream

    def start(self) -> None:
        with self._lock:
            if self._manager is None or self._input_stream is None or self._output_stream is None:
                raise RuntimeError("duplex session is not open")
            if self._running:
                return
            input_stream = self._input_stream
            output_stream = self._output_stream
        input_stream.start_stream()
        try:
            output_stream.start_stream()
        except Exception:
            if input_stream.is_active():
                input_stream.stop_stream()
            raise
        with self._lock:
            self._running = True

    def stop(self) -> None:
        with self._lock:
            streams = (self._input_stream, self._output_stream)
            self._running = False
        for stream in streams:
            if stream is not None and stream.is_active():
                stream.stop_stream()

    def close(self) -> None:
        with self._lock:
            if self._closed and self._manager is None:
                return
        self.stop()
        with self._lock:
            streams = (self._input_stream, self._output_stream)
            manager = self._manager
            self._input_stream = None
            self._output_stream = None
            self._manager = None
            self._plan = None
            self._callbacks = None
            self._closed = True
        try:
            for stream in streams:
                if stream is not None:
                    stream.close()
        finally:
            if manager is not None:
                manager.terminate()

    def _capture_callback(self, in_data, _frame_count, _time_info, _status_flags):
        module = self._pyaudio_module()
        with self._lock:
            plan = self._plan
            callbacks = self._callbacks
            sequence = self._capture_sequence
            stream_generation = self._stream_generation
            active = self._running or self._manager is not None
            self._capture_sequence += 1
        if not active or plan is None or callbacks is None:
            return (None, module.paComplete)
        payload = bytes(in_data)
        if len(payload) != plan.capture_format.bytes_per_frame:
            return (None, module.paContinue)
        try:
            callbacks.capture_sink(
                TimedPcmFrame(
                    route_generation=plan.route_generation,
                    stream_generation=stream_generation,
                    sequence=sequence,
                    monotonic_ns=time.perf_counter_ns(),
                    audio_format=plan.capture_format,
                    pcm16_le=payload,
                )
            )
        except Exception:
            pass
        return (None, module.paContinue)

    def _render_callback(self, _in_data, frame_count, _time_info, _status_flags):
        module = self._pyaudio_module()
        with self._lock:
            plan = self._plan
            callbacks = self._callbacks
        if plan is None or callbacks is None:
            return (b"", module.paComplete)
        expected = frame_count * plan.render_format.channels * plan.render_format.sample_width_bytes
        try:
            frame = callbacks.render_source()
        except Exception:
            frame = None
        if frame is None or frame.route_generation != plan.route_generation:
            payload = b"\x00" * expected
        else:
            payload = frame.pcm16_le[:expected]
            if len(payload) < expected:
                payload += b"\x00" * (expected - len(payload))
        return (payload, module.paContinue)

    def _pyaudio_module(self) -> Any:
        if self._module is not None:
            return self._module
        try:
            import pyaudio
        except ImportError as exc:
            raise RuntimeError("pyaudio is not installed") from exc
        return pyaudio
