from __future__ import annotations

import json
from urllib.request import Request, urlopen


BASE = "http://127.0.0.1:17891"


def get(path: str) -> dict:
    with urlopen(BASE + path, timeout=5) as response:
        return json.loads(response.read().decode("utf-8", errors="replace"))


def post(path: str, payload: dict | None = None) -> dict:
    data = json.dumps(payload or {}, ensure_ascii=False).encode("utf-8")
    req = Request(
        BASE + path,
        data=data,
        method="POST",
        headers={"Content-Type": "application/json; charset=utf-8"},
    )
    with urlopen(req, timeout=12) as response:
        return json.loads(response.read().decode("utf-8", errors="replace"))


def main() -> int:
    print("Checking Sidecar health...")
    health = get("/api/health")
    print(json.dumps(health, ensure_ascii=False, indent=2))

    print("\nChecking py-xiaozhi runtime status...")
    status = get("/api/runtime/py-xiaozhi/status")
    print(json.dumps(status, ensure_ascii=False, indent=2))

    print("\nRequesting py-xiaozhi start...")
    result = post("/api/runtime/py-xiaozhi/start", {"mode": "minimized"})
    print(json.dumps(result, ensure_ascii=False, indent=2))

    print("\nDone. Check PC App settings page and py-xiaozhi logs.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
