"""Real Xiaozhi OTA and activation adapter for the PC Runtime."""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import socket
import urllib.error
import urllib.request
from dataclasses import replace
from urllib.parse import urljoin

from ..identity import DeviceIdentity, DeviceIdentityManager
from ..runtime_config import AssistantRuntimeConfig, RuntimeConfigStore
from .models import (
    ActivationHttpTransport,
    ActivationOutcome,
    ActivationOutcomeStatus,
    HttpJsonResponse,
    OtaResponse,
)
from .parser import OtaResponseError, parse_ota_response

APP_NAME = "note-assistant-pc"
APP_VERSION = "0.1.0-gate2.2"
BOARD_TYPE = "windows"
DEFAULT_TIMEOUT_SECONDS = 10.0


class ActivationError(RuntimeError):
    """Raised for transport, HTTP, configuration, or protocol activation failures."""


class UrllibActivationHttpTransport:
    """Small stdlib HTTP adapter executed outside the qasync/Qt event loop."""

    def __init__(self, timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS) -> None:
        self._timeout_seconds = timeout_seconds

    async def post_json(
        self,
        *,
        url: str,
        headers: dict[str, str],
        payload: dict[str, object],
    ) -> HttpJsonResponse:
        return await asyncio.to_thread(
            self._post_json_sync,
            url,
            headers,
            payload,
        )

    def _post_json_sync(
        self,
        url: str,
        headers: dict[str, str],
        payload: dict[str, object],
    ) -> HttpJsonResponse:
        body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        request = urllib.request.Request(url=url, data=body, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(request, timeout=self._timeout_seconds) as response:
                response_body = response.read().decode("utf-8", errors="replace")
                return HttpJsonResponse(status_code=response.status, body=response_body)
        except urllib.error.HTTPError as exc:
            response_body = exc.read().decode("utf-8", errors="replace")
            return HttpJsonResponse(status_code=exc.code, body=response_body)
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise ActivationError(f"OTA/Activation 网络请求失败：{exc}") from exc


class RealOtaActivationClient:
    """Run one cancellable real activation step using persisted identity and config."""

    def __init__(
        self,
        *,
        config_store: RuntimeConfigStore,
        identity_manager: DeviceIdentityManager,
        http_transport: ActivationHttpTransport | None = None,
    ) -> None:
        self._config_store = config_store
        self._identity_manager = identity_manager
        self._http = http_transport or UrllibActivationHttpTransport()

    async def run(self) -> ActivationOutcome:
        identity = await self._identity_manager.ensure_identity()
        config = await asyncio.to_thread(self._config_store.load)
        self._validate_endpoint_config(config)

        if config.real.activation_challenge:
            pending = await self._check_pending_activation(identity, config)
            if pending is not None:
                return pending
            config = await asyncio.to_thread(self._config_store.load)

        return await self._request_ota(identity, config)

    async def _check_pending_activation(
        self,
        identity: DeviceIdentity,
        config: AssistantRuntimeConfig,
    ) -> ActivationOutcome | None:
        activate_url = urljoin(f"{config.real.ota_url.rstrip('/')}/", "activate")
        signature = hmac.new(
            identity.hmac_key.encode("utf-8"),
            config.real.activation_challenge.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        payload: dict[str, object] = {
            "Payload": {
                "algorithm": "hmac-sha256",
                "serial_number": identity.serial_number,
                "challenge": config.real.activation_challenge,
                "hmac": signature,
            }
        }
        response = await self._http.post_json(
            url=activate_url,
            headers=self._activation_headers(identity),
            payload=payload,
        )
        if response.status_code == 202:
            return self._required_outcome(config, "设备仍等待用户完成验证码激活")
        if response.status_code != 200:
            raise ActivationError(
                f"Activation 服务返回 HTTP {response.status_code}: "
                f"{_safe_body_excerpt(response.body)}"
            )

        await asyncio.to_thread(self._mark_pending_activation_complete)
        return None

    async def _request_ota(
        self,
        identity: DeviceIdentity,
        config: AssistantRuntimeConfig,
    ) -> ActivationOutcome:
        response = await self._http.post_json(
            url=config.real.ota_url,
            headers=self._ota_headers(identity, config.real.activation_version),
            payload=self._ota_payload(identity),
        )
        if not 200 <= response.status_code < 300:
            raise ActivationError(
                f"OTA 服务返回 HTTP {response.status_code}: " f"{_safe_body_excerpt(response.body)}"
            )
        try:
            parsed = parse_ota_response(response.body)
        except OtaResponseError as exc:
            raise ActivationError(str(exc)) from exc

        await asyncio.to_thread(self._save_ota_response, parsed)
        refreshed = await asyncio.to_thread(self._config_store.load)
        if parsed.activation is not None:
            return self._required_outcome(
                refreshed,
                parsed.activation.message or "设备需要验证码激活",
            )

        await asyncio.to_thread(self._mark_activated)
        return ActivationOutcome(
            status=ActivationOutcomeStatus.ACTIVATED,
            message="真实 OTA 成功，设备已激活",
            websocket_url_public=parsed.websocket_url,
            diagnostics_json_redacted=parsed.redacted_json,
        )

    def _save_ota_response(self, parsed: OtaResponse) -> None:
        def mutate(current: AssistantRuntimeConfig) -> AssistantRuntimeConfig:
            activation = parsed.activation
            return replace(
                current,
                real=replace(
                    current.real,
                    websocket_url=parsed.websocket_url or current.real.websocket_url,
                    websocket_token=(
                        parsed.websocket_token
                        if parsed.websocket_token is not None
                        else current.real.websocket_token
                    ),
                    activated=activation is None,
                    activation_code=activation.code if activation else "",
                    activation_challenge=activation.challenge if activation else "",
                    activation_message=activation.message if activation else "",
                    last_ota_json_redacted=parsed.redacted_json,
                ),
            )

        self._config_store.update(mutate)

    def _mark_pending_activation_complete(self) -> None:
        self._config_store.update(
            lambda current: replace(
                current,
                real=replace(
                    current.real,
                    activated=True,
                    activation_code="",
                    activation_challenge="",
                    activation_message="",
                ),
            )
        )

    def _mark_activated(self) -> None:
        self._mark_pending_activation_complete()

    @staticmethod
    def _required_outcome(
        config: AssistantRuntimeConfig,
        message: str,
    ) -> ActivationOutcome:
        code = config.real.activation_code or None
        authorization_url = config.real.authorization_url or None
        display_message = message
        if code and authorization_url:
            display_message = (
                f"{message}。请打开 {authorization_url} 并输入验证码 {code}，"
                "完成后再次执行真实激活检查。"
            )
        return ActivationOutcome(
            status=ActivationOutcomeStatus.REQUIRED,
            message=display_message,
            websocket_url_public=config.real.websocket_url or None,
            activation_code=code,
            authorization_url=authorization_url,
            diagnostics_json_redacted=config.real.last_ota_json_redacted or None,
        )

    @staticmethod
    def _validate_endpoint_config(config: AssistantRuntimeConfig) -> None:
        if not config.real.ota_url.strip():
            raise ActivationError("真实 OTA URL 未配置")
        if not config.real.authorization_url.strip():
            raise ActivationError("真实设备授权 URL 未配置")

    @staticmethod
    def _ota_headers(identity: DeviceIdentity, activation_version: str) -> dict[str, str]:
        headers = {
            "Device-Id": identity.device_id,
            "Client-Id": identity.client_id,
            "Content-Type": "application/json",
            "User-Agent": f"{BOARD_TYPE}/{APP_NAME}-{APP_VERSION}",
            "Accept-Language": "zh-CN",
        }
        if activation_version.lower() == "v2":
            headers["Activation-Version"] = APP_VERSION
        return headers

    @staticmethod
    def _activation_headers(identity: DeviceIdentity) -> dict[str, str]:
        return {
            "Activation-Version": "2",
            "Device-Id": identity.device_id,
            "Client-Id": identity.client_id,
            "Content-Type": "application/json",
        }

    @staticmethod
    def _ota_payload(identity: DeviceIdentity) -> dict[str, object]:
        return {
            "application": {
                "version": APP_VERSION,
                "elf_sha256": identity.hmac_key,
            },
            "board": {
                "type": BOARD_TYPE,
                "name": APP_NAME,
                "ip": _local_ip_address(),
                "mac": identity.device_id,
            },
        }


class ScriptedActivationHttpTransport:
    """Deterministic HTTP test double that records full request shapes."""

    def __init__(self, responses: list[HttpJsonResponse]) -> None:
        self._responses = list(responses)
        self.requests: list[tuple[str, dict[str, str], dict[str, object]]] = []

    async def post_json(
        self,
        *,
        url: str,
        headers: dict[str, str],
        payload: dict[str, object],
    ) -> HttpJsonResponse:
        self.requests.append((url, dict(headers), payload))
        if not self._responses:
            raise ActivationError("scripted activation response queue is empty")
        return self._responses.pop(0)


def _local_ip_address() -> str:
    try:
        return socket.gethostbyname(socket.gethostname())
    except OSError:
        return "127.0.0.1"


def _safe_body_excerpt(body: str) -> str:
    compact = " ".join(body.split())
    lowered = compact.lower()
    if any(key in lowered for key in ("token", "challenge", "hmac", "secret")):
        return "<redacted response body>"
    return compact[:200]
