"""Where v5 keeps its small amount of state and config, and where each harness keeps its sessions."""

from __future__ import annotations

import json
import os
import unicodedata
from pathlib import Path


def home() -> Path:
    return Path(os.environ.get("SYNTHESIS_HOME") or Path.home() / ".synthesis" / "v5")


def account_home() -> Path:
    """This account's home as the system's user database names it, never HOME, which a command sets for itself (A9)."""
    import pwd
    return Path(pwd.getpwuid(os.getuid()).pw_dir)


def state() -> Path:
    return home() / "state"


def board() -> Path:
    """Sessions, claims, messages and the snapshot journal: with the outbox, the v5 folders a sandboxed agent may
    write (Codex's writable roots), so nothing in it grants anything. Approvals and send windows are in approvals()."""
    return home() / "board"


def approvals() -> Path:
    """The sealed records every approval rests on (the guard's sandbox, the principal's rulings of 2026-11-15): grants,
    the hook's requests, the map of each session's record, the send window and ledger, deploys, desktop, browser and
    turn-end records, the approved commit lines. Only the hook writes here; each harness's sandbox keeps every shell out."""
    return home() / "approvals"


def install_dir() -> Path:
    """Sealed like approvals(): what only the installer writes (setup's record of the Codex hooks it declared)."""
    return home() / "install"


def requests() -> Path:
    """Requests a shell files: a request grants nothing until the principal types its code, so a shell may write it."""
    return state() / "requests"


# Each sealed record's name in state/, where releases before the sandbox kept it, and its name in approvals/: the
# installer, at the switch, and the first hook that finds the old layout move it once, until `moved` (install.move_approvals).
MOVED = {"approvals": "grants", "approval-requests": "requests", "transcripts": "records", "approvals.lock": "lock", "sends": "sends",
         "deploys": "deploys", "desktop": "desktop", "typed": "typed", "imessage-sends": "imessage-sends", "stop": "stop",
         "browser.json": "browser.json", "browser-accounts.json": "browser-accounts.json",
         "browser-accounts.lock": "browser-accounts.lock", "release-grants": "release-grants"}


def moved(home_folder: Path | None = None) -> bool:
    """Whether the sealed records are in approvals(): the move's last write is the store of approved lines, so what an
    install writes there before its switch, such as the code it answered, never stops the move (review round 1 of 5.25.0,
    finding 3). After it, a file in an old place is a shell's and never moves in."""
    return os.path.lexists((home_folder or home()) / "approvals" / "line-allowances.json")


def old_approvals() -> list[str]:
    """Sealed records left in state() by a release before the sandbox, and approved lines the config placed elsewhere,
    until they are moved (one lstat on every hook call after the move)."""
    if moved():
        return []
    try:
        lines = old_line_allowances(config())
    except (OSError, ValueError):
        lines = None
    return [name for name in (*MOVED, "codex-user-hooks.json") if os.path.lexists(state() / name)] + [
        "line-allowances.json"] * bool(lines and lines.is_file()) + ["registrations.json"] * os.path.lexists(home() / "registrations.json")


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


def line_allowances() -> Path:
    """The commit lines the principal approved, sealed: the hook adds a line once his code for it is read in his record."""
    return approvals() / "line-allowances.json"


def old_line_allowances(config: dict) -> Path | None:
    """Where releases before the sandbox kept the approved lines: `line_allowances`, else beside the commit policy. Read
    once, by the move into approvals()."""
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


SPELLED: dict = {}  # each path as compared, kept: the guard compares the same few protected paths many times a call (22.26)


def spelled(path: str) -> str:
    """A path as a Mac's file system compares it: neither the case of a letter nor the form an accent is written in
    makes it another file (2026-11-11: a protected file named in capitals was written)."""
    key = str(path)
    found = SPELLED.get(key)
    if found is None:
        if len(SPELLED) > 1 << 16:
            SPELLED.clear()
        found = SPELLED[key] = unicodedata.normalize("NFD", key).casefold()
    return found


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


