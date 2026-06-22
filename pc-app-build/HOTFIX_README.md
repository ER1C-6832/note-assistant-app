# Phase 1 Hotfix Replacement Files

This package contains focused replacement files for the Phase 1 repository.

## Changes

1. Fixed `scripts/start_notes_api.bat` so it starts uvicorn from
   `services\notes-api` and uses `app.main:app`.
2. Consolidated the Notes API health endpoint through `routers/health.py`.
3. Updated health-check documentation to use `/api/health`.
4. Updated Notes API README quick-start commands.
5. Added a clear Phase 1 skeleton note to the root README.

## How to apply

Unzip this package into:

```text
C:\yuyinzhushou\note-assistant-app
```

Choose "replace files" when prompted.
