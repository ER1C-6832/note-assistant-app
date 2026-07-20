from __future__ import annotations

import asyncio
from dataclasses import replace

import pytest

from app.assistant.audio.barge_in import AcousticBargeInCoordinator
from app.assistant.audio.device_registry import PyAudioDeviceRegistry
from app.assistant.audio.gate6_contracts import (
    AudioProcessingMetrics,
    MicrophoneOwner,
    PlaybackActivity,
    ProcessingState,
)
from app.assistant.audio.models import PcmFrame
from app.assistant.audio.session_supervisor import AudioSessionSupervisor
from app.assistant.preferences import AssistantPreferencesStore
from app.assistant.state import (
    AssistantAudioStatus,
    AssistantConnectionStatus,
    AssistantEntrySource,
    AssistantPhase,
    AssistantState,
    StreamingConversationState,
    VoiceInteractionMode,
)


class _FakePyAudioManager:
    def get_device_count(self) -> int:
        return 2

    def get_device_info_by_index(self, index: int):
        if index == 0:
            return {
                "index": 0,
                "name": "Microphone",
                "hostApi": 0,
                "maxInputChannels": 1,
                "maxOutputChannels": 0,
                "defaultSampleRate": 16000.0,
                "defaultLowInputLatency": 0.02,
            }
        return {
            "index": 1,
            "name": "Speakers",
            "hostApi": 0,
            "maxInputChannels": 0,
            "maxOutputChannels": 2,
            "defaultSampleRate": 48000.0,
            "defaultLowOutputLatency": 0.1,
        }

    def get_host_api_info_by_index(self, _index: int):
        return {"name": "Windows WASAPI"}

    def get_default_input_device_info(self):
        return {"index": 0}

    def get_default_output_device_info(self):
        return {"index": 1}

    def is_format_supported(self, _rate: int, **_kwargs):
        return True

    def terminate(self) -> None:
        return None


class _Observer:
    def start(self, sink) -> None:
        self.sink = sink

    def stop(self) -> None:
        return None

    def close(self) -> None:
        return None


class _Duplex:
    def close(self) -> None:
        return None


class _Controller:
    def __init__(self) -> None:
        disabled = AssistantState.disabled(now_ns=0)
        self.state = replace(
            disabled,
            enabled=True,
            phase=AssistantPhase.SPEAKING,
            connection=replace(
                disabled.connection,
                status=AssistantConnectionStatus.CONNECTED,
                connection_generation=1,
                session_id="connection",
            ),
            audio=replace(
                disabled.audio,
                status=AssistantAudioStatus.PLAYING,
                capture_generation=4,
                playback_generation=7,
                last_audio_summary="playback_active stream=7 packets=3",
            ),
            conversation=replace(
                disabled.conversation,
                preferred_voice_mode=VoiceInteractionMode.STREAMING_CONVERSATION,
                active_entry_source=AssistantEntrySource.STREAMING_BUTTON,
                streaming_barge_in_enabled=True,
                streaming_session_active=True,
                streaming_generation=2,
                streaming_session_id="streaming",
                streaming_turn_index=1,
                streaming_state=StreamingConversationState.SPEAKING,
                voice_turn_counter=1,
                last_completed_voice_turn_token=1,
                last_completed_streaming_turn_token=1,
            ),
        )
        self.listeners = []
        self.confirm_count = 0

    def subscribe(self, listener):
        self.listeners.append(listener)
        return lambda: self.listeners.remove(listener) if listener in self.listeners else None

    async def confirm_acoustic_barge_in(self, **values) -> None:
        self.confirm_count += 1
        self.state = replace(
            self.state,
            phase=AssistantPhase.LISTENING,
            audio=replace(
                self.state.audio,
                status=AssistantAudioStatus.RECORDING,
                capture_generation=values["next_capture_generation"],
            ),
            conversation=replace(
                self.state.conversation,
                barge_in_trigger_count=self.state.conversation.barge_in_trigger_count + 1,
            ),
        )
        for listener in tuple(self.listeners):
            listener(self.state)


class _AudioEngine:
    def __init__(self) -> None:
        self.staged: dict[int, tuple[PcmFrame, ...]] = {}

    def stage_processed_pre_roll(self, generation: int, frames) -> None:
        self.staged[generation] = tuple(frames)

    def clear_staged_pre_roll(self, generation: int) -> None:
        self.staged.pop(generation, None)


class _Playback:
    def bind_render_reference_sink(self, sink) -> None:
        self.sink = sink


class _Runtime:
    def __init__(self) -> None:
        self.active = False
        self.worker_alive = False
        self.queue_size = 0
        self.overflow_count = 0
        self.confirm_sink = None

    def start(self, generation, route_generation, playback_generation, confirm_sink, failure_sink):
        del route_generation, failure_sink
        self.generation = generation
        self.playback_generation = playback_generation
        self.confirm_sink = confirm_sink
        self.active = True
        self.worker_alive = True

    def offer_render(self, _chunk) -> bool:
        return self.active

    def metrics(self):
        return AudioProcessingMetrics(
            backend_public_name="fake-apm",
            state=ProcessingState.READY,
            aec_available=True,
            aec_effective=True,
            ns_available=True,
            ns_effective=False,
            agc_available=True,
            agc_effective=False,
            render_frames=30,
            capture_frames=30,
            processed_frames=30,
        )

    def stop(self) -> None:
        self.active = False
        self.worker_alive = False

    def confirm(self) -> None:
        payload = b"\x01\x00" * 320
        frames = tuple(PcmFrame(self.generation, index, index + 1, payload) for index in range(8))
        self.confirm_sink(self.generation, self.playback_generation, frames)


async def _wait_until(predicate) -> None:
    for _ in range(200):
        if predicate():
            return
        await asyncio.sleep(0.005)
    raise TimeoutError("condition not reached")


@pytest.mark.asyncio
async def test_monitor_confirm_promotes_once_and_cleans_monitor_owner(tmp_path) -> None:
    store = AssistantPreferencesStore(tmp_path / "preferences.json")
    supervisor = AudioSessionSupervisor(
        store,
        registry=PyAudioDeviceRegistry(pyaudio_factory=_FakePyAudioManager),
        route_observer=_Observer(),
        duplex_session=_Duplex(),
    )
    await supervisor.start()
    supervisor.set_playback_activity(PlaybackActivity.PLAYING)
    controller = _Controller()
    audio_engine = _AudioEngine()
    playback = _Playback()
    runtimes: list[_Runtime] = []

    def factory(_supervisor):
        runtime = _Runtime()
        runtimes.append(runtime)
        return runtime

    coordinator = AcousticBargeInCoordinator(
        controller,
        supervisor,
        audio_engine,
        playback,
        runtime_factory=factory,
    )
    try:
        await coordinator.start()
        assert runtimes[-1].active
        assert supervisor.microphone_coordinator.owner is MicrophoneOwner.BARGE_IN_MONITOR

        runtimes[-1].confirm()
        await _wait_until(lambda: controller.confirm_count == 1)
        assert coordinator.snapshot.confirmed_count == 1
        assert coordinator.snapshot.monitor_uploaded_frames == 0
        assert len(audio_engine.staged[5]) == 8
        assert supervisor.microphone_coordinator.owner is MicrophoneOwner.ASSISTANT_CAPTURE
        assert not runtimes[-1].active
    finally:
        await supervisor.microphone_coordinator.force_release()
        await coordinator.close()
        await supervisor.close()

    assert coordinator.diagnostics()["pending_tasks"] == []
    assert supervisor.microphone_coordinator.owner is MicrophoneOwner.NONE
