"""Coordination board: who is working where, and messages between sessions (R2).

Each session is one small JSON file, so no hook ever re-reads a large shared
file. A claim is an absolute path; a trailing "/**" claims the whole subtree.
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

from synthesis import paths

STALE_SECONDS = 8 * 3600


@dataclass
class Session:
    session: str
    harness: str = ""
    project: str = ""
    goal: str = ""
    cwd: str = ""
    claims: list[str] = field(default_factory=list)
    started: float = 0.0
    seen: float = 0.0

    @property
    def stale(self) -> bool:
        return time.time() - self.seen > STALE_SECONDS


class ClaimConflict(Exception):
    pass


def _session_file(session_id: str) -> Path:
    safe = "".join(c if c.isalnum() or c in "-_." else "_" for c in session_id)
    if not safe:
        raise ValueError("session id is empty")
    return paths.state() / "sessions" / f"{safe}.json"


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    tmp.write_text(json.dumps(data, indent=1, sort_keys=True), encoding="utf-8")
    os.replace(tmp, path)


def load(session_id: str) -> Session | None:
    try:
        data = json.loads(_session_file(session_id).read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return None
    return Session(**{k: v for k, v in data.items() if k in Session.__dataclass_fields__})


def save(session: Session) -> None:
    _write_json(_session_file(session.session), asdict(session))


def sessions() -> list[Session]:
    directory = paths.state() / "sessions"
    found = []
    for file in sorted(directory.glob("*.json")) if directory.is_dir() else []:
        try:
            data = json.loads(file.read_text(encoding="utf-8"))
            found.append(Session(**{k: v for k, v in data.items() if k in Session.__dataclass_fields__}))
        except (json.JSONDecodeError, TypeError):
            continue
    return found


def touch(session_id: str, **updates) -> Session:
    """Register or refresh a session; updates only the given fields."""
    now = time.time()
    session = load(session_id) or Session(session=session_id, started=now)
    for key, value in updates.items():
        if value is not None:
            setattr(session, key, value)
    session.seen = now
    save(session)
    return session


def _parts(claim: str) -> tuple[tuple[str, ...], bool]:
    subtree = claim.endswith("/**")
    base = claim[:-3] if subtree else claim
    return Path(os.path.realpath(os.path.expanduser(base))).parts, subtree


def overlaps(a: str, b: str) -> bool:
    (pa, sa), (pb, sb) = _parts(a), _parts(b)
    if pa == pb:
        return True
    if sa and pb[: len(pa)] == pa:
        return True
    if sb and pa[: len(pb)] == pb:
        return True
    return False


def holders(path: str, *, exclude: str = "") -> list[Session]:
    """Live sessions other than `exclude` whose claims cover or overlap `path`."""
    return [s for s in sessions()
            if s.session != exclude and not s.stale and any(overlaps(c, path) for c in s.claims)]


def claim(session_id: str, claims: list[str], *, take_stale: bool = False, **updates) -> Session:
    normalized = [c if c.endswith("/**") else os.path.realpath(os.path.expanduser(c)) for c in claims]
    for c in normalized:
        for other in sessions():
            if other.session == session_id or not any(overlaps(c, o) for o in other.claims):
                continue
            if other.stale and take_stale:
                other.claims = [o for o in other.claims if not overlaps(c, o)]
                save(other)
                message(other.session, session_id, f"Took over your stale claim on {c}.")
                continue
            raise ClaimConflict(
                f"{c} overlaps a claim held by {other.session} ({other.harness}, project "
                f"{other.project or '-'}: {other.goal or 'no goal'})"
                + ("; it is stale, retry with --take" if other.stale else ""))
    session = touch(session_id, **updates)
    session.claims = sorted(set(session.claims) | set(normalized))
    save(session)
    return session


def release(session_id: str, claims: list[str] | None = None) -> Session | None:
    session = load(session_id)
    if session is None:
        return None
    session.claims = [] if claims is None else [c for c in session.claims if c not in claims]
    save(session)
    return session


def message(to: str, sender: str, text: str) -> Path:
    """Address a session id or `project:<id>`; the recipient reads it at its next start."""
    safe = "".join(c if c.isalnum() or c in "-_.:" else "_" for c in to).replace(":", "__")
    path = paths.state() / "messages" / safe / f"{time.time_ns()}-{os.getpid()}.json"
    _write_json(path, {"to": to, "from": sender, "at": time.time(), "text": text})
    return path


def inbox(session_id: str, project: str = "", *, mark_read: bool = False) -> list[dict]:
    boxes = [session_id] + ([f"project:{project}"] if project else [])
    found = []
    for box in boxes:
        directory = paths.state() / "messages" / box.replace(":", "__")
        for file in sorted(directory.glob("*.json")) if directory.is_dir() else []:
            read_marker = paths.state() / "read" / session_id / file.name
            if read_marker.exists():
                continue
            found.append(json.loads(file.read_text(encoding="utf-8")))
            if mark_read:
                read_marker.parent.mkdir(parents=True, exist_ok=True)
                read_marker.touch()
    return found
