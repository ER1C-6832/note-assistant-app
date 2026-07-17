# Gate 5.1 Real Natural-Language Acceptance Contract

状态：冻结补充

## Required surface

Gate 5.1 Real acceptance must use the production desktop composition root and visible QML UI. A headless `AssistantController.send_text()` probe is supplementary and cannot replace the real UI language gate.

## Required commands

The user must issue ordinary language through the real assistant UI, preferably by microphone. The acceptance set covers:

1. request recent notes -> `notes.list_recent`;
2. request a keyword search -> `notes.search`;
3. request a note by numeric id -> `notes.get`;
4. request opening a note -> `ui.open_note` plus visible selection;
5. request return to all notes -> `ui.show_note_list` plus visible navigation.

Prompts must not require the user to say internal tool names.

## Result rules

- `real_gate_complete` / exit 0: all required tools and UI effects are observed, user confirms visible navigation, and resources close cleanly.
- `real_gate_blocked` / exit 2: credentials, network, activation, microphone/audio, seed data, or initialize/tools-list capability handshake is unavailable.
- `failed` / exit 1: the connected assistant receives the real UI command but does not emit the expected tools/call, a tool returns a non-success status, visible UI effect is absent, or resources leak.

A non-interactive text probe that completes without tools/call is classified as endpoint-selection blocked. It is not accepted as proof of natural-language behavior.
