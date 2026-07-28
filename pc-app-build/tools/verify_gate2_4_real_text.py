"""Run one real Gate 2.4 WebSocket text turn with redacted diagnostics."""

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
from app.assistant.protocol import has_readable_transcript_text  # noqa: E402

DEFAULT_TEXT_PROMPT = "请用一句中文回复：Gate 2.4 真实文本链路正常。"
CONNECT_TIMEOUT_SECONDS = 15.0
TEXT_TIMEOUT_SECONDS = 45.0
MAX_PUBLIC_REPLY_CHARS = 500


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
    return pattern.sub(lambda match: f"{match.group(1)}=***", message)[:500]


def _credentials_unavailable(message: str) -> bool:
    lowered = message.lower()
    return any(
        marker in lowered
        for marker in (
            "token 未配置",
            "websocket url 未配置",
            "activation",
            "尚未建立有效 session",
        )
    )


async def _run() -> int:
    data_root = _optional_env("NOTE_ASSISTANT_DATA_ROOT")
    prompt = _optional_env("NOTE_ASSISTANT_GATE2_4_TEXT") or DEFAULT_TEXT_PROMPT
    paths = AppPaths.resolve(root_override=data_root)
    paths.ensure_directories()

    config_store = RuntimeConfigStore(paths.assistant_runtime_config)
    compatibility_source = LegacyPyXiaozhiIdentitySource.from_local_app_data()
    identity_manager = DeviceIdentityManager(
        DeviceIdentityStore(config_store),
        legacy_identity=compatibility_source.load,
    )
    identity = await identity_manager.ensure_identity()
    provider = PersistedConnectionConfigProvider(
        config_store=config_store,
        identity_manager=identity_manager,
    )
    clock = MonotonicClock()
    real_transport = RealWebSocketTransport(config_provider=provider, clock=clock)
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
        connected = await controller.wait_for_state(
            lambda snapshot: snapshot.is_connected or snapshot.error is not None,
            timeout_seconds=CONNECT_TIMEOUT_SECONDS,
        )
        if not connected.is_connected:
            message = connected.error.message if connected.error else "真实 WebSocket 未连接"
            print(
                json.dumps(
                    _public_result(connected, identity, paths, "failed", prompt),
                    ensure_ascii=False,
                    indent=2,
                    sort_keys=True,
                )
            )
            return 2 if _credentials_unavailable(message) else 1

        await controller.send_text(prompt)
        submitted = controller.state
        turn_token = submitted.conversation.active_text_turn_token
        if turn_token is None:
            print(
                json.dumps(
                    _public_result(submitted, identity, paths, "failed", prompt),
                    ensure_ascii=False,
                    indent=2,
                    sort_keys=True,
                )
            )
            return 1

        final_state = await controller.wait_for_state(
            lambda snapshot: (
                snapshot.error is not None
                or snapshot.diagnostics.gate_real_text_verified
                or snapshot.conversation.last_completed_text_turn_token >= turn_token
            ),
            timeout_seconds=TEXT_TIMEOUT_SECONDS,
        )
        reply = final_state.conversation.last_assistant_text or ""
        verified = (
            final_state.diagnostics.gate_real_handshake_verified
            and final_state.diagnostics.gate_real_text_verified
            and has_readable_transcript_text(reply)
        )
        print(
            json.dumps(
                _public_result(
                    final_state,
                    identity,
                    paths,
                    "text_verified" if verified else "failed",
                    prompt,
                ),
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
        )
        if verified:
            await controller.disconnect("gate2_4_real_text_acceptance_complete")
            return 0
        if final_state.error and _credentials_unavailable(final_state.error.message):
            return 2
        return 1
    finally:
        await controller.shutdown()


def _public_result(state, identity, paths: AppPaths, status: str, prompt: str) -> dict[str, object]:
    reply = state.conversation.last_assistant_text
    return {
        "status": status,
        "phase": state.phase.value,
        "websocket_url": state.connection.websocket_url_public,
        "session_id_masked": _mask(state.connection.session_id),
        "device_id_masked": identity.device_id_masked,
        "client_id_masked": identity.client_id_masked,
        "identity_source": identity.source,
        "connection_generation": state.connection.connection_generation,
        "turn_token": (
            state.conversation.active_text_turn_token
            or state.conversation.last_completed_text_turn_token
        ),
        "last_completed_turn_token": state.conversation.last_completed_text_turn_token,
        "prompt_chars": len(prompt),
        "assistant_text": reply[:MAX_PUBLIC_REPLY_CHARS] if reply else None,
        "assistant_source_type": state.conversation.last_assistant_source_type,
        "late_text_event_count": state.conversation.late_text_event_count,
        "real_handshake_verified": state.diagnostics.gate_real_handshake_verified,
        "real_text_verified": state.diagnostics.gate_real_text_verified,
        "last_protocol_event": state.protocol.last_protocol_event,
        "last_protocol_error": state.protocol.last_protocol_error,
        "last_binary_size_bytes": state.protocol.last_binary_size_bytes,
        "token_usage": {
            "observed": state.token_usage.observed,
            "model": state.token_usage.model,
            "input_tokens": state.token_usage.input_tokens,
            "output_tokens": state.token_usage.output_tokens,
            "total_tokens": state.token_usage.total_tokens,
            "known_total_tokens": state.token_usage.known_total_tokens,
            "provider_usage_complete": state.token_usage.provider_usage_complete,
            "llm_calls_started": state.token_usage.llm_calls_started,
            "tool_call_count": state.token_usage.tool_call_count,
            "budget_enabled": state.token_usage.budget_enabled,
            "budget_status": state.token_usage.budget_status,
            "budget_reason": state.token_usage.budget_reason,
            "max_total_tokens_per_turn": (
                state.token_usage.max_total_tokens_per_turn
            ),
            "max_output_tokens_per_request": (
                state.token_usage.max_output_tokens_per_request
            ),
            "output_cap_enforced": state.token_usage.output_cap_enforced,
        },
        "error_code": state.error.code if state.error else None,
        "error_message": _redact_message(state.error.message) if state.error else None,
        "config_path": str(paths.assistant_runtime_config),
    }


def main() -> int:
    try:
        return asyncio.run(_run())
    except TimeoutError:
        print(
            json.dumps(
                {
                    "status": "failed",
                    "error_type": "TimeoutError",
                    "message": "等待真实文本回复超时",
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
