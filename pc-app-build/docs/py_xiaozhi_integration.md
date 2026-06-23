# py-xiaozhi Integration

## Current status

Phase 5.0 / 5.0.1 validated the MCP tool-only path:

```text
py-xiaozhi
  -> notes MCP tool
  -> Notes API
  -> SQLite
  -> PC App displays "来自语音"
```

Phase 5.1 added the Sidecar lightweight bridge.

Phase 5.1.1 connects the PC App to Sidecar WebSocket:

```text
PC App
  <-> ws://127.0.0.1:17890/assistant
Sidecar
  -> Notes API health
  -> py-xiaozhi runtime status
  -> notes_changed polling events
```

When Sidecar emits `notes_changed`, the PC App calls `notesController.refresh()`.

## Start

```bat
scripts\start_notes_api.bat
scripts\start_sidecar.bat
scripts\start_pc_app.bat
```

Or:

```bat
scripts\start_all.bat
```
