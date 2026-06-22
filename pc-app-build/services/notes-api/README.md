# Notes API

RESTful note management service built with FastAPI + SQLite.

This service is the single source of truth for all note data. Both the PySide6
desktop app and the voice assistant tool layer operate through this API.

## Endpoints

| Method | Path | Description |
|---|---|---|
| POST | `/api/notes` | Create a note |
| GET | `/api/notes` | List notes |
| GET | `/api/notes/{id}` | Get a note by ID |
| PATCH | `/api/notes/{id}` | Update a note |
| DELETE | `/api/notes/{id}` | Soft-delete a note |
| GET | `/api/notes/search` | Fuzzy search across notes |
| GET | `/api/health` | Health check |

## Quick Start

From the repository root:

```bat
cd pc-app-build\services\notes-api
python -m uvicorn app.main:app --host 127.0.0.1 --port 18080 --reload
```

Or from `pc-app-build`:

```bat
scripts\start_notes_api.bat
```

Then open:

```text
http://127.0.0.1:18080/api/health
```

## Data

SQLite database is stored at `data/notes.db` by default.

The path is configurable via the `NOTES_DB_PATH` environment variable.
