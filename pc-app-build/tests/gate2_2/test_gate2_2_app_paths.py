from __future__ import annotations

from app.app_paths import AppPaths


def test_assistant_runtime_config_uses_local_app_data_data_directory(tmp_path) -> None:
    paths = AppPaths.resolve(root_override=tmp_path / "NoteAssistant")

    assert paths.assistant_runtime_config == paths.data_dir / "assistant_runtime.json"
    assert paths.assistant_runtime_config.parent == paths.notes_db.parent
