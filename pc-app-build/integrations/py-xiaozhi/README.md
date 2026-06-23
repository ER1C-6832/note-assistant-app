# py-xiaozhi Integration

This folder stores only the Note Assistant integration layer for py-xiaozhi.

Do **not** copy the full py-xiaozhi repository into `pc-app-build`.

Recommended local layout:

```text
C:\yuyinzhushou\
  note-assistant-app\
    pc-app-build\
  py-xiaozhi-tao\
```

## Phase 5.0

Phase 5.0 validates that py-xiaozhi can call Note Assistant through local MCP tools.

Install the notes MCP tool:

```bat
cd /d C:\yuyinzhushou\note-assistant-app\pc-app-build
integrations\py-xiaozhi\scripts\install_notes_tool.bat
```

Check py-xiaozhi dependencies:

```bat
integrations\py-xiaozhi\scripts\check_py_xiaozhi_env.bat
```

Start py-xiaozhi CLI:

```bat
integrations\py-xiaozhi\scripts\start_py_xiaozhi_cli.bat
```
