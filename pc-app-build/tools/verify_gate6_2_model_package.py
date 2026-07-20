"""Verify that the installed Gate 6.2 model layout can be resolved and loaded."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP_ROOT = ROOT / "apps" / "notes-pyside"
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

from app.assistant.audio.kws_model_registry import KwsModelRegistry  # noqa: E402
from app.assistant.audio.sherpa_kws import (  # noqa: E402
    KwsBackendError,
    SherpaOnnxKeywordSpotter,
)


def default_models_root() -> Path:
    local = os.environ.get("LOCALAPPDATA", "").strip()
    root = Path(local) / "NoteAssistant" if local else Path.home() / ".note-assistant"
    return root / "models" / "kws"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--models-root", type=Path, default=default_models_root())
    parser.add_argument("--allow-missing", action="store_true")
    args = parser.parse_args()
    registry = KwsModelRegistry(args.models_root)
    snapshot = registry.snapshot()
    report: dict[str, object] = {
        "status": "pending",
        "model_status": snapshot.status,
        "model_summary": snapshot.public_summary,
        "wake_phrase": snapshot.wake_phrase,
        "model_downloaded_at_runtime": False,
        "pcm_persisted": False,
        "payload_persisted": False,
        "secrets_redacted": True,
    }
    if not snapshot.ready:
        allowed = bool(args.allow_missing)
        report["status"] = "model_layout_checked" if allowed else "model_package_failed"
        report["error_code"] = snapshot.error_code
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
        return 0 if allowed else 2
    try:
        spotter = SherpaOnnxKeywordSpotter(registry.resolve())
        spotter.close()
    except KwsBackendError as exc:
        report["status"] = "model_package_failed"
        report["error_code"] = exc.code
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
        return 2
    report["status"] = "gate6_2_model_package_complete"
    report["error_code"] = None
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
