from __future__ import annotations

import ast
from pathlib import Path


def test_notes_package_does_not_import_pyside6() -> None:
    app_root = (
        Path(__file__).resolve().parents[2] / "apps" / "notes-pyside" / "app" / "notes"
    )
    violations: list[str] = []
    for path in app_root.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                names = [node.module or ""]
            else:
                continue
            if any(name == "PySide6" or name.startswith("PySide6.") for name in names):
                violations.append(path.name)
    assert violations == []


def test_gitignore_ignores_egg_info() -> None:
    gitignore = Path(__file__).resolve().parents[2] / ".gitignore"
    assert "*.egg-info/" in gitignore.read_text(encoding="utf-8")
