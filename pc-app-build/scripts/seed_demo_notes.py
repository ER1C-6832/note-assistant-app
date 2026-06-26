from __future__ import annotations

import json
import os
import sys
from urllib.parse import urlencode
from urllib.request import Request, urlopen

API_BASE = os.getenv("NOTES_API_BASE_URL", "http://127.0.0.1:18080").rstrip("/")
DEMO_TAG = "demo-seed"


DEMO_NOTES = [
    {
        "title": "明天十点项目例会",
        "content": "演示语音新增便签：明天十点和团队确认小智便签 Demo 流程。",
        "tags": [DEMO_TAG, "演示", "会议"],
        "is_pinned": True,
        "source": "imported",
    },
    {
        "title": "周五项目例会",
        "content": "多候选演示 A：周五上午十点，讨论阶段 9 Demo 包装。",
        "tags": [DEMO_TAG, "演示", "会议"],
        "is_pinned": False,
        "source": "imported",
    },
    {
        "title": "周五例会纪要",
        "content": "多候选演示 B：用于测试语音模糊查询后选择第一条、第二条。",
        "tags": [DEMO_TAG, "演示", "会议"],
        "is_pinned": False,
        "source": "imported",
    },
    {
        "title": "临时删除测试便签",
        "content": "防误删演示：删除前必须二次确认，并且必须基于明确 note_id。",
        "tags": [DEMO_TAG, "演示", "删除测试"],
        "is_pinned": False,
        "source": "imported",
    },
    {
        "title": "刚才那条演示便签",
        "content": "上下文指代演示：用户可以说修改刚才那条、删除它。",
        "tags": [DEMO_TAG, "演示", "上下文"],
        "is_pinned": False,
        "source": "imported",
    },
    {
        "title": "待办：准备演示设备",
        "content": "检查麦克风、扬声器、投屏、备用网络和 fallback 演示路径。",
        "tags": [DEMO_TAG, "演示", "待办"],
        "is_pinned": False,
        "source": "imported",
    },
    {
        "title": "Demo 讲解顺序",
        "content": "1. 手动 CRUD；2. 语音新增；3. 模糊查询；4. 多候选确认；5. 删除二次确认。",
        "tags": [DEMO_TAG, "演示", "讲解"],
        "is_pinned": True,
        "source": "imported",
    },
]


def request_json(method: str, path: str, payload: dict | None = None) -> object:
    data = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json; charset=utf-8"

    request = Request(API_BASE + path, data=data, method=method, headers=headers)
    with urlopen(request, timeout=5) as response:
        raw = response.read()
    if not raw:
        return {}
    return json.loads(raw.decode("utf-8"))


def reset_demo_notes() -> int:
    query = urlencode({"include_deleted": "true", "limit": "200"})
    notes = request_json("GET", f"/api/notes?{query}")
    deleted = 0
    if not isinstance(notes, list):
        return 0

    for note in notes:
        if not isinstance(note, dict):
            continue
        tags = note.get("tags") or []
        if DEMO_TAG not in tags:
            continue
        note_id = note.get("id")
        if note_id is None:
            continue
        try:
            request_json("DELETE", f"/api/notes/{int(note_id)}/hard")
            deleted += 1
        except Exception as exc:
            print(f"WARN failed to delete demo note {note_id}: {exc}")
    return deleted


def seed_demo_notes() -> int:
    created = 0
    for item in DEMO_NOTES:
        request_json("POST", "/api/notes", item)
        created += 1
    return created


def main() -> int:
    print(f"Notes API: {API_BASE}")
    try:
        deleted = reset_demo_notes()
        created = seed_demo_notes()
    except Exception as exc:
        print(f"ERROR seed demo notes failed: {exc}")
        print("Make sure Notes API is running on http://127.0.0.1:18080")
        return 1

    print(f"OK deleted old demo notes: {deleted}")
    print(f"OK created demo notes: {created}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
