# Architecture Overview

This document describes the overall architecture of the Note Assistant project.

*For the latest authoritative reference, see the development plan at
`note_xiaozhi_demo_plan_v0.3_pyside6.md` (located in the repository root).*

## System Context

```
                     ┌────────────────────────┐
                     │       Notes API         │
                     │   FastAPI + SQLite      │
                     │   CRUD / Search         │
                     └───────────▲────────────┘
                                 │
              ┌──────────────────┼──────────────────┐
              │                  │                  │
              ▼                  │                  │
┌─────────────────────┐  ┌──────┴──────────┐
│ PySide6 + QML       │  │ Notes Tool      │
│ Desktop App         │  │ (via py-xiaozhi)│
│ Manual CRUD / UI    │  │ Voice CRUD      │
└──────────▲──────────┘  └──────▲──────────┘
           │                    │
           │     ┌──────────────┴──────────┐
           │     │ PC Assistant Sidecar    │
           └─────│ WebSocket Bridge        │
                 └─────────────────────────┘
```

## Key Design Decisions

1. **Notes API as single entry point** — All note operations,
   whether from the UI or voice, go through the same REST API.

2. **Sidecar decoupling** — The voice runtime runs as a separate
   process, preventing audio/event-loop conflicts with the Qt UI.

3. **SQLite for Phase 1** — Server-local database suitable for demo
   and single-user scenarios. Migratable to PostgreSQL or other DBMS.

Refer to individual module README files for component-specific details.
