"""Coordination board: who is working where, and messages between sessions (R2).

Each session is one small JSON file, so no hook ever re-reads a large shared
file. A claim is an absolute path; a trailing "/**" claims the whole subtree.
A message goes to exactly one live session, named by its id, its short name or
`project:<id>`; an address that names none or several is refused, never guessed.
"""

from __future__ import annotations

import base64
import hashlib
import json
from contextlib import contextmanager
import os
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

from synthesis import paths

STALE_SECONDS = 8 * 3600
BROADCAST_SECONDS = 3600


def short_name(session_id: str) -> str:
    """Six letters and digits from a hash of the id: harness ids that share a
    prefix (UUIDv7 ids start with their creation time) still get distinct names."""
    return base64.b32encode(hashlib.sha256(session_id.encode("utf-8")).digest()).decode()[:6].lower()


@dataclass
class Session:
    session: str
    short: str = ""
    harness: str = ""
    project: str = ""
    goal: str = ""
    cwd: str = ""
    claims: list[str] = field(default_factory=list)
    started: float = 0.0
    seen: float = 0.0

    def __post_init__(self):
        self.short = self.short or short_name(self.session)

    @property
    def stale(self) -> bool:
        return time.time() - self.seen > STALE_SECONDS


class ClaimConflict(Exception):
    pass


class AddressError(ValueError):
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


@contextmanager
def _claim_lock():
    """One claim decision at a time, so two sessions can't both win the same path."""
    import fcntl

    path = paths.state() / "claims.lock"
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)


def claim(session_id: str, claims: list[str], *, take_stale: bool = False, **updates) -> Session:
    with _claim_lock():
        return _claim(session_id, claims, take_stale=take_stale, **updates)


def _claim(session_id: str, claims: list[str], *, take_stale: bool = False, **updates) -> Session:
    normalized = [c if c.endswith("/**") else os.path.realpath(os.path.expanduser(c)) for c in claims]
    for c in normalized:
        for other in sessions():
            if other.session == session_id or not any(overlaps(c, o) for o in other.claims):
                continue
            if other.stale and take_stale:
                other.claims = [o for o in other.claims if not overlaps(c, o)]
                save(other)
                notify(other.session, session_id, f"Took over your stale claim on {c}.")
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


def _describe(found: list[Session]) -> str:
    now = time.time()
    return "".join(f"\n  {s.session} (short {s.short}, project {s.project or '-'}, {s.harness or 'harness ?'}, "
                   f"last seen {int((now - s.seen) / 60)} min ago{', stale' if s.stale else ''})"
                   for s in found[:20]) + (f"\n  ... and {len(found) - 20} more" if len(found) > 20 else "")


def resolve(address: str, *, exclude: str = "") -> Session:
    """The one live session an address names: its session id, its short name, or
    `project:<id>`. Zero or several matches raise AddressError listing the candidates."""
    address = address.strip()
    pool = [s for s in sessions() if s.session != exclude]
    if address.startswith("project:"):
        matches = [s for s in pool if s.project and s.project == address[len("project:"):]]
    else:
        matches = [s for s in pool if address and address in (s.session, s.short)]
    alive = [s for s in matches if not s.stale]
    if len(alive) == 1:
        return alive[0]
    if alive:
        raise AddressError(f"{address!r} names {len(alive)} live sessions; nothing was sent. "
                           f"Address one of them by session id:{_describe(alive)}")
    if matches:
        raise AddressError(f"{address!r} names only stale sessions; nothing was sent:{_describe(matches)}")
    others = [s for s in pool if not s.stale]
    raise AddressError(f"{address!r} names no live session; nothing was sent. Addresses are a session id, "
                       "its short name or project:<id> (display names and titles are not addresses). "
                       + (f"Live sessions:{_describe(others)}" if others else "No other session is live."))


def _box(address: str) -> Path:
    safe = "".join(c if c.isalnum() or c in "-_.:" else "_" for c in address).replace(":", "__")
    return paths.state() / "messages" / safe


def _post(box: str, data: dict) -> Path:
    path = _box(box) / f"{time.time_ns()}-{os.getpid()}.json"
    _write_json(path, {**data, "at": time.time()})
    return path


def notify(session_id: str, sender: str, text: str) -> Path:
    """A notice to one exact session id, live or stale: used when taking over or releasing its claims."""
    return _post(session_id, {"to": session_id, "from": sender, "text": text})


def message(to: str, sender: str, text: str, *, durable: bool = False) -> Path:
    """Deliver to the one live session `to` names; it sees the message at its next prompt.

    A durable message to `project:<id>` instead reaches every session that works on
    the project, now or later, once each. A project-addressed message that is not
    durable is never replayed to a session that joins the project afterwards.
    """
    if not sender:
        raise AddressError("a message must carry the sender's session id")
    if not text.strip():
        raise AddressError("the message is empty")
    if durable:
        from synthesis import project  # imported here: project imports this module

        name = to[len("project:"):] if to.startswith("project:") else ""
        if not name:
            raise AddressError("a durable message goes to project:<id>")
        if project.find(name) is None and not any(s.project == name for s in sessions()):
            raise AddressError(f"no project named {name!r} is on the board or in the knowledge roots; nothing was sent")
        return _post(to, {"to": to, "from": sender, "text": text, "durable": True})
    target = resolve(to, exclude=sender)
    digest = hashlib.sha256(text.strip().encode("utf-8")).hexdigest()[:24]
    mark = paths.state() / "sent" / _session_file(sender).stem / digest
    try:
        earlier = json.loads(mark.read_text(encoding="utf-8"))
    except (FileNotFoundError, ValueError):
        earlier = {}
    if earlier.get("to", target.session) != target.session and time.time() - earlier.get("at", 0) < BROADCAST_SECONDS:
        raise AddressError(f"the same text already went to {earlier['to']}; sending it to {target.session} "
                           "too is a broadcast. Address the project with a durable message instead.")
    _write_json(mark, {"to": target.session, "at": time.time()})
    return _post(target.session, {"to": to, "session": target.session, "from": sender, "text": text})


def inbox(session_id: str, project: str = "", *, mark_read: bool = False) -> list[dict]:
    boxes = [session_id] + ([f"project:{project}"] if project else [])
    found = []
    for box in boxes:
        directory = _box(box)
        for file in sorted(directory.glob("*.json")) if directory.is_dir() else []:
            read_marker = paths.state() / "read" / _session_file(session_id).stem / file.name
            if read_marker.exists():
                continue
            found.append(json.loads(file.read_text(encoding="utf-8")))
            if mark_read:
                read_marker.parent.mkdir(parents=True, exist_ok=True)
                read_marker.touch()
    return found
