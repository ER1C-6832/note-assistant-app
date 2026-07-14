from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QUICK_CONTROLS_STYLE", "Basic")

APP_ROOT = Path(__file__).resolve().parents[2] / "apps" / "notes-pyside"
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

from PySide6.QtCore import QTimer  # noqa: E402
from PySide6.QtGui import QGuiApplication  # noqa: E402

from app.bootstrap import run_application  # noqa: E402


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="note-assistant-gate1-7-") as temp_dir:
        root = Path(temp_dir)
        app = QGuiApplication.instance() or QGuiApplication(["gate1.7-startup-smoke"])
        QTimer.singleShot(750, app.quit)
        exit_code = run_application(
            ["gate1.7-startup-smoke"],
            data_root=root / "runtime",
            worktree_root=root / "worktree",
            migration_env={},
        )
        if exit_code != 0:
            return exit_code

    print("GATE1_7_STARTUP_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
