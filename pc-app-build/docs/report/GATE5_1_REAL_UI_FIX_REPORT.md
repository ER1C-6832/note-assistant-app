# Gate 5.1 Real UI Acceptance Fix Report

状态：修复候选  
基线：`3faefba365bc71de93573fd56007c7346b8147de` (`first tools`)

## 1. Windows evidence

The Gate 5.1 Fake read/UI verifier completed successfully. The first Real runner connected to the production endpoint and closed all resources, but the endpoint completed the text turn without emitting `tools/call` for `notes.list_recent`. The previous verifier reported this as a product failure even though `initialize` and `tools/list` had already proved the client registry was available.

The cumulative pytest run also exposed one unrelated source-contract regression: Gate 1.6 expected the exact import statement `from .ui import NoteListModel, NotesViewModel`, while Gate 5.1 had combined `NotesUiCommandAdapter` into the same import.

## 2. Fixes

- Restore the Gate 1.6-compatible bootstrap import while retaining `NotesUiCommandAdapter`.
- Change the non-interactive Real endpoint probe to distinguish:
  - missing MCP capability handshake: `real_gate_blocked`, exit 2;
  - completed text turn with no endpoint-selected tool: `real_gate_blocked`, exit 2;
  - observed tool execution error: `failed`, exit 1;
  - successful tools/call and UI dispatch: exit 0.
- Replace explicit tool-name prompts with normal user-language prompts.
- Add `verify_gate5_1_real_ui_language.py`, which launches the actual desktop UI, connects the real runtime, and requires the user to speak natural-language commands through the UI.
- Add a bounded safe command-kind history to `NotesUiCommandAdapter` so the interactive verifier can prove real QML navigation without storing note contents or MCP arguments.
- Add cumulative flag `--include-gate5-real-ui-language`.

## 3. Acceptance split

### Non-interactive endpoint probe

```powershell
python tools/verify_gate5_1_real_read_ui.py
```

This probe is useful for endpoint automation. If the endpoint does not select a tool for a text turn, the result is blocked rather than a false client failure.

### Canonical Gate 5.1 Real UI language acceptance

```powershell
python tools/verify_gate5_1_real_ui_language.py
```

The runner opens the real desktop app and requires natural-language commands through the visible assistant UI. Gate 5.1 is not accepted until this runner returns `real_gate_complete` with:

- `notes.list_recent`, `notes.search`, and `notes.get` successful;
- `ui.open_note` and `ui.show_note_list` successful;
- matching typed UI commands observed;
- manual visible UI confirmation true;
- terminal MCP/UI resources zero;
- no pending `assistant-*` tasks.

## 4. Privacy

The runner reports tool names, statuses, note IDs, command kinds, masked identity, and resource counters only. It does not report note titles, note content, MCP arguments, tokens, or complete identity values.
