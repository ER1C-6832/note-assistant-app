from __future__ import annotations

import hashlib
import hmac
from pathlib import Path

import pytest

from app.assistant.activation import (
    ActivationOutcomeStatus,
    FakeActivationClient,
    HttpJsonResponse,
    RealOtaActivationClient,
    ScriptedActivationHttpTransport,
)
from app.assistant.identity import DeviceIdentityManager, DeviceIdentityStore
from app.assistant.runtime_config import RuntimeConfigStore

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def _components(tmp_path):
    store = RuntimeConfigStore(tmp_path / "assistant_runtime.json")
    store.update_real_endpoints(
        ota_url="https://ota.example/v1",
        authorization_url="https://auth.example/devices",
        activation_version="v2",
    )
    manager = DeviceIdentityManager(DeviceIdentityStore(store))
    return store, manager


@pytest.mark.asyncio
async def test_fake_activation_never_overwrites_real_configuration(tmp_path) -> None:
    store, manager = _components(tmp_path)
    store.update(
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
            fake=current.fake,
        )
    )
    client = FakeActivationClient(config_store=store, identity_manager=manager)

    outcome = await client.run()
    persisted = store.load()

    assert outcome.status is ActivationOutcomeStatus.ACTIVATED
    assert persisted.fake.activated is True
    assert persisted.fake.websocket_token == "gate2.2-fake-token"
    assert persisted.real.websocket_url == "wss://real.example/ws"
    assert persisted.real.websocket_token == "real-token"
    assert "gate2.2-fake-token" not in (outcome.diagnostics_json_redacted or "")


@pytest.mark.asyncio
async def test_real_ota_activated_path_uses_pc_headers_and_persists_credentials(
    tmp_path,
) -> None:
    store, manager = _components(tmp_path)
    response_body = (FIXTURES / "ota_activated.json").read_text(encoding="utf-8")
    transport = ScriptedActivationHttpTransport([HttpJsonResponse(200, response_body)])
    client = RealOtaActivationClient(
        config_store=store,
        identity_manager=manager,
        http_transport=transport,
    )

    outcome = await client.run()
    persisted = store.load()
    identity = await manager.ensure_identity()

    assert outcome.status is ActivationOutcomeStatus.ACTIVATED
    assert persisted.real.activated is True
    assert persisted.real.websocket_url == "wss://assistant.example/ws"
    assert persisted.real.websocket_token == "real-secret-token"
    assert "real-secret-token" not in (outcome.diagnostics_json_redacted or "")

    url, headers, payload = transport.requests[0]
    assert url == "https://ota.example/v1"
    assert headers["Device-Id"] == identity.device_id
    assert headers["Client-Id"] == identity.client_id
    assert headers["Activation-Version"] == "0.1.0-gate2.2"
    assert headers["User-Agent"].startswith("windows/note-assistant-pc-")
    assert payload["board"]["type"] == "windows"
    assert payload["board"]["name"] == "note-assistant-pc"


@pytest.mark.asyncio
async def test_real_activation_required_then_hmac_check_and_ota_refresh(
    tmp_path,
) -> None:
    store, manager = _components(tmp_path)
    required_body = (FIXTURES / "ota_activation_required.json").read_text(encoding="utf-8")
    activated_body = (FIXTURES / "ota_activated.json").read_text(encoding="utf-8")
    transport = ScriptedActivationHttpTransport(
        [
            HttpJsonResponse(200, required_body),
            HttpJsonResponse(200, "{}"),
            HttpJsonResponse(200, activated_body),
        ]
    )
    client = RealOtaActivationClient(
        config_store=store,
        identity_manager=manager,
        http_transport=transport,
    )

    required = await client.run()
    assert required.status is ActivationOutcomeStatus.REQUIRED
    assert required.activation_code == "482913"
    assert required.authorization_url == "https://auth.example/devices"
    assert "server-challenge-secret" not in (required.diagnostics_json_redacted or "")

    activated = await client.run()
    persisted = store.load()
    identity = await manager.ensure_identity()

    assert activated.status is ActivationOutcomeStatus.ACTIVATED
    assert persisted.real.activated is True
    assert persisted.real.activation_challenge == ""
    assert len(transport.requests) == 3

    activation_url, activation_headers, activation_payload = transport.requests[1]
    assert activation_url == "https://ota.example/v1/activate"
    assert activation_headers["Activation-Version"] == "2"
    nested = activation_payload["Payload"]
    expected_hmac = hmac.new(
        identity.hmac_key.encode("utf-8"),
        b"server-challenge-secret",
        hashlib.sha256,
    ).hexdigest()
    assert nested["serial_number"] == identity.serial_number
    assert nested["challenge"] == "server-challenge-secret"
    assert nested["hmac"] == expected_hmac


@pytest.mark.asyncio
async def test_pending_activation_202_remains_required_without_long_polling(
    tmp_path,
) -> None:
    store, manager = _components(tmp_path)
    required_body = (FIXTURES / "ota_activation_required.json").read_text(encoding="utf-8")
    transport = ScriptedActivationHttpTransport(
        [HttpJsonResponse(200, required_body), HttpJsonResponse(202, "pending")]
    )
    client = RealOtaActivationClient(
        config_store=store,
        identity_manager=manager,
        http_transport=transport,
    )

    await client.run()
    pending = await client.run()

    assert pending.status is ActivationOutcomeStatus.REQUIRED
    assert pending.activation_code == "482913"
    assert len(transport.requests) == 2
