"""PyAudio/PortAudio microphone adapter with a non-blocking native callback."""

from __future__ import annotations

import threading
import time
from typing import Any

from .models import (
    DEFAULT_CHANNELS,
    DEFAULT_SAMPLE_RATE_HZ,
    DEFAULT_SAMPLES_PER_FRAME,
    PcmFrame,
)
from .ports import PcmFrameSink


class PyAudioUnavailableError(RuntimeError):
    pass


class PyAudioCaptureAdapter:
    """Own one input stream; callback only copies a frame and calls the bounded sink."""

    def __init__(self, *, input_device_index: int | None = None) -> None:
        self._input_device_index = input_device_index
        self._lock = threading.RLock()
        self._audio: Any | None = None
        self._stream: Any | None = None
        self._generation: int | None = None
        self._sink: PcmFrameSink | None = None
        self._sequence = 0
        self._input_name: str | None = None
        self._closed = False

    @property
    def input_device_public_name(self) -> str | None:
        with self._lock:
            return self._input_name

    @property
    def is_active(self) -> bool:
        with self._lock:
            return self._stream is not None and self._generation is not None

    def start(self, generation: int, frame_sink: PcmFrameSink) -> None:
        with self._lock:
            if self._closed:
                raise RuntimeError("PyAudio capture adapter is closed")
            if self._stream is not None:
                raise RuntimeError("one PyAudio input stream is already active")
        try:
            import pyaudio
        except ImportError as exc:
            raise PyAudioUnavailableError(
                "PyAudio is not installed; run pip install -e .[dev]"
            ) from exc

        audio = pyaudio.PyAudio()
        try:
            device_index = self._input_device_index
            if device_index is None:
                info = audio.get_default_input_device_info()
                device_index = int(info["index"])
            else:
                info = audio.get_device_info_by_index(device_index)
            name = str(info.get("name") or f"input-{device_index}")

            with self._lock:
                self._audio = audio
                self._generation = generation
                self._sink = frame_sink
                self._sequence = 0
                self._input_name = name[:120]

            def callback(in_data, frame_count, time_info, status_flags):
                del frame_count, time_info, status_flags
                with self._lock:
                    active_generation = self._generation
                    sink = self._sink
                    sequence = self._sequence
                    if active_generation is None or sink is None:
                        return (None, pyaudio.paComplete)
                    self._sequence += 1
                try:
                    sink(
                        PcmFrame(
                            generation=active_generation,
                            sequence=sequence,
                            captured_at_ns=time.perf_counter_ns(),
                            pcm16_le=bytes(in_data),
                        )
                    )
                except Exception:
                    # Never unwind into PortAudio's native callback thread.
                    pass
                return (None, pyaudio.paContinue)

            stream = audio.open(
                format=pyaudio.paInt16,
                channels=DEFAULT_CHANNELS,
                rate=DEFAULT_SAMPLE_RATE_HZ,
                input=True,
                input_device_index=device_index,
                frames_per_buffer=DEFAULT_SAMPLES_PER_FRAME,
                stream_callback=callback,
                start=False,
            )
            with self._lock:
                self._stream = stream
            stream.start_stream()
        except Exception:
            with self._lock:
                self._audio = None
                self._stream = None
                self._generation = None
                self._sink = None
            audio.terminate()
            raise

    def stop(self, generation: int) -> None:
        with self._lock:
            if self._generation is None:
                return
            if self._generation != generation:
                raise RuntimeError("stale generation cannot stop the active PyAudio stream")
            stream = self._stream
            audio = self._audio
            self._stream = None
            self._audio = None
            self._generation = None
            self._sink = None
        try:
            if stream is not None:
                if stream.is_active():
                    stream.stop_stream()
                stream.close()
        finally:
            if audio is not None:
                audio.terminate()

    def close(self) -> None:
        with self._lock:
            generation = self._generation
            self._closed = True
        if generation is not None:
            self.stop(generation)
