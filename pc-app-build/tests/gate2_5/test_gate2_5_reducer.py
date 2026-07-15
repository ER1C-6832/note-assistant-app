from __future__ import annotations

from app.assistant.effects import (
    CancelReconnect,
    CancelRuntimeEffects,
    CloseTransport,
    OpenTransport,
    ScheduleReconnect,
)
from app.assistant.events import (
    ConnectRequested,
    EnableRequested,
    ReconnectTimerFired,
    ServerHelloReceived,
    TransportClosed,
    TransportFailed,
    TransportOpened,
    UseFakeRuntimeRequested,
)
from app.assistant.network import ReconnectPolicy
from app.assistant.state import AssistantPhase, AssistantRuntimeMode, AssistantState
from app.assistant.state_machine import ConversationStateMachine


def _connected(machine: ConversationStateMachine) -> AssistantState:
    state = AssistantState.disabled(now_ns=1)
    state = machine.reduce(state, EnableRequested(at_ns=2)).state
    state = machine.reduce(state, UseFakeRuntimeRequested(at_ns=3)).state
    state = machine.reduce(state, ConnectRequested(at_ns=4)).state
    generation = state.connection.connection_generation
    state = machine.reduce(
        state,
        TransportOpened(at_ns=5, generation=generation),
    ).state
    return machine.reduce(
        state,
        ServerHelloReceived(
            at_ns=6,
            generation=generation,
            session_id="session-1",
            transport="websocket",
        ),
    ).state


def test_abnormal_close_schedules_one_reconnect_and_timer_opens_new_generation() -> None:
    machine = ConversationStateMachine(ReconnectPolicy(jitter_fraction=0.0))
    connected = _connected(machine)
    generation = connected.connection.connection_generation

    closed = machine.reduce(
        connected,
        TransportClosed(
            at_ns=1_000_000_000,
            generation=generation,
            code=1006,
            reason="network_lost",
        ),
    )

    assert closed.state.phase is AssistantPhase.RECONNECTING
    assert closed.state.recovery.reconnect_attempt == 1
    assert closed.state.recovery.next_reconnect_at_ns == 1_500_000_000
    assert closed.effects == (
        CancelRuntimeEffects(reason="transport_closed_abnormally"),
        CloseTransport(generation=generation, reason="transport_closed_abnormally"),
        ScheduleReconnect(attempt=1, delay_seconds=0.5, generation=generation),
    )

    fired = machine.reduce(
        closed.state,
        ReconnectTimerFired(
            at_ns=1_500_000_000,
            generation=generation,
            attempt=1,
        ),
    )
    assert fired.state.phase is AssistantPhase.RECONNECTING
    assert fired.state.connection.connection_generation == generation + 1
    assert fired.effects == (
        CancelReconnect(),
        CloseTransport(generation=generation, reason="auto_reconnect"),
        OpenTransport(
            generation=generation + 1,
            runtime_mode=AssistantRuntimeMode.FAKE,
        ),
    )


def test_stale_or_wrong_attempt_timer_has_no_effect() -> None:
    machine = ConversationStateMachine(ReconnectPolicy(jitter_fraction=0.0))
    connected = _connected(machine)
    generation = connected.connection.connection_generation
    scheduled = machine.reduce(
        connected,
        TransportFailed(
            at_ns=100,
            generation=generation,
            message="temporary failure",
        ),
    ).state

    stale = machine.reduce(
        scheduled,
        ReconnectTimerFired(at_ns=200, generation=generation - 1, attempt=1),
    )
    wrong_attempt = machine.reduce(
        scheduled,
        ReconnectTimerFired(at_ns=200, generation=generation, attempt=2),
    )

    assert stale.state is scheduled
    assert stale.effects == ()
    assert wrong_attempt.state is scheduled
    assert wrong_attempt.effects == ()


def test_successful_hello_resets_attempt_and_cancels_timer() -> None:
    machine = ConversationStateMachine(ReconnectPolicy(jitter_fraction=0.0))
    connected = _connected(machine)
    generation = connected.connection.connection_generation
    scheduled = machine.reduce(
        connected,
        TransportFailed(at_ns=100, generation=generation, message="temporary"),
    ).state
    opening = machine.reduce(
        scheduled,
        ReconnectTimerFired(at_ns=500_000_100, generation=generation, attempt=1),
    ).state
    new_generation = opening.connection.connection_generation
    restored = machine.reduce(
        opening,
        ServerHelloReceived(
            at_ns=500_000_200,
            generation=new_generation,
            session_id="session-2",
            transport="websocket",
        ),
    )

    assert restored.state.is_connected is True
    assert restored.state.recovery.reconnect_attempt == 0
    assert restored.state.recovery.next_reconnect_at_ns is None
    assert restored.effects == (CancelReconnect(),)


