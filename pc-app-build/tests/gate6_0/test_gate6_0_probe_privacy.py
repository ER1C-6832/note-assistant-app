from __future__ import annotations

import json

import pytest

from app.assistant.audio.gate6_probe import (
    BoundedProbeQueue,
    ProbeQueueOverflow,
    ProbeReport,
    ProbeScenario,
    ProbeStatus,
    ensure_probe_report_safe,
    sanitize_public_value,
)


def test_bounded_probe_queue_fails_visible_and_closes_idempotently() -> None:
    queue = BoundedProbeQueue[int](2)
    queue.put(1)
    queue.put(2)

    with pytest.raises(ProbeQueueOverflow):
        queue.put(3)

    assert queue.peak == 2
    assert queue.overflow_count == 1
    assert queue.drain() == (1, 2)
    queue.close()
    queue.close()
    assert len(queue) == 0


def test_probe_report_redacts_private_ids_secrets_and_binary_payloads() -> None:
    safe = sanitize_public_value(
        {
            "endpoint_guid": "9b2ec23d-75b7-4da7-a73a-123456789abc",
            "authorization": "Bearer private-token",
            "pcm16_le": b"private-audio",
            "public_name": "Microphone 9b2ec23d-75b7-4da7-a73a-123456789abc",
        }
    )
    payload = json.dumps(safe, ensure_ascii=False)

    assert "private-token" not in payload
    assert "private-audio" not in payload
    assert "9b2ec23d-75b7-4da7-a73a-123456789abc" not in payload
    assert "<redacted>" in payload or "masked:" in payload


def test_probe_report_rejects_unsafe_unredacted_json() -> None:
    with pytest.raises(ValueError, match="private endpoint"):
        ensure_probe_report_safe({"device": "9b2ec23d-75b7-4da7-a73a-123456789abc"})


def test_probe_report_public_dict_is_bounded_and_has_no_payload_persistence() -> None:
    report = ProbeReport(
        scenario=ProbeScenario.FAKE_CONTRACT,
        status=ProbeStatus.COMPLETE,
        platform_public="test",
        result={"count": 1},
        terminal={"capture_stream": 0},
    )

    value = report.public_dict()
    assert value["payload_persisted"] is False
    assert value["secrets_redacted"] is True
