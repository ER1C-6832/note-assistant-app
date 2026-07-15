from __future__ import annotations

import ast
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[2] / "apps" / "notes-pyside" / "app"
ASSISTANT_ROOT = APP_ROOT / "assistant"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_gate2_2_sources_parse_and_do_not_depend_on_qt() -> None:
    for path in ASSISTANT_ROOT.rglob("*.py"):
        source = _read(path)
        ast.parse(source, filename=str(path))
        assert "PySide6" not in source


def test_identity_and_activation_are_effects_not_controller_state_writes() -> None:
    controller = _read(ASSISTANT_ROOT / "controller.py")
    state_machine = _read(ASSISTANT_ROOT / "state_machine.py")

    assert "EnsureIdentity" in controller
    assert "RunActivation" in controller
    assert "self._state = transition.state" in controller

    tree = ast.parse(controller)
    state_assignments = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.Assign, ast.AnnAssign)):
            continue
        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        for target in targets:
            if (
                isinstance(target, ast.Attribute)
                and isinstance(target.value, ast.Name)
                and target.value.id == "self"
                and target.attr == "_state"
            ):
                state_assignments.append(node)
    assert len(state_assignments) == 2
    assert "RunActivation(fake=fake)" in state_machine
    assert "RuntimeConfigStore" not in state_machine
    assert "urllib" not in state_machine


def test_real_activation_uses_pc_identity_and_never_logs_raw_secrets() -> None:
    client = _read(ASSISTANT_ROOT / "activation" / "client.py")
    state = _read(ASSISTANT_ROOT / "state.py")

    assert 'BOARD_TYPE = "windows"' in client
    assert 'APP_NAME = "note-assistant-pc"' in client
    assert '"Device-Id": identity.device_id' in client
    assert '"Client-Id": identity.client_id' in client
    assert "websocket_token" not in state
    assert "hmac_key" not in state


def test_real_activation_check_uses_defaults_and_repairs_pre_fix_identity() -> None:
    pc_build_root = Path(__file__).resolve().parents[2]
    tool = _read(pc_build_root / "tools" / "verify_gate2_2_real_activation.py")
    runtime_config = _read(ASSISTANT_ROOT / "runtime_config.py")
    manager = _read(ASSISTANT_ROOT / "identity" / "manager.py")

    assert "_required_env" not in tool
    assert "LegacyPyXiaozhiIdentitySource" in tool
    assert '"identity_repaired": identity_manager.last_identity_replaced' in tool
    assert "install_migrated" in manager
    assert "create_machine_identity" in manager
    assert 'DEFAULT_ASSISTANT_OTA_URL = "https://api.tenclass.net/xiaozhi/ota/"' in runtime_config
    assert 'DEFAULT_ASSISTANT_AUTHORIZATION_URL = "https://xiaozhi.me/"' in runtime_config
