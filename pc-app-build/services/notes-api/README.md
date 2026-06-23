# Notes API

The Notes API is the only backend entry point for notes data.

## Start

```bat
cd /d C:\yuyinzhushou\note-assistant-app\pc-app-build
venv\Scripts\activate
scripts\start_notes_api.bat
```

## Health

```text
GET /api/health
```

## Main endpoints

```text
POST   /api/notes
GET    /api/notes
GET    /api/notes/search?q=关键词
GET    /api/notes/{id}
PATCH  /api/notes/{id}
DELETE /api/notes/{id}
POST   /api/notes/{id}/restore
DELETE /api/notes/{id}/hard
```

## py-xiaozhi integration rule

py-xiaozhi tools must call this API. They must not read or write the SQLite
database directly.
