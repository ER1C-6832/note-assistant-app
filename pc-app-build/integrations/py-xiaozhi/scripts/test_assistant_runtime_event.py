from __future__ import annotations

import json
import sys
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


SIDECAR_EVENTS_URL = "http://127.0.0.1:17891/api/events"


def post_event(event: dict[str, Any]) -> None:
    data = json.dumps(event, ensure_ascii=False).encode("utf-8")
    request = Request(
        SIDECAR_EVENTS_URL,
        data=data,
        method="POST",
        headers={
            "Content-Type": "application/json; charset=utf-8",
            "Accept": "application/json",
        },
    )

    with urlopen(request, timeout=3.0) as response:
        raw = response.read().decode("utf-8", errors="replace")
        if response.status != 200:
            raise RuntimeError(f"HTTP {response.status}: {raw}")


def main() -> int:
    events = [
        {
            "type": "assistant_transcript",
            "source": "test_assistant_runtime_event",
            "text": "帮我记录一条测试便签",
            "message": "识别文本：帮我记录一条测试便签",
        },
        {
            "type": "assistant_reply",
            "source": "test_assistant_runtime_event",
            "text": "好的，已帮你记录。",
            "message": "助手回复：好的，已帮你记录。",
        },
        {
            "type": "assistant_state",
            "source": "test_assistant_runtime_event",
            "state": "speaking",
            "message": "语音助手正在播报",
        },
    ]

    try:
        for event in events:
            post_event(event)
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        print(f"ERROR: Sidecar returned HTTP {exc.code}: {detail}")
        return 1
    except URLError as exc:
        print(f"ERROR: Cannot connect to Sidecar at {SIDECAR_EVENTS_URL}: {exc}")
        print("Please start scripts\\start_sidecar.bat first.")
        return 1
    except Exception as exc:
        print(f"ERROR: {exc}")
        return 1

    print("OK: test assistant runtime events sent.")
    print("Please check the PC App Voice Assistant panel.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
