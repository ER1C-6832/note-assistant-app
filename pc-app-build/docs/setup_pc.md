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

Edit `.env` if custom ports or paths are needed. The defaults are suitable for
local development.

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

With the virtual environment activated:

```bat
python scripts\seed_demo_data.py --reset
```

This initializes `services\notes-api\data\notes.db` and inserts demo notes.

## Verification

1. Visit `http://127.0.0.1:18080/api/health`.
2. Visit `http://127.0.0.1:18080/api/notes`.
3. Visit `http://127.0.0.1:18080/api/notes/search?q=王总&limit=10`.

Expected health response:

```json
{"status": "ok", "service": "notes-api", "version": "0.2.0"}
```

## Running All Components

Phase 2 implements the Notes API. The Sidecar and PC App are still skeletons for
later phases.

```bat
scripts\start_all.bat
```
