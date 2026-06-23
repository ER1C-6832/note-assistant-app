# py-xiaozhi Integration Plan

## Repository boundary

`note-assistant-app` stores the product app and integration layer. The full
py-xiaozhi runtime stays outside this repository.

Recommended layout:

```text
C:\yuyinzhushou\
  note-assistant-app\
    pc-app-build\
  py-xiaozhi-tao\
```

## Phase 5.0

The first validation step is tool-only:

```text
py-xiaozhi CLI
  -> local MCP notes tool
  -> Notes API
```

Install:

```bat
integrations\py-xiaozhi\scripts\install_notes_tool.bat
```

Run:

```bat
integrations\py-xiaozhi\scripts\start_py_xiaozhi_cli.bat
```

## Environment

Configure:

```env
PY_XIAOZHI_ROOT=C:\yuyinzhushou\py-xiaozhi-tao
PY_XIAOZHI_PYTHON=
NOTES_API_BASE_URL=http://127.0.0.1:18080
```

If `PY_XIAOZHI_PYTHON` is empty, scripts auto-detect:

```text
%PY_XIAOZHI_ROOT%\.venv\Scripts\python.exe
%PY_XIAOZHI_ROOT%\venv\Scripts\python.exe
python
```
