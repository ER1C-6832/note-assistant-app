# PC Assistant Sidecar

A local WebSocket service that bridges the PySide6 Note Assistant desktop
application with the `py-xiaozhi` voice runtime.

The sidecar manages the voice assistant lifecycle separately from the UI
process, ensuring that a crash or restart of the voice runtime does not
affect the note application.

## WebSocket Protocol

**Endpoint:** `ws://127.0.0.1:17890/assistant`

### Client → Sidecar

| Message Type       | Description                     |
|--------------------|---------------------------------|
| `start_listen`     | Begin voice capture             |
| `stop_listen`      | Stop voice capture              |

### Sidecar → Client

| Message Type         | Description                            |
|----------------------|----------------------------------------|
| `assistant_status`   | Current state (listening, processing)   |
| `transcript`         | ASR transcription text                 |
| `assistant_reply`    | LLM reply text                         |
| `tool_result`        | Result of a note tool invocation       |
| `notes_changed`      | Notification that note data changed    |

## Quick Start

```bash
# From the pc-app-build root
pip install -r services/pc-assistant-sidecar/requirements.txt

# Start the sidecar
python services/pc-assistant-sidecar/main.py
```
