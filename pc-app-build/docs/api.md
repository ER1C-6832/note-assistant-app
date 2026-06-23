# Notes API Reference

Base URL:

```text
http://127.0.0.1:18080
```

| Method | Path | Description |
|---|---|---|
| POST | `/api/notes` | Create a note |
| GET | `/api/notes` | List notes |
| GET | `/api/notes/{id}` | Get a note by ID |
| PATCH | `/api/notes/{id}` | Update a note, including `is_pinned` |
| DELETE | `/api/notes/{id}` | Soft-delete a note |
| POST | `/api/notes/{id}/restore` | Restore a soft-deleted note |
| DELETE | `/api/notes/{id}/hard` | Permanently delete a note |
| GET | `/api/notes/search?q=王总` | Search notes |

Update payload example:

```json
{
  "title": "联系王总",
  "content": "明天下午三点联系王总。",
  "tags": ["客户", "跟进"],
  "is_pinned": true
}
```
