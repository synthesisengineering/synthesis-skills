"""Acquisition archive publication, factored from the meeting owner.

One bounded descriptor-relative publisher; fixed validators are selected by the
source-owned meeting/Slack/raw-custody callers, never by a CLI skip switch.
"""

import hashlib
import json
import os
from pathlib import Path
import secrets
import sys
import time

try:
    import fcntl
except ImportError:
    fcntl = None


def _archive_directory(path, *, create=False):
    """Open each component without following links; caller owns the returned fd."""
    current = os.open(path.anchor, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        for part in path.parts[1:]:
            if create:
                try:
                    os.mkdir(part, 0o700, dir_fd=current)
                except FileExistsError:
                    pass
            child = os.open(
                part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=current
            )
            os.close(current)
            current = child
        return current
    except BaseException:
        os.close(current)
        raise


def _publish(path, content, *, validate, force=False, expected_sha256=None):
    """Publish under a cooperative directory lock; preserve replaced/staging bytes.

    All writes are descriptor-relative to the no-follow opened archive directory.
    Managed project records still use the separate context transaction owner.
    """
    if fcntl is None:
        raise ValueError(
            "archive publication requires an available bounded file-lock owner"
        )
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from ritual_workers import read_regular

    path = Path(path)
    if ".." in path.parts:
        raise ValueError("archive traversal refused")
    path = Path(os.path.abspath(path))
    parent = path.parent
    fd = _archive_directory(parent, create=True)
    original = os.fstat(fd)
    staging = None

    def same_parent():
        check = _archive_directory(parent)
        try:
            present = os.fstat(check)
            if (present.st_dev, present.st_ino) != (original.st_dev, original.st_ino):
                raise ValueError("archive directory changed")
        finally:
            os.close(check)

    try:
        deadline = time.monotonic() + 5
        while True:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    raise ValueError("archive writer busy; no write attempted")
                time.sleep(0.02)
        same_parent()
        payload = content.encode("utf-8")
        if len(payload) > 8 * 1024 * 1024:
            raise ValueError("transcript exceeds archive bound")
        digest = hashlib.sha256(payload).hexdigest()
        old = None
        if expected_sha256 == "ABSENT" and os.path.lexists(path):
            raise ValueError("archive appeared after merge preflight")
        if expected_sha256 not in (None, "ABSENT") and not os.path.lexists(path):
            raise ValueError("archive disappeared after merge preflight")
        if os.path.lexists(path):
            old = read_regular(path, 8 * 1024 * 1024)
            if (
                expected_sha256 not in (None, "ABSENT")
                and hashlib.sha256(old).hexdigest() != expected_sha256
            ):
                raise ValueError("archive changed after merge preflight")
            if old == payload:
                rows = validate(path, digest)
                if any(row["status"] == "INCOMPLETE" for row in rows):
                    raise ValueError("existing exact transcript incomplete")
                return {"path": str(path), "sha256": digest, "saved": False}
            if not force:
                raise ValueError(
                    "archive differs; explicit force required to preserve and replace"
                )
            backup = path.with_name(
                path.name + ".old-" + hashlib.sha256(old).hexdigest() + ".md"
            )
            if os.path.lexists(backup):
                if read_regular(backup, 8 * 1024 * 1024) != old:
                    raise ValueError("archive backup conflict")
            else:
                same_parent()
                bfd = os.open(
                    backup.name,
                    os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                    0o600,
                    dir_fd=fd,
                )
                with os.fdopen(bfd, "wb") as stream:
                    stream.write(old)
                    stream.flush()
                    os.fsync(stream.fileno())
                os.fsync(fd)
        same_parent()
        name = "." + path.name + "." + secrets.token_hex(16) + ".md"
        staging = parent / name
        handle = os.open(
            name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=fd
        )
        with os.fdopen(handle, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.fsync(fd)
        rows = validate(staging, digest)
        if any(row["status"] == "INCOMPLETE" for row in rows):
            raise ValueError(
                "exact fetched transcript failed completeness; staging retained: "
                + str(staging)
            )
        same_parent()
        if old is not None and read_regular(path, 8 * 1024 * 1024) != old:
            raise ValueError("archive changed before replacement")
        if old is None and os.path.lexists(path):
            raise ValueError("archive appeared before publication")
        os.replace(name, path.name, src_dir_fd=fd, dst_dir_fd=fd)
        staging = None
        os.fsync(fd)
        rows = validate(path, digest)
        if any(row["status"] == "INCOMPLETE" for row in rows):
            raise ValueError("saved transcript failed exact verification")
        return {
            "path": str(path),
            "sha256": digest,
            "saved": True,
            "verification": rows,
        }
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)


def publish_json(path, value):
    content = (
        json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False)
        + "\n"
    )

    def validate(target, digest):
        from ritual_workers import read_regular

        data = read_regular(target, 8 * 1024 * 1024)
        if hashlib.sha256(data).hexdigest() != digest or data != content.encode(
            "utf-8"
        ):
            raise ValueError("raw acquisition custody readback differs")
        json.loads(data)
        return [{"status": "EXACT"}]

    return _publish(path, content, validate=validate)
