# Notes API

RESTful note management service built with FastAPI + SQLite. This service
is the single source of truth for all note data — both the PySide6 desktop
app and the voice assistant tool layer operate through this API.

## Endpoints

| Method | Path                | Description              |
|--------|---------------------|--------------------------|
| POST   | `/api/notes`        | Create a note            |
| GET    | `/api/notes`        | List notes               |
| GET    | `/api/notes/{id}`   | Get a note by ID         |
| PATCH  | `/api/notes/{id}`   | Update a note            |
| DELETE | `/api/notes/{id}`   | Soft-delete a note       |
| GET    | `/api/notes/search` | Fuzzy search across notes|
| GET    | `/api/health`       | Health check             |

## Quick Start

```bash
# From the pc-app-build root
pip install -r services/notes-api/requirements.txt

# Start the server
python -m uvicorn app.main:app --host 127.0.0.1 --port 18080 --reload
```

## Data

SQLite database is stored at `data/notes.db` by default.
Path is configurable via the `NOTES_DB_PATH` environment variable.
