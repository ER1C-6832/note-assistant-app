from __future__ import annotations

import sys
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[2] / "apps" / "notes-pyside"
sys.path.insert(0, str(APP_ROOT))
