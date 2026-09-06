#!/usr/bin/env python3
"""Peer addressing for coordination-board sessions: seats, lanes, receipts, inbox.

Three naming systems cover one population of agent sessions: the board's
identities (UUIDv7 with aliases), each client's chat handle (a desktop
session id, a Codex thread id), and the harness's peer registry (a derived
display name that collides by construction, plus a Unix socket). Only the
board says what a session owns; only the session itself knows all of its
own handles. This module keeps that join and turns it into exact addresses:

- a **seat** is the per-session sidecar of delivery handles written beside
  the board at claim time (identity stays on the board; handles are a cache
  the doctor validates);
- a **lane** is one exact way to deliver to a seat (bus, ccd, harness,
  codex), computed from live truth at resolve time;
- a **receipt** binds a sender to one resolved target and its exact
  per-lane addresses for a bounded time, so the send gate can tell a
  resolved address from a guessed one;
- the **inbox** reads the board's addressed message bus for one seat with a
  per-seat watermark, which is what makes the bus a delivery lane rather
  than a dead letter.

Everything here is pure file I/O over ``~/.synthesis/coordination`` and the
harness registry; nothing sends.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import socket
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

SEATS_DIRNAME = "seats"
RECEIPTS_DIRNAME = "receipts"
INBOX_DIRNAME = "inbox"
SEND_LOG_NAME = "peer-sends.jsonl"
RECEIPT_SCHEMA = 1
SEAT_SCHEMA = 1
RECEIPT_TTL_MINUTES = 20
BROADCAST_WINDOW_MINUTES = 15
DEFAULT_REGISTRY = Path.home() / ".claude" / "sessions"

CLIENT_CLAUDE = "claude-code"
CLIENT_CODEX = "codex"

UUID_RE = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)
MESSAGE_ADDRESS_PREFIX = r"^### → (?P<recipient>.+?), from "
MESSAGE_HEADING_PREFIX = MESSAGE_ADDRESS_PREFIX + r"(?P<sender>.+?) — "
MESSAGE_HEADING = re.compile(MESSAGE_HEADING_PREFIX + r"(?P<timestamp>\S+)\s*$")
# Diagnostics must inspect retained human-written dates to decide whether
# they affect this inbox. Normal delivery retains its single-token grammar.
DIAGNOSTIC_MESSAGE_HEADING = re.compile(MESSAGE_HEADING_PREFIX + r"(?P<timestamp>\S.*?)\s*$")
LEGACY_UNTIMED_HEADING = re.compile(MESSAGE_ADDRESS_PREFIX + r"(?P<sender>[^—\r\n]+?)\s*$")
MESSAGE_HEADING_CANDIDATE = re.compile(r"^###\s+.*?,\s*from\b")
PROTOCOL_HEADING = re.compile(r"^## Protocol(?: \([^()\r\n]+\))?$")


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def iso(moment: datetime) -> str:
    return moment.astimezone(timezone.utc).isoformat(timespec="seconds")


def parse_iso(value: object) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def coordination_root(board: Path) -> Path:
    return Path(board).expanduser().parent


def seats_dir(board: Path) -> Path:
    return coordination_root(board) / SEATS_DIRNAME


def receipts_dir(board: Path) -> Path:
    return coordination_root(board) / RECEIPTS_DIRNAME


def inbox_dir(board: Path) -> Path:
    return coordination_root(board) / INBOX_DIRNAME


def send_log_path(board: Path) -> Path:
    return coordination_root(board) / SEND_LOG_NAME


def safe_name(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", value).strip("._") or "unknown"


def _unique_json_object(pairs: list[tuple[str, object]]) -> dict:
    """Reject ambiguous diagnostic state instead of accepting the last key."""
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate coordination JSON field: {key}")
        result[key] = value
    return result


# --------------------------------------------------------------------------
# Self identity: what the running session knows about its own handles
# --------------------------------------------------------------------------

@dataclass
class SelfIdentity:
    client: str = ""
    harness_session_id: str = ""
    host_session_id: str = ""
    pid: int | None = None
    explicit_ref: str = ""

    @property
    def sender_key(self) -> str:
        """The stable per-session key receipts and inboxes are filed under.

        A Claude Code session is keyed by its harness session id, which the
        hook payload carries as ``session_id`` and the shell carries as
        ``CLAUDE_CODE_SESSION_ID``; a Codex session by its thread id, which
        hooks receive as ``session_id`` and shells learn from the exported
        ``SYNTHESIS_CLIENT_SESSION_REF``. Both halves must agree or the gate
        finds no receipt, which is the safe failure."""
        if self.client == CLIENT_CLAUDE and self.harness_session_id:
            return f"cc:{self.harness_session_id}"
        if self.client == CLIENT_CODEX and self.harness_session_id:
            return f"codex:{self.harness_session_id}"
        if self.explicit_ref:
            return self.explicit_ref
        return ""

    @property
    def primary_ref(self) -> str:
        """The single scheme-prefixed delivery ref the board row carries."""
        if self.explicit_ref:
            return self.explicit_ref
        if self.host_session_id:
            return f"ccd:{self.host_session_id}"
        if self.client == CLIENT_CLAUDE and self.harness_session_id:
            return f"cc:{self.harness_session_id}"
        return ""


def detect_self(environ: dict[str, str] | None = None) -> SelfIdentity:
    env = os.environ if environ is None else environ
    explicit = env.get("SYNTHESIS_CLIENT_SESSION_REF", "").strip()
    harness = env.get("CLAUDE_CODE_SESSION_ID", "").strip()
    host = env.get("CLAUDE_CODE_HOST_SESSION_ID", "").strip()
    pid_text = env.get("CLAUDE_PID", "").strip()
    pid = int(pid_text) if pid_text.isdigit() else None
    if explicit.startswith("codex:"):
        return SelfIdentity(
            client=CLIENT_CODEX,
            harness_session_id=explicit[len("codex:"):],
            explicit_ref=explicit,
            pid=pid,
        )
    if harness or env.get("CLAUDECODE"):
        return SelfIdentity(
            client=CLIENT_CLAUDE,
            harness_session_id=harness,
            host_session_id=host,
            pid=pid,
            explicit_ref=explicit,
        )
    if explicit:
        return SelfIdentity(explicit_ref=explicit, pid=pid)
    return SelfIdentity()


def identity_from_hook(payload: dict, environ: dict[str, str] | None = None) -> SelfIdentity:
    """The sender identity as a hook process sees it.

    A hook runs inside the client process tree with the same environment as
    the shells, plus a payload whose ``session_id`` is authoritative: for
    Claude Code it is the harness session id, for Codex the thread id."""
    env = os.environ if environ is None else environ
    session_id = str(payload.get("session_id") or "").strip()
    base = detect_self(env)
    if not session_id:
        return base
    if base.client == CLIENT_CLAUDE:
        return SelfIdentity(
            client=CLIENT_CLAUDE,
            harness_session_id=session_id,
            host_session_id=base.host_session_id,
            pid=base.pid,
        )
    return SelfIdentity(
        client=CLIENT_CODEX,
        harness_session_id=session_id,
        explicit_ref=f"codex:{session_id}",
    )


# --------------------------------------------------------------------------
# Seats: the per-session sidecar of delivery handles
# --------------------------------------------------------------------------

@dataclass
class Seat:
    session_uuid: str
    compact_id: str
    client: str
    machine: str
    harness_session_id: str = ""
    host_session_id: str = ""
    pid: int | None = None
    cwd: str = ""
    updated_at: str = ""
    schema: int = SEAT_SCHEMA


def seat_path(board: Path, session_uuid: str) -> Path:
    return seats_dir(board) / f"{safe_name(session_uuid)}.json"


def write_seat(
    board: Path,
    *,
    session_uuid: str,
    compact_id: str,
    machine: str,
    identity: SelfIdentity,
    cwd: str = "",
    now: datetime | None = None,
) -> Path | None:
    """Record this session's delivery handles beside its board row.

    Returns None when the session knows no handle at all (nothing to
    register is not an error: such a session is reachable on the bus)."""
    if not (identity.harness_session_id or identity.host_session_id or identity.explicit_ref):
        return None
    seat = Seat(
        session_uuid=session_uuid,
        compact_id=compact_id,
        client=identity.client or (identity.explicit_ref.split(":", 1)[0] if identity.explicit_ref else ""),
        machine=machine,
        harness_session_id=identity.harness_session_id,
        host_session_id=identity.host_session_id,
        pid=identity.pid,
        cwd=cwd or os.getcwd(),
        updated_at=iso(now or utcnow()),
    )
    path = seat_path(board, session_uuid)
    path.parent.mkdir(parents=True, exist_ok=True)
    staging = path.with_suffix(".json.tmp")
    staging.write_text(json.dumps(asdict(seat), indent=2) + "\n", encoding="utf-8")
    os.replace(staging, path)
    return path


def read_seat(board: Path, session_uuid: str, *, strict: bool = False) -> Seat | None:
    return _read_seat_path(seat_path(board, session_uuid), expected_uuid=session_uuid, strict=strict)


def _read_seat_path(path: Path, *, expected_uuid: str | None = None, strict: bool = False) -> Seat | None:
    """Shared reader; ordinary directory discovery retains its filename tolerance."""
    try:
        data = json.loads(
            path.read_text(encoding="utf-8"), object_pairs_hook=_unique_json_object if strict else None
        )
    except FileNotFoundError:
        if strict and path.is_symlink():
            raise
        return None
    except (OSError, ValueError):
        if strict:
            raise
        return None
    if (
        not isinstance(data, dict) or not data.get("session_uuid")
        or (expected_uuid is not None and data.get("session_uuid") != expected_uuid)
    ):
        if strict:
            raise ValueError(f"invalid coordination seat: {path}")
        return None
    if strict:
        required = ("session_uuid", "compact_id", "client", "machine")
        string_fields = (*required, "harness_session_id", "host_session_id", "cwd", "updated_at")
        if (
            type(data.get("schema")) is not int or data["schema"] != SEAT_SCHEMA
            or any(not isinstance(data.get(key), str) or not data[key] for key in required)
            or any(key in data and not isinstance(data[key], str) for key in string_fields)
            or not UUID_RE.fullmatch(data["session_uuid"])
            or (data.get("pid") is not None and (type(data["pid"]) is not int or data["pid"] <= 0))
        ):
            raise ValueError(f"invalid coordination seat fields: {path}")
        from coordination_schema import identity_from_uuid

        if data["compact_id"] != identity_from_uuid(data["session_uuid"]).compact_id:
            raise ValueError(f"coordination seat identity mismatch: {path}")
    known = {field for field in Seat.__dataclass_fields__}
    return Seat(**{key: value for key, value in data.items() if key in known})


def remove_seat(board: Path, session_uuid: str) -> bool:
    path = seat_path(board, session_uuid)
    try:
        path.unlink()
    except FileNotFoundError:
        return False
    return True


def all_seats(board: Path, *, strict: bool = False) -> list[Seat]:
    directory = seats_dir(board)
    if strict:
        try:
            # glob/is_dir may suppress filesystem errors; diagnostics must
            # distinguish an absent optional directory from an unreadable one.
            paths = sorted(path for path in directory.iterdir() if path.suffix == ".json")
        except FileNotFoundError:
            if directory.is_symlink():
                raise
            return []
    else:
        if not directory.is_dir():
            return []
        paths = sorted(directory.glob("*.json"))
    seats = []
    for path in paths:
        if strict and not UUID_RE.fullmatch(path.stem):
            raise ValueError(f"invalid coordination seat filename: {path}")
        seat = _read_seat_path(path, expected_uuid=path.stem if strict else None, strict=strict)
        if seat is not None:
            seats.append(seat)
    return seats


def seat_for_identity(board: Path, identity: SelfIdentity, *, strict: bool = False) -> Seat | None:
    """This session's own seat, found by the handle a hook or shell knows."""
    matches = []
    for seat in all_seats(board, strict=strict):
        harness_match = (
            identity.harness_session_id and seat.harness_session_id == identity.harness_session_id
            and (seat.client == identity.client or not identity.client)
        )
        host_match = identity.host_session_id and seat.host_session_id == identity.host_session_id
        if harness_match or host_match:
            if not strict:
                return seat
            matches.append(seat)
    if len(matches) > 1:
        raise ValueError("multiple coordination seats match this session's identity")
    return matches[0] if matches else None


