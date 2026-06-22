# PC Setup Guide

## Prerequisites

- Python 3.10 or later
- Git

## Installation

1. Clone the repository:

```bat
git clone https://github.com/ER1C-6832/note-assistant-app.git
cd note-assistant-app\pc-app-build
```

2. Create and activate a virtual environment:

```bat
python -m venv venv
venv\Scripts\activate
```

3. Install dependencies:

```bat
pip install -r requirements.txt
```

4. Configure environment:

```bat
copy .env.example .env
```

## Running the Notes API

```bat
scripts\start_notes_api.bat
```

Or manually:

```bat
cd services\notes-api
python -m uvicorn app.main:app --host 127.0.0.1 --port 18080 --reload
```

## Seed Demo Data

```bat
python scripts\seed_demo_data.py --reset
```

## Running the PC App

```bat
scripts\start_pc_app.bat
```

Phase 3 PC App behavior:

```text
1. Opens a PySide6 + QML desktop window.
2. Shows the bright card-style note UI.
3. Supports static page switching between home, create, edit, delete, search,
   assistant states, and settings.
4. Uses mock QML note data only.
```

## Verification

1. Visit `http://127.0.0.1:18080/api/health`.
2. Visit `http://127.0.0.1:18080/api/notes`.
3. Visit `http://127.0.0.1:18080/api/notes/search?q=王总&limit=10`.
4. Run `scripts\start_pc_app.bat`.
5. Confirm the PC App window appears.
6. Click:
   - 新建便签
   - 编辑
   - 删除
   - 搜索
   - 语音助手
   - 设置

## Running All Components

```bat
scripts\start_all.bat
```

The Sidecar remains a skeleton until Phase 5.
