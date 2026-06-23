from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path

CURRENT_DIR = Path(__file__).resolve().parent
if str(CURRENT_DIR) not in sys.path:
    sys.path.insert(0, str(CURRENT_DIR))

from app_ws_server import SidecarWebSocketServer
from config import load_config
from health_server import start_health_server

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s [%(name)s] %(message)s",
)

# Reduce noisy polling logs. Sidecar still logs startup, client connect/disconnect,
# and meaningful bridge events.
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("websockets.server").setLevel(logging.WARNING)

logger = logging.getLogger("sidecar")


async def main() -> None:
    config = load_config()

    logger.info("PC Assistant Sidecar starting...")
    logger.info("PC build root: %s", config.pc_build_root)
    logger.info("Notes API: %s", config.notes_api_base_url)
    logger.info("py-xiaozhi root: %s", config.py_xiaozhi_root)
    logger.info("WebSocket: %s", config.ws_url)
    logger.info("Health: %s", config.health_url)

    ws_server = SidecarWebSocketServer(config)

    await asyncio.gather(
        ws_server.start(),
        start_health_server(config),
    )


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("PC Assistant Sidecar stopped.")
