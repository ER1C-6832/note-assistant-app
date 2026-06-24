from __future__ import annotations

import json
from urllib.request import urlopen

BASE = "http://127.0.0.1:17891"


def get(path: str) -> dict:
    with urlopen(BASE + path, timeout=8) as response:
        return json.loads(response.read().decode("utf-8", errors="replace"))


def main() -> int:
    for title, path in [
        ("Sidecar Health", "/api/health"),
        ("Runtime Config", "/api/runtime/config"),
        ("py-xiaozhi Status", "/api/runtime/py-xiaozhi/status"),
    ]:
        print("\n=== " + title + " ===")
        print(json.dumps(get(path), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
