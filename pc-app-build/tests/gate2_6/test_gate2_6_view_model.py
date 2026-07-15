from __future__ import annotations

import asyncio

import pytest

pytest.importorskip("PySide6")

from app.assistant import (  # noqa: E402
    AssistantController,
    AssistantPhase,
    DeviceIdentity,
    AssistantRuntimeMode,
    ConversationStateMachine,
    ReconnectPolicy,
)
from app.assistant.testing import (
    OpenSucceeded,
    ScriptedFakeTransport,
    TextReply,
)  # noqa: E402
from app.ui import AssistantViewModel  # noqa: E402


class _IdentityManager:
    def __init__(self) -> None:
        self._identity = DeviceIdentity(
            device_id="38:00:00:00:00:01",
            client_id="gate2-6-client-id",
            serial_number="gate2-6-serial",
            hmac_key="gate2-6-hmac",
            generation=1,
            source="test",
        )

    async def ensure_identity(self) -> DeviceIdentity:
        return self._identity

    async def reset_identity(self) -> DeviceIdentity:
        self._identity = DeviceIdentity(
            device_id=self._identity.device_id,
            client_id=self._identity.client_id,
            serial_number=self._identity.serial_number,
            hmac_key=self._identity.hmac_key,
            generation=self._identity.generation + 1,
            source="test",
        )
        return self._identity


async def _wait_until(predicate, *, timeout: float = 2.0) -> None:
    async def wait_loop() -> None:
        while not predicate():
            await asyncio.sleep(0)

    await asyncio.wait_for(wait_loop(), timeout=timeout)


@pytest.mark.asyncio
async def test_view_model_projects_controller_state_and_dispatches_text() -> None:
    transport = ScriptedFakeTransport(
        open_steps=[OpenSucceeded(session_id="gate2-6-session")],
        text_steps=[TextReply("Gate 2.6 reply")],
    )
    controller = AssistantController(
        transport=transport,
        state_machine=ConversationStateMachine(ReconnectPolicy(jitter_fraction=0.0)),
        clock=transport.clock,
    )
    view_model = AssistantViewModel(controller)

    try:
        await controller.use_fake_runtime()
        await controller.enable_assistant()
        await controller.connect()
        await controller.wait_for_state(lambda state: state.is_connected)

        assert view_model.enabled
        assert view_model.connected
        assert view_model.phase == AssistantPhase.CONNECTED.value
        assert view_model.runtimeMode == AssistantRuntimeMode.FAKE.value
        assert view_model.canSendText
        assert view_model.sessionIdMasked

        view_model.requestSendText("你好")
        await controller.wait_for_state(
            lambda state: state.conversation.last_assistant_text == "Gate 2.6 reply"
        )
        await _wait_until(lambda: not view_model.commandBusy)

        assert view_model.lastUserText == "你好"
        assert view_model.lastAssistantText == "Gate 2.6 reply"
        assert transport.sent_texts[-1][1] == "你好"
    finally:
        await view_model.close()
        await controller.shutdown()


@pytest.mark.asyncio
async def test_view_model_enable_and_runtime_mode_slots_use_controller_commands() -> None:
    transport = ScriptedFakeTransport()
    controller = AssistantController(
        transport=transport,
        state_machine=ConversationStateMachine(ReconnectPolicy(jitter_fraction=0.0)),
        clock=transport.clock,
        identity_manager=_IdentityManager(),
    )
    view_model = AssistantViewModel(controller)

    try:
        view_model.requestRuntimeMode("fake")
        await _wait_until(lambda: controller.state.runtime_mode is AssistantRuntimeMode.FAKE)
        await _wait_until(lambda: not view_model.commandBusy)

        view_model.requestSetEnabled(True)
        await _wait_until(lambda: controller.state.enabled)
        await _wait_until(lambda: not view_model.commandBusy)

        assert view_model.enabled
        assert view_model.runtimeMode == "fake"
        assert view_model.phase == AssistantPhase.IDLE.value
    finally:
        await view_model.close()
        await controller.shutdown()


@pytest.mark.asyncio
async def test_view_model_never_exposes_secrets_in_diagnostics() -> None:
    transport = ScriptedFakeTransport(open_steps=[OpenSucceeded()])
    controller = AssistantController(
        transport=transport,
        state_machine=ConversationStateMachine(ReconnectPolicy(jitter_fraction=0.0)),
        clock=transport.clock,
    )
    view_model = AssistantViewModel(controller)

    try:
        await controller.use_fake_runtime()
        await controller.enable_assistant()
        await controller.connect()
        await controller.wait_for_state(lambda state: state.is_connected)

        combined = "\n".join(
            (
                view_model.lastClientJsonRedacted,
                view_model.lastServerJsonRedacted,
                view_model.lastProtocolError,
                view_model.websocketUrl,
            )
        ).lower()
        assert "bearer " not in combined
        assert "gate2.2-fake-token" not in combined
    finally:
        await view_model.close()
        await controller.shutdown()
