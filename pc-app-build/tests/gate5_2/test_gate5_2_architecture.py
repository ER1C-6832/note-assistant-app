from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
APP = ROOT / "apps" / "notes-pyside" / "app"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_executor_uses_application_services_not_repository_or_qml() -> None:
    source = _read(APP / "assistant" / "mcp" / "gate5_2_executor.py")
    assert "NoteCommandService" in source
    assert "NoteQueryService" in source
    assert "TagCatalogService" in source
    assert "UiCommandBus" in source
    assert "SqlAlchemy" not in source
    assert "NoteRepository" not in source
    assert "QML" not in source


def test_batch_tag_binding_is_one_repository_transaction() -> None:
    source = _read(APP / "notes" / "sqlalchemy_repository.py")
    assert "def update_tags_many" in source
    assert "with self._session_factory() as session, session.begin():" in source
    assert "BatchUpdateTagsCommand" in source


def test_bootstrap_shares_gate52_capabilities_and_tag_service() -> None:
    source = _read(APP / "bootstrap.py")
    gate53 = _read(APP / "assistant" / "mcp" / "gate5_3_executor.py")
    assert "Gate53ToolExecutor" in source
    assert "class Gate53ToolExecutor(Gate52ToolExecutor)" in gate53
    assert "TagCatalogService" in source
    assert "tag_catalog=tag_catalog_service" in source
    assert "from .ui import NoteListModel, NotesViewModel" in source
