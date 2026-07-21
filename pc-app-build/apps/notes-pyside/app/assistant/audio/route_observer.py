"""Bounded polling observer for PortAudio route and default-device changes."""

from __future__ import annotations

import threading
import time

from .gate6_contracts import AudioRouteEvent, RouteEventKind, RouteEventSink
from .device_registry import PyAudioDeviceRegistry


class PollingAudioRouteObserver:
    """Observe snapshot generation without exposing native device identifiers."""

    def __init__(
        self,
        registry: PyAudioDeviceRegistry,
        *,
        poll_interval_seconds: float = 1.0,
        join_timeout_seconds: float = 2.0,
    ) -> None:
        if poll_interval_seconds <= 0 or join_timeout_seconds <= 0:
            raise ValueError("route observer timeouts must be positive")
        self._registry = registry
        self._poll_interval_seconds = float(poll_interval_seconds)
        self._join_timeout_seconds = float(join_timeout_seconds)
        self._lock = threading.RLock()
        self._sink: RouteEventSink | None = None
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._pause_event = threading.Event()
        self._closed = False

    @property
    def running(self) -> bool:
        with self._lock:
            return bool(self._thread and self._thread.is_alive())

    def start(self, sink: RouteEventSink) -> None:
        with self._lock:
            if self._closed:
                raise RuntimeError("route observer is closed")
            if self._thread is not None and self._thread.is_alive():
                return
            self._sink = sink
            self._stop_event.clear()
            self._thread = threading.Thread(
                target=self._run,
                name="assistant-audio-route-observer",
                daemon=False,
            )
            self._thread.start()

    def stop(self) -> None:
        with self._lock:
            thread = self._thread
            self._thread = None
            self._stop_event.set()
        if thread is not None and thread is not threading.current_thread():
            thread.join(self._join_timeout_seconds)
            if thread.is_alive():
                raise RuntimeError("route observer did not stop within its budget")
        with self._lock:
            self._sink = None

    def pause(self) -> None:
        """Quiesce polling before another component opens a native audio stream."""

        self._pause_event.set()
        # Drain an enumeration which passed the pause check before it can race
        # a capture/output PyAudio initialization or lifetime transition.
        with self._registry.native_operation():
            return

    def resume(self) -> None:
        with self._lock:
            if self._closed:
                return
        self._pause_event.clear()

    def close(self) -> None:
        with self._lock:
            if self._closed:
                return
        self.stop()
        with self._lock:
            self._closed = True

    def _run(self) -> None:
        previous_generation: int | None = None
        while not self._stop_event.is_set():
            if self._pause_event.is_set():
                self._stop_event.wait(self._poll_interval_seconds)
                continue
            try:
                with self._registry.native_operation():
                    if self._pause_event.is_set():
                        continue
                    snapshot = self._registry.snapshot()
                if previous_generation is None:
                    previous_generation = snapshot.generation
                elif snapshot.generation != previous_generation:
                    previous_generation = snapshot.generation
                    self._emit(
                        AudioRouteEvent(
                            generation=snapshot.generation,
                            kind=RouteEventKind.SNAPSHOT_CHANGED,
                            monotonic_ns=time.perf_counter_ns(),
                            public_summary="audio device snapshot changed",
                            error_code=snapshot.error_code,
                        )
                    )
            except Exception as exc:
                self._emit(
                    AudioRouteEvent(
                        generation=max(0, previous_generation or 0),
                        kind=RouteEventKind.INTERRUPTED,
                        monotonic_ns=time.perf_counter_ns(),
                        public_summary="audio route observer interrupted",
                        error_code=f"route_observer_failed:{type(exc).__name__}",
                    )
                )
            self._stop_event.wait(self._poll_interval_seconds)

    def _emit(self, event: AudioRouteEvent) -> None:
        with self._lock:
            sink = self._sink
        if sink is None:
            return
        try:
            sink(event)
        except Exception:
            # A consumer cannot terminate the platform observer thread.
            return
