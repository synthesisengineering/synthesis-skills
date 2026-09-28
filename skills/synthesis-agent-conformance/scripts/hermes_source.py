"""Bounded metadata-only snapshots of the documented Hermes SQLite history.

A matching row binds a source identity, not hook trust, live loading, authority,
provider use, or an outcome. SQLite opens only copied bytes, never the live path.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import stat
import struct
import tempfile
import time

MAX_BYTES = 128 * 1024 * 1024
MAX_SECONDS = 2.0
MAX_JSON = 1024 * 1024


def identity(st):
    return (
        st.st_dev,
        st.st_ino,
        st.st_mode,
        st.st_uid,
        st.st_nlink,
        st.st_size,
        st.st_mtime_ns,
        st.st_ctime_ns,
    )


def chain(path):
    path = Path(path)
    if not path.is_absolute() or ".." in path.parts:
        raise ValueError("absolute confined path required")
    result = []
    for part in [*reversed(path.parents), path]:
        st = part.lstat()
        if stat.S_ISLNK(st.st_mode):
            raise ValueError("path aliases are not accepted")
        result.append((part, (st.st_dev, st.st_ino, st.st_mode, st.st_uid)))
    return result


def unchanged(parts):
    return all(
        (s.st_dev, s.st_ino, s.st_mode, s.st_uid) == expected
        for p, expected in parts
        for s in [p.lstat()]
    )


def read_regular(path, *, limit=MAX_JSON, deadline=None, private=False):
    path = Path(path)
    parts = chain(path)
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        before = os.fstat(fd)
        if (
            not stat.S_ISREG(before.st_mode)
            or before.st_nlink != 1
            or before.st_uid != os.getuid()
            or before.st_size > limit
            or not before.st_mode & 0o400
            or before.st_mode & (0o022 if private else 0o002)
        ):
            raise ValueError("unsafe or oversized source file")
        data = bytearray()
        while True:
            if deadline is not None and time.monotonic() > deadline:
                raise ValueError("source observation deadline exceeded")
            chunk = os.read(fd, min(65536, limit + 1 - len(data)))
            if not chunk:
                break
            data.extend(chunk)
            if len(data) > limit:
                raise ValueError("source byte ceiling exceeded")
        if (
            identity(before) != identity(os.fstat(fd))
            or identity(before) != identity(path.lstat())
            or not unchanged(parts)
        ):
            raise ValueError("source changed during observation")
        return bytes(data), identity(before), parts
    finally:
        os.close(fd)


def read_json(path):
    def pairs(values):
        result = {}
        for key, value in values:
            if key in result:
                raise ValueError("duplicate JSON key")
            result[key] = value
        return result

    raw, _, _ = read_regular(path)
    return json.loads(
        raw,
        object_pairs_hook=pairs,
        parse_constant=lambda _: (_ for _ in ()).throw(ValueError("nonfinite JSON")),
    )


def validate_wal(raw, database, deadline):
    """Refuse an invalid current WAL instead of SQLite's silent older fallback.

    SQLite file-format sections 4.1/4.2 define the header and checksums. Old
    post-reset tail frames with a different salt are outside this generation.
    The original DB/WAL are never modified or checkpointed.
    """
    if not raw:
        return
    if len(raw) < 32 or database[:16] != b"SQLite format 3\x00" or len(database) < 100:
        raise ValueError("native WAL header is unavailable")
    magic, version, page_size, _, salt1, salt2, check1, check2 = struct.unpack(
        ">8I", raw[:32]
    )
    db_page_size = int.from_bytes(database[16:18], "big")
    if db_page_size == 1:
        db_page_size = 65536
    if (
        magic not in (0x377F0682, 0x377F0683)
        or version != 3007000
        or page_size != db_page_size
        or page_size < 512
        or page_size > 65536
        or page_size & (page_size - 1)
        or database[18:20] != b"\x02\x02"
    ):
        raise ValueError("native WAL format differs from the selected database")
    endian = "<" if magic == 0x377F0682 else ">"

    def checksum(data, state=(0, 0)):
        first, second = state
        for x, y in struct.iter_unpack(endian + "II", data):
            first = (first + x + second) & 0xFFFFFFFF
            second = (second + y + first) & 0xFFFFFFFF
        return first, second

    state = checksum(raw[:24])
    if state != (check1, check2):
        raise ValueError("native WAL header checksum differs")
    frame_size = 24 + page_size
    position = 32
    while position < len(raw):
        if time.monotonic() > deadline:
            raise ValueError("native WAL validation exceeded observation deadline")
        if len(raw) - position < 24:
            raise ValueError("native WAL has an incomplete frame")
        page, _, fsalt1, fsalt2, fcheck1, fcheck2 = struct.unpack(
            ">6I", raw[position : position + 24]
        )
        if (fsalt1, fsalt2) != (salt1, salt2):
            break  # Documented leftover generation after a WAL reset.
        if page == 0 or len(raw) - position < frame_size:
            raise ValueError("native WAL current frame is invalid")
        state = checksum(raw[position : position + 8], state)
        state = checksum(raw[position + 24 : position + frame_size], state)
        if state != (fcheck1, fcheck2):
            raise ValueError("native WAL current frame checksum differs")
        position += frame_size


def binding(home, session_id, *, profile, cwd, now=None):
    result = {
        "status": "UNKNOWN",
        "native_live": "UNKNOWN",
        "authority": False,
        "session_id": session_id,
    }
    deadline = time.monotonic() + MAX_SECONDS
    try:
        if (
            not isinstance(session_id, str)
            or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}", session_id)
            or not isinstance(profile, str)
            or not re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,63}", profile)
        ):
            raise ValueError("invalid native identity")
        home, cwd = Path(home), Path(cwd)
        if not cwd.is_absolute():
            raise ValueError("absolute native cwd required")
        roots = chain(home)
        if home.stat().st_uid != os.getuid() or home.stat().st_mode & 0o022:
            raise ValueError("unsafe profile ownership")
        journal = home / "state.db-journal"
        if os.path.lexists(journal):
            raise ValueError("rollback-journal observation is unsupported")
        sources, absent, total = [], [], 0
        for suffix in ("", "-wal"):
            path = home / ("state.db" + suffix)
            if suffix and not os.path.lexists(path):
                absent.append(path)
                continue
            raw, ident, parts = read_regular(
                path, limit=MAX_BYTES - total, deadline=deadline, private=True
            )
            total += len(raw)
            sources.append((path, raw, ident, parts))
        if len(sources) == 2:
            validate_wal(sources[1][1], sources[0][1], deadline)
        # No extensions, network, native client or live database writes. WAL is
        # copied with the exact DB generation; membership and bytes close below.
        with tempfile.TemporaryDirectory(prefix="synthesis-hermes-observe-") as temp:
            snapshot = Path(temp) / "state.db"
            for path, raw, _, _ in sources:
                (Path(temp) / path.name).write_bytes(raw)
            db = sqlite3.connect(str(snapshot), timeout=0.05)
            try:
                if hasattr(db, "enable_load_extension"):
                    db.enable_load_extension(False)
                db.execute("PRAGMA trusted_schema=OFF")
                db.execute("PRAGMA query_only=ON")
                db.set_progress_handler(lambda: int(time.monotonic() > deadline), 1000)
                # Read only declared metadata, never message/prompt/token bodies.
                row = db.execute(
                    "SELECT id,source,parent_session_id,started_at,ended_at,cwd,profile_name FROM sessions WHERE id=? LIMIT 2",
                    (session_id,),
                ).fetchall()
            finally:
                db.close()
        if len(row) != 1:
            raise ValueError("exact native session not found")
        sid, source, parent, started, ended, observed_cwd, owner_profile = row[0]
        observed_now = time.time() if now is None else now
        if (
            sid != session_id
            or source != "cli"
            or parent is not None
            or ended is not None
            or type(started) not in (int, float)
            or not 0 <= observed_now - started <= 86400
            or owner_profile != profile
            or observed_cwd != str(cwd)
        ):
            raise ValueError(
                "session metadata does not bind the selected live CLI scope"
            )
        for path, _, ident, parts in sources:
            if identity(path.lstat()) != ident or not unchanged(parts):
                raise ValueError("native source changed during observation")
        if (
            os.path.lexists(journal)
            or any(os.path.lexists(p) for p in absent)
            or not unchanged(roots)
            or time.monotonic() > deadline
        ):
            raise ValueError("native source membership or observation budget changed")
        result.update(
            status="BOUND",
            source="hermes-profile-sqlite",
            profile=profile,
            source_sha256=hashlib.sha256(
                b"".join(raw for _, raw, _, _ in sources)
            ).hexdigest(),
            source_bytes=total,
            started_at=started,
        )
    except (OSError, ValueError, TypeError, sqlite3.Error, RuntimeError) as exc:
        result["reason"] = str(exc)[:300]
    return result
