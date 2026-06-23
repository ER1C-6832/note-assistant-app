from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path


def resolve_paths() -> tuple[Path, Path, Path]:
    script_dir = Path(__file__).resolve().parent
    integration_dir = script_dir.parent
    pc_build_root = integration_dir.parent.parent

    py_root = os.getenv("PY_XIAOZHI_ROOT", "").strip()
    if not py_root:
        env_file = pc_build_root / ".env"
        if env_file.exists():
            for raw_line in env_file.read_text(encoding="utf-8").splitlines():
                line = raw_line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                if key.strip().upper() == "PY_XIAOZHI_ROOT":
                    py_root = value.strip().strip('"').strip("'")
                    break

    if not py_root:
        py_root = r"C:\yuyinzhushou\py-xiaozhi-tao"

    return pc_build_root, integration_dir, Path(py_root)


def patch_container(container_path: Path) -> bool:
    original = container_path.read_text(encoding="utf-8")
    text = original

    if "from src.plugins.pc_bridge import PCBridgePlugin" not in text:
        anchor = "        from src.plugins.mcp import McpPlugin\n"
        if anchor not in text:
            raise RuntimeError("Cannot find McpPlugin import anchor in container.py")
        text = text.replace(anchor, anchor + "        from src.plugins.pc_bridge import PCBridgePlugin\n")

    if "pc_bridge_plugin = PCBridgePlugin()" not in text:
        anchor = "        mcp_plugin = McpPlugin()\n"
        if anchor not in text:
            raise RuntimeError("Cannot find mcp_plugin instance anchor in container.py")
        text = text.replace(anchor, anchor + "        pc_bridge_plugin = PCBridgePlugin()\n")

    if "            pc_bridge_plugin,\n" not in text:
        anchor = "            mcp_plugin,\n"
        if anchor not in text:
            raise RuntimeError("Cannot find mcp_plugin register anchor in container.py")
        text = text.replace(anchor, anchor + "            pc_bridge_plugin,\n", 1)

    if text == original:
        return False

    backup = container_path.with_suffix(container_path.suffix + ".phase5_4_backup")
    if not backup.exists():
        backup.write_text(original, encoding="utf-8")

    container_path.write_text(text, encoding="utf-8", newline="\n")
    return True


def main() -> int:
    pc_build_root, integration_dir, py_root = resolve_paths()

    source_plugin = integration_dir / "event-bridge" / "pc_bridge.py"
    target_plugin = py_root / "src" / "plugins" / "pc_bridge.py"
    container_path = py_root / "src" / "bootstrap" / "container.py"

    print(f"PC build root:     {pc_build_root}")
    print(f"Integration root:  {integration_dir}")
    print(f"py-xiaozhi root:   {py_root}")
    print(f"Plugin source:     {source_plugin}")
    print(f"Plugin target:     {target_plugin}")
    print(f"Container target:  {container_path}")
    print()

    if not source_plugin.exists():
        print(f"ERROR: missing plugin source: {source_plugin}")
        return 1

    if not container_path.exists():
        print(f"ERROR: missing py-xiaozhi container.py: {container_path}")
        return 1

    target_plugin.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source_plugin, target_plugin)
    print("OK: copied PCBridgePlugin")

    changed = patch_container(container_path)
    print("OK: patched container.py" if changed else "OK: container.py already patched")

    print()
    print("Next step: restart py-xiaozhi GUI.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