# --------------------------------------------------------------------------
# Harness peer registry (Claude Code): sessionId -> socket, name, pid
# --------------------------------------------------------------------------

def registry_dir(registry: Path | None = None) -> Path:
    if registry is not None:
        return Path(registry)
    override = os.environ.get("SYNTHESIS_PEER_REGISTRY", "").strip()
    return Path(override).expanduser() if override else DEFAULT_REGISTRY


def process_alive(pid: int | None) -> bool:
    if not pid:
        return False
    try:
        os.kill(int(pid), 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except (OSError, ValueError):
        return False
    return True


def registry_entries(registry: Path | None = None) -> list[dict]:
    directory = registry_dir(registry)
    if not directory.is_dir():
        return []
    entries = []
    for path in sorted(directory.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if isinstance(data, dict) and data.get("sessionId") and data.get("messagingSocketPath"):
            entries.append(data)
    return entries


def registry_entry_for_session(
    harness_session_id: str,
    registry: Path | None = None,
    alive=process_alive,
) -> dict | None:
    """The live registry entry whose sessionId is the given harness id."""
    if not harness_session_id:
        return None
    for entry in registry_entries(registry):
        if entry.get("sessionId") == harness_session_id and alive(entry.get("pid")):
            return entry
    return None


def registry_entry_for_socket(
    socket_path: str, registry: Path | None = None, alive=process_alive
) -> dict | None:
    for entry in registry_entries(registry):
        if entry.get("messagingSocketPath") == socket_path and alive(entry.get("pid")):
            return entry
    return None


def harness_address(entry: dict) -> str:
    return f"uds:{entry['messagingSocketPath']}"


# --------------------------------------------------------------------------
# Lanes: exact per-client delivery addresses for one resolved target
# --------------------------------------------------------------------------

def delivery_lanes(
    *,
    client_ref: str,
    compact_id: str,
    target_machine: str,
    seat: Seat | None,
    local_machine: str | None = None,
    registry: Path | None = None,
    alive=process_alive,
) -> dict[str, dict]:
    """Every exact way to reach one target from this machine.

    The bus is always a lane. Direct lanes exist only on the target's own
    machine and only while live truth confirms them: the ccd lane needs the
    row's ``ccd:`` ref, the harness lane needs the registry to still map the
    seat's harness session id to a running process, the codex lane needs a
    ``codex:`` ref. A name never appears as an address."""
    machine = local_machine or socket.gethostname()
    same_machine = bool(target_machine) and target_machine == machine
    lanes: dict[str, dict] = {"bus": {"to": compact_id}}
    if same_machine and client_ref.startswith("ccd:"):
        lanes["ccd"] = {"session_id": client_ref[len("ccd:"):]}
    if same_machine and seat is not None and seat.harness_session_id and seat.client == CLIENT_CLAUDE:
        entry = registry_entry_for_session(seat.harness_session_id, registry, alive)
        if entry is not None:
            lanes["harness"] = {
                "to": harness_address(entry),
                "name": str(entry.get("name") or ""),
                "harness_session_id": seat.harness_session_id,
            }
    codex_thread = ""
    if client_ref.startswith("codex:"):
        codex_thread = client_ref[len("codex:"):]
    elif seat is not None and seat.client == CLIENT_CODEX and seat.harness_session_id:
        codex_thread = seat.harness_session_id
    if same_machine and codex_thread:
        lanes["codex"] = {
            "thread": codex_thread,
            "command": f"codex queue --thread {codex_thread} --message <text>",
        }
    return lanes


def lane_invocations(lanes: dict[str, dict], sender_compact: str) -> list[str]:
    """Human-readable exact invocations, one per lane, for the resolver output."""
    lines = []
    prefix = f"from {sender_compact}: " if sender_compact else ""
    if "ccd" in lanes:
        lines.append(
            "ccd lane: mcp__ccd_session_mgmt__send_message session_id="
            f"{lanes['ccd']['session_id']!r} message={prefix + '…'!r}"
        )
    if "harness" in lanes:
        lines.append(
            f"harness lane: SendMessage to={lanes['harness']['to']!r} "
            f"(registry name {lanes['harness']['name']!r}; the socket is the address, "
            f"the name is display only) message={prefix + '…'!r}"
        )
    if "codex" in lanes:
        lines.append(
            f"codex lane: {lanes['codex']['command'].replace('<text>', repr(prefix + '…'))}"
        )
    lines.append(
        "bus lane: coordination.py message --from "
        f"{sender_compact or '<your session id>'} --to {lanes['bus']['to']}"
    )
    return lines


# --------------------------------------------------------------------------
# Receipts: one sender, one resolved target, exact addresses, bounded time
# --------------------------------------------------------------------------

def receipt_dir_for(board: Path, sender_key: str) -> Path:
    return receipts_dir(board) / safe_name(sender_key)


def write_receipt(
    board: Path,
    *,
    sender: SelfIdentity,
    sender_row: dict | None,
    selector: str,
    matched_by: str,
    target: dict,
    lanes: dict[str, dict],
    ttl_minutes: int = RECEIPT_TTL_MINUTES,
    now: datetime | None = None,
) -> Path | None:
    """Persist the resolution so the gate can match a send to it.

    Returns None when the sender has no identity: a receipt no gate could
    attribute would be a receipt anyone could use."""
    key = sender.sender_key
    if not key:
        return None
    moment = now or utcnow()
    receipt = {
        "schema": RECEIPT_SCHEMA,
        "issued_at": iso(moment),
        "expires_at": iso(moment + timedelta(minutes=ttl_minutes)),
        "issued_by": {
            "sender_key": key,
            "client": sender.client,
            "board": sender_row or {},
        },
        "selector": selector,
        "matched_by": matched_by,
        "target": target,
        "lanes": lanes,
    }
    directory = receipt_dir_for(board, key)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{safe_name(target.get('uuid') or target.get('compact') or 'target')}.json"
    staging = path.with_suffix(".json.tmp")
    staging.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    os.replace(staging, path)
    return path


def load_receipts(board: Path, sender_key: str, now: datetime | None = None) -> list[dict]:
    """Unexpired receipts held by one sender; expired files are pruned."""
    directory = receipt_dir_for(board, sender_key)
    if not sender_key or not directory.is_dir():
        return []
    moment = now or utcnow()
    live = []
    for path in sorted(directory.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        expires = parse_iso(data.get("expires_at")) if isinstance(data, dict) else None
        if expires is None or expires < moment:
            try:
                path.unlink()
            except OSError:
                pass
            continue
        if data.get("issued_by", {}).get("sender_key") != sender_key:
            continue
        live.append(data)
    return live


def receipts_for_address(receipts: list[dict], lane: str, address: str) -> list[dict]:
    """Every live receipt whose lane address equals the one about to be used,
    newest first. A session that released and claimed again keeps its client
    handle but gets a new board identity, so two receipts can name one
    address; the gate must judge the newest one whose target is still
    active, not whichever file sorts first."""
    field = {"ccd": "session_id", "harness": "to", "codex": "thread"}.get(lane)
    if field is None:
        return []
    matches = [
        receipt
        for receipt in receipts
        if isinstance(receipt.get("lanes", {}).get(lane), dict)
        and str(receipt["lanes"][lane].get(field, "")).strip() == address.strip()
    ]
    return sorted(matches, key=lambda r: str(r.get("issued_at", "")), reverse=True)


def receipt_for_address(receipts: list[dict], lane: str, address: str) -> dict | None:
    """The newest receipt whose lane address equals the one about to be used."""
    matches = receipts_for_address(receipts, lane, address)
    return matches[0] if matches else None


# --------------------------------------------------------------------------
# Send log and the broadcast rule
# --------------------------------------------------------------------------

def body_digest(text: str) -> str:
    normalized = re.sub(r"\s+", " ", (text or "")).strip().casefold()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def append_send_log(board: Path, record: dict) -> None:
    path = send_log_path(board)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, sort_keys=True) + "\n")


def recent_sends(board: Path, *, since: datetime, limit_bytes: int = 2_000_000) -> list[dict]:
    path = send_log_path(board)
    if not path.is_file():
        return []
    size = path.stat().st_size
    with path.open("rb") as handle:
        if size > limit_bytes:
            handle.seek(size - limit_bytes)
            handle.readline()
        raw = handle.read().decode("utf-8", errors="replace")
    records = []
    for line in raw.splitlines():
        try:
            data = json.loads(line)
        except ValueError:
            continue
        moment = parse_iso(data.get("at")) if isinstance(data, dict) else None
        if moment is not None and moment >= since:
            records.append(data)
    return records


def broadcast_conflict(
    board: Path,
    *,
    sender_key: str,
    digest: str,
    target_uuid: str,
    now: datetime | None = None,
    window_minutes: int = BROADCAST_WINDOW_MINUTES,
) -> dict | None:
    """An allowed send of the same text to a different session in the window."""
    moment = now or utcnow()
    for record in recent_sends(board, since=moment - timedelta(minutes=window_minutes)):
        if (
            record.get("decision") == "allow"
            and record.get("sender_key") == sender_key
            and record.get("digest") == digest
            and record.get("target_uuid")
            and record.get("target_uuid") != target_uuid
        ):
            return record
    return None


# --------------------------------------------------------------------------
# Inbox: the addressed bus, read for one seat with a watermark
# --------------------------------------------------------------------------

@dataclass
class BoardMessage:
    recipient: str
    sender: str
    timestamp: str
    body: str

    @property
    def key(self) -> str:
        return hashlib.sha256(
            f"{self.recipient}\n{self.sender}\n{self.timestamp}\n{self.body}".encode("utf-8")
        ).hexdigest()[:16]


def _mentions_inbox_scope(recipient: str, identity_forms: set[str] | None, project: str) -> bool:
    folded = recipient.casefold()
    return any(value and value.casefold() in folded for value in [*(identity_forms or ()), project])


def _unrelated_legacy_recipient(recipient: str, identity_forms: set[str] | None, project: str) -> bool:
    """A narrow structural exclusion, never a guess about an unknown addressee."""
    if not (identity_forms or project) or _mentions_inbox_scope(recipient, identity_forms, project):
        return False
    if re.search(r"\b(?:all|any|every|both|current|this|everyone|anyone|whoever|you|your|our)\b", recipient, re.I):
        return False
    return bool(
        UUID_RE.fullmatch(recipient)
        or re.fullmatch(r"s-[a-z0-9]{4}-[a-z0-9]{4}-[a-z0-9]{4}", recipient)
        or re.fullmatch(r"(?:[a-z]+-){4}\d{5}", recipient)
        or re.fullmatch(r"[a-z0-9][a-z0-9-]* sessions", recipient)
        or re.fullmatch(r"[A-Za-z][A-Za-z0-9 .-]* \(session [A-Za-z0-9_.:-]+\)", recipient)
    )


def parse_messages(
    board_text: str, *, strict: bool = False, identity_forms: set[str] | None = None, project: str = ""
) -> list[BoardMessage]:
    """Every addressed message under ``## Messages``, in board order."""
    lines = board_text.splitlines()
    try:
        start = next(i for i, line in enumerate(lines) if line.strip() == "## Messages")
    except StopIteration:
        if strict:
            raise ValueError("coordination board is missing its Messages section")
        return []
    if strict and sum(line.strip() == "## Messages" for line in lines) != 1:
        raise ValueError("coordination board has multiple Messages sections")
    end = len(lines)
    for i in range(start + 1, len(lines)):
        if lines[i].startswith("## "):
            end = i
            break
    if strict:
        section_lines = [line.strip() for line in lines[start + 1:end] if line.strip()]
        if end == len(lines) or PROTOCOL_HEADING.fullmatch(lines[end].strip()) is None:
            raise ValueError("coordination Messages section must end at Protocol, not an unexpected heading")
        if not section_lines or section_lines[-1] != "---":
            raise ValueError("coordination Messages section is missing its Protocol separator")
    messages: list[BoardMessage] = []
    current: BoardMessage | None = None
    body: list[str] = []

    def finish(text_lines: list[str]) -> str:
        # The section ends with the `---` rule that precedes ## Protocol; it
        # is a boundary, not part of the last message.
        while text_lines and text_lines[-1].strip() in {"", "---"}:
            text_lines.pop()
        return "\n".join(text_lines).strip()

    heading = DIAGNOSTIC_MESSAGE_HEADING if strict else MESSAGE_HEADING
    for line in lines[start + 1:end]:
        match = heading.match(line)
        candidate = bool(MESSAGE_HEADING_CANDIDATE.match(line))
        if (
            strict and match and identity_forms is None
            and (MESSAGE_HEADING.match(line) is None or parse_iso(match.group("timestamp")) is None)
        ):
            raise ValueError("unscoped diagnostic cannot waive message timestamp or native header grammar")
        if (
            strict and match and MESSAGE_HEADING.match(line) is None
            and _mentions_inbox_scope(match.group("recipient"), identity_forms, project)
        ):
            raise ValueError("diagnostic cannot create an addressed message outside native header grammar")
        if strict and candidate and MESSAGE_HEADING.match(line) is None and current is not None:
            # A boundary the native parser did not recognize is part of its
            # previous body/key. Never silently redefine relevant delivered
            # evidence, even when its native key already has a watermark.
            if identity_forms is None or _mentions_inbox_scope(current.recipient, identity_forms, project):
                raise ValueError("diagnostic message boundary would change an addressed native body or key")
        # Only the addressed-header grammar is reserved. Ordinary Markdown
        # headings, including arrow headings without an addressee/sender,
        # remain message body content.
        if strict and candidate and match is None:
            legacy = LEGACY_UNTIMED_HEADING.fullmatch(line)
            if (
                legacy is None or identity_forms is None
                or not legacy.group("sender").strip()
                or re.search(r"\s[-–—]\s", legacy.group("sender"))
                or not _unrelated_legacy_recipient(legacy.group("recipient").strip(), identity_forms, project)
            ):
                raise ValueError("coordination board has a malformed addressed message heading")
            if current is not None:
                current.body = finish(body)
                messages.append(current)
            # Exclude this independently addressed legacy block without
            # inventing a timestamp, message key, or delivery watermark.
            current = None
            body = []
            continue
        if match:
            if current is not None:
                current.body = finish(body)
                messages.append(current)
            current = BoardMessage(
                recipient=match.group("recipient").strip(),
                sender=match.group("sender").strip(),
                timestamp=match.group("timestamp").strip(),
                body="",
            )
            body = []
        elif current is not None:
            body.append(line)
    if current is not None:
        current.body = finish(body)
        messages.append(current)
    return messages


def addressed_to(
    message: BoardMessage,
    identity_forms: set[str],
    project: str = "",
    since: object = None,
) -> bool:
    """Whether a message names this seat exactly, or its project's sessions.

    A message that names the session exactly is always its own. A message
    addressed to the project's sessions was for the sessions of its time:
    it is delivered only when posted at or after ``since`` (the seat's claim
    moment), so a new seat is not greeted with the project's whole history
    as unread — the SessionStart board read still covers history. A
    ``since`` that does not parse disables the bound rather than the
    delivery. Free-text addressees are never delivered: the sender was told
    the address did not resolve when it posted."""
    recipient = message.recipient.strip()
    tokens = {token.strip(",;") for token in recipient.split()}
    if any(form and form in tokens for form in identity_forms):
        return True
    if project and recipient.casefold().startswith(f"{project.casefold()} sessions"):
        floor = parse_iso(since) if since else None
        posted = parse_iso(message.timestamp)
        if floor is not None and posted is not None and posted < floor:
            return False
        return True
    return False


def watermark_path(board: Path, sender_key: str) -> Path:
    return inbox_dir(board) / f"{safe_name(sender_key)}.json"


def seen_keys(board: Path, sender_key: str, *, strict: bool = False) -> set[str]:
    path = watermark_path(board, sender_key)
    try:
        data = json.loads(
            path.read_text(encoding="utf-8"), object_pairs_hook=_unique_json_object if strict else None
        )
    except FileNotFoundError:
        if strict and path.is_symlink():
            raise
        return set()
    except (OSError, ValueError):
        if strict:
            raise
        return set()
    seen = data.get("seen") if isinstance(data, dict) else None
    if strict and (not isinstance(seen, list) or any(not isinstance(key, str) for key in seen)):
        raise ValueError(f"invalid coordination inbox watermark: {path}")
    return set(seen) if isinstance(seen, list) else set()


def mark_seen(board: Path, sender_key: str, keys: set[str], *, keep: int = 2000) -> None:
    path = watermark_path(board, sender_key)
    path.parent.mkdir(parents=True, exist_ok=True)
    merged = list(seen_keys(board, sender_key) | keys)[-keep:]
    staging = path.with_suffix(".json.tmp")
    staging.write_text(
        json.dumps({"seen": merged, "updated_at": iso(utcnow())}) + "\n", encoding="utf-8"
    )
    os.replace(staging, path)


def unread_messages(
    board_text: str,
    *,
    board: Path,
    sender_key: str,
    identity_forms: set[str],
    project: str = "",
    since: object = None,
    strict: bool = False,
) -> list[BoardMessage]:
    seen = seen_keys(board, sender_key, strict=strict) if sender_key else set()
    messages = []
    for message in parse_messages(board_text, strict=strict, identity_forms=identity_forms, project=project):
        # Historical free-text addressees can have human-written timestamps.
        # They do not participate in this inbox. An addressed message needs
        # a verifiable timestamp before a diagnostic can apply the claim floor.
        if strict and addressed_to(message, identity_forms, project) and parse_iso(message.timestamp) is None:
            raise ValueError("coordination inbox has an invalid addressed message timestamp")
        if addressed_to(message, identity_forms, project, since) and message.key not in seen:
            messages.append(message)
    return messages


def render_inbox(messages: list[BoardMessage], *, limit: int = 5, body_lines: int = 25) -> str:
    """A bounded, self-describing rendering: counts plus the newest messages."""
    if not messages:
        return ""
    shown = messages[-limit:]
    lines = [
        f"Coordination board inbox: {len(messages)} unread message(s) addressed to this "
        f"session or its project" + (f"; showing the newest {len(shown)}." if len(messages) > len(shown) else ".")
    ]
    for message in shown:
        lines.append(f"- from {message.sender} at {message.timestamp} → {message.recipient}:")
        body = message.body.splitlines()
        for line in body[:body_lines]:
            lines.append(f"    {line}")
        if len(body) > body_lines:
            lines.append(f"    … {len(body) - body_lines} more line(s) on the board")
    lines.append(
        "Reply by resolving the sender's session id (coordination.py resolve --to <id>) "
        "and using the lane it returns; never a chat title or display name."
    )
    return "\n".join(lines)
