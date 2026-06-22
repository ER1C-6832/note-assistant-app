# Note Assistant

A note-taking desktop application with voice assistant capabilities. This project combines a modern PySide6 + QML note editor with a speech-driven assistant backend, enabling hands-free note management through natural language commands.

## Overview

**Note Assistant** is a three-tier desktop application:

- **PC App** — A PySide6 + QML desktop interface for managing notes with a modern card-style layout (sidebar, note list, detail/editor panel).
- **Notes API** — A FastAPI-based RESTful service providing unified note CRUD and fuzzy search, consumed by both the PC App and the voice assistant tool layer.
- **PC Assistant Sidecar** — A local WebSocket service that bridges the PC App with the `py-xiaozhi` voice runtime, relaying speech recognition, assistant replies, and tool execution events.

The assistant module is designed as a built-in capability of the note app rather than a standalone voice client. All note operations — whether manual or voice-initiated — go through the same Notes API, ensuring a consistent data path.

## Features

- **Note management** — Create, edit, delete, and search notes through the desktop UI
- **Fuzzy search** — Full-text LIKE search across note titles, content, and tags
- **Voice assistant integration** — Hands-free note operations via speech commands:
  - *"Remind me to call Mr. Wang at 10 AM tomorrow"* → Create a note
  - *"Find notes about Mr. Wang"* → Search notes
  - *"Change that to 3 PM"* → Update a note
  - *"Delete that note"* → Delete with confirmation
- **Unified data path** — Both manual and voice operations use the same Notes API and SQLite database
- **Modular architecture** — UI, business logic, and voice runtime are decoupled for independent development and testing

## Technology Stack

| Layer | Technology |
|-------|-----------|
| Desktop UI | PySide 6.6+ / QtQuick / QML |
| Backend API | FastAPI + uvicorn |
| Database | SQLite via SQLAlchemy 2.0 |
| Voice Runtime | py-xiaozhi (sidecar process) |
| IPC | Local WebSocket (sidecar ↔ PC App) |
| Data Validation | Pydantic 2.0 |

## Project Structure

```
pc-app-build/
├── apps/
│   └── notes-pyside/          # PySide6 + QML desktop application
│       ├── main.py            # Application entry point
│       └── app/
│           ├── qml/           # QML UI components and pages
│           ├── controllers/   # Python controllers (notes, assistant, app state)
│           ├── services/      # API and WebSocket client services
│           ├── models/        # Data models
│           └── assets/        # Icons and images
├── services/
│   ├── notes-api/             # FastAPI-based note management service
│   │   ├── app/               # API application code (routers, services, models)
│   │   └── data/              # SQLite database storage
│   └── pc-assistant-sidecar/  # Local WebSocket bridge to py-xiaozhi
├── integrations/
│   └── py-xiaozhi/            # Voice runtime integration patches and prompts
├── scripts/                   # One-click startup and utility scripts
└── docs/                      # Architecture, API, setup, and demo documentation
```

## Getting Started

### Prerequisites

- Python 3.10 or later
- Git

### Setup

1. **Clone the repository** (if not already done):

   ```bash
   git clone https://github.com/ER1C-6832/note-assistant-app.git
   cd note-assistant-app/pc-app-build
   ```

2. **Create a virtual environment**:

   ```bash
   python -m venv venv
   ```

   Activate it:

   - **Windows**: `venv\Scripts\activate`
   - **Linux / macOS**: `source venv/bin/activate`

3. **Install dependencies**:

   ```bash
   pip install -r requirements.txt
   ```

   Or using Poetry (if `pyproject.toml` is configured):

   ```bash
   pip install poetry
   poetry install
   ```

4. **Configure environment**:

   ```bash
   cp .env.example .env
   ```

   Edit `.env` to match your local setup if needed (defaults work for local development).

5. **Start the services**:

   Use the one-click launcher or start each service individually:

   ```bash
   # Terminal 1: Notes API
   scripts/start_notes_api.bat

   # Terminal 2: PC Assistant Sidecar
   scripts/start_sidecar.bat

   # Terminal 3: PC App
   scripts/start_pc_app.bat
   ```

   Or start everything at once:

   ```bash
   scripts/start_all.bat
   ```

### Quick Verification

1. Open `http://127.0.0.1:18080/health` in a browser — the Notes API should return a health check response.
2. Launch the PC App — the main note-taking window should appear.

## Architecture Overview

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

- The **PC App** reads and writes notes exclusively through the **Notes API**.
- The **PC Assistant Sidecar** wraps the `py-xiaozhi` voice runtime and exposes a local WebSocket for the PC App to send/receive voice events.
- The `py-xiaozhi` runtime uses **Notes Tools** (function-calling layer) to perform note operations through the same **Notes API**, keeping all data access unified.
- Future Android clients (not yet in development) will also consume the same **Notes API**, preserving the architecture for cross-platform expansion.

## Development

- **QML UI**: Components live in `apps/notes-pyside/app/qml/`. The design follows a three-panel layout: sidebar (tags, settings), note list, and detail/editor panel.
- **Notes API**: Located in `services/notes-api/`. Add new endpoints in `routers/` and business logic in `services/`.
- **Sidecar**: Located in `services/pc-assistant-sidecar/`. The WebSocket protocol uses JSON messages for speech events, status updates, and tool results.

Refer to `docs/architecture.md` for a deeper architectural walkthrough.

## License

This project is provided for evaluation and development purposes.

---

*Note Assistant — A note app with voice, not a voice app with notes.*
