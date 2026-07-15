from __future__ import annotations

from pathlib import Path

import pytest

from verify_gate2_7_fake_acceptance import run_fake_acceptance


@pytest.mark.asyncio
async def test_complete_fake_gate_and_notes_db_isolation(tmp_path: Path) -> None:
    result = await run_fake_acceptance(tmp_path / "runtime")

    assert result["status"] == "fake_gate_complete"
    assert result["complete_state_defaults"] is True
    assert result["future_capabilities_frozen"] is True
    assert result["fake_activation_verified"] is True
    assert result["fake_config_isolated"] is True
    assert result["fake_hello_session_verified"] is True
    assert result["fake_text_verified"] is True
    assert result["invalid_unknown_json_verified"] is True
    assert result["mcp_blocked_verified"] is True
    assert result["abnormal_close_recovery_verified"] is True
    assert result["disable_verified"] is True
    assert result["shutdown_verified"] is True
    assert result["notes_db_unchanged"] is True
    assert result["no_pending_runtime_tasks"] is True
    assert result["recovered_generation"] == result["first_generation"] + 1
