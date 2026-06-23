# PC Assistant Sidecar

A lightweight local bridge between the Note Assistant PC App and the external
py-xiaozhi runtime.

## Endpoints

```text
WebSocket: ws://127.0.0.1:17890/assistant
Health:    http://127.0.0.1:17891/api/health
Events:    http://127.0.0.1:17891/api/events
```

## Phase 5.2

Phase 5.2 adds event intake:

```text
POST /api/events
GET  /api/events?limit=20
```

py-xiaozhi notes MCP tools submit:

```text
tool_call
tool_result
```

The Sidecar stores recent events and broadcasts them to WebSocket clients.
