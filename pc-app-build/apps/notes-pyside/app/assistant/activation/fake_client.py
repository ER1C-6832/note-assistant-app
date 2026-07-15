"""Fake activation adapter isolated from real endpoint credentials."""

from __future__ import annotations

import asyncio
import json
from dataclasses import replace

from ..identity import DeviceIdentityManager
from ..runtime_config import AssistantRuntimeConfig, RuntimeConfigStore
from .models import ActivationOutcome, ActivationOutcomeStatus


class FakeActivationClient:
    def __init__(
        self,
        *,
        config_store: RuntimeConfigStore,
        identity_manager: DeviceIdentityManager,
    ) -> None:
        self._config_store = config_store
        self._identity_manager = identity_manager

    async def run(self) -> ActivationOutcome:
        identity = await self._identity_manager.ensure_identity()
        websocket_url = f"wss://fake.local/xiaozhi/{identity.client_id[:8]}"
        token = "gate2.2-fake-token"
        redacted = json.dumps(
            {
                "fake": True,
                "websocket": {"url": websocket_url, "token": "***"},
            },
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )

        def mutate(current: AssistantRuntimeConfig) -> AssistantRuntimeConfig:
            return replace(
                current,
                fake=replace(
                    current.fake,
                    websocket_url=websocket_url,
                    websocket_token=token,
                    activated=True,
                    last_activation_json_redacted=redacted,
                ),
            )

        await asyncio.to_thread(self._config_store.update, mutate)
        return ActivationOutcome(
            status=ActivationOutcomeStatus.ACTIVATED,
            message="Fake Activation 成功；真实 Runtime 配置未被修改",
            websocket_url_public=websocket_url,
            diagnostics_json_redacted=redacted,
        )
