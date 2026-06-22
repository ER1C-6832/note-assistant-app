# Notes API Reference

## Base URL

```
http://127.0.0.1:18080
```

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

*Detailed request/response schemas will be documented in Phase 2*
*when the API is implemented.*
