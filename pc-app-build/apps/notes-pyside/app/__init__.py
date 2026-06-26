"""
PySide6 + QML application bootstrap.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from urllib.request import Request, urlopen

_PKG_DIR = os.path.dirname(os.path.abspath(__file__))
if _PKG_DIR not in sys.path:
    sys.path.insert(0, _PKG_DIR)


def _load_env_file(path: Path, *, override: bool = True) -> None:
    """Load pc-app-build\\.env into the PC App process.

    Phase 9.3.1.2:
    .env is the App's source of truth for exit behavior. Override inherited
    terminal variables so stale shell/session values cannot disable
    PC_APP_STOP_PY_XIAOZHI_ON_EXIT.
    """
    if not path.exists():
        return

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and (override or key not in os.environ):
            os.environ[key] = value


def _truthy_env(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None or str(raw).strip() == "":
        return default
    value = str(raw).strip().lower()
    if value in {"1", "true", "yes", "y", "on", "是"}:
        return True
    if value in {"0", "false", "no", "n", "off", "否"}:
        return False
    return default


def _post_runtime_stop_via_sidecar(timeout: float = 5.0) -> bool:
    host = os.getenv("SIDECAR_HEALTH_HOST", "127.0.0.1")
    port = os.getenv("SIDECAR_HEALTH_PORT", "17891")
    url = f"http://{host}:{port}/api/runtime/py-xiaozhi/stop"

    data = json.dumps({"source": "pc_app_exit"}).encode("utf-8")
    request = Request(
        url,
        data=data,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
    )

    try:
        with urlopen(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8", errors="replace")
    except Exception:
        return False

    try:
        payload = json.loads(raw) if raw else {}
    except Exception:
        payload = {}

    return bool(payload.get("ok", response.status == 200))


def _kill_py_xiaozhi_processes_fallback(timeout: float = 4.0) -> bool:
    if os.name != "nt":
        return False

    py_root = os.getenv("PY_XIAOZHI_ROOT", r"C:\yuyinzhushou\py-xiaozhi-tao").strip()
    if not py_root:
        return False

    main_py = str(Path(py_root) / "main.py")
    escaped_main = main_py.replace("'", "''")

    script = f"""
$main = '{escaped_main}'.ToLower().Replace('/', [string][char]92);
$targets = Get-CimInstance Win32_Process | Where-Object {{
  $_.CommandLine -and
  ($_.Name.ToLower() -eq 'python.exe' -or $_.Name.ToLower() -eq 'pythonw.exe') -and
  $_.CommandLine.ToLower().Replace('/', [string][char]92).Contains($main)
}};
foreach ($p in $targets) {{
  try {{
    Stop-Process -Id $p.ProcessId -Force -ErrorAction Stop;
  }} catch {{}}
}}
"""

    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=timeout,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        return result.returncode == 0
    except Exception:
        return False


def _request_stop_py_xiaozhi_on_exit(pc_build_root: Path) -> None:
    """Stop py-xiaozhi reliably when the desktop App exits.

    This replaces the old detached PowerShell fire-and-forget path. Fire-and-
    forget was fast, but it could silently fail or race with App shutdown. The
    close path now does a short synchronous HTTP stop through Sidecar and then
    falls back to killing only the configured py-xiaozhi main.py process.
    """
    _load_env_file(pc_build_root / ".env", override=True)

    if not _truthy_env("PC_APP_STOP_PY_XIAOZHI_ON_EXIT", default=False):
        return

    stopped = _post_runtime_stop_via_sidecar(timeout=5.0)
    if not stopped:
        _kill_py_xiaozhi_processes_fallback(timeout=4.0)


def run_app() -> int:
    """Create the Qt application, load QML, and start the event loop."""

    os.environ.setdefault("QT_QUICK_CONTROLS_STYLE", "Basic")
    os.environ.setdefault("QT_API", "pyside6")

    pc_build_root = Path(__file__).resolve().parents[3]
    _load_env_file(pc_build_root / ".env", override=True)

    from PySide6.QtGui import QGuiApplication
    from PySide6.QtQml import QQmlApplicationEngine

    from app.controllers.notes_controller import NotesController
    from app.services.continuous_sidecar_client import ContinuousSidecarClient
    from app.services.login_prewarm import LoginPrewarmController
    from app.services.voice_mode import VoiceModeController

    app = QGuiApplication(sys.argv)
    app.setQuitOnLastWindowClosed(True)
    app.setApplicationDisplayName("小智便签")
    app.setOrganizationName("NoteAssistant")

    notes_controller = NotesController()
    voice_mode_controller = VoiceModeController(pc_build_root)
    sidecar_client = ContinuousSidecarClient(voice_mode_controller=voice_mode_controller)
    login_prewarm_controller = LoginPrewarmController(pc_build_root)

    sidecar_client.notesChanged.connect(notes_controller.refresh)
    sidecar_client.start()
    app.aboutToQuit.connect(lambda: _request_stop_py_xiaozhi_on_exit(pc_build_root))
    app.aboutToQuit.connect(sidecar_client.stop)

    engine = QQmlApplicationEngine()
    context = engine.rootContext()

    context.setContextProperty("notesController", notes_controller)
    context.setContextProperty("notesModel", notes_controller.notes_model)
    context.setContextProperty("deletedNotesModel", notes_controller.deleted_notes_model)
    context.setContextProperty("notesListModel", notes_controller.notes_model)
    context.setContextProperty("deletedNotesListModel", notes_controller.deleted_notes_model)
    context.setContextProperty("sidecarClient", sidecar_client)
    context.setContextProperty("loginPrewarmController", login_prewarm_controller)
    context.setContextProperty("voiceModeController", voice_mode_controller)

    engine.notes_controller = notes_controller  # type: ignore[attr-defined]
    engine.sidecar_client = sidecar_client  # type: ignore[attr-defined]
    engine.login_prewarm_controller = login_prewarm_controller  # type: ignore[attr-defined]
    engine.voice_mode_controller = voice_mode_controller  # type: ignore[attr-defined]

    qml_path = Path(__file__).resolve().parent / "qml" / "Main.qml"
    engine.load(qml_path.as_uri())

    if not engine.rootObjects():
        _request_stop_py_xiaozhi_on_exit(pc_build_root)
        sidecar_client.stop()
        return 1

    exit_code = app.exec()
    sidecar_client.stop()
    return int(exit_code)
