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


@pytest.mark.asyncio
async def test_legacy_py_xiaozhi_identity_is_migrated_before_generating_new_identity(
    tmp_path,
) -> None:
    from app.assistant.identity import LegacyPyXiaozhiIdentitySource

    legacy_config_dir = tmp_path / "py-xiaozhi" / "config"
    legacy_config_dir.mkdir(parents=True)
    (legacy_config_dir / "efuse.json").write_text(
        """
        {
          "mac_address": "AA-BB-CC-DD-EE-FF",
          "serial_number": "SN-LEGACY",
          "hmac_key": "legacy-hmac",
          "activation_status": true
        }
        """,
        encoding="utf-8",
    )
    (legacy_config_dir / "config.json").write_text(
        """
        {
          "SYSTEM_OPTIONS": {
            "CLIENT_ID": "legacy-client-id",
            "DEVICE_ID": "aa:bb:cc:dd:ee:ff"
          }
        }
        """,
        encoding="utf-8",
    )

    config_store = RuntimeConfigStore(tmp_path / "assistant_runtime.json")
    legacy_source = LegacyPyXiaozhiIdentitySource(legacy_config_dir)
    manager = DeviceIdentityManager(
        DeviceIdentityStore(config_store),
        legacy_identity=legacy_source.load,
    )

    identity = await manager.ensure_identity()

    assert identity.device_id == "aa:bb:cc:dd:ee:ff"
    assert identity.client_id == "legacy-client-id"
    assert identity.serial_number == "SN-LEGACY"
    assert identity.hmac_key == "legacy-hmac"
    assert legacy_source.local_activation_marked is True
    assert config_store.load().identity is not None


@pytest.mark.asyncio
async def test_pre_fix_unknown_identity_is_repaired_from_legacy_and_clears_bad_activation(
    tmp_path,
) -> None:
    from dataclasses import replace

    from app.assistant.identity import DeviceIdentity, LegacyPyXiaozhiIdentitySource

    legacy_config_dir = tmp_path / "legacy" / "config"
    legacy_config_dir.mkdir(parents=True)
    (legacy_config_dir / "efuse.json").write_text(
        """
        {
          "mac_address": "10-20-30-40-50-60",
          "serial_number": "SN-OLD-PC",
          "hmac_key": "old-pc-hmac",
          "activation_status": true
        }
        """,
        encoding="utf-8",
    )
    (legacy_config_dir / "config.json").write_text(
        """
        {
          "SYSTEM_OPTIONS": {
            "CLIENT_ID": "old-pc-client",
            "DEVICE_ID": "10:20:30:40:50:60"
          }
        }
        """,
        encoding="utf-8",
    )

    config_store = RuntimeConfigStore(tmp_path / "assistant_runtime.json")
    store = DeviceIdentityStore(config_store)
    store.save(
        DeviceIdentity(
            device_id="22:33:44:55:66:77",
            client_id="bug-generated-client",
            serial_number="BUG-SERIAL",
            hmac_key="bug-hmac",
            generation=1,
            source="unknown",
        )
    )
    config_store.update(
        lambda current: replace(
            current,
            real=replace(
                current.real,
                websocket_url="wss://bad-identity.example/ws",
                websocket_token="bad-token",
                activated=False,
                activation_code="046173",
                activation_challenge="bad-challenge",
            ),
        )
    )

    source = LegacyPyXiaozhiIdentitySource(legacy_config_dir)
    manager = DeviceIdentityManager(store, legacy_identity=source.load)
    repaired = await manager.ensure_identity()
    persisted = config_store.load()

    assert manager.last_identity_replaced is True
    assert repaired.device_id == "10:20:30:40:50:60"
    assert repaired.client_id == "old-pc-client"
    assert repaired.source == "legacy_config"
    assert repaired.generation == 2
    assert persisted.real.websocket_url == ""
    assert persisted.real.websocket_token == ""
    assert persisted.real.activation_code == ""
    assert persisted.real.activation_challenge == ""


def test_legacy_source_combines_partial_files_and_machine_fingerprint(
    tmp_path,
    monkeypatch,
) -> None:
    from app.assistant.identity import LegacyPyXiaozhiIdentitySource
    from app.assistant.identity import legacy as legacy_module

    first_dir = tmp_path / "first" / "config"
    second_dir = tmp_path / "second" / "config"
    first_dir.mkdir(parents=True)
    second_dir.mkdir(parents=True)
    (first_dir / "config.json").write_text(
        '{"SYSTEM_OPTIONS":{"CLIENT_ID":"remembered-client"}}',
        encoding="utf-8",
    )
    (second_dir / "efuse.json").write_text(
        '{"activation_status":true}',
        encoding="utf-8",
    )
    monkeypatch.setattr(
        legacy_module,
        "_physical_mac_address",
        lambda: "aa:bb:cc:dd:ee:11",
    )
    monkeypatch.setattr(legacy_module, "_windows_machine_guid", lambda: "machine-guid")
    monkeypatch.setattr(legacy_module.platform, "node", lambda: "test-host")

    source = LegacyPyXiaozhiIdentitySource(
        config_dir=first_dir,
        additional_config_dirs=(second_dir,),
    )
    identity = source.load()

    assert identity is not None
    assert identity.device_id == "aa:bb:cc:dd:ee:11"
    assert identity.client_id == "remembered-client"
    assert identity.source == "machine_fingerprint_with_legacy_client"
    assert identity.serial_number.startswith("SN-")
    assert len(identity.hmac_key) == 64


def test_legacy_source_finds_platformdirs_windows_nested_app_directory(tmp_path) -> None:
    from app.assistant.identity import LegacyPyXiaozhiIdentitySource

    nested = tmp_path / "py-xiaozhi" / "py-xiaozhi" / "config"
    nested.mkdir(parents=True)
    (nested / "efuse.json").write_text(
        '{"mac_address":"de:ad:be:ef:00:01","serial_number":"SN-NESTED",'
        '"hmac_key":"nested-hmac","activation_status":true}',
        encoding="utf-8",
    )
    (nested / "config.json").write_text(
        '{"SYSTEM_OPTIONS":{"CLIENT_ID":"nested-client",' '"DEVICE_ID":"de:ad:be:ef:00:01"}}',
        encoding="utf-8",
    )

    source = LegacyPyXiaozhiIdentitySource.from_local_app_data(tmp_path)
    identity = source.load()

    assert identity is not None
    assert identity.client_id == "nested-client"
    assert identity.source == "legacy_config"
    assert source.imported_from == nested