# Where a harness's own command is found besides PATH, in each vendor's stable install locations (2026-10-30): the
# doctor and the release tool look there, and the guard holds an agent's write there for the principal's code (22.26).
PROGRAM_DIRS = ("~/.local/bin", "/opt/homebrew/bin", "/usr/local/bin")
PROGRAM_PLACES = {"codex": tuple(f"/Applications/{app}.app/Contents/Resources/{p}" for p in ("codex-cli/bin/codex", "codex")
                                 for app in ("ChatGPT", "Codex")),
                  "claude": ("~/Library/Application Support/Claude/claude-code/*/*/claude.app/Contents/MacOS/claude",)}


def codex_home() -> Path:
    """Codex's own folder: `CODEX_HOME` where it is set, else ~/.codex."""
    return Path(os.environ.get("CODEX_HOME") or Path.home() / ".codex")


def codex_hooks_record() -> Path:
    """What `setup.py plugin --codex-user-hooks` declared in each Codex home's hooks.json, by the path Codex keys it by:
    setup takes out only its own, and the doctor knows whose a declaration is (review round 1 of 5.21.0)."""
    return install_dir() / "codex-user-hooks.json"


# Each harness's own install locations: where the doctor finds its command line, and the only programs, beside its name
# on PATH, the judge runs for it (review round 1 of 21.3: a setting never chooses what the Stop hook runs).
INSTALLS = {h: tuple(f"{d}/{h}" for d in PROGRAM_DIRS) + PROGRAM_PLACES.get(h, ()) for h in ("claude", "codex", "muse")}


def expand_install(candidate: str) -> list:
    """A location as it is, or a pattern's matches with the newest version folder first."""
    if "*" not in candidate:
        return [candidate]
    import glob
    import re

    def newest(path: str) -> tuple:
        return max((tuple(map(int, p.split("."))) for p in Path(path).parts if re.fullmatch(r"\d+(\.\d+)+", p)), default=())
    return sorted(glob.glob(os.path.expanduser(candidate)), key=newest, reverse=True)


def transcript_roots() -> dict:
    """Where each harness writes its record of every session, as the M5 sandbox found them."""
    env, user = os.environ, Path.home()
    return {"claude-code": Path(env.get("CLAUDE_CONFIG_DIR") or user / ".claude") / "projects",
            "codex": codex_home() / "sessions",
            "muse": Path(env.get("XDG_DATA_HOME") or user / ".local" / "share") / "muse" / "sessions"}


HOMES_KEPT = "claude-homes.json"  # in approvals(): the other Claude folders the last config the hook read in full named


def resolved(path) -> str:
    """A folder as two are compared: where it really leads, `~` read, spelled as a Mac's file system compares names, so
    a link to a folder, or its name in other capitals, is that folder (review round 1 of C2, N2)."""
    return spelled(os.path.realpath(os.path.expanduser(str(path))))


def _named_homes(config: dict, base: Path | None = None) -> tuple:
    """(the folders, why each other value names none, whether the config names any) of what the config gives as other
    Claude accounts' folders: each value of `claude_homes` and each `browser_routing` workspace's `claude_home`, each read
    on its own, `~/` read as `base` (default: this home), once each as `resolved` compares them."""
    listed, routing = config.get("claude_homes", []), config.get("browser_routing")
    spaces = routing.get("workspaces") if isinstance(routing, dict) else None
    values = (listed if isinstance(listed, list) else [listed]) + [
        m["claude_home"] for m in (spaces.values() if isinstance(spaces, dict) else ()) if isinstance(m, dict) and "claude_home" in m]
    found, problems, home = {}, [] if isinstance(listed, list) else ["claude_homes must be a list of folders"], str(base or Path.home())
    for value in values:
        text = value.strip() if isinstance(value, str) else ""
        folder = Path(os.path.normpath(home + text[1:] if text[:2] == "~/" else text)) if text.startswith(("/", "~/")) else None
        if folder is None:
            problems.append(f"it names {value!r}, which is no absolute or ~/ path")
        elif resolved(folder) == resolved(Path(home) / ".claude"):
            problems.append("it names ~/.claude, the default home, by that name, another spelling or a link: name only the "
                            "folders of other Claude accounts")
        else:
            found.setdefault(resolved(folder), folder)
    return list(found.values()), problems, "claude_homes" in config or bool(values)


