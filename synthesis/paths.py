"""Where v5 keeps its small amount of state and config, and where each harness keeps its sessions."""

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


def line_allowances(config: dict) -> Path | None:
    """The commit lines the principal approved: `line_allowances`, else line-allowances.json beside the commit policy."""
    given = config.get("line_allowances") or (config.get("commit_policy") and Path(str(config["commit_policy"])).with_name("line-allowances.json"))
    return Path(os.path.expanduser(str(given))) if given else None


def read_json(path: Path) -> dict:
    """A small state file's object; {} when it is missing, unreadable or not an object."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def write_json(path: Path, data: dict) -> None:
    """Replace a small state file atomically, so a reader never sees half of it."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    tmp.write_text(json.dumps(data, indent=1, sort_keys=True), encoding="utf-8")
    os.replace(tmp, path)


def inside(path: str, root: str) -> bool:
    return path == root or path.startswith(root.rstrip(os.sep) + os.sep)


def session_id(payload: dict | None = None) -> str:
    """The harness's own session id: from a hook payload, else the environment."""
    if payload and payload.get("session_id"):
        return str(payload["session_id"])
    for key in ("SYNTHESIS_SESSION", "CLAUDE_CODE_SESSION_ID", "CODEX_THREAD_ID", "MUSE_SESSION_ID"):
        if os.environ.get(key):
            return os.environ[key]
    return ""


def transcript_roots() -> dict:
    """Where each harness writes its record of every session, as the M5 sandbox found them."""
    env, user = os.environ, Path.home()
    return {"claude-code": Path(env.get("CLAUDE_CONFIG_DIR") or user / ".claude") / "projects",
            "codex": Path(env.get("CODEX_HOME") or user / ".codex") / "sessions",
            "muse": Path(env.get("XDG_DATA_HOME") or user / ".local" / "share") / "muse" / "sessions"}


def harness(payload: dict | None = None) -> str:
    """The harness running this process: where its transcript lives, else its environment. Codex sets
    CODEX_THREAD_ID in its shell but not in hook processes, so a hook knows Codex by its rollout file."""
    where = str((payload or {}).get("transcript_path") or "")
    for name, root in transcript_roots().items():
        if inside(where, str(root)) or (name == "codex" and os.path.basename(where).startswith("rollout-")):
            return name
    if os.environ.get("CLAUDECODE") or os.environ.get("CLAUDE_CODE_SESSION_ID"):
        return "claude-code"
    if os.environ.get("CODEX_THREAD_ID"):
        return "codex"
    if os.environ.get("MUSE_SESSION_ID") or os.environ.get("MUSE_PLUGIN_ROOT"):
        return "muse"
    return "unknown"
