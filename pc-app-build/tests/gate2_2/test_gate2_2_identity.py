from __future__ import annotations

import pytest

from app.assistant.identity import DeviceIdentityManager, DeviceIdentityStore
from app.assistant.runtime_config import RuntimeConfigStore


@pytest.mark.asyncio
async def test_identity_is_stable_across_manager_restarts(tmp_path) -> None:
    config_store = RuntimeConfigStore(tmp_path / "assistant_runtime.json")
    first_manager = DeviceIdentityManager(DeviceIdentityStore(config_store))
    first = await first_manager.ensure_identity()

    second_manager = DeviceIdentityManager(DeviceIdentityStore(config_store))
    second = await second_manager.ensure_identity()

    assert second == first
    assert first.generation == 1
    assert first.device_id_masked != first.device_id
    assert first.client_id_masked != first.client_id
    assert first.hmac_key not in first.device_id_masked


@pytest.mark.asyncio
async def test_reset_identity_increments_generation_and_clears_bound_credentials(
    tmp_path,
) -> None:
    config_store = RuntimeConfigStore(tmp_path / "assistant_runtime.json")
    config_store.update_real_endpoints(
        ota_url="https://ota.example/v1",
        authorization_url="https://auth.example/devices",
    )
    manager = DeviceIdentityManager(DeviceIdentityStore(config_store))
    first = await manager.ensure_identity()

    config_store.update(
        lambda current: current.__class__(
            schema_version=current.schema_version,
            identity=current.identity,
            real=current.real.__class__(
                ota_url=current.real.ota_url,
                authorization_url=current.real.authorization_url,
                activation_version=current.real.activation_version,
                websocket_url="wss://real.example/ws",
                websocket_token="real-token",
                activated=True,
            ),
            fake=current.fake.__class__(
                websocket_url="wss://fake.local/ws",
                websocket_token="fake-token",
                activated=True,
            ),
        )
    )

    reset = await manager.reset_identity()
    persisted = config_store.load()

    assert reset.generation == first.generation + 1
    assert reset.device_id != first.device_id
    assert reset.client_id != first.client_id
    assert persisted.identity is not None
    assert persisted.identity.generation == reset.generation
    assert persisted.real.ota_url == "https://ota.example/v1"
    assert persisted.real.authorization_url == "https://auth.example/devices"
    assert persisted.real.websocket_url == ""
    assert persisted.real.websocket_token == ""
    assert persisted.real.activated is False
    assert persisted.fake.websocket_url == ""
    assert persisted.fake.websocket_token == ""
