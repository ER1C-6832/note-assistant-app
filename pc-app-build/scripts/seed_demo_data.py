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
        content="明天上午十点联系王总，确认屏幕样机报价和交付时间。",
        tags=["客户", "跟进"],
        source="manual",
    ),
    NoteCreate(
        title="王总屏幕报价",
        content="整理 27 寸显示屏、32 寸显示屏的报价区间，重点标注质保和批量采购折扣。",
        tags=["客户", "报价", "屏幕"],
        source="manual",
    ),
    NoteCreate(
        title="27 寸屏幕样机",
        content="检查样机亮度、色温、边框间隙和支架稳定性，拍照留档后发给客户。",
        tags=["屏幕", "样机"],
        is_pinned=True,
        source="manual",
    ),
    NoteCreate(
        title="游戏手柄测试",
        content="测试蓝牙连接、摇杆漂移、按键回弹和震动反馈，记录异常批次。",
        tags=["游戏手柄", "测试"],
        source="manual",
    ),
    NoteCreate(
        title="手柄包装清单",
        content="确认游戏手柄包装内含 USB-C 线、说明书、保修卡和防滑贴。",
        tags=["游戏手柄", "包装"],
        source="manual",
    ),
    NoteCreate(
        title="客户样品寄送",
        content="本周五前寄出屏幕样机和两只游戏手柄，快递单号同步给客户。",
        tags=["客户", "待办"],
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
