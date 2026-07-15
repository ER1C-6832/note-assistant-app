from __future__ import annotations

import ast
from pathlib import Path

PC_BUILD_ROOT = Path(__file__).resolve().parents[2]
ASSISTANT_ROOT = PC_BUILD_ROOT / "apps" / "notes-pyside" / "app" / "assistant"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_gate2_3_files_exist_and_parse_without_qt_or_database_dependencies() -> None:
    expected = (
        ASSISTANT_ROOT / "network" / "transport.py",
        ASSISTANT_ROOT / "network" / "websocket_transport.py",
        ASSISTANT_ROOT / "network" / "fake_transport.py",
        ASSISTANT_ROOT / "protocol" / "message_builder.py",
        ASSISTANT_ROOT / "protocol" / "message_router.py",
        ASSISTANT_ROOT / "protocol" / "events.py",
    )
    for path in expected:
        source = _read(path)
        ast.parse(source, filename=str(path))
        lowered = source.lower()
        assert "pyside6" not in lowered
        assert "sqlalchemy" not in lowered
        assert "localhost" not in lowered
        assert "sidecar" not in lowered


def test_real_websocket_has_one_sender_and_one_receiver_owner() -> None:
    source = _read(ASSISTANT_ROOT / "network" / "websocket_transport.py")

    assert source.count("def _sender_loop(") == 1
    assert source.count("def _receiver_loop(") == 1
    assert "asyncio.Queue(maxsize=SEND_QUEUE_CAPACITY)" in source
    assert "await active.connection.send(item.payload)" in source
    assert "await active.connection.recv()" in source
    assert "additional_headers=config.headers()" in source
    assert '"Protocol-Version": "1"' in _read(ASSISTANT_ROOT / "network" / "transport.py")


def test_current_gate_verifier_and_real_acceptance_runner_are_present() -> None:
    pyproject = _read(PC_BUILD_ROOT / "pyproject.toml")

    verifiers = tuple(sorted(PC_BUILD_ROOT.parent.glob("VERIFY_GATE*.ps1")))
    assert verifiers

    covering = [path for path in verifiers if "tests/gate2_3" in _read(path).replace("\\", "/")]
    assert covering

    verifier = _read(covering[-1])
    real_runner = _read(PC_BUILD_ROOT.parent / "RUN_GATE2_4_REAL_TEXT.ps1")

    assert '"websockets>=16.0,<17"' in pyproject
    assert "tests/gate2_3" in verifier
    assert "$LASTEXITCODE -ne 0" in verifier
    assert "exit 1" in verifier
    assert "RUN_GATE2_4_REAL_TEXT" in real_runner or "verify_gate2_4_real_text.py" in real_runner
    assert (PC_BUILD_ROOT / "docs" / "report" / "GATE2_3_IMPLEMENTATION_REPORT.md").is_file()
