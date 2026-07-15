from __future__ import annotations

from app.assistant.network import ReconnectPolicy


def test_policy_preserves_spec_backoff_and_max_attempts_without_jitter() -> None:
    policy = ReconnectPolicy(jitter_fraction=0.0)

    first = policy.decide_failure(
        assistant_enabled=True,
        manual_disconnect_requested=False,
        current_attempt=0,
        generation=5,
    )
    second = policy.decide_failure(
        assistant_enabled=True,
        manual_disconnect_requested=False,
        current_attempt=1,
        generation=6,
    )
    third = policy.decide_failure(
        assistant_enabled=True,
        manual_disconnect_requested=False,
        current_attempt=2,
        generation=7,
    )
    exhausted = policy.decide_failure(
        assistant_enabled=True,
        manual_disconnect_requested=False,
        current_attempt=3,
        generation=8,
    )

    assert (first.next_attempt, first.delay_seconds) == (1, 0.5)
    assert (second.next_attempt, second.delay_seconds) == (2, 1.5)
    assert (third.next_attempt, third.delay_seconds) == (3, 3.0)
    assert exhausted.should_reconnect is False
    assert exhausted.delay_seconds is None
    assert exhausted.decision_label == "failure_max_attempts_reached"


def test_policy_never_reconnects_disabled_manual_or_normal_close() -> None:
    policy = ReconnectPolicy(jitter_fraction=0.0)

    disabled = policy.decide_close(
        close_code=1006,
        reason="abnormal",
        assistant_enabled=False,
        manual_disconnect_requested=False,
        current_attempt=0,
        generation=1,
    )
    manual = policy.decide_close(
        close_code=1006,
        reason="manual",
        assistant_enabled=True,
        manual_disconnect_requested=True,
        current_attempt=0,
        generation=1,
    )
    normal = policy.decide_close(
        close_code=1000,
        reason="normal",
        assistant_enabled=True,
        manual_disconnect_requested=False,
        current_attempt=0,
        generation=1,
    )

    assert disabled.should_reconnect is False
    assert manual.should_reconnect is False
    assert normal.should_reconnect is False
    assert normal.decision_label == "normal_close_no_reconnect"


def test_default_jitter_is_deterministic_and_bounded() -> None:
    policy = ReconnectPolicy()
    first = policy.decide_failure(
        assistant_enabled=True,
        manual_disconnect_requested=False,
        current_attempt=0,
        generation=17,
    )
    repeated = policy.decide_failure(
        assistant_enabled=True,
        manual_disconnect_requested=False,
        current_attempt=0,
        generation=17,
    )

    assert first.delay_seconds == repeated.delay_seconds
    assert first.delay_seconds is not None
    assert 0.45 <= first.delay_seconds <= 0.55


def test_jitter_seed_spreads_different_failure_events_while_remaining_bounded() -> None:
    policy = ReconnectPolicy()
    first = policy.decide_failure(
        assistant_enabled=True,
        manual_disconnect_requested=False,
        current_attempt=0,
        generation=17,
        jitter_seed=100,
    )
    second = policy.decide_failure(
        assistant_enabled=True,
        manual_disconnect_requested=False,
        current_attempt=0,
        generation=17,
        jitter_seed=101,
    )

    assert first.delay_seconds != second.delay_seconds
    assert first.delay_seconds is not None
    assert second.delay_seconds is not None
    assert 0.45 <= first.delay_seconds <= 0.55
    assert 0.45 <= second.delay_seconds <= 0.55
