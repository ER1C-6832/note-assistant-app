"""Verify the Gate 3.1 floating shell, position persistence, and bounded shutdown."""

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

from PySide6.QtCore import QObject  # noqa: E402
from PySide6.QtGui import QGuiApplication  # noqa: E402

from app.bootstrap import create_application_context, create_event_loop  # noqa: E402


async def _settle(seconds: float = 0.15) -> None:
    await asyncio.sleep(seconds)


def main() -> int:
    app = QGuiApplication.instance() or QGuiApplication(["gate3_1_ui_shell"])
    loop = create_event_loop(app)
    asyncio.set_event_loop(loop)
    context = None

    try:
        with tempfile.TemporaryDirectory(prefix="note-assistant-gate3-1-") as data_root:
            context = create_application_context(
                app,
                data_root=data_root,
                worktree_root=Path(__file__).resolve().parents[2],
                migration_env={},
            )
            with loop:
                loop.run_until_complete(_settle())
                roots = context.engine.rootObjects()
                root = roots[0] if roots else None
                overlay = root.findChild(QObject, "assistantOverlay") if root is not None else None
                launcher = (
                    root.findChild(QObject, "assistantLauncher") if root is not None else None
                )
                page_loader = root.findChild(QObject, "pageLoader") if root is not None else None
                floating = (
                    root.findChild(QObject, "assistantFloatingPanel") if root is not None else None
                )
                settings_button = (
                    root.findChild(QObject, "assistantSettingsButton") if root is not None else None
                )
                settings_page = (
                    root.findChild(QObject, "assistantSettingsPage") if root is not None else None
                )
                voice_settings = (
                    root.findChild(QObject, "assistantVoiceModeSettings")
                    if root is not None
                    else None
                )
                outer_ring = (
                    root.findChild(QObject, "assistantOuterRing") if root is not None else None
                )

                width_before = float(page_loader.property("width")) if page_loader else -1.0
                collapsed_by_default = bool(overlay and not overlay.property("expanded"))
                if overlay is not None:
                    overlay.setProperty("expanded", True)
                loop.run_until_complete(_settle())
                width_after = float(page_loader.property("width")) if page_loader else -2.0
                settings_dedicated = bool(
                    floating
                    and settings_button
                    and settings_page
                    and voice_settings
                    and not floating.property("settingsOpen")
                )
                if floating is not None:
                    floating.setProperty("settingsOpen", True)
                loop.run_until_complete(_settle())
                settings_page_opened = bool(
                    floating
                    and floating.property("settingsOpen")
                    and settings_page
                    and settings_page.property("visible")
                    and voice_settings
                    and voice_settings.property("visible")
                )

                context.assistant_view_model.requestLauncherPosition(0.31, 0.67)
                loop.run_until_complete(_settle(0.45))
                saved = context.assistant_runtime.preferences_store.load()

                runtime_was_running = context.assistant_controller.event_pump_running
                loop.run_until_complete(context.lifecycle.shutdown(timeout_seconds=10.0))
                no_pending_runtime_tasks = all(
                    (
                        context.assistant_controller.closed,
                        not context.assistant_controller.event_pump_running,
                        not context.assistant_controller.reconnect_timer_running,
                        context.assistant_controller.pending_effect_count == 0,
                    )
                )
                verified = all(
                    (
                        len(roots) == 1,
                        overlay is not None,
                        launcher is not None,
                        floating is not None,
                        settings_button is not None,
                        settings_page is not None,
                        voice_settings is not None,
                        outer_ring is not None,
                        page_loader is not None,
                        collapsed_by_default,
                        settings_dedicated,
                        settings_page_opened,
                        abs(width_before - width_after) < 0.5,
                        abs(saved.launcher_x_ratio - 0.31) < 0.001,
                        abs(saved.launcher_y_ratio - 0.67) < 0.001,
                        runtime_was_running,
                        no_pending_runtime_tasks,
                    )
                )
                result = {
                    "assistant_overlay_present": overlay is not None,
                    "collapsed_by_default": collapsed_by_default,
                    "floating_panel_present": floating is not None,
                    "launcher_present": launcher is not None,
                    "outer_ring_inset": outer_ring is not None,
                    "settings_button_present": settings_button is not None,
                    "settings_dedicated_page": settings_dedicated,
                    "settings_page_opened": settings_page_opened,
                    "launcher_position_persisted": (
                        abs(saved.launcher_x_ratio - 0.31) < 0.001
                        and abs(saved.launcher_y_ratio - 0.67) < 0.001
                    ),
                    "no_pending_runtime_tasks": no_pending_runtime_tasks,
                    "notes_width_after_expand": width_after,
                    "notes_width_before_expand": width_before,
                    "notes_width_unchanged": abs(width_before - width_after) < 0.5,
                    "qml_root_count": len(roots),
                    "runtime_was_running": runtime_was_running,
                    "status": "gate3_1_ui_shell_verified" if verified else "failed",
                }
                print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
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
