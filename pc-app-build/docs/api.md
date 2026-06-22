# Notes API Reference

Base URL:

```text
http://127.0.0.1:18080
```

## Health

### GET `/api/health`

Returns service status.

Response:

```json
{
  "status": "ok",
  "service": "notes-api",
  "version": "0.2.0"
}
```

---

## Notes

### POST `/api/notes`

Create a note.

Request:

```json
{
  "title": "联系王总",
  "content": "明天上午十点联系王总，确认项目报价。",
  "tags": ["客户", "跟进"],
  "is_pinned": false,
  "source": "manual"
}
```

Response:

```json
{
  "id": 1,
  "title": "联系王总",
  "content": "明天上午十点联系王总，确认项目报价。",
  "tags": ["客户", "跟进"],
  "is_pinned": false,
  "is_deleted": false,
  "created_at": "2026-06-22T10:00:00",
  "updated_at": "2026-06-22T10:00:00",
  "source": "manual"
}
```

---

### GET `/api/notes`

List notes.

Query parameters:

| Name | Type | Default | Description |
|---|---|---:|---|
| `include_deleted` | bool | `false` | Include soft-deleted notes |
| `tag` | string | null | Filter by tag keyword |
| `limit` | int | `50` | Page size, 1–200 |
| `offset` | int | `0` | Offset |

Example:

```text
GET /api/notes?limit=20&offset=0
```

---

### GET `/api/notes/{id}`

Get a note by ID.

Query parameters:

| Name | Type | Default | Description |
|---|---|---:|---|
| `include_deleted` | bool | `false` | Allow reading a soft-deleted note |

---

### PATCH `/api/notes/{id}`

Update a note.

Request:

```json
{
  "title": "联系王总",
  "content": "明天下午三点联系王总，确认项目报价。",
  "tags": ["客户", "跟进"],
  "is_pinned": true
}
```

All fields are optional.

---

### DELETE `/api/notes/{id}`

Soft-delete a note.

Response:

```json
{
  "success": true,
  "note_id": 1,
  "is_deleted": true
}
```

---

## Search

### GET `/api/notes/search`

Fuzzy search notes by title, content, and tags.

Query parameters:

| Name | Type | Default | Description |
|---|---|---:|---|
| `q` | string | `""` | Search keyword |
| `limit` | int | `10` | Max results, 1–100 |
| `date_from` | datetime | null | Created-at lower bound |
| `date_to` | datetime | null | Created-at upper bound |
| `tags` | string | null | Comma-separated tag filters |

Example:

```text
GET /api/notes/search?q=王总&limit=10
```

Response:

```json
{
  "query": "王总",
  "total": 2,
  "items": [
    {
      "id": 1,
      "title": "联系王总",
      "content": "明天上午十点联系王总，确认项目报价。",
      "tags": ["客户", "跟进"],
      "is_pinned": false,
      "is_deleted": false,
      "created_at": "2026-06-22T10:00:00",
      "updated_at": "2026-06-22T10:00:00",
      "source": "manual"
    }
  ]
}
```

## Search Strategy

Phase 2 uses SQLite LIKE matching:

```sql
title LIKE '%keyword%'
OR content LIKE '%keyword%'
OR tags LIKE '%keyword%'
```

Future phases may add FTS5, Chinese segmentation, embeddings, or hybrid search.
