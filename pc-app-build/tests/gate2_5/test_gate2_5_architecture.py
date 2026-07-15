from __future__ import annotations

import ast
from pathlib import Path

PC_BUILD_ROOT = Path(__file__).resolve().parents[2]
ASSISTANT_ROOT = PC_BUILD_ROOT / "apps" / "notes-pyside" / "app" / "assistant"
REPO_ROOT = PC_BUILD_ROOT.parent


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_recovery_files_exist_parse_and_keep_single_state_writer() -> None:
    expected = (
        ASSISTANT_ROOT / "network" / "reconnect_policy.py",
        ASSISTANT_ROOT / "errors.py",
        ASSISTANT_ROOT / "controller.py",
        ASSISTANT_ROOT / "state_machine.py",
    )
    for path in expected:
        source = _read(path)
        ast.parse(source, filename=str(path))
        lowered = source.lower()
        assert "pyside6" not in lowered
        assert "sqlalchemy" not in lowered
        assert "subprocess" not in lowered
        assert "multiprocessing" not in lowered

    controller = _read(ASSISTANT_ROOT / "controller.py")
    machine = _read(ASSISTANT_ROOT / "state_machine.py")
    assert controller.count("self._state = transition.state") == 1
    assert "self._reconnect_task: asyncio.Task[None] | None = None" in controller
    assert "ReconnectTimerFired(" in controller
    assert "reconnect timer 修改 State" not in controller
    assert "await " not in machine


def test_current_verifier_and_real_recovery_runner_are_present() -> None:
    verifier = _read(REPO_ROOT / "VERIFY_GATE2_5.ps1")
    runner = _read(REPO_ROOT / "RUN_GATE2_5_REAL_RECOVERY.ps1")

    assert "tests/gate2_5" in verifier
    assert "$LASTEXITCODE -ne 0" in verifier
    assert "exit 1" in verifier
    assert "verify_gate2_5_real_recovery.py" in runner
    assert (PC_BUILD_ROOT / "docs" / "report" / "GATE2_5_IMPLEMENTATION_REPORT.md").is_file()
