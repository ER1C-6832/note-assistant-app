# Notes API

RESTful note management service built with FastAPI + SQLite.

This service is the single source of truth for all note data. Both the PySide6
desktop app and the voice assistant tool layer operate through this API.

## Current Phase

Phase 2 implements:

- SQLite initialization
- `notes` table ORM model
- CRUD endpoints
- Soft delete
- LIKE-based fuzzy search across title, content, and tags
- Demo data seeding script

## Endpoints

| Method | Path | Description |
|---|---|---|
| POST | `/api/notes` | Create a note |
| GET | `/api/notes` | List notes |
| GET | `/api/notes/{id}` | Get a note by ID |
| PATCH | `/api/notes/{id}` | Update a note |
| DELETE | `/api/notes/{id}` | Soft-delete a note |
| GET | `/api/notes/search?q=王总&limit=10` | Fuzzy search across notes |
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

SQLite database is stored at:

```text
services/notes-api/data/notes.db
```

The path is configurable via the `NOTES_DB_PATH` environment variable.

## Example Requests

Create a note:

```bat
curl -X POST http://127.0.0.1:18080/api/notes ^
  -H "Content-Type: application/json" ^
  -d "{\"title\":\"联系王总\",\"content\":\"明天上午十点联系王总，确认项目报价。\",\"tags\":[\"客户\",\"跟进\"],\"source\":\"manual\"}"
```

List notes:

```bat
curl http://127.0.0.1:18080/api/notes
```

Search notes:

```bat
curl "http://127.0.0.1:18080/api/notes/search?q=王总&limit=10"
```

Update a note:

```bat
curl -X PATCH http://127.0.0.1:18080/api/notes/1 ^
  -H "Content-Type: application/json" ^
  -d "{\"content\":\"明天下午三点联系王总，确认项目报价。\"}"
```

Soft-delete a note:

```bat
curl -X DELETE http://127.0.0.1:18080/api/notes/1
```
