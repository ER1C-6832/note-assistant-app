from __future__ import annotations

import json

from app.assistant.events import (
    ConnectRequested,
    EnableRequested,
    ServerHelloReceived,
    TokenUsageReceived,
    UseRealRuntimeRequested,
)
from app.assistant.protocol import ProtocolError, TokenUsage, XiaozhiMessageRouter
from app.assistant.state import AssistantState
from app.assistant.state_machine import ConversationStateMachine


def _connected_real(machine: ConversationStateMachine) -> AssistantState:
    state = machine.reduce(
        AssistantState.disabled(now_ns=1), EnableRequested(at_ns=2)
    ).state
    state = machine.reduce(state, UseRealRuntimeRequested(at_ns=3)).state
    opening = machine.reduce(state, ConnectRequested(at_ns=4)).state
    return machine.reduce(
        opening,
        ServerHelloReceived(
            at_ns=5,
            generation=opening.connection.connection_generation,
            session_id="session-real",
        ),
    ).state


def _wire_payload() -> str:
    return json.dumps(
        {
            "type": "token_usage",
            "session_id": "session-real",
            "usage": {
                "turn_id": "turn-public",
                "model": "glm-test",
                "api_call_count": 2,
                "llm_calls_started": 2,
                "tool_call_count": 1,
                "tool_followup_count": 1,
                "input_tokens": 1000,
                "output_tokens": 30,
                "total_tokens": 1030,
                "known_total_tokens": 1030,
                "provider_usage_complete": True,
                "duration_ms": 900,
                "status": "completed",
                "budget_enabled": True,
                "budget_status": "within_budget",
                "budget_reason": None,
                "max_total_tokens_per_turn": 12000,
                "max_llm_calls_per_turn": 3,
                "max_tool_calls_per_turn": 8,
                "max_output_tokens_per_request": 200,
                "warn_at_percent": 80,
                "output_cap_enforced": True,
            },
        },
        ensure_ascii=False,
    )


def test_token_usage_router_is_typed_and_rejects_invalid_counts() -> None:
    router = XiaozhiMessageRouter()
    event = router.route_text(_wire_payload())

    assert isinstance(event, TokenUsage)
    assert event.model == "glm-test"
    assert event.total_tokens == 1030
    assert event.max_total_tokens_per_turn == 12000

    invalid = router.route_text(
        '{"type":"token_usage","usage":{"known_total_tokens":-1}}'
    )
    assert isinstance(invalid, ProtocolError)
    assert invalid.error == "token_usage_invalid_known_total_tokens"


def test_token_usage_reducer_keeps_explicit_budget_snapshot() -> None:
    machine = ConversationStateMachine()
    connected = _connected_real(machine)
    generation = connected.connection.connection_generation
    state = machine.reduce(
        connected,
        TokenUsageReceived(
            at_ns=10,
            generation=generation,
            session_id="session-real",
            turn_id="turn-public",
            model="glm-test",
            api_call_count=2,
            llm_calls_started=2,
            tool_call_count=1,
            tool_followup_count=1,
            input_tokens=1000,
            output_tokens=30,
            total_tokens=1030,
            known_total_tokens=1030,
            provider_usage_complete=True,
            duration_ms=900,
            status="completed",
            budget_enabled=True,
            budget_status="within_budget",
            max_total_tokens_per_turn=12000,
            max_llm_calls_per_turn=3,
            max_tool_calls_per_turn=8,
            max_output_tokens_per_request=200,
            warn_at_percent=80,
            output_cap_enforced=True,
            raw_json_redacted=_wire_payload(),
        ),
    ).state

    assert state.token_usage.observed is True
    assert state.token_usage.total_tokens == 1030
    assert state.token_usage.provider_usage_complete is True
    assert state.token_usage.max_total_tokens_per_turn == 12000
    assert state.token_usage.output_cap_enforced is True
    assert state.protocol.last_protocol_event == "TokenUsageReceived"


def test_stale_or_foreign_token_usage_is_ignored() -> None:
    machine = ConversationStateMachine()
    connected = _connected_real(machine)

    stale = machine.reduce(
        connected,
        TokenUsageReceived(
            at_ns=10,
            generation=connected.connection.connection_generation - 1,
            session_id="session-real",
            known_total_tokens=1,
        ),
    ).state
    foreign = machine.reduce(
        connected,
        TokenUsageReceived(
            at_ns=11,
            generation=connected.connection.connection_generation,
            session_id="other-session",
            known_total_tokens=1,
        ),
    ).state

    assert stale == connected
    assert foreign == connected
