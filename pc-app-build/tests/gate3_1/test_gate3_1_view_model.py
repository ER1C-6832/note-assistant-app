from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

pytest.importorskip("PySide6")

from app.assistant import (  # noqa: E402
    AssistantController,
    AssistantPreferencesStore,
    VoiceInteractionMode,
)
from app.assistant.testing import ScriptedFakeTransport  # noqa: E402
from app.ui import AssistantViewModel  # noqa: E402


async def _wait_until(predicate, timeout: float = 2.0) -> None:
    async def wait_loop() -> None:
        while not predicate():
            await asyncio.sleep(0.01)

    await asyncio.wait_for(wait_loop(), timeout=timeout)


@pytest.mark.asyncio
async def test_view_model_persists_launcher_position_with_debounce(tmp_path: Path) -> None:
    store = AssistantPreferencesStore(tmp_path / "assistant_preferences.json")
    transport = ScriptedFakeTransport()
    controller = AssistantController(
        transport=transport,
        clock=transport.clock,
        preferences_store=store,
    )
    view_model = AssistantViewModel(
        controller,
        preferences_store=store,
        initial_preferences=store.load(),
    )

    try:
        view_model.requestLauncherPosition(-1.0, 0.3)
        view_model.requestLauncherPosition(0.42, 2.0)
        await _wait_until(
            lambda: (
                store.path.is_file()
                and store.load().launcher_x_ratio == pytest.approx(0.42)
                and store.load().launcher_y_ratio == pytest.approx(1.0)
            )
        )
        assert view_model.launcherXRatio == pytest.approx(0.42)
        assert view_model.launcherYRatio == pytest.approx(1.0)
    finally:
        await view_model.close()
        await controller.shutdown()


@pytest.mark.asyncio
async def test_view_model_exposes_state_driven_aurora_and_mode_selector(tmp_path: Path) -> None:
    store = AssistantPreferencesStore(tmp_path / "assistant_preferences.json")
    transport = ScriptedFakeTransport()
    controller = AssistantController(
        transport=transport,
        clock=transport.clock,
        preferences_store=store,
    )
    view_model = AssistantViewModel(controller, preferences_store=store)

    try:
        assert view_model.auroraVisualState == "idle"
        assert view_model.compactStatusLabel == "关闭"
        assert view_model.streamingCapabilityReady is False

        view_model.requestVoiceInteractionMode("streaming_conversation")
        await _wait_until(
            lambda: controller.state.conversation.preferred_voice_mode
            is VoiceInteractionMode.STREAMING_CONVERSATION
        )
        await _wait_until(lambda: not view_model.commandBusy)
        assert view_model.voiceInteractionMode == "streaming_conversation"
        assert view_model.auroraColorA.startswith("#")
        assert view_model.auroraSpeed > 0
    finally:
        await view_model.close()
        await controller.shutdown()
