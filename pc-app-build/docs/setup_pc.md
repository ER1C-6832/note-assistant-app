# PC Setup Guide

## Prerequisites

- Python 3.10 or later
- Git

## Installation

1. Clone the repository:

```bat
git clone https://github.com/ER1C-6832/note-assistant-app.git
cd note-assistant-app\pc-app-build
```

2. Create and activate a virtual environment:

```bat
python -m venv venv
venv\Scripts\activate
```

3. Install dependencies:

```bat
pip install -r requirements.txt
```

4. Configure environment:

```bat
copy .env.example .env
```

Edit `.env` if custom ports or paths are needed. The defaults are suitable for
local development.

## Running

Start everything with the one-click launcher:

```bat
scripts\start_all.bat
```

Or start each service individually:

```bat
REM Terminal 1: Notes API
scripts\start_notes_api.bat

REM Terminal 2: PC Assistant Sidecar
scripts\start_sidecar.bat

REM Terminal 3: PC App
scripts\start_pc_app.bat
```

## Verification

1. Visit `http://127.0.0.1:18080/api/health`.
2. The response should include:

```json
{"status": "ok", "service": "notes-api", "version": "0.1.0"}
```

3. Launch the PC App and confirm the Note Assistant main window appears.
