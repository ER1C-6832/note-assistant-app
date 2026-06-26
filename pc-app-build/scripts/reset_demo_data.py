from __future__ import annotations

import json
import os
from urllib.parse import urlencode
from urllib.request import Request, urlopen

API_BASE = os.getenv("NOTES_API_BASE_URL", "http://127.0.0.1:18080").rstrip("/")
DEMO_TAG = "demo-seed"


def request_json(method: str, path: str) -> object:
    request = Request(API_BASE + path, method=method, headers={"Accept": "application/json"})
    with urlopen(request, timeout=5) as response:
        raw = response.read()
    return json.loads(raw.decode("utf-8")) if raw else {}


def main() -> int:
    print(f"Notes API: {API_BASE}")
    try:
        query = urlencode({"include_deleted": "true", "limit": "200"})
        notes = request_json("GET", f"/api/notes?{query}")
        deleted = 0
        if isinstance(notes, list):
            for note in notes:
                if not isinstance(note, dict):
                    continue
                if DEMO_TAG not in (note.get("tags") or []):
                    continue
                note_id = note.get("id")
                if note_id is None:
                    continue
                request_json("DELETE", f"/api/notes/{int(note_id)}/hard")
                deleted += 1
        print(f"OK deleted demo notes: {deleted}")
        return 0
    except Exception as exc:
        print(f"ERROR reset demo notes failed: {exc}")
        print("Make sure Notes API is running on http://127.0.0.1:18080")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
