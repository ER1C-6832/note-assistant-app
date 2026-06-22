# PC Sidecar Integration — py-xiaozhi

## Overview

py-xiaozhi runs as a child process managed by the PC Assistant Sidecar.
It does **not** show its own UI. Instead, it operates as a headless
voice runtime, processing ASR → LLM → TTS and invoking note tools
via the Notes API.

## Architecture

```
PySide6 PC App
    │ WebSocket (ws://127.0.0.1:17890)
    ▼
PC Assistant Sidecar
    │ subprocess
    ▼
py-xiaozhi (headless)
    │ function calling
    ▼
Notes Tool → Notes API → SQLite
```

## Integration Points

1. **Tool Registration**: py-xiaozhi's function-calling system is
   extended with note tools defined in `integrations/py-xiaozhi/patches/`.

2. **Prompt Injection**: The operation rules in
   `integrations/py-xiaozhi/prompts/notes_assistant_rules.md` are
   injected into the LLM prompt to guide assistant behavior.

3. **Event Relay**: ASR transcripts, LLM replies, and tool results
   flow from py-xiaozhi → Sidecar WebSocket → PC App UI.

## Lifecycle

- Sidecar starts py-xiaozhi as a subprocess on startup.
- Sidecar monitors the process and restarts it on unexpected exit.
- On sidecar shutdown, py-xiaozhi is gracefully terminated.
