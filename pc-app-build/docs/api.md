# Notes API Reference

Base URL:

```text
http://127.0.0.1:18080
```

## Health

### GET `/api/health`

Returns service status.

## Notes

### POST `/api/notes`

Create a note.

### GET `/api/notes`

List notes.

Query parameters:

| Name | Type | Default | Description |
|---|---|---:|---|
| `include_deleted` | bool | `false` | Include soft-deleted notes |
| `tag` | string | null | Filter by tag keyword |
| `limit` | int | `50` | Page size, 1–200 |
| `offset` | int | `0` | Offset |

### GET `/api/notes/{id}`

Get a note by ID.

### PATCH `/api/notes/{id}`

Update a note.

Supported fields:

```json
{
  "title": "联系王总",
  "content": "明天下午三点联系王总。",
  "tags": ["客户", "跟进"],
  "is_pinned": true
}
```

### DELETE `/api/notes/{id}`

Soft-delete a note.

### POST `/api/notes/{id}/restore`

Restore a soft-deleted note.

## Search

### GET `/api/notes/search`

Fuzzy search notes by title, content, and tags.

Example:

```text
GET /api/notes/search?q=王总&limit=10
```
