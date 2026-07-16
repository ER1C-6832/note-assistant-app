from __future__ import annotations

from pathlib import Path

PC_BUILD_ROOT = Path(__file__).resolve().parents[2]
REPO_ROOT = PC_BUILD_ROOT.parent
APP_ROOT = PC_BUILD_ROOT / "apps" / "notes-pyside" / "app"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_gate3_4_verifier_is_fail_fast_and_covers_all_required_layers() -> None:
    verifier_path = REPO_ROOT / "VERIFY_GATE3_3.ps1"
    verifier = _read(verifier_path).replace("\\", "/")

    assert '$ErrorActionPreference = "Stop"' in verifier
    assert "$LASTEXITCODE -ne 0" in verifier
    assert "exit $code" in verifier
    assert "compileall" in verifier
    assert "black --check" in verifier
    assert "ruff check" in verifier
    assert "pytest -W error" in verifier
    for gate in (
        "tests/gate1_7",
        "tests/gate2_1",
        "tests/gate2_2",
        "tests/gate2_3",
        "tests/gate2_4",
        "tests/gate2_5",
        "tests/gate2_6",
        "tests/gate2_7",
        "tests/gate3_1",
        "tests/gate3_2",
        "tests/gate3_3",
        "tests/gate3_4",
    ):
        assert gate in verifier
    assert "verify_gate2_7_fake_acceptance.py" in verifier
    assert "verify_gate3_1_ui_shell.py" in verifier
    assert "verify_gate3_2_fake_ptt.py" in verifier
    assert "verify_gate3_3_fake_streaming.py" in verifier


def test_real_runner_preserves_zero_one_two_exit_contract() -> None:
    runner = _read(REPO_ROOT / "RUN_GATE3_3_REAL_STREAMING.ps1")
    assert "verify_gate3_3_real_streaming.py" in runner
    assert "$code -notin @(0, 1, 2)" in runner
    assert "exit $code" in runner
    lowered = runner.lower()
    for secret_name in ("token", "device_id", "client_id", "secret", "authorization"):
        assert f"write-host ${secret_name}" not in lowered


def test_audio_dependencies_are_owned_by_pyproject_not_a_legacy_installer() -> None:
    pyproject = _read(PC_BUILD_ROOT / "pyproject.toml")
    report = _read(PC_BUILD_ROOT / "docs" / "report" / "GATE3_2_IMPLEMENTATION_REPORT.md")
    assert '"PyAudio>=0.2.14,<0.3"' in pyproject
    assert '"av>=13,<17"' in pyproject
    assert 'pip install -e ".[dev]"' in report
    assert not (REPO_ROOT / "INSTALL_GATE3_2_AUDIO_DEPS.ps1").exists()


def test_gate3_does_not_introduce_a_second_python_runtime_process() -> None:
    assistant_root = APP_ROOT / "assistant"
    source = "\n".join(
        path.read_text(encoding="utf-8") for path in sorted(assistant_root.rglob("*.py"))
    ).lower()
    assert "import subprocess" not in source
    assert "from subprocess" not in source
    assert "import multiprocessing" not in source
    assert "from multiprocessing" not in source
    assert "python.exe" not in source


def test_gate3_4_report_and_merged_authority_documents_exist() -> None:
    report = PC_BUILD_ROOT / "docs" / "report" / "GATE3_4_FINAL_ACCEPTANCE_REPORT.md"
    master = PC_BUILD_ROOT / "docs" / "PC_ASSISTANT_RUNTIME_MASTER_PLAN.md"
    amendment = (
        PC_BUILD_ROOT
        / "docs"
        / "amendments"
        / "PC_ASSISTANT_RUNTIME_MASTER_PLAN_GATE3_AMENDMENT.md"
    )
    adr = PC_BUILD_ROOT / "docs" / "adr" / "ADR-007-current-pc-audio-and-gate3-boundary.md"
    for path in (report, master, amendment, adr):
        assert path.is_file(), path
    assert "Gate 4：未开始" in _read(report)
    assert "已并入总纲" in _read(amendment)
    assert "WAITING_FOR_NEXT_TURN" in _read(master)


def test_controller_owns_bounded_turn_and_session_finalization_ledgers() -> None:
    controller = _read(APP_ROOT / "assistant" / "controller.py")
    assert "_finalized_streaming_turns" in controller
    assert "_stopped_streaming_sessions" in controller
    assert "_claim_streaming_turn_finalize" in controller
    assert "_claim_streaming_session_stop" in controller
    assert "len(self._finalized_streaming_turns) > 256" in controller
    assert "len(self._stopped_streaming_sessions) > 64" in controller
