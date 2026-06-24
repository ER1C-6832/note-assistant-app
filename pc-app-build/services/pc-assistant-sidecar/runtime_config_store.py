from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from config import SidecarConfig, load_config

RUNTIME_KEYS = [
    "PY_XIAOZHI_ROOT",
    "PY_XIAOZHI_PYTHON",
    "PY_XIAOZHI_RUNTIME_MODE",
    "PY_XIAOZHI_START_MODE",
    "PY_XIAOZHI_WINDOW_MODE",
    "PY_XIAOZHI_AUTO_START",
    "PY_XIAOZHI_SKIP_ACTIVATION",
    "PY_XIAOZHI_MODE",
]

ALLOWED_RUNTIME_MODES = ["headless", "gui", "cli"]
ALLOWED_START_MODES = ["normal", "minimized", "hidden", "debug"]
ALLOWED_WINDOW_MODES = ["normal", "minimized", "hidden"]


def _normalize_runtime_mode(value: str) -> str:
    mode = (value or "").strip().lower()
    if mode in {"background", "service", "nogui", "no_gui"}:
        return "headless"
    if mode in ALLOWED_RUNTIME_MODES:
        return mode
    return "headless"


def _normalize_start_mode(value: str) -> str:
    mode = (value or "").strip().lower()
    if mode in {"min", "minimize"}:
        return "minimized"
    if mode in {"hide", "cli", "no_window", "nowindow"}:
        return "hidden"
    if mode in ALLOWED_START_MODES:
        return mode
    return "minimized"


def _normalize_window_mode(value: str) -> str:
    mode = (value or "").strip().lower()
    if mode in {"min", "minimize"}:
        return "minimized"
    if mode in {"hide", "cli", "no_window", "nowindow"}:
        return "hidden"
    if mode in ALLOWED_WINDOW_MODES:
        return mode
    return "minimized"


def _as_bool_text(value: Any) -> str:
    if isinstance(value, bool):
        return "1" if value else "0"
    normalized = str(value or "").strip().lower()
    return "1" if normalized in {"1", "true", "yes", "y", "on", "是"} else "0"


def get_runtime_config(config: SidecarConfig | None = None) -> dict[str, Any]:
    config = config or load_config()
    return {
        "type": "runtime_config",
        "env_path": str(config.env_path),
        "settings": {
            "py_xiaozhi_root": str(config.py_xiaozhi_root),
            "py_xiaozhi_python": str(config.py_xiaozhi_python or ""),
            "py_xiaozhi_runtime_mode": config.py_xiaozhi_runtime_mode,
            "py_xiaozhi_start_mode": config.py_xiaozhi_start_mode,
            "py_xiaozhi_window_mode": config.py_xiaozhi_window_mode,
            "py_xiaozhi_auto_start": bool(config.py_xiaozhi_auto_start),
            "py_xiaozhi_skip_activation": bool(config.py_xiaozhi_skip_activation),
            "py_xiaozhi_protocol": config.py_xiaozhi_protocol,
        },
        "allowed_runtime_modes": ALLOWED_RUNTIME_MODES,
        "allowed_start_modes": ALLOWED_START_MODES,
        "allowed_window_modes": ALLOWED_WINDOW_MODES,
    }


def save_runtime_config(payload: dict[str, Any], config: SidecarConfig | None = None) -> dict[str, Any]:
    config = config or load_config()

    root = str(payload.get("py_xiaozhi_root") or payload.get("root") or config.py_xiaozhi_root).strip()
    python = str(payload.get("py_xiaozhi_python") or payload.get("python") or config.py_xiaozhi_python or "").strip()
    runtime_mode = _normalize_runtime_mode(str(payload.get("py_xiaozhi_runtime_mode") or payload.get("runtime_mode") or config.py_xiaozhi_runtime_mode))
    start_mode = _normalize_start_mode(str(payload.get("py_xiaozhi_start_mode") or payload.get("start_mode") or config.py_xiaozhi_start_mode))
    window_mode = _normalize_window_mode(str(payload.get("py_xiaozhi_window_mode") or payload.get("window_mode") or config.py_xiaozhi_window_mode))
    auto_start = _as_bool_text(payload.get("py_xiaozhi_auto_start", payload.get("auto_start", config.py_xiaozhi_auto_start)))
    skip_activation = _as_bool_text(payload.get("py_xiaozhi_skip_activation", payload.get("skip_activation", config.py_xiaozhi_skip_activation)))

    updates = {
        "PY_XIAOZHI_ROOT": root,
        "PY_XIAOZHI_PYTHON": python,
        "PY_XIAOZHI_RUNTIME_MODE": runtime_mode,
        "PY_XIAOZHI_START_MODE": start_mode,
        "PY_XIAOZHI_WINDOW_MODE": window_mode,
        "PY_XIAOZHI_AUTO_START": auto_start,
        "PY_XIAOZHI_SKIP_ACTIVATION": skip_activation,
    }

    updates["PY_XIAOZHI_MODE"] = runtime_mode

    _update_env_file(config.env_path, updates)
    for key, value in updates.items():
        os.environ[key] = value

    fresh = load_config()
    return {
        "ok": True,
        "type": "runtime_config_saved",
        "message": "py-xiaozhi 运行时配置已保存到 .env",
        "config": get_runtime_config(fresh),
    }


def _update_env_file(env_path: Path, updates: dict[str, str]) -> None:
    env_path.parent.mkdir(parents=True, exist_ok=True)

    lines = env_path.read_text(encoding="utf-8").splitlines() if env_path.exists() else []
    seen: set[str] = set()
    output: list[str] = []

    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in line:
            output.append(line)
            continue

        key, _value = line.split("=", 1)
        key = key.strip()
        if key in updates:
            output.append(f"{key}={updates[key]}")
            seen.add(key)
        else:
            output.append(line)

    missing = [key for key in RUNTIME_KEYS if key in updates and key not in seen]
    if missing:
        if output and output[-1].strip():
            output.append("")
        output.append("# Phase 8.0.1 safe py-xiaozhi runtime settings")
        for key in missing:
            output.append(f"{key}={updates[key]}")

    env_path.write_text("\n".join(output).rstrip() + "\n", encoding="utf-8")
