from __future__ import annotations

import json
import sys
import time
from urllib.request import Request, urlopen


URL = "http://127.0.0.1:17891/api/control"


def post(command: str, mode: str = "manual") -> None:
    payload = {
        "command": command,
        "mode": mode,
        "source": "verify_voice_control_bridge",
    }
    req = Request(
        URL,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        method="POST",
        headers={"Content-Type": "application/json; charset=utf-8"},
    )
    with urlopen(req, timeout=3) as response:
        print(response.read().decode("utf-8", errors="replace"))


def main() -> int:
    print("Sending start_listen...")
    post("start_listen")
    time.sleep(1.5)

    print("Sending stop_listen...")
    post("stop_listen")
    time.sleep(0.8)

    print("Sending abort...")
    post("abort")

    print("OK: voice control bridge verification commands sent.")
    print("Check py-xiaozhi logs for assistant_control_received / command execution.")
    print("Check Sidecar logs for assistant_control and assistant_control_result.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
