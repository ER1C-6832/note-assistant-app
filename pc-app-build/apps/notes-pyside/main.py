"""
Note Assistant — PySide6 Desktop Application

Entry point for the PC note-taking application.
Launches the main QML-based window and initializes backend services.
"""

import sys
import os

# Ensure the project root is on sys.path so that
# apps, services, and integrations are importable.
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


def main():
    from app import run_app

    run_app()


if __name__ == "__main__":
    main()
