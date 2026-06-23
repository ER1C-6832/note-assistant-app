from __future__ import annotations

import json
import os
import sys
from pathlib import Path

TOOLS_DIR = Path(__file__).resolve().parents[1] / "mcp-tools" / "notes"
sys.path.insert(0, str(TOOLS_DIR))

from notes_api_client import NotesApiClient  # noqa: E402


def main() -> int:
    client = NotesApiClient(os.getenv("NOTES_API_BASE_URL", "http://127.0.0.1:18080"))
    created = client.create_note(
        title="Phase 5.0.1 MCP direct test",
        content="这是一条用于验证 notes MCP API 链路的测试便签。",
        tags=["测试", "待办"],
    )
    print("CREATE OK")
    print(json.dumps(created, ensure_ascii=False, indent=2))
    result = client.search_notes("Phase 5.0.1", limit=5)
    print("SEARCH OK")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
