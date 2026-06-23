"""Remove old development demo notes and insert product-facing notes without resetting the whole DB."""
from __future__ import annotations
import sys
from pathlib import Path
REPO_ROOT = Path(__file__).resolve().parents[1]
NOTES_API_ROOT = REPO_ROOT / "services" / "notes-api"
sys.path.insert(0, str(NOTES_API_ROOT))
from app.db import SessionLocal, init_db  # noqa: E402
from app.models import Note  # noqa: E402
from app.schemas import NoteCreate  # noqa: E402
from app.services.note_service import create_note  # noqa: E402
OLD_DEMO_TITLES = {"项目会议纪要", "小智服务部署"}
PRODUCT_NOTES = [
    NoteCreate(title="27 寸屏幕样机", content="检查样机亮度、色温、边框间隙和支架稳定性，拍照留档后发给客户。", tags=["屏幕", "样机"], is_pinned=True, source="manual"),
    NoteCreate(title="游戏手柄测试", content="测试蓝牙连接、摇杆漂移、按键回弹和震动反馈，记录异常批次。", tags=["游戏手柄", "测试"], source="manual"),
    NoteCreate(title="手柄包装清单", content="确认游戏手柄包装内含 USB-C 线、说明书、保修卡和防滑贴。", tags=["游戏手柄", "包装"], source="manual"),
]

def main() -> None:
    init_db()
    with SessionLocal() as db:
        removed = 0
        for title in OLD_DEMO_TITLES:
            for row in db.query(Note).filter(Note.title == title).all():
                db.delete(row); removed += 1
        db.commit()
        existing = {row.title for row in db.query(Note).all()}
        inserted = 0
        for payload in PRODUCT_NOTES:
            if payload.title not in existing:
                create_note(db, payload); inserted += 1
        total = db.query(Note).count()
    print(f"Removed old demo notes: {removed}")
    print(f"Inserted product demo notes: {inserted}")
    print(f"Total notes in database: {total}")

if __name__ == "__main__": main()
