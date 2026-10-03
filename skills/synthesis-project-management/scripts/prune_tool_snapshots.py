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
import hmac
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
def locked(path: Path, *, deadline=None):
    safe(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with _parent_descriptor(path) as (parent, verify_parent):
        descriptor = os.open(path.name, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600, dir_fd=parent)
        try:
            held = os.fstat(descriptor)
            if not stat.S_ISREG(held.st_mode) or held.st_nlink != 1 or held.st_uid != os.getuid():
                raise RuntimeError("snapshot maintenance lock is not regular")
            identity = (held.st_dev, held.st_ino, held.st_mode, held.st_uid)
            def verify():
                verify_parent()
                current = os.stat(path.name, dir_fd=parent, follow_symlinks=False)
                if (current.st_dev, current.st_ino, current.st_mode, current.st_uid) != identity:
                    raise RuntimeError("snapshot maintenance lock changed after acquisition")
            if deadline is None:
                fcntl.flock(descriptor, fcntl.LOCK_EX)
            else:
                while True:
                    _remaining(deadline)
                    try:
                        fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
                        break
                    except BlockingIOError:
                        time.sleep(min(0.01, max(0, deadline - time.monotonic())))
            verify()
            yield verify
            verify()
        finally:
            os.close(descriptor)


@contextmanager
def _parent_descriptor(path):
    """Open each parent without following links; pin writes to that directory."""
    path = path.absolute()
    current = Path(path.anchor)
    descriptor = os.open(path.anchor, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    observed = []
    try:
        for part in path.parts[1:-1]:
            child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=descriptor)
            os.close(descriptor); descriptor = child
            current /= part
            info = os.fstat(descriptor)
            observed.append((current, (info.st_dev, info.st_ino, info.st_mode)))
        def verify():
            for parent, identity in observed:
                info = parent.lstat()
                if (info.st_dev, info.st_ino, info.st_mode) != identity:
                    raise RuntimeError("snapshot parent changed; evidence retained")
        verify()
        yield descriptor, verify
        verify()
    finally:
        os.close(descriptor)


def read_regular(path, *, limit=128 * 1024 * 1024, deadline=None):
    safe(path)
    with _parent_descriptor(path) as (parent, verify):
        descriptor = os.open(path.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent)
        with os.fdopen(descriptor, "rb") as stream:
            meta = os.fstat(stream.fileno())
            if not stat.S_ISREG(meta.st_mode) or meta.st_nlink != 1:
                raise ValueError("snapshot evidence is not a unique regular file")
            if meta.st_size > limit:
                raise ValueError("snapshot byte ceiling; evidence retained")
            chunks, count = [], 0
            while True:
                if deadline is not None:
                    _remaining(deadline)
                part = stream.read(min(1024 * 1024, limit + 1 - count))
                if not part:
                    break
                chunks.append(part); count += len(part)
                if count > limit:
                    raise ValueError("snapshot byte ceiling; evidence retained")
            raw = b"".join(chunks)
            identity = _identity(meta)
            if identity != _identity(os.fstat(stream.fileno())):
                raise RuntimeError("snapshot changed during read")
            verify()
            if identity != _identity(os.stat(path.name, dir_fd=parent, follow_symlinks=False)):
                raise RuntimeError("snapshot pathname changed during read")
            return raw, meta, identity


# Authenticated owner references select payloads without repeatedly decoding
# unrelated dirty-state maps. These are I/O evidence, never edit attribution.
SNAPSHOT_BYTES = 128 * 1024 * 1024
SNAPSHOT_TOTAL_BYTES = 256 * 1024 * 1024
SNAPSHOT_FILES = 200_000
SNAPSHOT_SECONDS = 10.0
OWNER_REFERENCE_BYTES = 4096


def _remaining(deadline):
    if time.monotonic() >= deadline:
        raise RuntimeError("snapshot observation exceeded its time ceiling; evidence retained")


def _identity(meta):
    return (meta.st_dev, meta.st_ino, meta.st_mtime_ns, meta.st_ctime_ns, meta.st_size)


def _owner_path(path):
    if path.name in {"", ".", ".."} or path.suffix != ".json":
        raise ValueError("snapshot owner reference needs a literal JSON leaf")
    return path.parent / ".owners" / (path.name + ".ref")


def _owner_key(directory, *, create=False, deadline=None):
    if deadline is not None:
        _remaining(deadline)
    key_path = directory / ".owner-key"
    safe(key_path)
    if create and not os.path.lexists(key_path):
        with _parent_descriptor(key_path) as (parent, verify):
            descriptor = os.open(key_path.name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=parent)
            try:
                os.write(descriptor, os.urandom(32))
                os.fsync(descriptor)
                verify()
                os.fsync(parent)
            finally:
                os.close(descriptor)
    raw, meta, _ = read_regular(key_path, limit=32, deadline=deadline)
    if len(raw) != 32 or meta.st_uid != os.getuid() or stat.S_IMODE(meta.st_mode) != 0o600:
        raise ValueError("snapshot owner key is unsafe; evidence retained")
    return raw


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def _strict_json(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("duplicate snapshot JSON key")
            result[key] = value
        return result
    return json.loads(raw, object_pairs_hook=pairs)


def _reference(path, key=None):
    reference = _owner_path(path)
    if not os.path.lexists(reference):
        return None
    raw, meta, _ = read_regular(reference, limit=OWNER_REFERENCE_BYTES)
    if meta.st_uid != os.getuid() or stat.S_IMODE(meta.st_mode) != 0o600:
        raise ValueError("snapshot owner reference is unsafe")
    envelope = _strict_json(raw)
    if not isinstance(envelope, dict) or set(envelope) != {"body", "mac"}:
        raise ValueError("invalid snapshot owner envelope")
    body, mac = envelope["body"], envelope["mac"]
    if (not isinstance(body, dict) or set(body) != {"schema", "owner", "snapshot", "identity", "sha256"}
            or type(body["schema"]) is not int or body["schema"] != 1
            or body["snapshot"] != path.name
            or not isinstance(body["owner"], str) or not re.fullmatch(r"[0-9a-f]{64}", body["owner"])
            or not isinstance(body["sha256"], str) or not re.fullmatch(r"[0-9a-f]{64}", body["sha256"])
            or not isinstance(body["identity"], list) or len(body["identity"]) != 5
            or any(type(value) is not int or value < 0 for value in body["identity"])
            or not isinstance(mac, str) or not re.fullmatch(r"[0-9a-f]{64}", mac)):
        raise ValueError("invalid snapshot owner reference")
    expected = hmac.digest(_owner_key(path.parent) if key is None else key, _canonical(body), "sha256").hex()
    if not hmac.compare_digest(mac, expected):
        raise ValueError("snapshot owner reference authentication failed")
    return body


def publish_owner_reference(path, session_id, *, deadline=None):
    """Caller holds .snapshot.lock; retain the source, publish a bounded hint."""
    deadline = time.monotonic() + SNAPSHOT_SECONDS if deadline is None else deadline
    _remaining(deadline)
    raw, meta, identity = read_regular(path, deadline=deadline)
    data = _strict_json(raw)
    _remaining(deadline)
    if (not isinstance(session_id, str) or not session_id or len(session_id) > 256
            or not isinstance(data, dict) or data.get("session_id") != session_id
            or meta.st_uid != os.getuid() or meta.st_mode & 0o022):
        raise ValueError("snapshot ownership cannot be established")
    reference = _owner_path(path)
    safe(reference)
    with _parent_descriptor(path) as (parent, verify):
        try:
            os.mkdir(".owners", 0o700, dir_fd=parent)
        except FileExistsError:
            pass
        verify()
    safe(reference)
    parent = reference.parent.stat()
    if parent.st_uid != os.getuid() or parent.st_mode & 0o077:
        raise ValueError("snapshot owner directory is unsafe")
    _remaining(deadline)
    key = _owner_key(path.parent, create=True, deadline=deadline)
    body = {"schema": 1, "owner": hashlib.sha256(session_id.encode()).hexdigest(),
            "snapshot": path.name, "identity": list(identity), "sha256": hashlib.sha256(raw).hexdigest()}
    envelope = _canonical({"body": body, "mac": hmac.digest(key, _canonical(body), "sha256").hex()})
    _remaining(deadline)
    with _parent_descriptor(reference) as (parent, verify):
        temporary = ".owner-" + os.urandom(16).hex()
        descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=parent)
        try:
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(envelope); stream.flush(); os.fsync(stream.fileno())
            safe(path); verify()
            if _identity(path.lstat()) != identity:
                raise RuntimeError("snapshot changed before owner publication; evidence retained")
            _remaining(deadline)
            os.replace(temporary, reference.name, src_dir_fd=parent, dst_dir_fd=parent)
            os.fsync(parent)
            verify()
            _remaining(deadline)
        finally:
            try:
                os.unlink(temporary, dir_fd=parent)
            except FileNotFoundError:
                pass
    sync_directory(path.parent)
    return body


def remove_owner_reference(path, session_id, *, deadline=None):
    """Existing snapshot cleanup owns this derived hint, never another payload."""
    deadline = time.monotonic() + SNAPSHOT_SECONDS if deadline is None else deadline
    _remaining(deadline)
    reference = _owner_path(path)
    reference_identity = _identity(reference.lstat()) if os.path.lexists(reference) else None
    body = _reference(path)
    if body is None:
        return
    if _identity(reference.lstat()) != reference_identity:
        raise RuntimeError("snapshot owner reference changed before cleanup")
    safe(path)
    if (body["owner"] != hashlib.sha256(session_id.encode()).hexdigest()
            or body["identity"] != list(_identity(path.lstat()))):
        raise RuntimeError("snapshot owner changed before cleanup; retained")
    reference = _owner_path(path)
    with _parent_descriptor(reference) as (parent, verify):
        verify()
        if _identity(os.stat(reference.name, dir_fd=parent, follow_symlinks=False)) != reference_identity:
            raise RuntimeError("snapshot owner reference changed before cleanup")
        _remaining(deadline)
        os.unlink(reference.name, dir_fd=parent)
        os.fsync(parent)
        _remaining(deadline)


def selected_snapshots(directory, session_id):
    """Read all own generations, including old start stamps; never age-filter.

    A missing/stale hint is explicitly legacy evidence and is decoded under a
    total byte ceiling. Malformed/authentication failures refuse, never erase
    obligations. Run this owner's --index-only mode to reconcile retained files.
    Cooperating writers/pruners share the lock; no partial listing is returned.
    """
    if not isinstance(session_id, str) or not session_id or len(session_id) > 256:
        raise ValueError("invalid snapshot session identity")
    safe(directory)
    if not directory.exists():
        return []
    deadline = time.monotonic() + SNAPSHOT_SECONDS
    selected, total = [], 0
    wanted = hashlib.sha256(session_id.encode()).hexdigest()
    with locked(directory / ".snapshot.lock", deadline=deadline) as verify:
        generation = _identity(directory.stat())
        key_path = directory / ".owner-key"
        key = _owner_key(directory) if os.path.lexists(key_path) else None
        key_identity = _identity(key_path.lstat()) if key is not None else None
        observations = {}
        paths = []
        for path in directory.iterdir():
            _remaining(deadline)
            if path.suffix == ".json":
                paths.append(path)
                if len(paths) > SNAPSHOT_FILES:
                    raise ValueError("snapshot count ceiling; evidence retained")
        for path in sorted(paths):
            _remaining(deadline)
            safe(path)
            meta = path.lstat()
            if (not stat.S_ISREG(meta.st_mode) or meta.st_nlink != 1
                    or meta.st_uid != os.getuid() or meta.st_mode & 0o022):
                raise ValueError("unsafe snapshot evidence; retained")
            observations[path] = _identity(meta)
            body = _reference(path, key)
            if _identity(path.lstat()) != observations[path]:
                raise RuntimeError("snapshot changed during owner selection")
            current = body is not None and body["identity"] == list(_identity(meta))
            if current and body["owner"] != wanted:
                continue
            if total + meta.st_size > SNAPSHOT_TOTAL_BYTES:
                raise ValueError("unindexed or selected snapshot byte ceiling; run snapshot maintenance --index-only; evidence retained")
            raw, observed, identity = read_regular(
                path, limit=min(SNAPSHOT_BYTES, SNAPSHOT_TOTAL_BYTES - total), deadline=deadline)
            total += len(raw)
            if current and (list(identity) != body["identity"] or hashlib.sha256(raw).hexdigest() != body["sha256"]):
                raise ValueError("snapshot owner binding changed; retained")
            data = _strict_json(raw)
            if not isinstance(data, dict) or not isinstance(data.get("session_id"), str) or not data["session_id"]:
                raise ValueError("unclassified snapshot ownership; evidence retained")
            if data["session_id"] == session_id:
                selected.append((path, data, observed.st_mtime))
            elif current:
                raise ValueError("snapshot owner differs from payload; retained")
        _remaining(deadline)
        verify()
        if key_identity is not None and _identity(key_path.lstat()) != key_identity:
            raise RuntimeError("snapshot owner key changed during selection")
        if _identity(directory.stat()) != generation:
            raise RuntimeError("snapshot directory changed during selection")
        for path, identity in observations.items():
            _remaining(deadline)
            safe(path)
            if _identity(path.lstat()) != identity:
                raise RuntimeError("snapshot changed during selection")
    return selected


def index_retained(root):
    """Explicit bounded reconciliation, without relocating/deleting snapshots.

    Prefix progress is durable and retryable; a failure never claims completion.
    New/replaced legacy files remain visible to the reader's bounded fallback.
    """
    directory = root.absolute() / "tool-snapshots"
    safe(directory)
    if not directory.exists():
        return {"indexed": 0, "unchanged": 0, "payloads_moved": 0}
    deadline = time.monotonic() + SNAPSHOT_SECONDS
    result = {"indexed": 0, "unchanged": 0, "payloads_moved": 0}
    with locked(root / "lifecycle.lock", deadline=deadline), locked(directory / ".snapshot.lock", deadline=deadline):
        paths = []
        for path in directory.iterdir():
            _remaining(deadline)
            paths.append(path)
            if len(paths) > SNAPSHOT_FILES:
                raise ValueError("snapshot directory count ceiling; evidence retained")
        count = 0
        for path in sorted(paths):
            _remaining(deadline)
            if path.suffix != ".json":
                continue
            count += 1
            if count > SNAPSHOT_FILES:
                raise ValueError("snapshot count ceiling; evidence retained")
            body = _reference(path)
            if body is not None and body["identity"] == list(_identity(path.lstat())):
                result["unchanged"] += 1
                continue
            raw, _meta, _identity_value = read_regular(path, deadline=deadline)
            data = _strict_json(raw)
            if not isinstance(data, dict):
                raise ValueError("snapshot ownership cannot be reconciled")
            publish_owner_reference(path, data.get("session_id"), deadline=deadline)
            result["indexed"] += 1
        _remaining(deadline)
    return result


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
            remove_owner_reference(path, sid)
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
    parser.add_argument("--index-only", action="store_true", help="authenticate retained snapshot owners without moving payloads")
    args = parser.parse_args()
    if args.index_only and args.dry_run:
        parser.error("--index-only and --dry-run are distinct operations")
    try:
        result = (index_retained(home / "repo-guard") if args.index_only else
                  prune(home / "coordination/active-sessions.md", home / "repo-guard", dry_run=args.dry_run))
    except (OSError, ValueError, RuntimeError, ImportError) as exc:
        print(f"snapshot maintenance refused: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
