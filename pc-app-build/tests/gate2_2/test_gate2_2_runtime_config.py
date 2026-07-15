from __future__ import annotations

import json

import pytest

from app.assistant.runtime_config import (
    AssistantRuntimeConfig,
    RuntimeConfigError,
    RuntimeConfigStore,
)


def test_runtime_config_is_versioned_and_round_trips(tmp_path) -> None:
    path = tmp_path / "assistant_runtime.json"
    store = RuntimeConfigStore(path)

    initial = store.load()
    assert initial == AssistantRuntimeConfig()

    updated = store.update_real_endpoints(
        ota_url="https://ota.example/v1",
        authorization_url="https://auth.example/devices",
        activation_version="v2",
    )

    assert updated.schema_version == 1
    assert store.load() == updated
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["schema_version"] == 1
    assert payload["real"]["ota_url"] == "https://ota.example/v1"
    assert not path.with_name(f".{path.name}.tmp").exists()


def test_runtime_config_rejects_unknown_schema_without_overwriting(tmp_path) -> None:
    path = tmp_path / "assistant_runtime.json"
    path.write_text('{"schema_version":99}', encoding="utf-8")
    store = RuntimeConfigStore(path)

    with pytest.raises(RuntimeConfigError, match="不支持"):
        store.load()

    assert path.read_text(encoding="utf-8") == '{"schema_version":99}'


def test_runtime_config_supplies_project_default_real_endpoints(tmp_path) -> None:
    store = RuntimeConfigStore(tmp_path / "assistant_runtime.json")

    config = store.load()

    assert config.real.ota_url == "https://api.tenclass.net/xiaozhi/ota/"
    assert config.real.authorization_url == "https://xiaozhi.me/"
    assert config.real.activation_version == "v2"


def test_blank_persisted_real_endpoints_are_migrated_to_defaults(tmp_path) -> None:
    path = tmp_path / "assistant_runtime.json"
    path.write_text(
        '{"schema_version":1,"identity":null,"real":{"ota_url":"",'
        '"authorization_url":"","activation_version":"",'
        '"websocket_url":"","websocket_token":"","activated":false,'
        '"activation_code":"","activation_challenge":"",'
        '"activation_message":"","last_ota_json_redacted":""},'
        '"fake":{"websocket_url":"","websocket_token":"",'
        '"activated":false,"last_activation_json_redacted":""}}',
        encoding="utf-8",
    )

    config = RuntimeConfigStore(path).load()

    assert config.real.ota_url == "https://api.tenclass.net/xiaozhi/ota/"
    assert config.real.authorization_url == "https://xiaozhi.me/"
    assert config.real.activation_version == "v2"
