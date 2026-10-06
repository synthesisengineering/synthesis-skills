"""Where v5 keeps its small amount of state and config."""

from __future__ import annotations

import json
import os
from pathlib import Path


def home() -> Path:
    return Path(os.environ.get("SYNTHESIS_HOME") or Path.home() / ".synthesis" / "v5")


def state() -> Path:
    return home() / "state"


def config_file() -> Path:
    return home() / "config.json"


def config() -> dict:
    """Merged config: public defaults, then the user's file. Missing file is fine."""
    try:
        return json.loads(config_file().read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}


def session_id(payload: dict | None = None) -> str:
    """The harness's own session id: from a hook payload, else the environment."""
    if payload and payload.get("session_id"):
        return str(payload["session_id"])
    for key in ("SYNTHESIS_SESSION", "CLAUDE_CODE_SESSION_ID", "CODEX_THREAD_ID", "MUSE_SESSION_ID"):
        if os.environ.get(key):
            return os.environ[key]
    return ""


def harness() -> str:
    if os.environ.get("CLAUDECODE") or os.environ.get("CLAUDE_CODE_SESSION_ID"):
        return "claude-code"
    if os.environ.get("CODEX_THREAD_ID"):
        return "codex"
    if os.environ.get("MUSE_SESSION_ID") or os.environ.get("MUSE_PLUGIN_ROOT"):
        return "muse"
    return "unknown"
