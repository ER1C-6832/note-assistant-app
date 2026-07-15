"""Run the complete deterministic Gate 2.7 Fake acceptance matrix."""

from __future__ import annotations

import asyncio
import json
import sqlite3
import sys
import tempfile
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1] / "apps" / "notes-pyside"
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

from app.app_paths import AppPaths  # noqa: E402
from app.assistant import (  # noqa: E402
    AssistantActivationStatus,
    AssistantCapability,
    AssistantController,
    AssistantPhase,
    AssistantRuntimeMode,
    AssistantState,
    CapabilityStatus,
    ConversationStateMachine,
    DeviceIdentityManager,
    DeviceIdentityStore,
    FakeActivationClient,
    ReconnectPolicy,
    RuntimeConfigStore,
    redact_error_text,
)
from app.assistant.protocol import (  # noqa: E402
    ProtocolError,
    UnknownJson,
    XiaozhiMessageRouter,
)
from app.assistant.testing import (  # noqa: E402
    FakeClock,
    OpenSucceeded,
    ScriptedFakeTransport,
    TextReply,
)


def _prepare_notes_db(path: Path) -> bytes:
    with sqlite3.connect(path) as connection:
        connection.execute(
            "CREATE TABLE gate2_7_sentinel (id INTEGER PRIMARY KEY, value TEXT NOT NULL)"
        )
        connection.execute(
            "INSERT INTO gate2_7_sentinel (id, value) VALUES (?, ?)",
            (1, "notes-db-must-remain-unchanged"),
        )
        connection.commit()
    return path.read_bytes()


