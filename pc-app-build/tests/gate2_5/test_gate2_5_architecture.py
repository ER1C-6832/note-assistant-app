from __future__ import annotations

import ast
from pathlib import Path

PC_BUILD_ROOT = Path(__file__).resolve().parents[2]
ASSISTANT_ROOT = PC_BUILD_ROOT / "apps" / "notes-pyside" / "app" / "assistant"
REPO_ROOT = PC_BUILD_ROOT.parent
TOOLS_ROOT = PC_BUILD_ROOT / "tools"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _normalized_source(path: Path) -> str:
    return _read(path).replace("\\", "/")


def _current_verifiers_covering(test_path: str) -> tuple[Path, ...]:
    verifiers = tuple(sorted(REPO_ROOT.glob("VERIFY_GATE*.ps1")))
    assert verifiers, "repository must contain a current Gate verifier"

    covering = tuple(path for path in verifiers if test_path in _normalized_source(path))
    assert covering, f"a current verifier must continue to run {test_path}"
    return covering


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


def test_current_verifier_and_persisted_real_recovery_tool_are_present() -> None:
    covering_verifiers = _current_verifiers_covering("tests/gate2_5")

    for verifier in covering_verifiers:
        source = _normalized_source(verifier)
        assert "$LASTEXITCODE -ne 0" in source, verifier.name
        assert "exit 1" in source, verifier.name

    assert (TOOLS_ROOT / "verify_gate2_5_real_recovery.py").is_file()
    assert (PC_BUILD_ROOT / "docs" / "report" / "GATE2_5_IMPLEMENTATION_REPORT.md").is_file()
