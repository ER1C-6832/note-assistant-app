"""
PySide6 desktop application entry point.
"""

from __future__ import annotations

import sys
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parent

if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

from app import run_app  # noqa: E402


if __name__ == "__main__":
    raise SystemExit(run_app())
