from __future__ import annotations

import asyncio
import json
import logging
import sys
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

CURRENT_DIR = Path(__file__).resolve().parent
if str(CURRENT_DIR) not in sys.path:
    sys.path.insert(0, str(CURRENT_DIR))

from app_ws_server import SidecarWebSocketServer
from config import SidecarConfig, load_config
from health_server import start_health_server

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s [%(name)s] %(message)s",
)

logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("websockets.server").setLevel(logging.WARNING)

logger = logging.getLogger("sidecar")


def _existing_sidecar_is_healthy(config: SidecarConfig) -> bool:
    try:
        with urlopen(config.health_url, timeout=1.0) as response:
            if response.status != 200:
                return False
            raw = response.read().decode("utf-8", errors="replace")
            payload = json.loads(raw)
            return bool(payload.get("ok"))
    except Exception:
        return False


async def main() -> None:
    config = load_config()

    if _existing_sidecar_is_healthy(config):
        logger.info("PC Assistant Sidecar is already running: %s", config.health_url)
        logger.info("Skip starting a duplicate Sidecar process.")
        return

    logger.info("PC Assistant Sidecar starting...")
    logger.info("PC build root: %s", config.pc_build_root)
    logger.info("Notes API: %s", config.notes_api_base_url)
    logger.info("py-xiaozhi root: %s", config.py_xiaozhi_root)
    logger.info("WebSocket: %s", config.ws_url)
    logger.info("Health: %s", config.health_url)

    ws_server = SidecarWebSocketServer(config)

    try:
        await asyncio.gather(
            ws_server.start(),
            start_health_server(config),
        )
    except OSError as exc:
        if getattr(exc, "winerror", None) == 10048 or getattr(exc, "errno", None) == 10048:
            logger.warning("Sidecar port is already in use. Another Sidecar is probably running.")
            logger.warning("Check: %s", config.health_url)
            return
        raise


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("PC Assistant Sidecar stopped.")
