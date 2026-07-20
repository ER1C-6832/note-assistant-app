from __future__ import annotations

import asyncio

import time
from pathlib import Path

import pytest

from app.assistant import (
    AssistantAudioStatus,
    AssistantController,
    AssistantEntrySource,
    VoiceActivityState,
    VoiceInteractionMode,
)
from app.assistant.audio import (
    AssistantAudioEngine,
    FakeCaptureScript,
    FakeOpusEncoder,
    ScriptedFakeAudioCapture,
    ScriptedVoiceActivityDetector,
)
from app.assistant.audio.device_registry import PyAudioDeviceRegistry
from app.assistant.audio.gate6_contracts import MicrophoneOwner
from app.assistant.audio.kws_model_registry import KwsModelRegistry
from app.assistant.audio.offline_kws import OfflineKwsCoordinator
from app.assistant.audio.session_supervisor import AudioSessionSupervisor
from app.assistant.preferences import AssistantPreferencesStore
from app.assistant.testing import OpenSucceeded, ScriptedFakeTransport

from gate6_2_fakes import (
    FakeDuplexSession,
    FakePyAudioManager,
    FakeRouteObserver,
    FakeRuntimeFactory,
)


def _model_registry(tmp_path: Path) -> KwsModelRegistry:
    registry = KwsModelRegistry(tmp_path / "models" / "kws")
    model = registry.resolve()
    model.root.mkdir(parents=True)
    for path in (model.tokens, model.encoder, model.decoder, model.joiner, model.keywords):
        path.write_bytes(b"fake")
    return registry


@pytest.mark.asyncio
async def test_real_controller_claims_atomic_kws_handoff_and_resumes_after_stop(
    tmp_path: Path,
) -> None:
    store = AssistantPreferencesStore(tmp_path / "preferences.json")
    store.update_offline_kws_enabled(True)
    supervisor = AudioSessionSupervisor(
        store,
        registry=PyAudioDeviceRegistry(pyaudio_factory=FakePyAudioManager),
        route_observer=FakeRouteObserver(),
        duplex_session=FakeDuplexSession(),
    )
    capture = ScriptedFakeAudioCapture(FakeCaptureScript.from_frames(()))
    engine = AssistantAudioEngine(
        capture=capture,
        encoder_factory=FakeOpusEncoder,
        vad_factory=lambda _timeout: ScriptedVoiceActivityDetector(
            (VoiceActivityState.WARMUP, VoiceActivityState.WAITING_FOR_SPEECH)
        ),
    )
    transport = ScriptedFakeTransport(open_steps=(OpenSucceeded(session_id="gate6-2-session"),))
    controller = AssistantController(
        transport=transport,
        clock=transport.clock,
        preferences_store=store,
        audio_engine=engine,
        microphone_coordinator=supervisor.microphone_coordinator,
    )
    factory = FakeRuntimeFactory()
    coordinator = OfflineKwsCoordinator(
        controller,
        store,
        supervisor,
        _model_registry(tmp_path),
        runtime_factory=factory,
    )
    try:
        await supervisor.start()
        await controller.enable_assistant()
        await controller.use_fake_runtime()
        await controller.connect()
        await controller.wait_for_state(lambda state: state.is_connected)
        await controller.set_voice_interaction_mode(VoiceInteractionMode.STREAMING_CONVERSATION)
        await coordinator.start()
        assert supervisor.microphone_coordinator.owner is MicrophoneOwner.WAKEWORD_KWS

        factory.instances[-1].emit_hit(at_ns=time.perf_counter_ns())
        started = await controller.wait_for_state(
            lambda state: state.conversation.streaming_session_active
            and state.audio.status is AssistantAudioStatus.RECORDING
        )
        assert started.conversation.active_entry_source is AssistantEntrySource.WAKEWORD
        assert supervisor.microphone_coordinator.owner is MicrophoneOwner.ASSISTANT_CAPTURE
        assert len(transport.listen_start_calls) == 1

        await controller.stop_streaming_conversation("gate6_2_test_stop")
        await controller.wait_for_state(
            lambda state: not state.conversation.streaming_session_active
        )
        for _ in range(100):
            if len(factory.instances) >= 2 and factory.instances[-1].active:
                break
            await asyncio.sleep(0.005)
        assert len(factory.instances) == 2
        assert factory.instances[-1].active is True
        assert supervisor.microphone_coordinator.owner is MicrophoneOwner.WAKEWORD_KWS
        assert coordinator.snapshot.resume_count == 2
    finally:
        await coordinator.close()
        await controller.shutdown()
        await supervisor.close()
