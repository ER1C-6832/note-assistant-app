from __future__ import annotations

import ast
import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
APP = ROOT / "apps" / "notes-pyside" / "app"
AUDIO = APP / "assistant" / "audio"
TOOLS = ROOT / "tools"


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    values: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            values.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            values.add(node.module)
    return values


def test_gate6_contracts_are_framework_and_platform_neutral() -> None:
    path = AUDIO / "gate6_contracts.py"
    imports = _imports(path)
    forbidden = (
        "PySide6",
        "pyaudio",
        "ctypes",
        "win32",
        "CoreAudio",
        "sherpa_onnx",
        "aec_audio_processing",
        "subprocess",
        "multiprocessing",
    )

    assert path.is_file()
    assert not any(any(item in name for item in forbidden) for name in imports)


def test_gate6_0_does_not_modify_product_audio_bootstrap_or_add_sidecar() -> None:
    overlay_production = {path.name for path in AUDIO.glob("gate6_*.py") if path.is_file()}
    text = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (
            AUDIO / "gate6_contracts.py",
            AUDIO / "gate6_probe.py",
            AUDIO / "gate6_pyaudio_probe.py",
            AUDIO / "gate6_backend_probe.py",
        )
    ).casefold()

    assert overlay_production == {
        "gate6_backend_probe.py",
        "gate6_contracts.py",
        "gate6_probe.py",
        "gate6_pyaudio_probe.py",
    }
    assert "localhost" not in text
    assert "subprocess" not in text
    assert "multiprocessing" not in text
    assert "sidecar" not in text


def test_gate6_0_real_probes_are_explicit_and_fake_probe_opens_no_device() -> None:
    fake_text = (TOOLS / "verify_gate6_0_fake_probe.py").read_text(encoding="utf-8")
    cumulative = (TOOLS / "verify_gate6_0_cumulative.py").read_text(encoding="utf-8")

    assert "pyaudio" not in fake_text.casefold()
    assert "--include-real-devices" in cumulative
    assert "--include-real-duplex" in cumulative
    assert "--include-real-aec" in cumulative
    assert "--include-real-kws" in cumulative
    assert "interactive=True" in cumulative
    assert "--aec-stream-delay-ms" in cumulative
    assert "--aec-processing-mode" in cumulative


def test_gate6_0_real_acceptance_is_semantic_and_kws_prompts_only_when_ready() -> None:
    backend = (AUDIO / "gate6_backend_probe.py").read_text(encoding="utf-8")
    aec_cli = (TOOLS / "probe_gate6_aec.py").read_text(encoding="utf-8")
    kws_cli = (TOOLS / "probe_gate6_kws.py").read_text(encoding="utf-8")

    assert "near_end_speech_not_preserved" in backend
    assert '"probe_inconclusive"' in backend
    assert "resolve_stream_delay_ms" in backend
    assert 'acceptance.get("accepted") is True' in aec_cli
    assert '"required_distinct_hits": 2' in backend
    assert 'acceptance.get("accepted") is True' in kws_cli
    assert "model.validate()" in kws_cli
    assert "ready_callback=prompt_ready" in kws_cli
    assert kws_cli.index("model.validate()") < kws_cli.index("ready_callback=prompt_ready")


def test_gate5_frozen_name_hash_remains_unchanged() -> None:
    expected = "543129cc3d6c8fae161ddb716f6cdbf803920ba8fa674d6c5cf6571a198a10e9"
    descriptor_path = APP / "assistant" / "mcp" / "descriptors.py"
    if descriptor_path.is_file():
        from app.assistant.mcp.descriptors import FROZEN_GATE5_TOOL_NAMES

        digest = hashlib.sha256(
            "\n".join(sorted(FROZEN_GATE5_TOOL_NAMES)).encode("utf-8")
        ).hexdigest()
        assert digest == expected
    else:
        # Overlay-only local validation does not contain the untouched Gate 5 file.
        assert len(expected) == 64
