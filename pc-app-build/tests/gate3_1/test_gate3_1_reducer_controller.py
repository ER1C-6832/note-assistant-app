from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from app.assistant import (
    AssistantController,
    AssistantPreferencesStore,
    AssistantState,
    ConversationStateMachine,
    VoiceInteractionMode,
)
from app.assistant.effects import SetStreamingBargeIn, SetVoiceInteractionMode
from app.assistant.events import StreamingBargeInRequested, VoiceInteractionModeRequested
from app.assistant.testing import ScriptedFakeTransport


def test_reducer_activates_preferences_without_claiming_streaming_runtime() -> None:
    machine = ConversationStateMachine()
    current = AssistantState.disabled(now_ns=1)

    mode = machine.reduce(
        current,
        VoiceInteractionModeRequested(
            at_ns=2,
            mode=VoiceInteractionMode.STREAMING_CONVERSATION,
        ),
    )
    assert (
        mode.state.conversation.preferred_voice_mode is VoiceInteractionMode.STREAMING_CONVERSATION
    )
    assert mode.state.phase is current.phase
    assert mode.effects == (
        SetVoiceInteractionMode(mode=VoiceInteractionMode.STREAMING_CONVERSATION),
    )

    barge = machine.reduce(
        mode.state,
        StreamingBargeInRequested(at_ns=3, enabled=True),
    )
    assert barge.state.conversation.streaming_barge_in_enabled is True
    assert barge.effects == (SetStreamingBargeIn(enabled=True),)
    assert barge.state.conversation.streaming_session_active is False


@pytest.mark.asyncio
async def test_controller_persists_voice_preferences_through_effect_runner(tmp_path: Path) -> None:
    store = AssistantPreferencesStore(tmp_path / "assistant_preferences.json")
    transport = ScriptedFakeTransport()
    controller = AssistantController(
        transport=transport,
        clock=transport.clock,
        preferences_store=store,
    )

    try:
        await controller.set_voice_interaction_mode(VoiceInteractionMode.STREAMING_CONVERSATION)
        await controller.set_streaming_barge_in_enabled(True)

        async def persisted() -> bool:
            loaded = await asyncio.to_thread(store.load)
            return (
                loaded.voice_interaction_mode is VoiceInteractionMode.STREAMING_CONVERSATION
                and loaded.streaming_barge_in_enabled
            )

        async def wait_loop() -> None:
            while not await persisted():
                await asyncio.sleep(0.01)

        await asyncio.wait_for(wait_loop(), timeout=2.0)
        assert (
            controller.state.conversation.preferred_voice_mode
            is VoiceInteractionMode.STREAMING_CONVERSATION
        )
        assert controller.state.conversation.streaming_barge_in_enabled is True
    finally:
        await controller.shutdown()


@pytest.mark.asyncio
async def test_preference_write_failure_is_visible_but_keeps_phase() -> None:
    class FailingStore:
        def update_voice_interaction_mode(self, mode):
            raise OSError("secret path details")

        def update_streaming_barge_in_enabled(self, enabled):
            raise OSError("secret path details")

    transport = ScriptedFakeTransport()
    controller = AssistantController(
        transport=transport,
        clock=transport.clock,
        preferences_store=FailingStore(),  # type: ignore[arg-type]
    )
    try:
        await controller.set_voice_interaction_mode(VoiceInteractionMode.STREAMING_CONVERSATION)
        failed = await controller.wait_for_state(
            lambda state: bool(
                state.error and state.error.code == "assistant_preferences_write_failed"
            ),
            timeout_seconds=2.0,
        )
        assert failed.phase is AssistantState.disabled().phase
        assert (
            failed.conversation.preferred_voice_mode is VoiceInteractionMode.STREAMING_CONVERSATION
        )
        assert failed.error is not None and failed.error.recoverable
    finally:
        await controller.shutdown()
