from __future__ import annotations

import asyncio
from dataclasses import dataclass

import pytest

from app.assistant import (
    AssistantActivationStatus,
    AssistantCapability,
    AssistantController,
    AssistantPhase,
    CapabilityStatus,
    DeviceIdentityManager,
    DeviceIdentityStore,
    FakeActivationClient,
    RuntimeConfigStore,
)
from app.assistant.activation import ActivationOutcome, ActivationOutcomeStatus
from app.assistant.testing import FakeClock, ScriptedFakeTransport


@dataclass
class StaticActivationClient:
    outcome: ActivationOutcome

    async def run(self) -> ActivationOutcome:
        return self.outcome


@dataclass
class BlockingActivationClient:
    gate: asyncio.Event
    cancelled: bool = False
    calls: int = 0

    async def run(self) -> ActivationOutcome:
        self.calls += 1
        try:
            await self.gate.wait()
        except asyncio.CancelledError:
            self.cancelled = True
            raise
        return ActivationOutcome(
            status=ActivationOutcomeStatus.ACTIVATED,
            message="late activation",
            websocket_url_public="wss://late.example/ws",
        )


def _runtime_components(tmp_path):
    store = RuntimeConfigStore(tmp_path / "assistant_runtime.json")
    manager = DeviceIdentityManager(DeviceIdentityStore(store))
    fake = FakeActivationClient(config_store=store, identity_manager=manager)
    return store, manager, fake


@pytest.mark.asyncio
async def test_controller_identity_and_fake_activation_use_single_event_pump(
    tmp_path,
) -> None:
    store, manager, fake = _runtime_components(tmp_path)
    clock = FakeClock()
    controller = AssistantController(
        transport=ScriptedFakeTransport(clock=clock),
        clock=clock,
        identity_manager=manager,
        fake_activation_client=fake,
    )

    try:
        await controller.ensure_device_identity()
        identity_state = await controller.wait_for_state(
            lambda state: state.identity.identity_ready
        )
        assert identity_state.phase is AssistantPhase.DISABLED
        assert identity_state.identity.identity_generation == 1
        assert (
            identity_state.capability_status(AssistantCapability.IDENTITY)
            is CapabilityStatus.ACTIVE
        )

        await controller.use_fake_runtime()
        await controller.run_fake_activation()
        activated = await controller.wait_for_state(
            lambda state: state.activation.status is AssistantActivationStatus.ACTIVATED
        )

        assert activated.phase is AssistantPhase.DISABLED
        assert activated.connection.websocket_url_public is not None
        assert activated.connection.websocket_url_public.startswith("wss://fake.local/")
        assert activated.protocol.last_server_json_redacted is not None
        assert "gate2.2-fake-token" not in activated.protocol.last_server_json_redacted
        assert store.load().real.websocket_url == ""
        assert (
            activated.capability_status(AssistantCapability.ACTIVATION) is CapabilityStatus.ACTIVE
        )
    finally:
        await controller.shutdown()


@pytest.mark.asyncio
async def test_activation_mode_mismatch_fails_before_calling_fake_client(
    tmp_path,
) -> None:
    _, manager, fake = _runtime_components(tmp_path)
    clock = FakeClock()
    controller = AssistantController(
        transport=ScriptedFakeTransport(clock=clock),
        clock=clock,
        identity_manager=manager,
        fake_activation_client=fake,
    )

    try:
        await controller.run_fake_activation()
        assert controller.state.error is not None
        assert controller.state.error.code == "activation_runtime_mode_mismatch"
    finally:
        await controller.shutdown()


@pytest.mark.asyncio
async def test_disable_cancels_blocked_activation_and_late_result_cannot_apply(
    tmp_path,
) -> None:
    _, manager, _ = _runtime_components(tmp_path)
    gate = asyncio.Event()
    blocking = BlockingActivationClient(gate)
    clock = FakeClock()
    controller = AssistantController(
        transport=ScriptedFakeTransport(clock=clock),
        clock=clock,
        identity_manager=manager,
        real_activation_client=blocking,
    )

    try:
        await controller.enable_assistant()
        await controller.run_real_activation()
        await asyncio.sleep(0)
        assert controller.state.phase is AssistantPhase.ACTIVATING

        await controller.disable_assistant()
        assert blocking.cancelled is True
        assert controller.state.phase is AssistantPhase.DISABLED
        assert controller.pending_effect_count == 0

        gate.set()
        await asyncio.sleep(0)
        assert controller.state.phase is AssistantPhase.DISABLED
        assert controller.state.connection.websocket_url_public is None
    finally:
        await controller.shutdown()


