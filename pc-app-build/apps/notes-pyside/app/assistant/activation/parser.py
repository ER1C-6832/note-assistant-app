"""Parse and redact Xiaozhi OTA responses without exposing credentials."""

from __future__ import annotations

import json
from collections.abc import Mapping

from .models import ActivationInfo, OtaResponse


class OtaResponseError(ValueError):
    """Raised when an OTA response cannot be safely interpreted."""


_SENSITIVE_KEY_FRAGMENTS = {
    "authorization",
    "challenge",
    "hmac",
    "hmac_key",
    "key",
    "secret",
    "token",
    "websocket_token",
}


def parse_ota_response(raw: str) -> OtaResponse:
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise OtaResponseError(f"OTA 响应不是合法 JSON：{exc.msg}") from exc
    if not isinstance(payload, dict):
        raise OtaResponseError("OTA 响应根节点必须是对象")

    websocket = payload.get("websocket")
    websocket_url: str | None = None
    websocket_token: str | None = None
    if websocket is not None:
        if not isinstance(websocket, dict):
            raise OtaResponseError("websocket 字段必须是对象")
        websocket_url = _optional_text(websocket.get("url"))
        websocket_token = _optional_text(websocket.get("token"))
        if websocket_url is None:
            raise OtaResponseError("websocket.url 不能为空")

    activation_payload = payload.get("activation")
    activation: ActivationInfo | None = None
    if activation_payload is not None:
        if not isinstance(activation_payload, dict):
            raise OtaResponseError("activation 字段必须是对象")
        code = _required_text(activation_payload.get("code"), "activation.code")
        challenge = _required_text(
            activation_payload.get("challenge"),
            "activation.challenge",
        )
        activation = ActivationInfo(
            code=code,
            challenge=challenge,
            message=_optional_text(activation_payload.get("message")) or "",
        )

    if websocket_url is None and activation is None:
        raise OtaResponseError("OTA 响应既没有 websocket 配置，也没有 activation 信息")

    redacted = redact_json(payload)
    return OtaResponse(
        websocket_url=websocket_url,
        websocket_token=websocket_token,
        activation=activation,
        redacted_json=json.dumps(
            redacted,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ),
    )


def redact_json(value: object) -> object:
    if isinstance(value, Mapping):
        result: dict[str, object] = {}
        for key, item in value.items():
            normalized = str(key).lower().replace("-", "_")
            result[str(key)] = (
                "***"
                if any(fragment in normalized for fragment in _SENSITIVE_KEY_FRAGMENTS)
                else redact_json(item)
            )
        return result
    if isinstance(value, list):
        return [redact_json(item) for item in value]
    return value


def _required_text(value: object, field_name: str) -> str:
    text = _optional_text(value)
    if text is None:
        raise OtaResponseError(f"{field_name} 不能为空")
    return text


def _optional_text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
