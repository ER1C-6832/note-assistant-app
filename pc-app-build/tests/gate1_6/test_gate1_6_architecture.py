from __future__ import annotations

import re
from pathlib import Path

PC_BUILD_ROOT = Path(__file__).resolve().parents[2]
APP_PACKAGE = PC_BUILD_ROOT / "apps" / "notes-pyside" / "app"
QML_ROOT = APP_PACKAGE / "qml"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_bootstrap_composes_real_models_and_view_model() -> None:
    source = _read(APP_PACKAGE / "bootstrap.py")

    assert "from .ui import NoteListModel, NotesViewModel" in source
    assert "notes_list_model = NoteListModel()" in source
    assert "deleted_notes_list_model = NoteListModel()" in source
    assert "notes_view_model = NotesViewModel(" in source
    assert '"notes-view-model",' in source
    assert "notes_view_model.close" in source
    assert "EmptyNotesViewModel" not in source
    assert "EmptyNoteListModel" not in source


def test_todo_category_uses_exact_tag_query() -> None:
    source = _read(APP_PACKAGE / "ui" / "notes_view_model.py")

    assert 'elif category == "todo":' in source
    assert 'lambda: self._query_service.list_by_tag("待办")' in source
    assert 'self.loadCategory("todo")' in source


def test_qml_has_only_search_debounce_timer_and_no_legacy_controller() -> None:
    qml_sources = {path: _read(path) for path in QML_ROOT.rglob("*.qml")}
    combined = "\n".join(qml_sources.values())
    main_source = qml_sources[QML_ROOT / "Main.qml"]

    assert "notesController" not in combined
    assert "NotesApi" not in combined
    assert "sidecar" not in combined.lower()
    assert main_source.count("Timer {") == 1
    assert "id: liveSearchTimer" in main_source
    assert "interval: 220" in main_source
    assert "reloadCurrentContext" not in main_source


def test_child_pages_receive_view_model_explicitly() -> None:
    page_names = (
        "CreateNotePage.qml",
        "EditNotePage.qml",
        "SearchPage.qml",
        "DeletedNotesPage.qml",
    )
    main_source = _read(QML_ROOT / "Main.qml")

    for page_name in page_names:
        source = _read(QML_ROOT / "pages" / page_name)
        assert "property var notesViewModelRef: null" in source
        assert re.search(r"\bnotesViewModel\.", source) is None

    assert "readonly property var viewModel: notesViewModel" in main_source
    assert main_source.count("notesViewModelRef: root.viewModel") >= len(page_names)


def test_mutation_navigation_and_bulk_state_are_signal_driven() -> None:
    main_source = _read(QML_ROOT / "Main.qml")
    note_list_source = _read(QML_ROOT / "components" / "NoteList.qml")
    deleted_source = _read(QML_ROOT / "pages" / "DeletedNotesPage.qml")

    assert "function onNoteCreated" in main_source
    assert "function onNoteUpdated" in main_source
    assert "function onNotesSoftDeleted" in main_source
    assert "onClicked: { root.bulk" not in note_list_source
    assert "function onNotesSoftDeleted" in note_list_source
    assert "function onPinStateChanged" in note_list_source
    assert "function onNotesRestored" in deleted_source
    assert "function onNotesHardDeleted" in deleted_source
    assert "root.notesViewModelRef.requestBulkRestoreDeleted(root.selectedIds)" in deleted_source
    assert "root.exitMultiSelect()" not in re.search(
        r"onClicked: root\.notesViewModelRef\.requestBulkRestoreDeleted.*",
        deleted_source,
    ).group(0)
