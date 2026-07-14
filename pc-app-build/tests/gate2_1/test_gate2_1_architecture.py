from __future__ import annotations

import ast
from pathlib import Path

PC_BUILD_ROOT = Path(__file__).resolve().parents[2]
APP_ROOT = PC_BUILD_ROOT / "apps" / "notes-pyside"
ASSISTANT_ROOT = APP_ROOT / "app" / "assistant"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_assistant_core_is_qt_database_and_legacy_transport_free() -> None:
    combined = "\n".join(_read(path).lower() for path in ASSISTANT_ROOT.rglob("*.py"))

    forbidden = (
        "pyside6",
        "pyqt",
        "sqlalchemy",
        "sqlite3",
        "notescontroller",
        "fastapi",
        "uvicorn",
        "http://127.0.0.1",
        "http://localhost",
        "sidecar",
        "subprocess",
        "multiprocessing",
        "qprocess",
    )
    for token in forbidden:
        assert token not in combined


def test_all_assistant_python_sources_parse() -> None:
    for path in ASSISTANT_ROOT.rglob("*.py"):
        ast.parse(_read(path), filename=str(path))


def test_app_package_does_not_import_bootstrap_during_core_import() -> None:
    source = _read(APP_ROOT / "app" / "__init__.py")
    tree = ast.parse(source)

    top_level_bootstrap_imports = []
    for node in tree.body:
        if isinstance(node, ast.ImportFrom) and node.module == "bootstrap":
            top_level_bootstrap_imports.append(node)
        if isinstance(node, ast.Import):
            top_level_bootstrap_imports.extend(
                alias for alias in node.names if alias.name.endswith("bootstrap")
            )

    assert top_level_bootstrap_imports == []
    assert "from .bootstrap import run_application" in source


def test_gate2_1_has_single_state_replacement_site() -> None:
    controller = _read(ASSISTANT_ROOT / "controller.py")
    state_machine = _read(ASSISTANT_ROOT / "state_machine.py")

    assert controller.count("self._state = transition.state") == 1
    assert "asyncio.Queue" in controller
    assert "EVENT_QUEUE_CAPACITY = 256" in controller
    assert "def reduce(" in state_machine
    assert "await " not in state_machine


def test_gate2_1_delivery_files_and_fail_fast_verifier_exist() -> None:
    report = PC_BUILD_ROOT / "docs" / "report" / "GATE2_1_IMPLEMENTATION_REPORT.md"
    verifier = PC_BUILD_ROOT.parent / "VERIFY_GATE2_1.ps1"

    assert report.is_file()
    assert verifier.is_file()
    verifier_source = _read(verifier)
    assert "$LASTEXITCODE -ne 0" in verifier_source
    assert "exit 1" in verifier_source
    assert "tests/gate1_7" in verifier_source
    assert "tests/gate2_1" in verifier_source
