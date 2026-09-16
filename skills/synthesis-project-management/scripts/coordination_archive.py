"""Archive released evidence without changing live ownership or losing history.

Leased boards keep their one-file tree. An archive commit (flat monthly files)
is a second parent of the board CAS commit; its OID travels in the board header.
Ordinary writers preserve that header and ancestry. Local monthly files are
verified mirrors, never the authority for a leased archive. Unleased boards use
a recoverable write-before-remove journal under the same board lock.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile

import coordination as c
from peer_addressing import MESSAGE_HEADING, MESSAGE_HEADING_CANDIDATE

MONTH = re.compile(r"\d{4}-(?:0[1-9]|1[0-2])\.md")
OID = re.compile(r"(?:[0-9a-f]{40}|[0-9a-f]{64})")
MARKER = b"<!-- synthesis-archive-entry "


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def month_header(name: str) -> str:
    if not MONTH.fullmatch(name):
        raise ValueError("invalid archive month")
    return f"# Coordination archive {name[:-3]}\n\n"


def encode_entry(kind: str, payload: str) -> str:
    data = payload.encode("utf-8")
    metadata = json.dumps({"kind": kind, "bytes": len(data), "sha256": digest(data)}, sort_keys=True)
    return MARKER.decode() + metadata + " -->\n" + payload + "\n"


def decode_month(name: str, text: str) -> list[dict]:
    prefix = month_header(name).encode()
    raw = text.encode("utf-8")
    if not raw.startswith(prefix):
        raise ValueError("invalid archive month header")
    pos, result = len(prefix), []
    while pos < len(raw):
        end = raw.find(b"\n", pos)
        line = raw[pos:end]
        if end < 0 or not line.startswith(MARKER) or not line.endswith(b" -->"):
            raise ValueError("invalid archive entry marker")
        try:
            item = json.loads(line[len(MARKER):-4])
            size = item["bytes"]
            if type(size) is not int or size < 0 or item["kind"] not in {"row", "message"}:
                raise ValueError("invalid archive entry shape")
            data = raw[end + 1:end + 1 + size]
            if digest(data) != item["sha256"] or raw[end + 1 + size:end + 2 + size] != b"\n":
                raise ValueError("archive entry digest or length mismatch")
            item["payload"] = data.decode("utf-8")
        except (KeyError, TypeError, UnicodeError, json.JSONDecodeError) as exc:
            raise ValueError("invalid archive entry") from exc
        result.append(item)
        pos = end + 2 + size
    return result


def aware(value: str) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(value)
        return parsed if parsed.tzinfo is not None else None
    except ValueError:
        return None


def outside_fences(text: str):
    """Yield top-level line offsets; quoted native headers confer no boundary."""
    fence = None
    offset = 0
    for line in text.splitlines(keepends=True):
        marker = re.match(r"^ {0,3}(`{3,}|~{3,})(.*)$", line.rstrip("\n"))
        if fence:
            if marker and marker[1][0] == fence[0] and len(marker[1]) >= len(fence) and not marker[2].strip():
                fence = None
        elif marker:
            fence = marker[1]
        else:
            yield offset, line.rstrip("\n")
        offset += len(line)


@dataclass
class Plan:
    board: str
    months: dict[str, str]
    rows: int
    messages: int


def archive_oid(text: str) -> str | None:
    header = text.split("## Active sessions", 1)[0]
    declarations = [line for line in header.splitlines() if line.startswith("Archive:")]
    if not declarations:
        return None
    if len(declarations) != 1 or not declarations[0].startswith("Archive: "):
        raise RuntimeError("invalid archive declaration")
    oid = declarations[0][9:].strip()
    if not OID.fullmatch(oid):
        raise RuntimeError("invalid archive object identity")
    return oid


def set_archive_oid(text: str, oid: str) -> str:
    prior = archive_oid(text)
    if prior:
        return text.replace(f"Archive: {prior}", f"Archive: {oid}", 1)
    start = text.index("## Active sessions")
    return text[:start] + f"Archive: {oid}\n\n" + text[start:]


def plan_archive(text: str, months: dict[str, str], *, now: datetime) -> Plan:
    if now.tzinfo is None:
        raise ValueError("archive clock must carry a timezone")
    cutoff = now - timedelta(days=30)
    sessions = c.rows(text, strict=True)
    if len({row.id for row in sessions}) != len(sessions):
        raise ValueError("duplicate session identity in archive source")
    archived = []
    for name, data in months.items():
        for entry in decode_month(name, data):
            if entry["kind"] == "row":
                cells = c.parse_cells(entry["payload"].rstrip("\n"))
                if cells is None:
                    raise ValueError("invalid archived session row")
                row = c.session_from_cells(cells)
                if c.active(row) or c.validate_identity(row.identity):
                    raise ValueError("invalid archived session identity/status")
                archived.append(row)
    selected = {row.id: row for row in sessions if row.status == "released"
                and (stamp := aware(row.heartbeat)) is not None and stamp < cutoff}
    known = {row.id: row for row in [*archived, *sessions]}
    retired = ({row.id for row in archived} | selected.keys()) - {row.id for row in sessions if c.active(row)}
    output = dict(months)
    def append(month, kind, payload):
        name = month + ".md"
        output[name] = output.get(name, month_header(name)) + encode_entry(kind, payload)

    # Remove only exact row lines; all surviving metadata, spacing and prose stay.
    lines = text.splitlines(keepends=True)
    start = next(i for i, line in enumerate(lines) if line.strip() == "## Active sessions")
    end = next(i for i in range(start + 1, len(lines)) if lines[i].strip() == "## Messages")
    selected_lines = set()
    row_index = 0
    for index in range(start + 1, end):
        cells = c.parse_cells(lines[index].rstrip("\n"))
        if cells is None:
            continue
        row = sessions[row_index]
        row_index += 1
        if row.id in selected:
            if c.validate_identity(row.identity):
                raise ValueError("invalid archive candidate identity")
            selected_lines.add(index)
            append(aware(row.heartbeat).strftime("%Y-%m"), "row", lines[index])
    text = "".join(line for index, line in enumerate(lines) if index not in selected_lines)

    def retired_address(label):
        # Resolve identity forms only; project-wide/free/broadcast addresses stay.
        matches = [row for row in known.values() if c.selector_matches(row.identity, label.strip())]
        return len(matches) == 1 and matches[0].id in retired

    message_start = text.index("## Messages") + len("## Messages")
    boundary = re.search(r"(?m)^---[ \t]*\n\n## Protocol(?:[^\n]*)?$", text[message_start:])
    if boundary is None:
        raise ValueError("archive source lacks Protocol boundary")
    message_end = message_start + boundary.start()
    section = text[message_start:message_end]
    candidates = [pos for pos, line in outside_fences(section) if MESSAGE_HEADING.fullmatch(line)]
    kept, count = [section[:candidates[0]]] if candidates else [section], 0
    for index, pos in enumerate(candidates):
        block = section[pos:candidates[index + 1] if index + 1 < len(candidates) else len(section)]
        heading = MESSAGE_HEADING.fullmatch(block.splitlines()[0])
        stamp = aware(heading.group("timestamp")) if heading else None
        # Administrative releases and other non-message headings are evidence
        # too. Keep their entire enclosing native block rather than infer a
        # timestamp/address for them or detach them from surrounding context.
        uncertain_boundary = any(line.startswith("### ") and not MESSAGE_HEADING.fullmatch(line)
                                 for pos, line in outside_fences(block) if pos)
        if (heading and not uncertain_boundary and stamp and stamp < cutoff and retired_address(heading.group("sender"))
                and retired_address(heading.group("recipient"))):
            append(stamp.strftime("%Y-%m"), "message", block)
            count += 1
        else:
            kept.append(block)
    return Plan(text[:message_start] + "".join(kept) + text[message_end:], output, len(selected), count)


def checked(config, *args, input_text=None):
    result = c.git_lease(c.lease_repository(config), *args, input_text=input_text)
    if result.returncode:
        raise RuntimeError(f"archive Git operation failed: {result.stderr.strip()}")
    return result.stdout


def load_months(config: dict, tip: str, text: str) -> dict[str, str]:
    oid = archive_oid(text)
    if not oid:
        return {}
    checked(config, "merge-base", "--is-ancestor", oid, tip)
    if checked(config, "cat-file", "-t", oid).strip() != "commit":
        raise RuntimeError("archive identity is not a reachable commit")
    result = {}
    for line in checked(config, "ls-tree", oid).splitlines():
        meta, name = line.split("\t", 1)
        mode, kind, blob = meta.split()
        if mode != "100644" or kind != "blob" or not MONTH.fullmatch(name):
            raise RuntimeError("invalid archive tree member")
        data = checked(config, "cat-file", "blob", blob)
        decode_month(name, data)
        result[name] = data
    if not result:
        raise RuntimeError("empty archive tree")
    return result


def commit_months(config, months, parent):
    entries = []
    for name, content in sorted(months.items()):
        decode_month(name, content)
        blob = checked(config, "hash-object", "-w", "--stdin", input_text=content).strip()
        entries.append(f"100644 blob {blob}\t{name}\n")
    tree = checked(config, "mktree", input_text="".join(entries)).strip()
    parents = ["-p", parent] if parent else []
    return checked(config, "commit-tree", tree, *parents, "-m", "Archive coordination evidence").strip()


def archive_dir(board):
    directory = board.parent / (board.stem + ".archive")
    if directory.is_symlink() or (directory.exists() and not directory.is_dir()):
        raise ValueError("archive directory is not a regular directory")
    return directory


def check_mirror(board, months):
    directory = archive_dir(board)
    if not directory.exists():
        return
    for path in directory.iterdir():
        if not MONTH.fullmatch(path.name):
            continue  # unrelated retained files are never swept
        if path.is_symlink() or not path.is_file():
            raise ValueError("archive mirror member is not a regular file")
        current = path.read_text(encoding="utf-8")
        if path.name not in months or not months[path.name].startswith(current):
            raise ValueError("archive mirror diverges from published history")
        decode_month(path.name, current)


def atomic_text(path, text):
    if path.is_symlink() or (path.exists() and not path.is_file()):
        raise ValueError("archive output must be a regular file")
    descriptor, temp = tempfile.mkstemp(prefix=".archive-", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="") as stream:
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp, path)
        sync_directory(path.parent)
    finally:
        Path(temp).unlink(missing_ok=True)


def sync_directory(path):
    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0))
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def hydrate(board, months):
    check_mirror(board, months)
    directory = archive_dir(board)
    if months:
        directory.mkdir(exist_ok=True)
        sync_directory(directory.parent)
    for name, data in months.items():
        atomic_text(directory / name, data)
        if (directory / name).read_text(encoding="utf-8") != data:
            raise RuntimeError("archive mirror verification failed")


def local_months(board):
    directory = archive_dir(board)
    result = {}
    if directory.exists():
        for path in directory.iterdir():
            if MONTH.fullmatch(path.name):
                if path.is_symlink() or not path.is_file():
                    raise ValueError("archive mirror member is not a regular file")
                data = path.read_text(encoding="utf-8")
                decode_month(path.name, data)
                result[path.name] = data
    return result


def recover_local(board, journal):
    if journal.is_symlink():
        raise ValueError("archive recovery journal is a symlink")
    record = json.loads(journal.read_text(encoding="utf-8"))
    current = board.read_text(encoding="utf-8")
    if digest(current.encode()) not in {record["before"], digest(record["after"].encode())}:
        raise RuntimeError("archive recovery board diverged; retained journal requires reconciliation")
    for name, data in record["months"].items():
        decode_month(name, data)
    hydrate(board, record["months"])
    c.write_board(board, record["after"])
    sync_directory(board.parent)
    journal.unlink()
    sync_directory(journal.parent)


def archive(board: Path, *, now: datetime | None = None, dry_run=False) -> dict:
    now = now or datetime.now(timezone.utc)
    board.parent.mkdir(parents=True, exist_ok=True)
    with (board.parent / ".active-sessions.lock").open("a+") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        config = c.lease_configuration(board)
        if config:
            c._invalidate_lease_stamp(board)
            failure = ""
            for _ in range(c.LEASE_RETRIES):
                tip, text = c.lease_fetch(config)
                if text is None:
                    text = board.read_text(encoding="utf-8") if board.exists() else c.template()
                months = load_months(config, tip, text)
                plan = plan_archive(text, months, now=now)
                check_mirror(board, months if not (plan.rows or plan.messages) else plan.months)
                result = {"rows": plan.rows, "messages": plan.messages, "dry_run": dry_run}
                if dry_run:
                    return result
                if plan.rows or plan.messages:
                    oid = commit_months(config, plan.months, archive_oid(text))
                    updated = c.ensure_lease_declaration(set_archive_oid(plan.board, oid), config["remote"])
                    success, failure = c.lease_publish(config, board.name, updated, tip, archive_parent=oid)
                    if not success:
                        continue
                    text = updated
                # A crash here is recoverable from the remote archive ancestry.
                hydrate(board, plan.months)
                c.write_board(board, text)
                return result
            raise RuntimeError("archive compare-and-swap failed: " + failure)
        text = board.read_text(encoding="utf-8") if board.exists() else c.template()
        if c.declared_lease(text) or archive_oid(text):
            raise RuntimeError("archive requires the declared lease configuration")
        journal = board.parent / f".{board.stem}.archive-journal.json"
        if journal.exists() or journal.is_symlink():
            if dry_run:
                raise RuntimeError("archive recovery pending")
            recover_local(board, journal)
            text = board.read_text(encoding="utf-8")
        plan = plan_archive(text, local_months(board), now=now)
        if not dry_run and (plan.rows or plan.messages):
            record = {"before": digest(text.encode()), "after": plan.board, "months": plan.months}
            atomic_text(journal, json.dumps(record, sort_keys=True))
            recover_local(board, journal)
        return {"rows": plan.rows, "messages": plan.messages, "dry_run": dry_run}
