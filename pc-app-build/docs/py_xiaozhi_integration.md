# py-xiaozhi Integration

## Current status

Phase 5.0 / 5.0.1 validated the notes MCP tool path.

Phase 5.1 added Sidecar status and notes_changed watching.

Phase 5.1.1 connected the PC App to Sidecar WebSocket.

Phase 5.2 added notes MCP tool_call / tool_result events.

Phase 5.3 adds a lightweight py-xiaozhi runtime log bridge.

## Phase 5.3 architecture

```text
py-xiaozhi GUI
  -> writes runtime log
Sidecar PyXiaozhiLogWatcher
  -> tails app.log
  -> emits assistant_state / assistant_transcript / assistant_reply
Sidecar WebSocket
  -> broadcasts events
PC App SidecarClient
  -> displays latest runtime activity in AssistantPanel
```

## Log path

The default path is:

```text
%LOCALAPPDATA%\py-xiaozhi\py-xiaozhi\logs\app.log
```

Override it in `.env`:

```text
PY_XIAOZHI_LOG_PATH=C:\Users\111\AppData\Local\py-xiaozhi\py-xiaozhi\logs\app.log
```

## Limits

Phase 5.3 is non-invasive. It does not modify py-xiaozhi internals or hook its
event bus. If the runtime log does not contain transcript/reply lines, the UI
will still show notes MCP tool events from Phase 5.2, but may not show full
ASR/assistant text. A deeper EventBus plugin can be a later phase after the tao
event bus files are inspected.
