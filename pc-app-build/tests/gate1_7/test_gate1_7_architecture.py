from __future__ import annotations

import ast
from pathlib import Path

PC_BUILD_ROOT = Path(__file__).resolve().parents[2]
APP_ROOT = PC_BUILD_ROOT / "apps" / "notes-pyside"
APP_PACKAGE = APP_ROOT / "app"
QML_ROOT = APP_PACKAGE / "qml"

FORBIDDEN_RUNTIME_TEXT = (
    "notescontroller",
    "notesapi",
    "fastapi",
    "uvicorn",
    "http://127.0.0.1",
    "http://localhost",
    "py-xiaozhi",
)
FORBIDDEN_PROCESS_APIS = (
    "subprocess",
    "multiprocessing",
    "qprocess",
    "popen(",
)

# "sidecar" alone is valid SQLite terminology for the -wal/-shm companion files.
# Match only names that indicate the removed helper-process architecture.
FORBIDDEN_SIDECAR_PATTERNS = (
    "sidecar_client",
    "sidecar_process",
    "sidecar_url",
    "start_sidecar",
    "stop_sidecar",
)


def _source_files() -> tuple[Path, ...]:
    return tuple(
        sorted(
            path
            for path in APP_PACKAGE.rglob("*")
            if path.is_file() and path.suffix in {".py", ".qml"}
        )
    )


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_python_sources_parse_and_gate1_has_one_composition_root() -> None:
    for path in APP_PACKAGE.rglob("*.py"):
        ast.parse(_read(path), filename=str(path))

    bootstrap = _read(APP_PACKAGE / "bootstrap.py")
    assert "class ApplicationContext" in bootstrap
    assert "notes_view_model = NotesViewModel(" in bootstrap
    assert "command_service=notes_runtime.note_command_service" in bootstrap
    assert "query_service=notes_runtime.note_query_service" in bootstrap
    assert 'context.setContextProperty("notesViewModel"' in bootstrap
    assert 'context.setContextProperty("notesListModel"' in bootstrap
    assert 'context.setContextProperty("deletedNotesListModel"' in bootstrap


def test_runtime_source_has_no_legacy_transport_or_second_process_path() -> None:
    violations: list[str] = []
    for path in _source_files():
        text = _read(path).lower()
        for token in (
            *FORBIDDEN_RUNTIME_TEXT,
            *FORBIDDEN_PROCESS_APIS,
            *FORBIDDEN_SIDECAR_PATTERNS,
        ):
            if token in text:
                violations.append(f"{path.relative_to(APP_PACKAGE)}: {token}")

    assert violations == []


def test_qml_uses_view_model_signals_and_only_search_debounce_timer() -> None:
    qml_sources = {path: _read(path) for path in QML_ROOT.rglob("*.qml")}
    combined = "\n".join(qml_sources.values())
    main_source = qml_sources[QML_ROOT / "Main.qml"]

    assert "notesController" not in combined
    assert "if (notesViewModel.request" not in combined
    assert "if (root.notesViewModelRef.request" not in combined
    assert main_source.count("Timer {") == 1
    assert "id: liveSearchTimer" in main_source
    assert "interval: 220" in main_source
    assert "function onNoteCreated" in main_source
    assert "function onNoteUpdated" in main_source
    assert "function onNotesSoftDeleted" in main_source
    assert "readonly property var viewModel: notesViewModel" in main_source
    assert "readonly property bool viewModelReady" in main_source
    assert (
        "selectedIndex: root.viewModelReady ? root.viewModel.selectedIndex : -1"
        in main_source
    )


def test_database_access_stays_behind_application_services() -> None:
    ui_sources = "\n".join(
        _read(path) for path in (APP_PACKAGE / "ui").rglob("*.py")
    ).lower()
    qml_sources = "\n".join(_read(path) for path in QML_ROOT.rglob("*.qml")).lower()

    for token in ("sqlalchemy", "sessionfactory", "sqlite3", "create_engine"):
        assert token not in ui_sources
        assert token not in qml_sources

    view_model_source = _read(APP_PACKAGE / "ui" / "notes_view_model.py")
    assert "NoteCommandService" in view_model_source
    assert "NoteQueryService" in view_model_source


def test_gate1_7_deliverables_exist() -> None:
    assert (
        PC_BUILD_ROOT / "docs" / "report" / "GATE1_IMPLEMENTATION_REPORT.md"
    ).is_file()

    verify_scripts = tuple(sorted(PC_BUILD_ROOT.parent.glob("VERIFY_GATE*.ps1")))
    assert verify_scripts, "At least one current Gate verification script must exist."

    for verify_script in verify_scripts:
        verify_source = _read(verify_script)
        assert "$LASTEXITCODE" in verify_source, verify_script.name
        assert "exit 1" in verify_source, verify_script.name
