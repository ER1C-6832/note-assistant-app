from pathlib import Path

from app.app_paths import AppPaths


def test_resolve_with_explicit_root(tmp_path: Path) -> None:
    paths = AppPaths.resolve(root_override=tmp_path / "runtime")

    assert paths.root == (tmp_path / "runtime").resolve()
    assert paths.notes_db == paths.root / "data" / "notes.db"
    assert paths.custom_tags == paths.root / "data" / "custom_tags.json"


def test_resolve_uses_local_app_data(tmp_path: Path) -> None:
    paths = AppPaths.resolve(env={"LOCALAPPDATA": str(tmp_path)})
    assert paths.root == (tmp_path / "NoteAssistant").resolve()


def test_resolve_falls_back_to_home(tmp_path: Path) -> None:
    paths = AppPaths.resolve(env={}, home=tmp_path)
    assert paths.root == (tmp_path / ".note-assistant").resolve()


def test_ensure_directories_is_idempotent(tmp_path: Path) -> None:
    paths = AppPaths.resolve(root_override=tmp_path / "runtime")
    paths.ensure_directories()
    paths.ensure_directories()

    assert paths.data_dir.is_dir()
    assert paths.logs_dir.is_dir()
    assert paths.backups_dir.is_dir()
