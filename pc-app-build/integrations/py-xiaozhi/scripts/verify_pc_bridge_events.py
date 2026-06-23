from __future__ import annotations

import json
from urllib.request import Request, urlopen


URL = "http://127.0.0.1:17891/api/events"


def post(payload: dict) -> None:
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = Request(
        URL,
        data=data,
        method="POST",
        headers={"Content-Type": "application/json; charset=utf-8"},
    )
    with urlopen(req, timeout=3) as response:
        print(response.read().decode("utf-8", errors="replace"))


def main() -> int:
    post({
        "type": "assistant_status",
        "source": "verify_pc_bridge_events",
        "status": "listening",
        "message": "5.4 验证事件：语音助手正在聆听",
    })
    post({
        "type": "assistant_transcript",
        "source": "verify_pc_bridge_events",
        "text": "帮我新增一条五点四验证便签",
        "message": "识别文本：帮我新增一条五点四验证便签",
    })
    post({
        "type": "assistant_reply",
        "source": "verify_pc_bridge_events",
        "text": "好的，已收到 5.4 验证事件。",
        "message": "助手回复：好的，已收到 5.4 验证事件。",
    })
    print("OK: verify events sent.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
