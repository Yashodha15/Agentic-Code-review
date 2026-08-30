"""Environment settings shared by API and worker entry points."""

from __future__ import annotations

import os
from pathlib import Path


def required_environment(name: str) -> str:
    """Read a required setting and fail with a deployment-focused message."""

    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"Required environment variable is missing: {name}")
    return value


def database_path() -> Path:
    """Resolve the durable database path and create its parent directory."""

    path = Path(os.getenv("AEGIS_DATABASE_PATH", "./data/aegis.db"))
    path.parent.mkdir(parents=True, exist_ok=True)
    return path

