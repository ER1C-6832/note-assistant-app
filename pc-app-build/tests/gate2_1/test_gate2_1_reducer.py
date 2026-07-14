from __future__ import annotations

from app.assistant.effects import CloseTransport, OpenTransport, SendText
from app.assistant.events import (
    AssistantTextReceived,
    ClientHelloSent,
    ConnectRequested,
    DisableRequested,
    EnableRequested,
    EnsureIdentityRequested,
    IncomingToolCallSimulationRequested,
    ServerHelloReceived,
    TextSubmitted,
    TransportOpened,
    UseFakeRuntimeRequested,
)
from app.assistant.state import (
    AssistantConnectionStatus,
    AssistantErrorCategory,
    AssistantPhase,
    AssistantRuntimeMode,
    AssistantState,
)
from app.assistant.state_machine import ConversationStateMachine


def _fake_enabled_state(machine: ConversationStateMachine) -> AssistantState:
    state = AssistantState.disabled(now_ns=1)
    state = machine.reduce(state, EnableRequested(at_ns=2)).state
    return machine.reduce(state, UseFakeRuntimeRequested(at_ns=3)).state


def test_connect_requires_valid_hello_before_connected() -> None:
    machine = ConversationStateMachine()
    state = _fake_enabled_state(machine)

    opening = machine.reduce(state, ConnectRequested(at_ns=4))
    assert opening.state.phase is AssistantPhase.CONNECTING
    assert opening.state.connection.status is AssistantConnectionStatus.CONNECTING
    assert opening.state.connection.session_id is None
    assert opening.effects == (OpenTransport(generation=2, runtime_mode=AssistantRuntimeMode.FAKE),)

    opened = machine.reduce(
        opening.state,
        TransportOpened(at_ns=5, generation=2),
    )
    assert opened.state.phase is AssistantPhase.CONNECTING
    assert opened.state.connection.opened_at_ns == 5

    hello_sent = machine.reduce(
        opened.state,
        ClientHelloSent(at_ns=6, generation=2),
    )
    assert hello_sent.state.connection.hello_sent_at_ns == 6

    connected = machine.reduce(
        hello_sent.state,
        ServerHelloReceived(at_ns=7, generation=2, session_id="session-2"),
    )
    assert connected.state.phase is AssistantPhase.CONNECTED
    assert connected.state.is_connected is True
    assert connected.state.connection.session_id == "session-2"


def test_empty_hello_session_fails_and_closes_transport() -> None:
    machine = ConversationStateMachine()
    opening = machine.reduce(_fake_enabled_state(machine), ConnectRequested(at_ns=10))

    failed = machine.reduce(
        opening.state,
        ServerHelloReceived(at_ns=11, generation=2, session_id="  "),
    )

    assert failed.state.phase is AssistantPhase.ERROR
    assert failed.state.connection.status is AssistantConnectionStatus.DISCONNECTED
    assert failed.state.error is not None
    assert failed.state.error.code == "hello_missing_session_id"
    assert failed.effects == (CloseTransport(generation=2, reason="hello_missing_session_id"),)


def test_text_round_trip_and_stale_generation_are_deterministic() -> None:
    machine = ConversationStateMachine()
    opening = machine.reduce(_fake_enabled_state(machine), ConnectRequested(at_ns=20))
    connected = machine.reduce(
        opening.state,
        ServerHelloReceived(at_ns=21, generation=2, session_id="session-2"),
    ).state

    submitted = machine.reduce(connected, TextSubmitted(at_ns=22, text="  你好  "))
    assert submitted.state.phase is AssistantPhase.THINKING
    assert submitted.state.conversation.last_user_text == "你好"
    assert submitted.effects == (SendText(generation=2, text="你好"),)

    stale = machine.reduce(
        submitted.state,
        AssistantTextReceived(at_ns=23, generation=1, text="旧回复"),
    )
    assert stale.state is submitted.state
    assert stale.effects == ()

    completed = machine.reduce(
        submitted.state,
        AssistantTextReceived(at_ns=24, generation=2, text="你好，我是小智"),
    )
    assert completed.state.phase is AssistantPhase.CONNECTED
    assert completed.state.conversation.last_assistant_text == "你好，我是小智"


def test_disable_invalidates_old_connection_generation() -> None:
    machine = ConversationStateMachine()
    opening = machine.reduce(_fake_enabled_state(machine), ConnectRequested(at_ns=30))
    old_generation = opening.state.connection.connection_generation

    disabled = machine.reduce(opening.state, DisableRequested(at_ns=31))
    assert disabled.state.phase is AssistantPhase.DISABLED
    assert disabled.state.connection.connection_generation == old_generation + 1

    late_hello = machine.reduce(
        disabled.state,
        ServerHelloReceived(
            at_ns=32,
            generation=old_generation,
            session_id="late-session",
        ),
    )
    assert late_hello.state is disabled.state
    assert late_hello.effects == ()


def test_future_capability_is_present_but_fails_explicitly() -> None:
    machine = ConversationStateMachine()
    state = machine.reduce(AssistantState.disabled(), EnableRequested(at_ns=40)).state

    result = machine.reduce(state, EnsureIdentityRequested(at_ns=41))

    assert result.state.phase is AssistantPhase.ERROR
    assert result.state.error is not None
    assert result.state.error.code == "capability_not_ready"
    assert result.state.error.category is AssistantErrorCategory.CAPABILITY
    assert "Gate 2.2" in result.state.error.message


def test_mcp_simulation_is_fail_closed_without_notes_effect() -> None:
    machine = ConversationStateMachine()
    state = machine.reduce(AssistantState.disabled(), EnableRequested(at_ns=50)).state

    result = machine.reduce(
        state,
        IncomingToolCallSimulationRequested(
            at_ns=51,
            tool_name="notes.delete",
            arguments_json='{"note_id":"sync-id"}',
        ),
    )

    assert result.effects == ()
    assert result.state.mcp.last_tool_name == "notes.delete"
    assert result.state.mcp.last_tool_status == "blocked_not_ready"
    assert "fail-closed" in result.state.status_text


def test_not_ready_command_while_disabled_keeps_disabled_invariants() -> None:
    machine = ConversationStateMachine()
    initial = AssistantState.disabled(now_ns=60)

    result = machine.reduce(initial, EnsureIdentityRequested(at_ns=61))

    result.state.validate()
    assert result.state.phase is AssistantPhase.DISABLED
    assert result.state.enabled is False
    assert result.state.error is not None
    assert result.state.error.code == "capability_not_ready"
