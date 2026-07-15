"""Load the Gate 2.6 QML surface offscreen and verify bounded shutdown."""

from __future__ import annotations

import asyncio
import json
import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

APP_ROOT = Path(__file__).resolve().parents[1] / "apps" / "notes-pyside"
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

from PySide6.QtGui import QGuiApplication  # noqa: E402

from app.bootstrap import create_application_context, create_event_loop  # noqa: E402


async def _settle() -> None:
    await asyncio.sleep(0.1)


def main() -> int:
    app = QGuiApplication.instance() or QGuiApplication(["gate2_6_ui_smoke"])
    loop = create_event_loop(app)
    asyncio.set_event_loop(loop)
    context = None

    try:
        with tempfile.TemporaryDirectory(prefix="note-assistant-gate2-6-") as data_root:
            context = create_application_context(
                app,
                data_root=data_root,
                worktree_root=Path(__file__).resolve().parents[2],
                migration_env={},
            )
            with loop:
                loop.run_until_complete(_settle())
                roots = context.engine.rootObjects()
                verified = (
                    len(roots) == 1
                    and context.assistant_view_model is not None
                    and context.assistant_controller.event_pump_running
                    and context.notes_runtime.database_engine is not None
                )
                result = {
                    "assistant_context_property": context.assistant_view_model is not None,
                    "assistant_event_pump_running": context.assistant_controller.event_pump_running,
                    "qml_root_count": len(roots),
                    "runtime_mode": context.assistant_view_model.runtimeMode,
                    "status": "ui_smoke_verified" if verified else "failed",
                }
                print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
                loop.run_until_complete(context.lifecycle.shutdown(timeout_seconds=10.0))
                return 0 if verified else 1
    except Exception as exc:
        print(
            json.dumps(
                {
                    "error": f"{type(exc).__name__}: {exc}",
                    "status": "failed",
                },
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
        )
        if context is not None and not context.lifecycle.is_closed:
            try:
                with loop:
                    loop.run_until_complete(context.lifecycle.shutdown(timeout_seconds=10.0))
            except Exception:
                pass
        return 1
    finally:
        asyncio.set_event_loop(None)


if __name__ == "__main__":
    raise SystemExit(main())
