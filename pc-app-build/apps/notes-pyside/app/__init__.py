"""Desktop application package."""

from __future__ import annotations

import os

# 项目中的 TextField、ScrollBar 等控件会自定义 background/contentItem。
# Windows 原生 Qt Quick Controls Style 不支持这些定制，因此固定使用
# 跨平台且可定制的 Basic Style。
os.environ.setdefault("QT_QUICK_CONTROLS_STYLE", "Basic")

from .bootstrap import run_application


def run_app() -> int:
    """Start the desktop application."""
    return run_application()


__all__ = ["run_app"]