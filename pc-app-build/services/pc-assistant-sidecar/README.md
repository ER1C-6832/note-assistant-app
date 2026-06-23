# PC Assistant Sidecar

## Endpoints

```text
WebSocket: ws://127.0.0.1:17890/assistant
Health:    http://127.0.0.1:17891/api/health
Events:    http://127.0.0.1:17891/api/events
```

## Phase 5.3

Phase 5.3 adds `PyXiaozhiLogWatcher`, a non-invasive runtime log bridge.

It tails py-xiaozhi's app log and emits:

```text
assistant_state
assistant_transcript
assistant_reply
assistant_log
```

This is best-effort and depends on log content. The more stable notes MCP tool
events from Phase 5.2 continue to work independently.
