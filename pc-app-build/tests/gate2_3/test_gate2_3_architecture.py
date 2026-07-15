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

    covering = tuple(
        path for path in verifiers if test_path in _normalized_source(path)
    )
    assert covering, f"a current verifier must continue to run {test_path}"
    return covering


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
    assert '"Protocol-Version": "1"' in _read(
        ASSISTANT_ROOT / "network" / "transport.py"
    )


def test_current_gate_verifier_and_persisted_real_acceptance_tool_are_present() -> None:
    pyproject = _read(PC_BUILD_ROOT / "pyproject.toml")
    covering_verifiers = _current_verifiers_covering("tests/gate2_3")

    assert '"websockets>=16.0,<17"' in pyproject
    for verifier in covering_verifiers:
        source = _normalized_source(verifier)
        assert "$LASTEXITCODE -ne 0" in source, verifier.name
        assert "exit 1" in source, verifier.name

    assert (TOOLS_ROOT / "verify_gate2_3_real_websocket.py").is_file()
    assert (
        PC_BUILD_ROOT / "docs" / "report" / "GATE2_3_IMPLEMENTATION_REPORT.md"
    ).is_file()
