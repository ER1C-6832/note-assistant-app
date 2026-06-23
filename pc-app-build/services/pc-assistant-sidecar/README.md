# PC Assistant Sidecar

The Sidecar is reserved for Phase 5.1+.

## Phase 5.0 status

Phase 5.0 does not start the Sidecar yet. It only validates:

```text
py-xiaozhi CLI
  -> local MCP notes tool
  -> Notes API
```

## Future responsibilities

```text
1. Start or detect the py-xiaozhi process
2. Expose ws://127.0.0.1:17890/assistant
3. Push assistant status to the PC App
4. Push notes_changed events
5. Later, bridge transcript / assistant_reply / tool_result
```
