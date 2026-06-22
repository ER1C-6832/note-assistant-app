# Note Assistant

A note-taking desktop application with voice assistant capabilities.

This project combines a modern PySide6 + QML note editor with a speech-driven
assistant backend, enabling hands-free note management through natural language
commands.

> Phase 1 is a repository initialization phase. It provides the project skeleton,
> configuration, scripts, and documentation foundation for later Notes API,
> PySide6 UI, Sidecar, and voice integration work.

## Overview

**Note Assistant** is a three-tier desktop application:

- **PC App** — A PySide6 + QML desktop interface for managing notes with a
  modern card-style layout.
- **Notes API** — A FastAPI-based RESTful service providing unified note CRUD
  and fuzzy search, consumed by both the PC App and the voice assistant tool
  layer.
- **PC Assistant Sidecar** — A local WebSocket service that bridges the PC App
  with the `py-xiaozhi` voice runtime, relaying speech recognition, assistant
  replies, and tool execution events.

The assistant module is designed as a built-in capability of the note app rather
than a standalone voice client.

All note operations, whether manual or voice-initiated, go through the same
Notes API.

## Features

- Note management: create, edit, delete, and search notes through the desktop UI.
- Fuzzy search: LIKE-based search across note titles, content, and tags.
- Voice assistant integration: hands-free note operations through speech commands.
- Unified data path: both manual and voice operations use the same Notes API and SQLite database.
- Modular architecture: UI, business logic, and voice runtime are decoupled.

## Technology Stack

| Layer | Technology |
|---|---|
| Desktop UI | PySide6 / QtQuick / QML |
| Backend API | FastAPI + uvicorn |
| Database | SQLite via SQLAlchemy |
| Voice Runtime | py-xiaozhi sidecar process |
| IPC | Local WebSocket |
| Data Validation | Pydantic |

## Project Structure

```text
pc-app-build/
├── apps/
│   └── notes-pyside/
├── services/
│   ├── notes-api/
│   └── pc-assistant-sidecar/
├── integrations/
│   └── py-xiaozhi/
├── scripts/
└── docs/
```

## Getting Started

### Prerequisites

- Python 3.10 or later
- Git

### Setup

```bat
git clone https://github.com/ER1C-6832/note-assistant-app.git
cd note-assistant-app\pc-app-build
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

### Start Services

```bat
scripts\start_all.bat
```

Or start each process manually:

```bat
scripts\start_notes_api.bat
scripts\start_sidecar.bat
scripts\start_pc_app.bat
```

### Quick Verification

Open:

```text
http://127.0.0.1:18080/api/health
```

The Notes API should return a health check response.

## Architecture Overview

```text
                     ┌────────────────────────┐
                     │       Notes API         │
                     │   FastAPI + SQLite      │
                     │   CRUD / Search         │
                     └───────────▲────────────┘
                                 │
              ┌──────────────────┼──────────────────┐
              │                  │                  │
┌─────────────┴───────┐  ┌───────┴──────────┐       │
│ PySide6 + QML App    │  │ Notes Tool       │       │
│ Manual CRUD / UI     │  │ Voice CRUD       │       │
└─────────────▲────────┘  └───────▲──────────┘       │
              │                   │                  │
              └──────┬────────────┘                  │
                     │                               │
              ┌──────┴──────────────┐                │
              │ PC Assistant Sidecar │                │
              │ WebSocket Bridge     │                │
              └─────────────────────┘                │
```

## Development

- QML UI: `apps/notes-pyside/app/qml/`
- Notes API: `services/notes-api/`
- Sidecar: `services/pc-assistant-sidecar/`
- py-xiaozhi integration: `integrations/py-xiaozhi/`

Refer to `docs/architecture.md` for the detailed architecture.
