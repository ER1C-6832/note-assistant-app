from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

import pytest

APP_ROOT = Path(__file__).resolve().parents[2] / "apps" / "notes-pyside"
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

from app.app_paths import AppPaths  # noqa: E402


@pytest.fixture
def app_paths(tmp_path: Path) -> AppPaths:
    paths = AppPaths.resolve(root_override=tmp_path / "runtime")
    paths.ensure_directories()
    return paths


@pytest.fixture
def worktree_root(tmp_path: Path) -> Path:
    root = tmp_path / "note-assistant-app-runtime-v2"
    root.mkdir()
    return root


@pytest.fixture
def fixed_now() -> datetime:
    return datetime(2026, 7, 14, 12, 30, 45)
