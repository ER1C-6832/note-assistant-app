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

## Seed Demo Data

```bat
python scripts\seed_demo_data.py --reset
```

## Start PC App

```bat
scripts\start_pc_app.bat
```

## Verification

Open these API URLs:

```text
http://127.0.0.1:18080/api/health
http://127.0.0.1:18080/api/notes
http://127.0.0.1:18080/api/notes/search?q=王总&limit=10
```

Then verify in the PC App:

```text
1. Notes are loaded from the Notes API.
2. Creating a note adds it to the list.
3. Editing a note updates the list and detail panel.
4. Deleting a note moves it out of the active list.
5. Searching "王总" shows matching notes.
6. The deleted list shows soft-deleted notes.
```
