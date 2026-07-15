from __future__ import annotations

from pathlib import Path

import pytest

from app.assistant.activation import OtaResponseError, parse_ota_response

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def test_activated_ota_response_parses_and_redacts_token() -> None:
    raw = (FIXTURES / "ota_activated.json").read_text(encoding="utf-8")

    response = parse_ota_response(raw)

    assert response.websocket_url == "wss://assistant.example/ws"
    assert response.websocket_token == "real-secret-token"
    assert response.activation is None
    assert "real-secret-token" not in response.redacted_json
    assert '"token":"***"' in response.redacted_json


def test_activation_required_response_keeps_code_but_redacts_challenge() -> None:
    raw = (FIXTURES / "ota_activation_required.json").read_text(encoding="utf-8")

    response = parse_ota_response(raw)

    assert response.activation is not None
    assert response.activation.code == "482913"
    assert response.activation.challenge == "server-challenge-secret"
    assert "482913" in response.redacted_json
    assert "server-challenge-secret" not in response.redacted_json
    assert '"challenge":"***"' in response.redacted_json


def test_invalid_ota_response_fails_closed() -> None:
    raw = (FIXTURES / "ota_invalid_missing_fields.json").read_text(encoding="utf-8")

    with pytest.raises(OtaResponseError, match="既没有"):
        parse_ota_response(raw)
