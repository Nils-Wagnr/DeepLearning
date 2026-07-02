"""Environment configuration shared by command-line entry points."""

from __future__ import annotations

from pathlib import Path


def load_environment(dotenv_path: str | Path | None = None) -> bool:
    """Load a local ``.env`` file when python-dotenv is installed."""

    try:
        from dotenv import load_dotenv
    except ImportError:
        return False
    return bool(load_dotenv(dotenv_path=dotenv_path, override=False))
