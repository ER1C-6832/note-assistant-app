from __future__ import annotations

from dataclasses import replace

import pytest

from app.assistant.state import (
    AssistantAudioStatus,
    AssistantCapability,
    AssistantConnectionStatus,
    AssistantPhase,
    AssistantRuntimeMode,
    AssistantState,
    CapabilityStatus,
    ConnectionState,
    StateInvariantError,
)


def test_complete_state_defaults_and_android_capability_registry() -> None:
    state = AssistantState.disabled(runtime_mode=AssistantRuntimeMode.REAL, now_ns=123)

    state.validate()
    assert state.schema_version == 1
    assert state.phase is AssistantPhase.DISABLED
    assert state.connection.status is AssistantConnectionStatus.DISCONNECTED
    assert state.audio.status is AssistantAudioStatus.IDLE
    assert state.audio.wakeword_generation == 0
    assert state.audio.microphone_lease_generation == 0
    assert state.conversation.streaming_generation == 0
    assert state.conversation.streaming_session_active is False
    assert state.conversation.vad_status_text == "VAD 未启用"
    assert state.protocol.last_client_json_redacted is None
    assert state.mcp.real_tool_call_verified is False
    assert state.diagnostics.gate_real_handshake_verified is False
    assert state.last_event_at_ns == 123

    registry = {item.name: item for item in state.capabilities}
    assert set(registry) == set(AssistantCapability)
    assert registry[AssistantCapability.RUNTIME_CORE].status is CapabilityStatus.ACTIVE
    assert registry[AssistantCapability.FAKE_TRANSPORT].status is CapabilityStatus.ACTIVE
    assert registry[AssistantCapability.REAL_TRANSPORT].status is CapabilityStatus.NOT_READY
    assert registry[AssistantCapability.PUSH_TO_TALK].target_gate == "3"
    assert registry[AssistantCapability.TTS_PLAYBACK].target_gate == "4"
    assert registry[AssistantCapability.MCP_NOTES].target_gate == "5"
    assert registry[AssistantCapability.STREAMING_CONVERSATION].target_gate == "6"
    assert registry[AssistantCapability.KWS].target_gate == "6.5"


def test_connected_state_requires_non_empty_session_id() -> None:
    invalid = replace(
        AssistantState.disabled(),
        enabled=True,
        phase=AssistantPhase.CONNECTED,
        connection=ConnectionState(status=AssistantConnectionStatus.CONNECTED),
    )

    with pytest.raises(StateInvariantError, match="session_id"):
        invalid.validate()


def test_disabled_state_rejects_transient_runtime_resources() -> None:
    invalid = replace(
        AssistantState.disabled(),
        connection=ConnectionState(status=AssistantConnectionStatus.CONNECTING),
    )

    with pytest.raises(StateInvariantError, match="cannot retain a connection"):
        invalid.validate()
