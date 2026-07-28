"""PySide6 desktop application entry point."""

from __future__ import annotations

import faulthandler
import os
import sys
import threading
import traceback
from datetime import datetime
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parent
_CRASH_LOG = None


def _install_crash_logging() -> None:
    """Persist Python and native crash evidence before importing Qt/audio code."""

    global _CRASH_LOG

    local_app_data = os.environ.get("LOCALAPPDATA", "").strip()
    data_root = Path(local_app_data) / "NoteAssistant" if local_app_data else Path.home() / ".note-assistant"
    logs_dir = data_root / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    log_path = logs_dir / "pc-runtime-crash.log"
    _CRASH_LOG = log_path.open("a", encoding="utf-8", buffering=1)
    _CRASH_LOG.write(
        f"\n[{datetime.now().astimezone().isoformat()}] "
        f"process_start pid={os.getpid()} python={sys.version.split()[0]}\n"
    )
    faulthandler.enable(file=_CRASH_LOG, all_threads=True)

    previous_sys_hook = sys.excepthook

    def _sys_hook(exc_type, exc_value, exc_traceback) -> None:
        _CRASH_LOG.write(
            f"[{datetime.now().astimezone().isoformat()}] unhandled_main_thread_exception\n"
        )
        traceback.print_exception(exc_type, exc_value, exc_traceback, file=_CRASH_LOG)
        _CRASH_LOG.flush()
        previous_sys_hook(exc_type, exc_value, exc_traceback)

    sys.excepthook = _sys_hook

    previous_thread_hook = threading.excepthook

    def _thread_hook(args: threading.ExceptHookArgs) -> None:
        _CRASH_LOG.write(
            f"[{datetime.now().astimezone().isoformat()}] "
            f"unhandled_thread_exception thread={args.thread.name if args.thread else 'unknown'}\n"
        )
        traceback.print_exception(
            args.exc_type,
            args.exc_value,
            args.exc_traceback,
            file=_CRASH_LOG,
        )
        _CRASH_LOG.flush()
        previous_thread_hook(args)

    threading.excepthook = _thread_hook


_install_crash_logging()

if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

from app import run_app  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(run_app())
