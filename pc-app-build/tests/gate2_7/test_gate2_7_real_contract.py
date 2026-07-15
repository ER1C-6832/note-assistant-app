from __future__ import annotations

from verify_gate2_7_real_acceptance import _environment_blocked, _mask


def test_real_gate_environment_blocking_is_distinct_from_protocol_failure() -> None:
    assert _environment_blocked("WebSocket token 未配置，请先完成 activation")
    assert _environment_blocked("OTA/Activation 网络请求失败：connection refused")
    assert not _environment_blocked("server hello session_id is empty")
    assert not _environment_blocked("assistant text payload is invalid")


def test_real_gate_masks_identity_and_session_values() -> None:
    assert _mask(None) is None
    assert _mask("12345678") == "********"
    assert _mask("1234567890abcdef") == "1234***cdef"
