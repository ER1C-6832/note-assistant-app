"""Shared decision helpers for Gate 5.1 Real natural-language probes."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ToolProbeDecision:
    status: str
    exit_code: int
    failure_stage: str | None
    reason: str | None


def classify_tool_probe(
    *,
    protocol_ready: bool,
    turn_completed: bool,
    observed_status: str | None,
    interactive_user_command: bool,
) -> ToolProbeDecision:
    """Separate client failures from endpoint tool-selection limitations."""

    if observed_status == "success":
        return ToolProbeDecision("real_gate_complete", 0, None, None)
    if observed_status is not None:
        return ToolProbeDecision(
            "failed",
            1,
            "tool_execution",
            f"tool returned status={observed_status}",
        )
    if not protocol_ready:
        return ToolProbeDecision(
            "real_gate_blocked",
            2,
            "mcp_capability_handshake",
            "initialize/tools-list capability handshake was not observed",
        )
    if not turn_completed:
        return ToolProbeDecision(
            "failed",
            1,
            "assistant_turn",
            "assistant turn did not complete",
        )
    if interactive_user_command:
        return ToolProbeDecision(
            "failed",
            1,
            "natural_language_tool_selection",
            "the connected assistant completed the real UI command without tools/call",
        )
    return ToolProbeDecision(
        "real_gate_blocked",
        2,
        "endpoint_tool_selection",
        "the endpoint completed the text turn without selecting an advertised tool",
    )


__all__ = ["ToolProbeDecision", "classify_tool_probe"]
