"""Where v5 keeps its small amount of state and config, and where each harness keeps its sessions."""

from __future__ import annotations

import json
import os
import unicodedata
from pathlib import Path


def home() -> Path:
    return Path(os.environ.get("SYNTHESIS_HOME") or Path.home() / ".synthesis" / "v5")


def state() -> Path:
    return home() / "state"


def board() -> Path:
    """Sessions, claims, messages and the snapshot journal: with the outbox, the v5 folders a sandboxed agent may
    write (Codex's writable roots), so nothing in it grants anything. Approvals and send windows stay in state()."""
    return home() / "board"


def sessions() -> Path:
    """Agent session transcripts from every harness, in one form (sessions.py); only the exporter writes here."""
    return home() / "sessions"


def outbox() -> Path:
    """Where an agent stages a file before attaching it to a message: the one folder the workspace-mcp connector is
    started to read (its start.sh names it in ALLOWED_FILE_DIRS), so the send guard passes a file here."""
    return home() / "outbox"


BOARD_FILES = ("sessions", "messages", "sent", "read", "claims.jsonl", "claims.lock", "journal.jsonl")


def old_board() -> list[str]:
    """Board entries left in state(), where releases before 5.1.18 kept them: install.move_board merges them."""
    return [name for name in BOARD_FILES if os.path.lexists(state() / name)]


def config_file() -> Path:
    return home() / "config.json"


class Unreadable(ValueError):
    """The config file is there and holds no settings: it is not JSON, or it is JSON that is no object."""


def config() -> dict:
    """Merged config: public defaults, then the user's file. Missing file is fine; JSON that is no object is unreadable."""
    try:
        found = json.loads(config_file().read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    except ValueError as exc:
        raise Unreadable(str(exc)) from None
    if not isinstance(found, dict):
        raise Unreadable(f"{config_file()} is not a JSON object")
    return found


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


WAITS = "harness-approvals.json"  # what was last seen of each harness's hook approval
HOOK_APPROVALS = {"codex hook trust": "codex", "muse hook approval": "muse"}  # the doctor's line: the harness it speaks of


def waits(home_: Path | None = None) -> dict:
    """{the doctor's line: {"at", "version", "waiting", "struck"}} for each harness whose hook approval the doctor saw
    within a day: when it looked, under which release, the hook events that waited then and have not run since,
    and when a hook that ran last struck one. An older sight says nothing of today, and each entry has its own
    date, so a harness nothing looks at any more drops out. Kept here, not in the doctor, so a hook reads it
    without loading the doctor."""
    import time
    seen, found = read_json((home_ or home()) / "state" / WAITS).get("seen"), {}
    for name, entry in seen.items() if isinstance(seen, dict) else ():
        at, waiting = (entry.get("at"), entry.get("waiting")) if isinstance(entry, dict) else (None, None)
        try:
            fresh = type(at) in (int, float) and 0 <= time.time() - at < 86400
        except OverflowError:  # a number no clock gives
            fresh = False
        if name in HOOK_APPROVALS and fresh and isinstance(waiting, list):
            struck = entry.get("struck")
            found[name] = {"at": float(at), "version": str(entry.get("version") or ""), "waiting": [e for e in waiting if isinstance(e, str)],
                           "struck": float(struck) if type(struck) in (int, float) and abs(struck) < 1e12 else 0.0}
    return found


def note_wait(name: str, waiting: list, at: float | None = None, struck: float = 0.0, home_: Path | None = None) -> None:
    """Write down what was seen of one harness's hook approval, under this release: the doctor's look at `at`, or
    a hook that ran and struck its own event at `struck`. The other harness's entry stays as it was."""
    import time
    from synthesis import __version__
    file = (home_ or home()) / "state" / WAITS
    seen = read_json(file).get("seen")
    write_json(file, {"seen": {**(seen if isinstance(seen, dict) else {}),
                               name: {"at": time.time() if at is None else at, "version": __version__, "waiting": waiting, "struck": struck}}})


def spelled(path: str) -> str:
    """A path as a Mac's file system compares it: neither the case of a letter nor the form an accent is written in
    makes it another file (2026-11-11: a protected file named in capitals was written)."""
    return unicodedata.normalize("NFD", str(path)).casefold()


def inside(path: str, root: str) -> bool:
    path, root = spelled(path), spelled(root).rstrip(os.sep)
    return path == root or path.startswith(root + os.sep)


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


def harness(payload: dict | None = None, by_env: bool = True) -> str:
    """The harness running this process: where its transcript lives, else its environment. Codex sets
    CODEX_THREAD_ID in its shell but not in hook processes, so a hook knows Codex by its rollout file. Without
    `by_env`, only the transcript a harness hands its own hook counts: a command run from a harness's shell carries
    that harness's environment and is no hook of it."""
    where = str((payload or {}).get("transcript_path") or "")
    for name, root in transcript_roots().items():
        if inside(where, str(root)) or (name == "codex" and os.path.basename(where).startswith("rollout-")):
            return name
    if not by_env:
        return "unknown"
    if os.environ.get("CLAUDECODE") or os.environ.get("CLAUDE_CODE_SESSION_ID"):
        return "claude-code"
    if os.environ.get("CODEX_THREAD_ID"):
        return "codex"
    if os.environ.get("MUSE_SESSION_ID") or os.environ.get("MUSE_PLUGIN_ROOT"):
        return "muse"
    return "unknown"
