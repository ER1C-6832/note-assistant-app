from __future__ import annotations

import ast
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[2] / "apps" / "notes-pyside" / "app"
NOTES_ROOT = APP_ROOT / "notes"


def test_services_do_not_import_pyside6() -> None:
    for filename in (
        "command_service.py",
        "query_service.py",
        "service_errors.py",
    ):
        content = (NOTES_ROOT / filename).read_text(encoding="utf-8")
        assert "PySide6" not in content


def test_bootstrap_contains_no_business_sql() -> None:
    content = (APP_ROOT / "bootstrap.py").read_text(encoding="utf-8")
    for forbidden in (
        "SELECT ",
        "INSERT ",
        "UPDATE notes",
        "DELETE FROM",
        ".execute(",
    ):
        assert forbidden not in content


def test_repository_helper_owns_the_only_executor_run_call() -> None:
    service_errors = ast.parse((NOTES_ROOT / "service_errors.py").read_text(encoding="utf-8"))
    executor_runs = [
        node
        for node in ast.walk(service_errors)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "run"
    ]
    assert len(executor_runs) == 1

    for filename in ("command_service.py", "query_service.py"):
        tree = ast.parse((NOTES_ROOT / filename).read_text(encoding="utf-8"))
        direct_runs = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "run"
        ]
        assert direct_runs == []
