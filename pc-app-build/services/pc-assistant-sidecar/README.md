# PC Assistant Sidecar

A lightweight local bridge between the Note Assistant PC App and the external
py-xiaozhi runtime.

## Phase 5.1.1 scope

Phase 5.1.1 connects the PC App to the Sidecar WebSocket.

It provides:

```text
1. WebSocket endpoint: ws://127.0.0.1:17890/assistant
2. HTTP health endpoint: http://127.0.0.1:17891/api/health
3. Notes API status check
4. py-xiaozhi root / notes MCP tool status check
5. notes_changed events by polling Notes API snapshots
6. PC App auto-refresh when notes_changed is received
```

## Start

From `pc-app-build`:

```bat
scripts\start_notes_api.bat
scripts\start_sidecar.bat
scripts\start_pc_app.bat
```

Or:

```bat
scripts\start_all.bat
```

## Health

```text
GET http://127.0.0.1:17891/api/health
```
