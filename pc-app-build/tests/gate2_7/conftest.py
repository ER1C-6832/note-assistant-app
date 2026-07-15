from __future__ import annotations

import sys
from pathlib import Path

PC_BUILD_ROOT = Path(__file__).resolve().parents[2]
APP_ROOT = PC_BUILD_ROOT / "apps" / "notes-pyside"
TOOLS_ROOT = PC_BUILD_ROOT / "tools"

for path in (APP_ROOT, TOOLS_ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))
