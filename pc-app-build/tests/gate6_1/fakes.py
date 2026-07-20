from __future__ import annotations

from typing import Any


class FakePyAudioManager:
    def __init__(self, devices: list[dict[str, Any]] | None = None) -> None:
        self.devices = devices or [
            {
                "index": 0,
                "name": "Default Microphone",
                "hostApi": 0,
                "maxInputChannels": 1,
                "maxOutputChannels": 0,
                "defaultSampleRate": 16000.0,
                "defaultLowInputLatency": 0.02,
            },
            {
                "index": 1,
                "name": "Default Speakers",
                "hostApi": 0,
                "maxInputChannels": 0,
                "maxOutputChannels": 2,
                "defaultSampleRate": 48000.0,
                "defaultLowOutputLatency": 0.1,
            },
            {
                "index": 2,
                "name": "USB Headset",
                "hostApi": 0,
                "maxInputChannels": 1,
                "maxOutputChannels": 2,
                "defaultSampleRate": 48000.0,
                "defaultLowInputLatency": 0.01,
                "defaultLowOutputLatency": 0.02,
            },
        ]
        self.terminated = False

    def get_device_count(self) -> int:
        return len(self.devices)

    def get_device_info_by_index(self, index: int) -> dict[str, Any]:
        return dict(self.devices[index])

    def get_host_api_info_by_index(self, _index: int) -> dict[str, str]:
        return {"name": "Windows WASAPI"}

    def get_default_input_device_info(self) -> dict[str, int]:
        return {"index": 0}

    def get_default_output_device_info(self) -> dict[str, int]:
        return {"index": 1}

    def is_format_supported(self, _rate: int, **_kwargs: object) -> bool:
        return True

    def terminate(self) -> None:
        self.terminated = True


class FakeRouteObserver:
    def __init__(self) -> None:
        self.running = False
        self.closed = False
        self.sink = None

    def start(self, sink) -> None:
        self.sink = sink
        self.running = True

    def stop(self) -> None:
        self.running = False
        self.sink = None

    def close(self) -> None:
        self.stop()
        self.closed = True


class FakeDuplexSession:
    def __init__(self) -> None:
        self.open_stream_count = 0
        self.closed = False

    def close(self) -> None:
        self.open_stream_count = 0
        self.closed = True
