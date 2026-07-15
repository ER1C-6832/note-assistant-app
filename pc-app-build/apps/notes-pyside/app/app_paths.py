"""Resolve writable application paths independently from the Git worktree."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping


@dataclass(frozen=True, slots=True)
class AppPaths:
    root: Path
    data_dir: Path
    notes_db: Path
    custom_tags: Path
    logs_dir: Path
    backups_dir: Path

    @classmethod
    def resolve(
        cls,
        *,
        root_override: str | Path | None = None,
        env: Mapping[str, str] | None = None,
        home: Path | None = None,
    ) -> "AppPaths":
        values = os.environ if env is None else env

        if root_override is not None:
            root = Path(root_override).expanduser()
        else:
            local_app_data = values.get("LOCALAPPDATA", "").strip()
            if local_app_data:
                root = Path(local_app_data) / "NoteAssistant"
            else:
                root = (Path.home() if home is None else home) / ".note-assistant"

        root = root.resolve()
        data_dir = root / "data"
        return cls(
            root=root,
            data_dir=data_dir,
            notes_db=data_dir / "notes.db",
            custom_tags=data_dir / "custom_tags.json",
            logs_dir=root / "logs",
            backups_dir=root / "backups",
        )

    @property
    def assistant_runtime_config(self) -> Path:
        return self.data_dir / "assistant_runtime.json"

    def ensure_directories(self) -> None:
        for path in (self.root, self.data_dir, self.logs_dir, self.backups_dir):
            path.mkdir(parents=True, exist_ok=True)
