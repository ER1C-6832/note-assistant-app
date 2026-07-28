from __future__ import annotations

from dataclasses import replace

import pytest

pytest.importorskip("PySide6")

from app.assistant.state import AssistantState, TokenUsageState  # noqa: E402
from app.ui import AssistantViewModel  # noqa: E402


class _StateOnlyController:
    def __init__(self, state: AssistantState) -> None:
        self.state = state

    def subscribe(self, callback):
        self._callback = callback
        return lambda: None


def test_view_model_exposes_explicit_budget_and_enforcement_status() -> None:
    state = replace(
        AssistantState.disabled(now_ns=1),
        token_usage=TokenUsageState(
            observed=True,
            model="glm-test",
            input_tokens=1000,
            output_tokens=30,
            total_tokens=1030,
            known_total_tokens=1030,
            provider_usage_complete=True,
            llm_calls_started=2,
            tool_call_count=1,
            status="completed",
            budget_enabled=True,
            budget_status="within_budget",
            max_total_tokens_per_turn=12000,
            max_output_tokens_per_request=200,
            output_cap_enforced=True,
        ),
    )
    view_model = AssistantViewModel(_StateOnlyController(state))

    assert view_model.tokenUsageAvailable is True
    assert view_model.tokenBudgetStatus == "预算内"
    assert view_model.tokenBudgetProgress == 9
    assert "1030 / 12000" in view_model.tokenUsageSummary
    assert "输出硬限制：已执行（每次 ≤ 200）" in view_model.tokenUsageSummary