def claude_homes(config: dict, base: Path | None = None) -> list:
    """The Claude Code configuration folders of other Claude accounts the config names, each one a seat runs from with
    `CLAUDE_CONFIG_DIR` set to it (C2, 2026-11-20): every folder in `claude_homes` and every one a `browser_routing`
    workspace binds with `claude_home`, once each (`_named_homes`). ValueError, saying why, for a list of another shape,
    a value that is no absolute or `~/` path, or ~/.claude, the default home, whose sessions share one extension pairing
    with every folder the config does not name."""
    found, problems, _ = _named_homes(config, base)
    if problems:
        raise ValueError(problems[0])
    return found


def claude_dirs(config: dict | None, strict: bool = False) -> list:
    """Every Claude Code configuration folder synthesis serves, once each as `resolved` compares them: the one this
    process's harness names (`CLAUDE_CONFIG_DIR`, else ~/.claude), then, where the config names any Claude home,
    ~/.claude and each folder named, in that order also when a seat's own process names one of them, so that what is
    built from the list (the sealed set setup stages) reads the same from any process. A value that names no folder
    drops none of the others, and the folders of the last config the hook read in full (`homes_kept`) are kept with
    them, so a config that cannot be read drops none either (review round 1 of C2, B1). With `strict`, the config's own
    folders alone, and ValueError says why a value names none."""
    own, (found, problems, named) = Path(os.environ.get("CLAUDE_CONFIG_DIR") or Path.home() / ".claude"), _named_homes(config or {})
    if strict and problems:
        raise ValueError(problems[0])
    others, kept = found + ([] if strict else homes_kept()), {}
    for folder in [own] * (resolved(own) not in {resolved(o) for o in others}) + [Path.home() / ".claude"] * bool(named or others) + others:
        kept.setdefault(resolved(folder), folder)
    return list(kept.values())


def homes_kept() -> list:
    """The other Claude accounts' folders the last config the hook read in full named (`keep_homes`): what the guard keeps
    while the config cannot be read, or names a folder wrongly."""
    listed = read_json(approvals() / HOMES_KEPT).get("homes")
    return [Path(h) for h in listed if isinstance(h, str) and os.path.isabs(h)] if isinstance(listed, list) else []


def homes_unread() -> dict:
    """The config a call is judged under while the file cannot be read: one that names, beside the folders the last
    config read in full named (`homes_kept`, which `claude_dirs` adds), each ~/.claude* folder in the home, as another
    account's is named, so that no process falls back to its own folder alone (review round 1 of C2, B1)."""
    return {"claude_homes": [str(folder) for folder in Path.home().glob(".claude?*") if folder.is_dir()]}


def keep_homes(config: dict) -> None:
    """The hook's record, in the sealed approvals folder, of the other Claude folders a config it read in full names. A
    config with a value that names no folder leaves the record as it was, and so does a record that cannot be written."""
    try:
        listed = [str(home) for home in claude_homes(config)]
        if (read_json(approvals() / HOMES_KEPT).get("homes") or []) != listed:
            write_json(approvals() / HOMES_KEPT, {"homes": listed})
    except (ValueError, OSError):
        pass


def harness_settings(claude: tuple = ()) -> list:
    """Each harness's hook and sandbox settings, and the launch agents that run with full access: what an approval rests
    on as much as the runtime does, so a write there waits for the principal's code (the guard's sandbox, design 2.1).
    The plugin caches are not among them: the skills' scripts run from there, and the sandbox seals them for a shell.
    `claude`: the Claude Code folders whose settings these are (default: the one this process's harness names)."""
    env, user = os.environ, Path.home()
    claude, muse = [Path(c) for c in claude] or [Path(env.get("CLAUDE_CONFIG_DIR") or user / ".claude")], Path(env.get("XDG_CONFIG_HOME") or user / ".config") / "muse"
    return [p for c in claude for p in (c / "settings.json", c / "settings.local.json")] + [
        codex_home() / "config.toml", codex_home() / "hooks.json", muse, user / "Library" / "LaunchAgents"]


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
