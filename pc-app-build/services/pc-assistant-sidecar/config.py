from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _pc_build_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _load_env_file(path: Path, *, override: bool = True) -> None:
    if not path.exists():
        return

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()

        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")

        if key and (override or key not in os.environ):
            os.environ[key] = value


@dataclass(frozen=True)
class SidecarConfig:
    pc_build_root: Path
    env_path: Path
    notes_api_base_url: str
    py_xiaozhi_root: Path
    py_xiaozhi_python: str
    py_xiaozhi_protocol: str
    py_xiaozhi_log_path: Path | None
    py_xiaozhi_start_mode: str
    py_xiaozhi_window_mode: str
    py_xiaozhi_auto_start: bool
    ws_host: str
    ws_port: int
    health_host: str
    health_port: int
    poll_interval_seconds: float
    log_poll_interval_seconds: float

    @property
    def ws_url(self) -> str:
        return f"ws://{self.ws_host}:{self.ws_port}/assistant"

    @property
    def health_url(self) -> str:
        return f"http://{self.health_host}:{self.health_port}/api/health"


def _as_bool(value: str, default: bool = False) -> bool:
    if value is None:
        return default
    normalized = str(value).strip().lower()
    if normalized in {"1", "true", "yes", "y", "on", "是"}:
        return True
    if normalized in {"0", "false", "no", "n", "off", "否"}:
        return False
    return default


def _normalize_mode(value: str, default: str = "minimized") -> str:
    mode = (value or "").strip().lower()

    aliases = {
        "min": "minimized",
        "minimize": "minimized",
        "minimized": "minimized",
        "hide": "hidden",
        "hidden": "hidden",
        "no_window": "hidden",
        "nowindow": "hidden",
        "normal": "normal",
        "gui": "normal",
        "debug": "debug",
        # Legacy env from previous packages. It means the user wants a less visible runtime.
        "cli": "hidden",
    }

    return aliases.get(mode, default)


def _default_py_xiaozhi_log_path() -> Path | None:
    explicit = os.getenv("PY_XIAOZHI_LOG_PATH", "").strip()
    if explicit:
        return Path(explicit)

    local_app_data = os.getenv("LOCALAPPDATA", "").strip()
    candidates: list[Path] = []

    if local_app_data:
        candidates.extend([
            Path(local_app_data) / "py-xiaozhi" / "py-xiaozhi" / "logs" / "app.log",
            Path(local_app_data) / "py-xiaozhi" / "logs" / "app.log",
        ])

    for candidate in candidates:
        if candidate.exists():
            return candidate

    return candidates[0] if candidates else None


def load_config() -> SidecarConfig:
    pc_root = _pc_build_root()
    env_path = pc_root / ".env"
    _load_env_file(env_path, override=True)

    py_root = Path(
        os.getenv("PY_XIAOZHI_ROOT", r"C:\yuyinzhushou\py-xiaozhi-tao")
    )

    legacy_mode = os.getenv("PY_XIAOZHI_MODE", "").strip()
    start_mode = _normalize_mode(
        os.getenv("PY_XIAOZHI_START_MODE", "").strip() or legacy_mode,
        default="minimized",
    )
    window_mode = _normalize_mode(
        os.getenv("PY_XIAOZHI_WINDOW_MODE", "").strip() or start_mode,
        default=start_mode,
    )

    return SidecarConfig(
        pc_build_root=pc_root,
        env_path=env_path,
        notes_api_base_url=os.getenv(
            "NOTES_API_BASE_URL",
            f"http://{os.getenv('NOTES_API_HOST', '127.0.0.1')}:{os.getenv('NOTES_API_PORT', '18080')}",
        ).rstrip("/"),
        py_xiaozhi_root=py_root,
        py_xiaozhi_python=os.getenv("PY_XIAOZHI_PYTHON", ""),
        py_xiaozhi_protocol=os.getenv("PY_XIAOZHI_PROTOCOL", "websocket"),
        py_xiaozhi_log_path=_default_py_xiaozhi_log_path(),
        py_xiaozhi_start_mode=start_mode,
        py_xiaozhi_window_mode=window_mode,
        py_xiaozhi_auto_start=_as_bool(os.getenv("PY_XIAOZHI_AUTO_START", "0"), default=False),
        ws_host=os.getenv("SIDECAR_HOST", "127.0.0.1"),
        ws_port=int(os.getenv("SIDECAR_PORT", os.getenv("SIDECAR_WS_PORT", "17890"))),
        health_host=os.getenv("SIDECAR_HEALTH_HOST", "127.0.0.1"),
        health_port=int(os.getenv("SIDECAR_HEALTH_PORT", "17891")),
        poll_interval_seconds=float(os.getenv("SIDECAR_NOTES_POLL_SECONDS", "2.0")),
        log_poll_interval_seconds=float(os.getenv("SIDECAR_LOG_POLL_SECONDS", "1.0")),
    )
