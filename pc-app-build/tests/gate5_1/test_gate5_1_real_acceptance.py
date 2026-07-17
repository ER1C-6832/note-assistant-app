from __future__ import annotations

from tools.gate5_1_acceptance import classify_tool_probe


def test_noninteractive_missing_tool_is_endpoint_blocked() -> None:
    decision = classify_tool_probe(
        protocol_ready=True,
        turn_completed=True,
        observed_status=None,
        interactive_user_command=False,
    )

    assert decision.status == "real_gate_blocked"
    assert decision.exit_code == 2
    assert decision.failure_stage == "endpoint_tool_selection"


def test_interactive_missing_tool_is_acceptance_failure() -> None:
    decision = classify_tool_probe(
        protocol_ready=True,
        turn_completed=True,
        observed_status=None,
        interactive_user_command=True,
    )

    assert decision.status == "failed"
    assert decision.exit_code == 1
    assert decision.failure_stage == "natural_language_tool_selection"


def test_protocol_handshake_missing_is_blocked() -> None:
    decision = classify_tool_probe(
        protocol_ready=False,
        turn_completed=False,
        observed_status=None,
        interactive_user_command=True,
    )

    assert decision.status == "real_gate_blocked"
    assert decision.exit_code == 2
    assert decision.failure_stage == "mcp_capability_handshake"


def test_observed_tool_failure_is_not_misclassified_as_blocked() -> None:
    decision = classify_tool_probe(
        protocol_ready=True,
        turn_completed=True,
        observed_status="invalid_params",
        interactive_user_command=False,
    )

    assert decision.status == "failed"
    assert decision.exit_code == 1
    assert decision.failure_stage == "tool_execution"
