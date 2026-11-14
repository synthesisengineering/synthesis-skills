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
    """Replace a small state file atomically, so a reader never sees half of it; a write that fails leaves no
    temporary file beside it. Each call writes a temporary file of its own: named for the process alone, two
    threads of one process shared it, and a reader could find half a file (2026-11-13, a review)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    mine = object()  # at an address no other call has while this one runs
    tmp = path.with_name(f".{path.name}.{os.getpid()}.{id(mine):x}.tmp")
    try:
        tmp.write_text(json.dumps(data, indent=1, sort_keys=True), encoding="utf-8")
        os.replace(tmp, path)
    finally:
        tmp.unlink(missing_ok=True)  # gone already where the replace was made


WAITS = "harness-approvals.json"  # what was last seen of each harness's hook approval
HOOK_APPROVALS = {"codex hook trust": "codex", "muse hook approval": "muse"}  # the doctor's line: the harness it speaks of


def _waits(note: dict) -> dict:
    import time
    from synthesis import __version__
    seen, found, now = note.get("seen"), {}, time.time()
    for name, entry in seen.items() if isinstance(seen, dict) else ():
        entry = entry if isinstance(entry, dict) else {}
        at, waiting, struck, version = entry.get("at"), entry.get("waiting"), entry.get("struck"), str(entry.get("version") or "")
        try:  # a day old, it says nothing of today; seen under another release, it is news until this one looks
            sound = type(at) in (int, float) and 0 <= now - at and (now - at < 86400 or version != __version__)
        except OverflowError:  # a number no clock gives
            sound = False
        if name in HOOK_APPROVALS and sound and isinstance(waiting, list):
            found[name] = {"at": float(at), "version": version, "waiting": [e for e in waiting if isinstance(e, str)],
                           "struck": {k: v for k, v in (struck.items() if isinstance(struck, dict) else ()) if type(v) in (int, float)},
                           "said": str(entry.get("said") or ""), "untold": entry.get("untold") is True}
    return found


def waits(home_: Path | None = None) -> dict:
    """{the doctor's line: {"at", "version", "waiting", "struck", "said", "untold"}} for each harness whose hook
    approval the doctor has looked at: when it looked, under which release, the hook events that were not running
    then and have not run since, when a hook that ran struck each of its own, and the doctor's line in its own
    words. `untold` is true where that look could not tell: `waiting` is then every hook not seen to run since, and
    `said` is why. An entry of this release says nothing once it is a day old, and each has its own date, so a
    harness nothing looks at any more drops out; one seen under another release is kept, since nothing has looked
    since the release changed. Kept here, not in the doctor, so a hook reads it without loading the doctor."""
    return _waits(read_json((home_ or home()) / "state" / WAITS))


def note_wait(name: str, change, home_: Path | None = None, wait: bool = True) -> None:
    """Change one harness's entry from what the note holds at that moment, under the note's lock: `change` is given
    the entry as `waits` reads it (None where it says nothing) and answers the entry to write, None to leave the
    note as it is, or "drop" to take the entry out. What is written is this release's sight; the other harness's
    entry stays as it was. A hook and the doctor both write here, and neither writes back what it read earlier.
    `change` must not call `note_wait`: the lock belongs to this open of its file, and a second open waits for it,
    in the same process too. With `wait` false, a note that someone holds is left alone: `change` is not called and
    nothing is written (a hook must not wait on the note; its next call makes its strike)."""
    import fcntl
    from synthesis import __version__
    file = (home_ or home()) / "state" / WAITS
    file.parent.mkdir(parents=True, exist_ok=True)
    with open(file.with_suffix(".lock"), "a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX if wait else fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return
        note = read_json(file)
        new = change(_waits(note).get(name))
        if new is not None:
            seen = {k: v for k, v in (note["seen"].items() if isinstance(note.get("seen"), dict) else ()) if k != name}
            write_json(file, {"seen": seen if new == "drop" else {**seen, name: {**new, "version": __version__}}})


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


def codex_home() -> Path:
    """Codex's own folder: `CODEX_HOME` where it is set, else ~/.codex."""
    return Path(os.environ.get("CODEX_HOME") or Path.home() / ".codex")


def codex_hooks_record() -> Path:
    """What `setup.py plugin --codex-user-hooks` declared in each Codex home's hooks.json, by the path Codex keys it by:
    setup takes out only its own, and the doctor knows whose a declaration is (review round 1 of 5.21.0)."""
    return state() / "codex-user-hooks.json"


def transcript_roots() -> dict:
    """Where each harness writes its record of every session, as the M5 sandbox found them."""
    env, user = os.environ, Path.home()
    return {"claude-code": Path(env.get("CLAUDE_CONFIG_DIR") or user / ".claude") / "projects",
            "codex": codex_home() / "sessions",
            "muse": Path(env.get("XDG_DATA_HOME") or user / ".local" / "share") / "muse" / "sessions"}


def desktop_dir() -> Path:
    """The Claude desktop app's data folder: `SYNTHESIS_CLAUDE_DESKTOP_DIR` where it is named (and the scheduled copy
    carries it, as it does each harness's folder), else the macOS one."""
    return Path(os.environ.get("SYNTHESIS_CLAUDE_DESKTOP_DIR") or Path.home() / "Library" / "Application Support" / "Claude")


def desktop_agent_roots(unread: list | None = None) -> list:
    """The `projects` folders of the Claude desktop app's local agent-mode sessions: each such session runs with a
    Claude Code configuration folder of its own (`<app>/local-agent-mode-sessions/<account>/<org>/local_<session>/
    .claude`), which `transcript_roots` never names (the audit of 2026-11-11, gap 14). They are read level by level;
    a folder on the way that cannot be listed goes into `unread` as (folder, why) and is never taken for an empty one
    (the review of 5.18.0: a glob passed such a folder over in silence, and the run stamped itself complete)."""
    found = []

    def listing(folder: Path) -> list:
        try:
            return sorted(p for p in folder.iterdir() if p.is_dir() and not p.is_symlink())
        except (FileNotFoundError, NotADirectoryError):  # a folder that is not there holds no session
            return []
        except OSError as exc:
            if unread is not None:
                unread.append((str(folder), exc.strerror or str(exc)))
            return []
    for account in listing(desktop_dir() / "local-agent-mode-sessions"):
        for org in listing(account):
            for session in (s for s in listing(org) if s.name.startswith("local_")):
                for config in (c for c in listing(session) if c.name == ".claude"):
                    found += [p for p in listing(config) if p.name == "projects"]
    return found


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
