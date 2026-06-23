# PC Assistant Sidecar

A lightweight local bridge between the Note Assistant PC App and the external
py-xiaozhi runtime.

## Phase 5.1 scope

Phase 5.1 does not embed py-xiaozhi and does not control its GUI.

It provides:

```text
1. WebSocket endpoint: ws://127.0.0.1:17890/assistant
2. HTTP health endpoint: http://127.0.0.1:17891/api/health
3. Notes API status check
4. py-xiaozhi root / notes MCP tool status check
5. notes_changed events by polling Notes API snapshots
```

## Start

From `pc-app-build`:

```bat
scripts\start_sidecar.bat
```

## WebSocket messages

Client to sidecar:

```json
{"type": "ping"}
{"type": "refresh_status"}
{"type": "refresh_notes"}
```

Sidecar to client:

```json
{"type": "sidecar_connected"}
{"type": "sidecar_status"}
{"type": "notes_changed"}
{"type": "error"}
```

## Health

```text
GET http://127.0.0.1:17891/api/health
```