@pytest.mark.asyncio
async def test_duplicate_activation_request_does_not_start_parallel_effect(
    tmp_path,
) -> None:
    _, manager, _ = _runtime_components(tmp_path)
    gate = asyncio.Event()
    blocking = BlockingActivationClient(gate)
    clock = FakeClock()
    controller = AssistantController(
        transport=ScriptedFakeTransport(clock=clock),
        clock=clock,
        identity_manager=manager,
        real_activation_client=blocking,
    )

    try:
        await controller.enable_assistant()
        await controller.run_real_activation()
        await asyncio.sleep(0)
        await controller.run_real_activation()
        await asyncio.sleep(0)

        assert blocking.calls == 1
        assert controller.state.phase is AssistantPhase.ACTIVATING
        assert controller.state.status_text == "Assistant Activation 已在进行中"
    finally:
        await controller.shutdown()


@pytest.mark.asyncio
async def test_switching_runtime_cancels_inflight_activation(tmp_path) -> None:
    _, manager, _ = _runtime_components(tmp_path)
    gate = asyncio.Event()
    blocking = BlockingActivationClient(gate)
    clock = FakeClock()
    controller = AssistantController(
        transport=ScriptedFakeTransport(clock=clock),
        clock=clock,
        identity_manager=manager,
        real_activation_client=blocking,
    )

    try:
        await controller.enable_assistant()
        await controller.run_real_activation()
        await asyncio.sleep(0)
        assert controller.state.phase is AssistantPhase.ACTIVATING

        await controller.use_fake_runtime()

        assert blocking.cancelled is True
        assert controller.state.runtime_mode.value == "fake"
        assert controller.state.phase is AssistantPhase.IDLE
        assert controller.pending_effect_count == 0
    finally:
        await controller.shutdown()


@pytest.mark.asyncio
async def test_real_activation_required_is_visible_without_exposing_secrets(tmp_path) -> None:
    _, manager, _ = _runtime_components(tmp_path)
    client = StaticActivationClient(
        ActivationOutcome(
            status=ActivationOutcomeStatus.REQUIRED,
            message="请完成设备激活",
            websocket_url_public="wss://assistant.example/ws",
            activation_code="482913",
            authorization_url="https://auth.example/devices",
            diagnostics_json_redacted='{"challenge":"***","token":"***"}',
        )
    )
    clock = FakeClock()
    controller = AssistantController(
        transport=ScriptedFakeTransport(clock=clock),
        clock=clock,
        identity_manager=manager,
        real_activation_client=client,
    )

    try:
        await controller.run_real_activation()
        required = await controller.wait_for_state(
            lambda state: state.activation.status is AssistantActivationStatus.REQUIRED
        )

        assert required.phase is AssistantPhase.DISABLED
        assert required.activation.activation_code == "482913"
        assert required.activation.authorization_url == "https://auth.example/devices"
        assert required.connection.websocket_url_public == "wss://assistant.example/ws"
        assert required.protocol.last_server_json_redacted == ('{"challenge":"***","token":"***"}')
    finally:
        await controller.shutdown()


@pytest.mark.asyncio
async def test_controller_reset_identity_replaces_public_identity_generation(tmp_path) -> None:
    _, manager, _ = _runtime_components(tmp_path)
    clock = FakeClock()
    controller = AssistantController(
        transport=ScriptedFakeTransport(clock=clock),
        clock=clock,
        identity_manager=manager,
    )

    try:
        await controller.ensure_device_identity()
        first = await controller.wait_for_state(lambda state: state.identity.identity_ready)
        first_device = first.identity.device_id_masked

        await controller.reset_device_identity()
        reset = await controller.wait_for_state(
            lambda state: state.identity.identity_ready and state.identity.identity_generation == 2
        )

        assert reset.identity.device_id_masked != first_device
        assert reset.activation.status is AssistantActivationStatus.UNKNOWN
        assert reset.connection.websocket_url_public is None
    finally:
        await controller.shutdown()
