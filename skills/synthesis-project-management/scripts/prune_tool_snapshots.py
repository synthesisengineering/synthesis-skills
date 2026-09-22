#!/usr/bin/env python3
"""Move proved-ended orphan snapshots out of the hot directory, retaining bytes.

Age alone never proves an orphan. Require one explicitly released native seat,
no pending manifest, a regular schema-valid snapshot older than one day, and
unchanged identity/bytes after a verified archive copy. Unknown, active, recent,
redirected and pending evidence stays. This day-start job never deletes history.
"""
from __future__ import annotations
import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import fcntl
import hashlib
import importlib
import json
import os
from pathlib import Path
import re
import stat
import sys
import tempfile
import time

SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))


def safe(path: Path):
    current = Path(path.absolute().anchor)
    for part in path.absolute().parts[1:]:
        current /= part
        if current.is_symlink():
            raise RuntimeError("snapshot maintenance path contains a symlink")


@contextmanager
def locked(path: Path):
    safe(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(path, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    try:
        if not stat.S_ISREG(os.fstat(descriptor).st_mode):
            raise RuntimeError("snapshot maintenance lock is not regular")
        fcntl.flock(descriptor, fcntl.LOCK_EX)
        yield
    finally:
        os.close(descriptor)


def read_regular(path):
    safe(path)
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(descriptor, "rb") as stream:
        meta = os.fstat(stream.fileno())
        if not stat.S_ISREG(meta.st_mode) or meta.st_nlink != 1:
            raise ValueError("snapshot evidence is not a unique regular file")
        raw = stream.read()
        identity = (meta.st_dev, meta.st_ino, meta.st_mtime_ns, meta.st_ctime_ns, meta.st_size)
        after = os.fstat(stream.fileno())
        if identity != (after.st_dev, after.st_ino, after.st_mtime_ns, after.st_ctime_ns, after.st_size):
            raise RuntimeError("snapshot changed during read")
        return raw, meta, identity


def archive_destination(root, path, raw, mtime):
    month = datetime.fromtimestamp(mtime, timezone.utc).strftime("%Y-%m")
    name = path.stem + "-" + hashlib.sha256(raw).hexdigest() + ".json"
    return root / "tool-snapshots.archive" / month / name


def sync_directory(path):
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    try: os.fsync(descriptor)
    finally: os.close(descriptor)


def write_archive(destination, raw):
    safe(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    safe(destination)
    if destination.exists():
        if read_regular(destination)[0] != raw:
            raise RuntimeError("snapshot archive collision; retained both sources")
        # An interrupted attempt may have linked the file but not persisted its
        # directory entries. Re-establish durability on every recovery path.
        for directory in (destination.parent, destination.parent.parent, destination.parent.parent.parent):
            sync_directory(directory)
        return
    descriptor, name = tempfile.mkstemp(prefix=".snapshot-", dir=destination.parent)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(raw); stream.flush(); os.fsync(stream.fileno())
        # Publish without replacing any independently created destination.
        os.link(name, destination)
        Path(name).unlink()
        for directory in (destination.parent, destination.parent.parent, destination.parent.parent.parent):
            sync_directory(directory)
    finally:
        Path(name).unlink(missing_ok=True)
    if read_regular(destination)[0] != raw:
        raise RuntimeError("snapshot archive verification failed")


def prune_locked(root: Path, rows, *, now: float, dry_run=False):
    """Caller holds lifecycle then fresh board lock; acquire snapshot lock."""
    root = root.absolute()
    directory = root / "tool-snapshots"
    safe(root); safe(directory); safe(root / "pending"); safe(root / "tool-snapshots.archive")
    result = {"scanned": 0, "eligible": 0, "archived": 0, "retained": 0}
    if not directory.exists():
        return result
    with locked(directory / ".snapshot.lock"):
        for path in sorted(directory.glob("*.json")):
            result["scanned"] += 1
            result["retained"] += 1
            if not re.fullmatch(r"[0-9a-f]{64}\.json", path.name):
                continue
            try:
                raw, meta, identity = read_regular(path)
                data = json.loads(raw)
                if (not isinstance(data, dict) or type(data.get("schema_version")) is not int
                        or data["schema_version"] != 1 or not isinstance(data.get("session_id"), str)
                        or not data["session_id"] or not isinstance(data.get("dirty"), dict)
                        or not isinstance(data.get("workdir"), str) or not Path(data["workdir"]).is_absolute()
                        or (data.get("repo") is not None and (not isinstance(data["repo"], str) or not Path(data["repo"]).is_absolute()))):
                    continue
            except (OSError, ValueError, RuntimeError):
                continue
            if now - meta.st_mtime <= 86400:
                continue
            sid = data["session_id"]
            # Desktop ids and unknown schemes cannot stand in for harness ids.
            matching = [row for row in rows if row.client_ref in {"codex:" + sid, "cc:" + sid}]
            if len(matching) != 1 or matching[0].status != "released":
                continue
            pending = root / "pending" / (hashlib.sha256(sid.encode()).hexdigest() + ".json")
            if os.path.lexists(pending):
                continue
            destination = archive_destination(root, path, raw, meta.st_mtime)
            result["eligible"] += 1
            if dry_run:
                continue
            write_archive(destination, raw)
            current, _, current_identity = read_regular(path)
            if current != raw or current_identity != identity:
                raise RuntimeError("snapshot changed before removal; retained")
            path.unlink()
            result["archived"] += 1
            result["retained"] -= 1
        descriptor = os.open(directory, os.O_RDONLY | os.O_NOFOLLOW)
        try: os.fsync(descriptor)
        finally: os.close(descriptor)
    return result


# Promoted from the private control plane (private agent-control, PRO-1, 2026-09-21); behavior identical, loader is the
# same-skill convention instead of the private verified runtime.
def coordination():
    module = importlib.import_module("coordination")
    if Path(module.__file__).resolve() != SCRIPTS_DIR / "coordination.py":
        raise RuntimeError("coordination module differs from this skill's scripts")
    return module


def prune(board, root, *, dry_run=False):
    c = coordination()
    safe(board)
    # Checkpoint publication holds lifecycle across git commit, whose authority
    # gate takes the board lock. Follow the same order to avoid a cycle.
    with locked(root / "lifecycle.lock"), locked(board.parent / ".active-sessions.lock"):
        config = c.lease_configuration(board)
        if config:
            tip, text = c.lease_fetch(config)
            if not tip or text is None:
                raise RuntimeError("snapshot maintenance requires a published lease board")
        else:
            text = board.read_text(encoding="utf-8")
            if c.declared_lease(text):
                raise RuntimeError("snapshot maintenance requires the missing lease configuration")
        rows = c.rows(text, strict=True)
        # Released seats may already have moved to monthly archive history.
        from coordination_archive import load_months, local_months, decode_month
        history = load_months(config, tip, text) if config else local_months(board)
        for month, content in history.items():
            for entry in decode_month(month, content):
                if entry["kind"] == "row":
                    rows.append(c.session_from_cells(c.parse_cells(entry["payload"].rstrip("\n"))))
        return prune_locked(root, rows, now=time.time(), dry_run=dry_run)


def main():
    home = Path(os.environ.get("SYNTHESIS_HOME", str(Path.home() / ".synthesis")))
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    try:
        result = prune(home / "coordination/active-sessions.md", home / "repo-guard", dry_run=args.dry_run)
    except (OSError, ValueError, RuntimeError, ImportError) as exc:
        print(f"snapshot maintenance refused: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
