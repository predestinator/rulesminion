"""Project paths and environment loading. Never logs secret values."""

from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATE_DIR = Path(os.environ.get("RULESMINION_STATE", ROOT / "state"))
SNAPSHOT_DIR = STATE_DIR / "snapshots"
ENV_PATH = ROOT / ".env"
OPENMINION_DIR = ROOT / ".openminion"
AGENTS_JSON = Path(os.environ.get("OPENMINION_CONFIG", OPENMINION_DIR / "agents.json"))


def load_env() -> None:
    """Load key=value pairs from .env without overriding a real process env."""
    if ENV_PATH.is_file():
        for raw in ENV_PATH.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip("'").strip('"')
            if key:
                os.environ.setdefault(key, value)
    os.environ.setdefault("OPENMINION_HOME", str(ROOT))
    os.environ.setdefault("OPENMINION_DATA_ROOT", str(OPENMINION_DIR))


def gemini_key_loaded() -> bool:
    return bool(os.environ.get("GEMINI_API_KEY", "").strip())
