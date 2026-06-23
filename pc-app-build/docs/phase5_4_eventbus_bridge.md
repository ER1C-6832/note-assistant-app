# Phase 5.4 — py-xiaozhi EventBus Bridge

## Purpose

Phase 5.4 completes the original Phase 5 enhanced bridge goal:

```text
transcript
assistant_reply
tool_result
listening / speaking / idle
App right-side voice panel shows the real voice process
```

Previous Phase 5.3 used a log watcher. Phase 5.4 adds a true py-xiaozhi plugin
that subscribes to EventBus and plugin callbacks.

## Architecture

```text
py-xiaozhi EventBus
  -> PCBridgePlugin
  -> POST Sidecar /api/events
  -> Sidecar WebSocket
  -> PC App SidecarClient
  -> AssistantPanel
```

## Events

```text
assistant_status
assistant_state
assistant_transcript
assistant_reply
audio_channel
runtime_error
tool_call
tool_result
notes_changed
```

## Install

```bat
cd /d C:\yuyinzhushou\note-assistant-app\pc-app-build
venv\Scripts\activate

integrations\py-xiaozhi\scripts\install_pc_bridge_plugin.bat
integrations\py-xiaozhi\scripts\install_notes_tool.bat
```

Restart py-xiaozhi GUI.

## Verify

Start Notes API, Sidecar, and PC App, then run:

```bat
integrations\py-xiaozhi\scripts\verify_pc_bridge_events.bat
```

Then use py-xiaozhi GUI voice interaction. Expected:

```text
1. Sidecar logs Broadcast sidecar event: assistant_status / assistant_transcript / assistant_reply
2. PC App right voice panel updates in real time
3. notes MCP tool_call/tool_result still appears
4. notes_changed still refreshes the notes list
```
