from __future__ import annotations

import time
from dataclasses import replace
from typing import Any

from app.assistant.audio.gate6_contracts import KeywordSpotResult
from app.assistant.state import (
    AssistantAudioStatus,
    AssistantConnectionStatus,
    AssistantPhase,
    AssistantState,
    VoiceInteractionMode,
)


class FakePyAudioManager:
    def __init__(self) -> None:
        self.devices = [
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
                "defaultSampleRate": 16000.0,
                "defaultLowInputLatency": 0.01,
                "defaultLowOutputLatency": 0.02,
            },
        ]

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
        return None


class FakeRouteObserver:
    running = False
    closed = False
    paused = False

    def start(self, sink) -> None:
        self.sink = sink
        self.running = True

    def stop(self) -> None:
        self.running = False

    def close(self) -> None:
        self.stop()
        self.closed = True

    def pause(self) -> None:
        self.paused = True

    def resume(self) -> None:
        self.paused = False


class FakeDuplexSession:
    open_stream_count = 0

    def close(self) -> None:
        self.open_stream_count = 0


class FakeController:
    def __init__(self) -> None:
        disabled = AssistantState.disabled(now_ns=0)
        self.state = replace(
            disabled,
            enabled=True,
            phase=AssistantPhase.CONNECTED,
            connection=replace(
                disabled.connection,
                status=AssistantConnectionStatus.CONNECTED,
                session_id="fake-session",
                connection_generation=1,
            ),
            conversation=replace(
                disabled.conversation,
                preferred_voice_mode=VoiceInteractionMode.STREAMING_CONVERSATION,
            ),
            status_text="已连接",
        )
        self.closed = False
        self.starts: list[dict[str, object]] = []
        self._listeners = []

    def subscribe(self, listener):
        self._listeners.append(listener)

        def unsubscribe() -> None:
            if listener in self._listeners:
                self._listeners.remove(listener)

        return unsubscribe

    async def start_streaming_conversation(
        self,
        permission_granted: bool,
        source,
        wake_keyword: str | None,
    ) -> None:
        self.starts.append(
            {
                "permission_granted": permission_granted,
                "source": source,
                "wake_keyword": wake_keyword,
            }
        )
        self.state = replace(
            self.state,
            phase=AssistantPhase.LISTENING,
            audio=replace(
                self.state.audio,
                status=AssistantAudioStatus.RECORDING,
                capture_generation=self.state.audio.capture_generation + 1,
            ),
            conversation=replace(
                self.state.conversation,
                streaming_session_active=True,
                active_voice_turn_token=1,
            ),
        )
        self.notify()

    def finish_session(self) -> None:
        self.state = replace(
            self.state,
            phase=AssistantPhase.CONNECTED,
            audio=replace(self.state.audio, status=AssistantAudioStatus.IDLE),
            conversation=replace(
                self.state.conversation,
                streaming_session_active=False,
                active_voice_turn_token=None,
            ),
        )
        self.notify()

    def set_disabled(self) -> None:
        disabled = AssistantState.disabled(now_ns=time.perf_counter_ns())
        self.state = disabled
        self.notify()

    def notify(self) -> None:
        for listener in tuple(self._listeners):
            listener(self.state)


class FakeKwsRuntime:
    def __init__(self) -> None:
        self.active = False
        self.worker_alive = False
        self.queue_size = 0
        self.overflow_count = 0
        self.generation = 0
        self.hit_sink = None
        self.stop_count = 0

    def start(self, generation: int, route_generation: int, hit_sink) -> None:
        assert route_generation > 0
        self.generation = generation
        self.hit_sink = hit_sink
        self.active = True
        self.worker_alive = True

    def stop(self) -> None:
        self.stop_count += 1
        self.active = False
        self.worker_alive = False
        self.queue_size = 0

    def emit_hit(self, *, at_ns: int | None = None, keyword: str = "小智") -> None:
        assert self.hit_sink is not None
        self.hit_sink(
            KeywordSpotResult(
                generation=self.generation,
                keyword_public_name=keyword,
                detected_at_ns=at_ns or time.perf_counter_ns(),
            )
        )


class FakeRuntimeFactory:
    def __init__(self) -> None:
        self.instances: list[FakeKwsRuntime] = []

    def __call__(self, _model, _supervisor) -> FakeKwsRuntime:
        value = FakeKwsRuntime()
        self.instances.append(value)
        return value
