from __future__ import annotations

from collections import deque

from app.assistant.audio.gate6_backend_probe import (
    analyze_double_talk_activity,
    evaluate_aec_probe,
    resolve_stream_delay_ms,
)


def _summary(*, frames: int = 500, rms: float, peak: int = 1000) -> dict[str, object]:
    return {
        "frame_count": frames,
        "clipped_frames": 0,
        "peak_max": peak,
        "peak_median": peak // 2,
        "rms_median": rms,
        "first_frame_ns_present": True,
        "duration_ms": frames * 10.0,
    }


def test_auto_stream_delay_uses_open_stream_latencies() -> None:
    delay_ms, source = resolve_stream_delay_ms(
        requested_delay_ms=None,
        input_latency_seconds=0.020,
        output_latency_seconds=0.100,
    )

    assert delay_ms == 120
    assert source == "stream_reported"
    assert resolve_stream_delay_ms(
        requested_delay_ms=50,
        input_latency_seconds=0.020,
        output_latency_seconds=0.100,
    ) == (50, "explicit")


def test_far_end_only_requires_observed_and_suppressed_echo() -> None:
    acceptance = evaluate_aec_probe(
        scenario="far_end_only",
        duration_seconds=5.0,
        render_frames=499,
        raw_summary=_summary(frames=499, rms=99.369, peak=1238),
        processed_summary=_summary(frames=499, rms=5.064, peak=81),
        raw_baseline_summary=None,
        processed_baseline_summary=None,
        raw_speech_summary=None,
        processed_speech_summary=None,
        double_talk_activity=None,
        errors=[],
        terminal_zero=True,
    )

    assert acceptance["accepted"] is True
    assert acceptance["criteria"]["echo_attenuation_db"] > 25


def test_double_talk_rejects_process_completion_when_near_end_is_erased() -> None:
    activity = analyze_double_talk_activity(
        raw_baseline_rms=[90.0] * 150,
        processed_baseline_rms=[5.0] * 150,
        raw_speech_rms=[90.0] * 200 + [260.0] * 30 + [90.0] * 221,
        processed_speech_rms=[5.0] * 451,
    )
    acceptance = evaluate_aec_probe(
        scenario="double_talk",
        duration_seconds=6.0,
        render_frames=599,
        raw_summary=_summary(frames=601, rms=168.381, peak=2561),
        processed_summary=_summary(frames=601, rms=4.82, peak=23),
        raw_baseline_summary=_summary(frames=150, rms=90.0, peak=1200),
        processed_baseline_summary=_summary(frames=150, rms=5.0, peak=30),
        raw_speech_summary=_summary(frames=451, rms=240.0, peak=2561),
        processed_speech_summary=_summary(frames=451, rms=5.1, peak=23),
        double_talk_activity=activity,
        errors=[],
        terminal_zero=True,
    )

    assert acceptance["accepted"] is False
    assert acceptance["failure_code"] == "aec_near_end_not_preserved"
    assert "near_end_speech_not_preserved" in acceptance["reasons"]


def test_double_talk_accepts_only_when_raw_speech_is_seen_and_processed_speech_survives() -> None:
    activity = analyze_double_talk_activity(
        raw_baseline_rms=[80.0] * 150,
        processed_baseline_rms=[5.0] * 150,
        raw_speech_rms=[80.0] * 200 + [260.0] * 30 + [80.0] * 220,
        processed_speech_rms=[5.0] * 200 + [32.0] * 30 + [5.0] * 220,
    )
    acceptance = evaluate_aec_probe(
        scenario="double_talk",
        duration_seconds=6.0,
        render_frames=600,
        raw_summary=_summary(frames=600, rms=180.0),
        processed_summary=_summary(frames=600, rms=20.0),
        raw_baseline_summary=_summary(frames=150, rms=80.0),
        processed_baseline_summary=_summary(frames=150, rms=5.0),
        raw_speech_summary=_summary(frames=450, rms=260.0),
        processed_speech_summary=_summary(frames=450, rms=32.0),
        double_talk_activity=activity,
        errors=[],
        terminal_zero=True,
    )

    assert acceptance["accepted"] is True
    assert acceptance["criteria"]["raw_near_speech_observed"] is True
    assert acceptance["criteria"]["near_end_preserved"] is True


def test_short_utterance_activity_does_not_require_half_the_window() -> None:
    raw_speech = [70.0] * 300 + [220.0] * 12 + [70.0] * 138
    processed_speech = [5.0] * 300 + [28.0] * 12 + [5.0] * 138

    activity = analyze_double_talk_activity(
        raw_baseline_rms=deque([70.0] * 150),
        processed_baseline_rms=deque([5.0] * 150),
        raw_speech_rms=deque(raw_speech),
        processed_speech_rms=deque(processed_speech),
    )

    assert activity["raw_near_speech_observed"] is True
    assert activity["processed_near_speech_observed"] is True
    assert activity["near_end_preserved"] is True
    assert activity["raw_active_frame_ratio"] < 0.05