async def run_fake_acceptance(data_root: Path) -> dict[str, object]:
    paths = AppPaths.resolve(root_override=data_root)
    paths.ensure_directories()
    notes_db_before = _prepare_notes_db(paths.notes_db)

    initial = AssistantState.disabled(now_ns=0)
    initial.validate()
    complete_state_defaults = (
        initial.phase is AssistantPhase.DISABLED
        and initial.enabled is False
        and initial.connection.session_id is None
        and initial.audio.capture_generation == 0
        and initial.conversation.streaming_session_active is False
        and initial.recovery.next_reconnect_at_ns is None
        and initial.mcp.last_tool_status is None
        and len(initial.capabilities) >= 10
    )
    future_capabilities_frozen = all(
        initial.capability_status(capability) is CapabilityStatus.NOT_READY
        for capability in (
            AssistantCapability.PUSH_TO_TALK,
            AssistantCapability.TTS_PLAYBACK,
            AssistantCapability.MCP_NOTES,
            AssistantCapability.STREAMING_CONVERSATION,
            AssistantCapability.VAD,
            AssistantCapability.BARGE_IN,
            AssistantCapability.KWS,
        )
    )

    config_store = RuntimeConfigStore(paths.assistant_runtime_config)
    identity_manager = DeviceIdentityManager(DeviceIdentityStore(config_store))
    fake_activation = FakeActivationClient(
        config_store=config_store,
        identity_manager=identity_manager,
    )
    clock = FakeClock()
    transport = ScriptedFakeTransport(
        clock=clock,
        open_steps=(
            OpenSucceeded(session_id="gate2-7-session-1"),
            OpenSucceeded(session_id="gate2-7-session-2"),
        ),
        text_steps=(TextReply("Gate 2.7 Fake 文本回复"),),
    )
    controller = AssistantController(
        transport=transport,
        state_machine=ConversationStateMachine(
            ReconnectPolicy(
                jitter_fraction=0.0,
                backoff_seconds=(0.01, 0.02, 0.03),
            )
        ),
        clock=clock,
        identity_manager=identity_manager,
        fake_activation_client=fake_activation,
    )

    activation_verified = False
    handshake_verified = False
    text_verified = False
    protocol_resilience_verified = False
    mcp_blocked_verified = False
    recovery_verified = False
    disable_verified = False
    shutdown_verified = False
    fake_config_isolated = False
    first_generation = 0
    recovered_generation = 0

    try:
        await controller.use_fake_runtime()
        await controller.ensure_device_identity()
        await controller.run_fake_activation()
        activated = await controller.wait_for_state(
            lambda state: state.activation.status is AssistantActivationStatus.ACTIVATED
        )
        stored_config = config_store.load()
        activation_verified = (
            activated.runtime_mode is AssistantRuntimeMode.FAKE
            and activated.identity.identity_ready
            and stored_config.fake.activated
        )
        fake_config_isolated = (
            stored_config.real.websocket_url == ""
            and stored_config.real.websocket_token == ""
            and stored_config.real.activated is False
        )

        await controller.enable_assistant()
        await controller.connect()
        connected = await controller.wait_for_state(lambda state: state.is_connected)
        first_generation = connected.connection.connection_generation
        handshake_verified = (
            connected.connection.session_id == "gate2-7-session-1"
            and transport.open_calls == [first_generation]
        )

        await controller.send_text("Gate 2.7 Fake 输入")
        replied = await controller.wait_for_state(
            lambda state: state.conversation.last_completed_text_turn_token == 1
        )
        text_verified = (
            replied.phase is AssistantPhase.CONNECTED
            and replied.conversation.last_user_text == "Gate 2.7 Fake 输入"
            and replied.conversation.last_assistant_text == "Gate 2.7 Fake 文本回复"
            and replied.conversation.active_text_turn_token is None
        )

        router = XiaozhiMessageRouter()
        unknown = router.route_text('{"type":"gate2_7_future","token":"must-not-leak","value":1}')
        invalid = router.route_text("{gate2-7-invalid-json")
        protocol_resilience_verified = (
            isinstance(unknown, UnknownJson)
            and "must-not-leak" not in (unknown.raw_json_redacted or "")
            and isinstance(invalid, ProtocolError)
            and "gate2-7-invalid-json" not in invalid.raw_text_redacted
            and controller.state.is_connected
        )

        await controller.simulate_incoming_tool_call(
            "notes.delete",
            '{"note_id":"gate2-7-sync-id"}',
        )
        mcp_state = controller.state.mcp
        mcp_blocked_verified = (
            mcp_state.last_tool_name == "notes.delete"
            and mcp_state.last_tool_status == "blocked_not_ready"
            and controller.state.is_connected
        )

        await transport.emit_server_close(code=1006, reason="gate2_7_fake_abnormal_close")
        recovered = await controller.wait_for_state(
            lambda state: state.is_connected
            and state.connection.connection_generation > first_generation,
            timeout_seconds=1.0,
        )
        recovered_generation = recovered.connection.connection_generation
        recovery_verified = (
            recovered.connection.session_id == "gate2-7-session-2"
            and recovered_generation == first_generation + 1
            and recovered.recovery.reconnect_attempt == 0
            and recovered.recovery.next_reconnect_at_ns is None
            and controller.reconnect_timer_running is False
            and len(transport.open_calls) == 2
        )

        await controller.disable_assistant()
        disable_verified = (
            controller.state.phase is AssistantPhase.DISABLED
            and controller.state.enabled is False
            and controller.state.connection.session_id is None
            and controller.reconnect_timer_running is False
        )
    finally:
        await controller.shutdown()
        await asyncio.sleep(0)
        shutdown_verified = (
            controller.closed
            and controller.event_pump_running is False
            and controller.reconnect_timer_running is False
            and controller.pending_effect_count == 0
        )

    pending_runtime_tasks = sorted(
        task.get_name()
        for task in asyncio.all_tasks()
        if task is not asyncio.current_task()
        and not task.done()
        and task.get_name().startswith("assistant-")
    )
    notes_db_unchanged = paths.notes_db.read_bytes() == notes_db_before

    checks = {
        "complete_state_defaults": complete_state_defaults,
        "future_capabilities_frozen": future_capabilities_frozen,
        "fake_activation_verified": activation_verified,
        "fake_config_isolated": fake_config_isolated,
        "fake_hello_session_verified": handshake_verified,
        "fake_text_verified": text_verified,
        "invalid_unknown_json_verified": protocol_resilience_verified,
        "mcp_blocked_verified": mcp_blocked_verified,
        "abnormal_close_recovery_verified": recovery_verified,
        "disable_verified": disable_verified,
        "shutdown_verified": shutdown_verified,
        "notes_db_unchanged": notes_db_unchanged,
        "no_pending_runtime_tasks": pending_runtime_tasks == [],
    }
    verified = all(checks.values())
    return {
        "status": "fake_gate_complete" if verified else "failed",
        **checks,
        "first_generation": first_generation,
        "recovered_generation": recovered_generation,
        "pending_runtime_tasks": pending_runtime_tasks,
    }


def main() -> int:
    try:
        with tempfile.TemporaryDirectory(prefix="note-assistant-gate2-7-fake-") as temp_dir:
            result = asyncio.run(run_fake_acceptance(Path(temp_dir)))
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
        return 0 if result["status"] == "fake_gate_complete" else 1
    except Exception as exc:
        print(
            json.dumps(
                {
                    "status": "failed",
                    "error_type": type(exc).__name__,
                    "message": redact_error_text(str(exc) or type(exc).__name__),
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