def test_fourth_failure_is_exhausted_without_another_timer() -> None:
    machine = ConversationStateMachine(ReconnectPolicy(jitter_fraction=0.0))
    state = _connected(machine)

    for attempt in range(1, 4):
        generation = state.connection.connection_generation
        scheduled = machine.reduce(
            state,
            TransportFailed(
                at_ns=attempt * 10,
                generation=generation,
                message=f"failure-{attempt}",
            ),
        )
        assert scheduled.state.recovery.reconnect_attempt == attempt
        fired = machine.reduce(
            scheduled.state,
            ReconnectTimerFired(
                at_ns=attempt * 10 + 1,
                generation=generation,
                attempt=attempt,
            ),
        )
        state = fired.state

    exhausted = machine.reduce(
        state,
        TransportFailed(
            at_ns=100,
            generation=state.connection.connection_generation,
            message="failure-4",
        ),
    )
    assert exhausted.state.phase is AssistantPhase.ERROR
    assert exhausted.state.error is not None
    assert exhausted.state.error.code == "reconnect_exhausted"
    assert exhausted.state.recovery.next_reconnect_at_ns is None
    assert exhausted.state.recovery.runtime_error_count == 4
    assert exhausted.effects == (CancelReconnect(),)


def test_duplicate_failure_for_same_generation_keeps_single_timer_and_attempt() -> None:
    machine = ConversationStateMachine(ReconnectPolicy(jitter_fraction=0.0))
    connected = _connected(machine)
    generation = connected.connection.connection_generation

    first = machine.reduce(
        connected,
        TransportFailed(at_ns=100, generation=generation, message="temporary-1"),
    )
    duplicate = machine.reduce(
        first.state,
        TransportFailed(at_ns=101, generation=generation, message="temporary-duplicate"),
    )

    assert duplicate.state is first.state
    assert duplicate.effects == ()
    assert duplicate.state.recovery.reconnect_attempt == 1
    assert duplicate.state.recovery.runtime_error_count == 1


def test_manual_connect_during_scheduled_recovery_cancels_old_owner_before_open() -> None:
    machine = ConversationStateMachine(ReconnectPolicy(jitter_fraction=0.0))
    connected = _connected(machine)
    generation = connected.connection.connection_generation
    scheduled = machine.reduce(
        connected,
        TransportClosed(
            at_ns=100,
            generation=generation,
            code=1006,
            reason="network_lost",
        ),
    ).state

    transition = machine.reduce(scheduled, ConnectRequested(at_ns=101))

    assert transition.state.connection.connection_generation == generation + 1
    assert transition.state.recovery.next_reconnect_at_ns is None
    assert transition.effects == (
        CancelReconnect(),
        CancelRuntimeEffects(reason="manual_connect"),
        CloseTransport(generation=generation, reason="manual_connect"),
        OpenTransport(
            generation=generation + 1,
            runtime_mode=AssistantRuntimeMode.FAKE,
        ),
    )


def test_normal_close_and_non_retryable_failure_never_schedule_reconnect() -> None:
    machine = ConversationStateMachine(ReconnectPolicy(jitter_fraction=0.0))
    connected = _connected(machine)
    generation = connected.connection.connection_generation

    normal = machine.reduce(
        connected,
        TransportClosed(
            at_ns=100,
            generation=generation,
            code=1000,
            reason="normal",
        ),
    )
    assert normal.state.phase is AssistantPhase.IDLE
    assert normal.state.recovery.next_reconnect_at_ns is None
    assert normal.state.recovery.last_reconnect_decision == "normal_close_no_reconnect"
    assert normal.effects == (CancelReconnect(),)

    connected_again = _connected(machine)
    failure = machine.reduce(
        connected_again,
        TransportFailed(
            at_ns=200,
            generation=connected_again.connection.connection_generation,
            message="WebSocket token 未配置",
            retryable=False,
        ),
    )
    assert failure.state.phase is AssistantPhase.ERROR
    assert failure.state.recovery.next_reconnect_at_ns is None
    assert failure.state.recovery.last_reconnect_decision == "non_retryable_failure"
    assert failure.effects == ()
