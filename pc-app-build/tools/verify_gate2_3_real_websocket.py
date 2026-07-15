"""Run one real Gate 2.3 WebSocket hello/session check with redacted output."""

from __future__ import annotations

import asyncio
import json
import os
import re
import sys
import time
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1] / "apps" / "notes-pyside"
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

from app.app_paths import AppPaths  # noqa: E402
from app.assistant import (  # noqa: E402
    AssistantController,
    DeviceIdentityManager,
    DeviceIdentityStore,
    PersistedConnectionConfigProvider,
    RealWebSocketTransport,
    RuntimeConfigStore,
    RuntimeTransportRouter,
)
from app.assistant.identity import LegacyPyXiaozhiIdentitySource  # noqa: E402
from app.assistant.network import ScriptedFakeTransport  # noqa: E402


class MonotonicClock:
    def now_ns(self) -> int:
        return time.perf_counter_ns()


def _optional_env(name: str) -> str | None:
    value = os.environ.get(name, "").strip()
    return value or None


def _mask(value: str | None) -> str | None:
    if not value:
        return None
    if len(value) <= 8:
        return "*" * len(value)
    return f"{value[:4]}***{value[-4:]}"


def _redact_message(message: str) -> str:
    pattern = re.compile(r"(?i)(token|authorization|hmac|challenge|secret|key)\s*[:=]\s*[^\s,;]+")
    return pattern.sub(lambda match: f"{match.group(1)}=***", message)[:400]


async def _run() -> int:
    data_root = _optional_env("NOTE_ASSISTANT_DATA_ROOT")
    paths = AppPaths.resolve(root_override=data_root)
    paths.ensure_directories()

    config_store = RuntimeConfigStore(paths.assistant_runtime_config)
    legacy_source = LegacyPyXiaozhiIdentitySource.from_local_app_data()
    identity_manager = DeviceIdentityManager(
        DeviceIdentityStore(config_store),
        legacy_identity=legacy_source.load,
    )
    identity = await identity_manager.ensure_identity()
    provider = PersistedConnectionConfigProvider(
        config_store=config_store,
        identity_manager=identity_manager,
    )
    clock = MonotonicClock()
    real_transport = RealWebSocketTransport(
        config_provider=provider,
        clock=clock,
    )
    transport = RuntimeTransportRouter(
        fake_transport=ScriptedFakeTransport(),
        real_transport=real_transport,
    )
    controller = AssistantController(
        transport=transport,
        clock=clock,
        identity_manager=identity_manager,
    )

    try:
        await controller.enable_assistant()
        await controller.ensure_device_identity()
        await controller.connect()
        state = await controller.wait_for_state(
            lambda snapshot: snapshot.is_connected or snapshot.error is not None,
            timeout_seconds=15.0,
        )

        public_result = {
            "status": "connected" if state.is_connected else "failed",
            "phase": state.phase.value,
            "websocket_url": state.connection.websocket_url_public,
            "session_id_masked": _mask(state.connection.session_id),
            "device_id_masked": identity.device_id_masked,
            "client_id_masked": identity.client_id_masked,
            "identity_source": identity.source,
            "connection_generation": state.connection.connection_generation,
            "opened_at_ns": state.connection.opened_at_ns,
            "hello_sent_at_ns": state.connection.hello_sent_at_ns,
            "hello_received_at_ns": state.connection.hello_received_at_ns,
            "real_handshake_verified": state.diagnostics.gate_real_handshake_verified,
            "last_protocol_event": state.protocol.last_protocol_event,
            "last_protocol_error": state.protocol.last_protocol_error,
            "error_code": state.error.code if state.error else None,
            "error_message": _redact_message(state.error.message) if state.error else None,
            "config_path": str(paths.assistant_runtime_config),
        }
        print(json.dumps(public_result, ensure_ascii=False, indent=2, sort_keys=True))

        if state.is_connected and state.diagnostics.gate_real_handshake_verified:
            await controller.disconnect("gate2_3_real_acceptance_complete")
            return 0
        if state.error and any(
            token in state.error.message.lower()
            for token in ("token 未配置", "websocket url 未配置", "activation")
        ):
            return 2
        return 1
    finally:
        await controller.shutdown()


def main() -> int:
    try:
        return asyncio.run(_run())
    except TimeoutError:
        print(
            json.dumps(
                {
                    "status": "failed",
                    "error_type": "TimeoutError",
                    "message": "等待真实 WebSocket hello/session 超时",
                },
                ensure_ascii=False,
                indent=2,
            ),
            file=sys.stderr,
        )
        return 1
    except Exception as exc:
        print(
            json.dumps(
                {
                    "status": "failed",
                    "error_type": type(exc).__name__,
                    "message": _redact_message(str(exc) or type(exc).__name__),
                },
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            ),
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
