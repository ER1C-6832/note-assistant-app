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

Phase 5.1.1 connected the PC App to Sidecar WebSocket:

```text
PC App
  <-> ws://127.0.0.1:17890/assistant
Sidecar
  -> Notes API health
  -> py-xiaozhi runtime status
  -> notes_changed polling events
```

Phase 5.2 adds a tool event bridge:

```text
py-xiaozhi notes MCP tool
  -> POST http://127.0.0.1:17891/api/events
Sidecar
  -> broadcast tool_call / tool_result over WebSocket
PC App
  -> show recent tool call and result
  -> refresh notes immediately when note_changed=true
```

## Phase 5.2 limits

Phase 5.2 does not hook py-xiaozhi ASR/LLM internal event bus yet. It captures
notes MCP tool calls and results, which are the most reliable app-facing events
for this project. Direct transcript / assistant_reply forwarding belongs to the
next py-xiaozhi-plugin phase.

## Start

```bat
scripts\start_notes_api.bat
scripts\start_sidecar.bat
scripts\start_pc_app.bat
```

Then start py-xiaozhi GUI separately.
