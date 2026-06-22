# PC Setup Guide

## Prerequisites

- Python 3.10 or later
- Git (for cloning the repository)

## Installation

1. **Clone the repository**

   ```bash
   git clone <repository-url>
   cd note-assistant-app/pc-app-build
   ```

2. **Create and activate a virtual environment**

   ```bash
   python -m venv venv
   ```

   - **Windows**: `venv\Scripts\activate`
   - **Linux / macOS**: `source venv/bin/activate`

3. **Install dependencies**

   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment**

   ```bash
   cp .env.example .env
   ```

   Edit `.env` if custom ports or paths are needed (defaults are suitable
   for local development).

## Running

See [scripts/start_all.bat](../scripts/start_all.bat) for the one-click
launcher, or start each service individually:

```bash
# Terminal 1: Notes API
python -m uvicorn services.notes-api.app.main:app --host 127.0.0.1 --port 18080 --reload

# Terminal 2: PC Assistant Sidecar
python services/pc-assistant-sidecar/main.py

# Terminal 3: PC App
python apps/notes-pyside/main.py
```

## Verification

1. Visit `http://127.0.0.1:18080/health` — should return `{"status": "ok"}`
2. The PC App window should display the Note Assistant main interface
