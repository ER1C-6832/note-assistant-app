"""
Seed demo notes for local development.

Usage:
    python scripts/seed_demo_data.py
    python scripts/seed_demo_data.py --reset
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
NOTES_API_ROOT = REPO_ROOT / "services" / "notes-api"

sys.path.insert(0, str(NOTES_API_ROOT))

from app.db import SessionLocal, init_db  # noqa: E402
from app.models import Note  # noqa: E402
from app.schemas import NoteCreate  # noqa: E402
from app.services.note_service import create_note  # noqa: E402


DEMO_NOTES = [
    NoteCreate(
        title="联系王总",
        content="明天上午十点联系王总，确认项目报价。",
        tags=["客户", "跟进"],
        source="manual",
    ),
    NoteCreate(
        title="王总项目报价",
        content="和王总确认 27 寸屏幕报价区间，以及演示安排。",
        tags=["客户", "报价"],
        source="manual",
    ),
    NoteCreate(
        title="项目会议纪要",
        content="讨论 PC 端 PySide6 + QML 落地，以及 py-xiaozhi sidecar 接入方式。",
        tags=["会议", "语音助手"],
        source="manual",
    ),
    NoteCreate(
        title="报销材料",
        content="下周提交差旅报销单，需要整理发票。",
        tags=["财务", "待办"],
        source="manual",
    ),
    NoteCreate(
        title="小智服务部署",
        content="后续内网部署 xiaozhi-esp32-server，测试 ASR、LLM、TTS 链路。",
        tags=["技术", "部署"],
        source="manual",
    ),
    NoteCreate(
        title="客户需求确认",
        content="甲方当前优先要求 PC 端落地，同时需要支持方便模糊查找。",
        tags=["客户", "需求"],
        source="manual",
    ),
]


def reset_data(db) -> None:
    """Delete all existing notes."""

    db.query(Note).delete()
    db.commit()


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed demo notes")
    parser.add_argument("--reset", action="store_true", help="Delete existing notes before inserting demo data")
    args = parser.parse_args()

    init_db()

    with SessionLocal() as db:
        if args.reset:
            reset_data(db)

        for payload in DEMO_NOTES:
            create_note(db, payload)

        total = db.query(Note).count()

    print(f"Seed completed. Total notes in database: {total}")
    print(f"Database path: {NOTES_API_ROOT / 'data' / 'notes.db'}")


if __name__ == "__main__":
    main()
