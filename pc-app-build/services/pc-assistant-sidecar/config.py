from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _pc_build_root() -> Path:
    # services/pc-assistant-sidecar/config.py -> pc-app-build
    return Path(__file__).resolve().parents[2]


def _load_env_file(path: Path) -> None:
    if not path.exists():
        return

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()

        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")

        if key and key not in os.environ:
            os.environ[key] = value


@dataclass(frozen=True)
class SidecarConfig:
    pc_build_root: Path
    notes_api_base_url: str
    py_xiaozhi_root: Path
    py_xiaozhi_python: str
    py_xiaozhi_protocol: str
    ws_host: str
    ws_port: int
    health_host: str
    health_port: int
    poll_interval_seconds: float

    @property
    def ws_url(self) -> str:
        return f"ws://{self.ws_host}:{self.ws_port}/assistant"

    @property
    def health_url(self) -> str:
        return f"http://{self.health_host}:{self.health_port}/api/health"


def load_config() -> SidecarConfig:
    pc_root = _pc_build_root()
    _load_env_file(pc_root / ".env")

    py_root = Path(
        os.getenv("PY_XIAOZHI_ROOT", r"C:\yuyinzhushou\py-xiaozhi-tao")
    )

    return SidecarConfig(
        pc_build_root=pc_root,
        notes_api_base_url=os.getenv(
            "NOTES_API_BASE_URL",
            f"http://{os.getenv('NOTES_API_HOST', '127.0.0.1')}:{os.getenv('NOTES_API_PORT', '18080')}",
        ).rstrip("/"),
        py_xiaozhi_root=py_root,
        py_xiaozhi_python=os.getenv("PY_XIAOZHI_PYTHON", ""),
        py_xiaozhi_protocol=os.getenv("PY_XIAOZHI_PROTOCOL", "websocket"),
        ws_host=os.getenv("SIDECAR_HOST", "127.0.0.1"),
        ws_port=int(os.getenv("SIDECAR_PORT", os.getenv("SIDECAR_WS_PORT", "17890"))),
        health_host=os.getenv("SIDECAR_HEALTH_HOST", "127.0.0.1"),
        health_port=int(os.getenv("SIDECAR_HEALTH_PORT", "17891")),
        poll_interval_seconds=float(os.getenv("SIDECAR_NOTES_POLL_SECONDS", "2.0")),
    )
