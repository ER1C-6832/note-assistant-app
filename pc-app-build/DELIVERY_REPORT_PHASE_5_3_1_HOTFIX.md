# Phase 5.3.1 Hotfix Report — Runtime Event Test Script Fix

> **Project:** Note Assistant  
> **Patch:** Phase 5.3.1 Hotfix  
> **Status:** ✅ Delivered

## 1. Problem

`test_assistant_runtime_event.bat` used a long inline PowerShell command with
nested quotes, hashtables, and pipeline characters. In Windows `cmd.exe`, this
is fragile and can be parsed incorrectly, producing errors such as:

```text
'tant_transcript'' 不是内部或外部命令，也不是可运行的程序或批处理文件。
```

The Sidecar runtime log bridge itself is not affected.

## 2. Fix

The test script is split into:

```text
test_assistant_runtime_event.bat
test_assistant_runtime_event.py
```

The BAT file now only calls Python. The Python script posts three JSON events to
Sidecar:

```text
assistant_transcript
assistant_reply
assistant_state
```

This avoids Windows batch quoting issues entirely.

## 3. Files Included

```text
pc-app-build/integrations/py-xiaozhi/scripts/test_assistant_runtime_event.bat
pc-app-build/integrations/py-xiaozhi/scripts/test_assistant_runtime_event.py
pc-app-build/DELIVERY_REPORT_PHASE_5_3_1_HOTFIX.md
```

## 4. Verification

Start Sidecar and PC App, then run:

```bat
integrations\py-xiaozhi\scripts\test_assistant_runtime_event.bat
```

Expected:

```text
OK: test assistant runtime events sent.
```

The PC App Voice Assistant panel should show test transcript / reply / runtime
state.
