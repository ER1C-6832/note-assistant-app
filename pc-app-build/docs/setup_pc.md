# PC Setup Guide

## Prerequisites

- Python 3.10 or later
- Git

## Installation

```bat
git clone https://github.com/ER1C-6832/note-assistant-app.git
cd note-assistant-app\pc-app-build
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

## Start Notes API

```bat
scripts\start_notes_api.bat
```

## Seed Product Demo Data

```bat
python scripts\seed_demo_data.py --reset
```

The demo notes are product-facing examples such as screen samples, quotes, game
controller testing, packaging, and customer delivery.

## Start PC App

```bat
scripts\start_pc_app.bat
```

## Verification

```text
1. Notes are loaded from the Notes API.
2. Demo notes do not contain development/project implementation content.
3. Clicking 置顶 on a note pins it.
4. The 置顶 category shows pinned notes.
5. Clicking 取消置顶 removes it from pinned notes.
6. Deleting a note moves it to 已删除.
7. Clicking 已删除 shows deleted notes.
8. Clicking 还原 restores the deleted note to the normal list.
```
