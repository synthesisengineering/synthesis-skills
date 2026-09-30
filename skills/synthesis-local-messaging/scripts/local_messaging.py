# SPDX-License-Identifier: Apache-2.0
"""Bounded, pointer-only local messaging acquisition. No native app discovery."""

from __future__ import annotations

import argparse
from collections import Counter
from contextlib import contextmanager
from datetime import datetime, timezone
import fcntl
import hashlib
import importlib
import json
import math
import os
from pathlib import Path
import plistlib
import re
import sqlite3
import stat
import sys
import time
import uuid

MAX_BODY = 256 * 1024
MAX_PAGE = 100
MAX_SECONDS = 5
APPLE_EPOCH = 978307200


class Refused(ValueError):
    """Incomplete or unsafe input never becomes complete coverage."""


def canonical(value):
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode()


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def unique(pairs):
    result = {}
    for k, v in pairs:
        if k in result:
            raise Refused("duplicate JSON key")
        result[k] = v
    return result


def physical(path, directory=False):
    path = Path(path)
    if not path.is_absolute() or ".." in path.parts:
        raise Refused("explicit physical absolute path required")
    for item in (path, *path.parents):
        s = item.lstat()
        if stat.S_ISLNK(s.st_mode):
            raise Refused("symlink path refused")
    info = path.stat()
    if not (stat.S_ISDIR(info.st_mode) if directory else stat.S_ISREG(info.st_mode)):
        raise Refused("wrong file type")
    return path


def stable_stat(info):
    # Access-time changes caused by this read are not source mutations.
    return (
        info.st_dev,
        info.st_ino,
        info.st_mode,
        info.st_uid,
        info.st_nlink,
        info.st_size,
        info.st_mtime_ns,
        info.st_ctime_ns,
    )


def file_json(path, limit=1024 * 1024):
    path = physical(path)
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    try:
        before = os.fstat(fd)
        if before.st_size > limit:
            raise Refused("input byte limit")
        raw = os.read(fd, limit + 1)
        after = os.fstat(fd)
        if (
            stable_stat(before) != stable_stat(after)
            or len(raw) != before.st_size
            or stable_stat(physical(path).stat()) != stable_stat(after)
        ):
            raise Refused("input changed during read")
    finally:
        os.close(fd)
    return json.loads(
        raw,
        object_pairs_hook=unique,
        parse_constant=lambda _: (_ for _ in ()).throw(Refused("nonfinite JSON")),
    )


def instant(value):
    if not isinstance(value, str):
        raise Refused("timestamp must be ISO8601")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise Refused("invalid timestamp") from exc
    if parsed.tzinfo is None:
        raise Refused("timestamp timezone required")
    return parsed.timestamp()


def validate(request):
    keys = {
        "schema",
        "adapter",
        "database",
        "start",
        "end",
        "page_size",
        "after",
        "upper",
        "excluded_chats",
        "self_names",
    }
    if (
        not isinstance(request, dict)
        or set(request) != keys
        or type(request["schema"]) is not int
        or request["schema"] != 1
    ):
        raise Refused("unknown request schema")
    if request["adapter"] not in ("imessage-v1", "whatsapp-v1"):
        raise Refused("unsupported adapter")
    for key in ("page_size", "after"):
        if type(request[key]) is not int:
            raise Refused("integer page bound required")
    if not 1 <= request["page_size"] <= MAX_PAGE or not 0 <= request["after"] < 2**63:
        raise Refused("page bound exceeded")
    if request["upper"] is not None and (
        type(request["upper"]) is not int
        or not request["after"] <= request["upper"] < 2**63
    ):
        raise Refused("invalid snapshot upper bound")
    start, end = instant(request["start"]), instant(request["end"])
    if not 0 < end - start <= 366 * 86400:
        raise Refused("window must be positive and at most366days")
    for key in ("excluded_chats", "self_names"):
        value = request[key]
        if (
            not isinstance(value, list)
            or len(value) > 1000
            or any(
                not isinstance(v, str) or not v.strip() or len(v) > 200 for v in value
            )
            or len(value) != len(set(value))
        ):
            raise Refused("invalid bounded selection")
    if not isinstance(request["database"], str):
        raise Refused("explicit database path required")
    physical(request["database"])
    return start, end


def decode_body(text, body):
    if text is not None and not isinstance(text, str):
        raise Refused("non-text body")
    if text:
        if len(text.encode()) > MAX_BODY:
            raise Refused("body exceeds limit")
        return text
    if not isinstance(body, bytes) or not body or len(body) > MAX_BODY:
        raise Refused("missing/oversized attributed body")
    if not body.startswith(b"bplist00") or len(body) < 40:
        raise Refused(
            "unsupported attributedBody encoding; typedstream is not unarchived"
        )
    # Bound the binary plist allocation before the parser allocates object tables.
    if not 1 <= int.from_bytes(body[-24:-16], "big") <= 2048:
        raise Refused("binary plist object count exceeds limit")
    try:
        data = plistlib.loads(body)
    except Exception as exc:
        raise Refused("malformed attributedBody") from exc
    if (
        not isinstance(data, dict)
        or data.get("$archiver") != "NSKeyedArchiver"
        or data.get("$version") != 100000
    ):
        raise Refused("unsupported keyed archive")
    objects = data.get("$objects")
    top = data.get("$top")
    if (
        not isinstance(objects, list)
        or not 1 <= len(objects) <= 2048
        or not isinstance(top, dict)
        or set(top) != {"root"}
    ):
        raise Refused("archive object bound/root")
    seen = set()

    def value(item, depth=0):
        if depth > 8:
            raise Refused("archive depth")
        if isinstance(item, plistlib.UID):
            index = item.data
            if index in seen or not 0 <= index < len(objects):
                raise Refused("archive cycle/reference")
            seen.add(index)
            return value(objects[index], depth + 1)
        if isinstance(item, str):
            return item
        if isinstance(item, dict):
            strings = [k for k in ("NSString", "NS.string") if k in item]
            if len(strings) != 1 or set(item) - {
                "NSString",
                "NS.string",
                "$class",
                "NS.attributes",
            }:
                raise Refused("unsupported attributed-string fields")
            return value(item[strings[0]], depth + 1)
        raise Refused("unsupported archive object")

    result = value(top["root"])
    if not result or len(result.encode()) > MAX_BODY:
        raise Refused("empty/oversized decoded body")
    return result


def _identity(path):
    p = physical(path)
    s = p.stat()
    return [s.st_dev, s.st_ino, stat.S_IMODE(s.st_mode)]


def generation(path):
    result = {}
    for suffix in ("", "-wal", "-shm"):
        item = Path(str(path) + suffix)
        if not item.exists() and not item.is_symlink():
            result[suffix] = None
            continue
        info = physical(item).stat()
        # SHM coordination bytes may change independently of database contents.
        fields = [info.st_dev, info.st_ino, info.st_mode, info.st_uid]
        if suffix != "-shm":
            fields += [info.st_size, info.st_mtime_ns, info.st_ctime_ns]
        result[suffix] = fields
    return result


def _require_confined(path):
    """An inherited claim is insufficient: observe denied write-open on each input."""
    for p in [path, Path(str(path) + "-wal"), Path(str(path) + "-shm")]:
        if not p.exists():
            continue
        physical(p)
        try:
            fd = os.open(p, os.O_WRONLY | os.O_NOFOLLOW)
        except PermissionError:
            continue
        else:
            os.close(fd)
            raise Refused("OS read-only confinement is required before SQLite access")


def _schema(db, adapter):
    required = (
        {
            "message": {
                "guid",
                "text",
                "attributedBody",
                "date",
                "is_from_me",
                "handle_id",
                "associated_message_type",
                "cache_has_attachments",
            },
            "handle": {"id"},
            "chat": {"chat_identifier"},
            "chat_message_join": {"chat_id", "message_id"},
            "chat_handle_join": {"chat_id", "handle_id"},
        }
        if adapter == "imessage-v1"
        else {
            "ZWAMESSAGE": {
                "Z_PK",
                "ZSTANZAID",
                "ZTEXT",
                "ZMESSAGEDATE",
                "ZISFROMME",
                "ZFROMJID",
                "ZCHATSESSION",
                "ZMESSAGETYPE",
            },
            "ZWACHATSESSION": {"Z_PK", "ZCONTACTJID", "ZSESSIONTYPE"},
        }
    )
    for table, columns in required.items():
        kind = db.execute(
            "select type from sqlite_master where name=?", (table,)
        ).fetchall()
        if kind != [("table",)]:
            raise Refused("missing/ambiguous table schema")
        actual = {r[1] for r in db.execute('pragma table_info("' + table + '")')}
        if not columns <= actual:
            raise Refused("unsupported schema columns")
    return digest({k: sorted(v) for k, v in required.items()})


def _classify(text, mine):
    lowered = text.casefold()
    if re.search(
        r"\b(verification|security|one.time|login|authentication)\s+code\b|\bOTP\b",
        text,
        re.I,
    ):
        return None, "security-code"
    if re.search(r"\b(package|parcel|shipment|delivery)\b", lowered):
        return None, "delivery"
    if re.search(r"\b(unsubscribe|discount|sale|marketing)\b", lowered):
        return None, "marketing"
    if re.search(r"\b(urgent|emergency|asap)\b", lowered):
        return "urgent-candidate", None
    if mine and re.search(r"\b(i will|i’ll|i'll|we will)\b", lowered):
        return "promise-candidate", None
    if "?" in text:
        return "ask-candidate", None
    if re.search(r"\b(meet|meeting|appointment|tomorrow|schedule)\b", lowered):
        return "plan-candidate", None
    return None, "no-deterministic-candidate"


def read_page(request):
    start, end = validate(request)
    path = physical(request["database"])
    identity = _identity(path)
    _require_confined(path)
    admitted = generation(path)
    # Require existing WAL custody. Never create sidecars or falsely declare live files immutable.
    if Path(str(path) + "-wal").exists() and not Path(str(path) + "-shm").is_file():
        raise Refused("WAL shared-memory sidecar unavailable")
    db = sqlite3.connect(path.as_uri() + "?mode=ro", uri=True, timeout=0.5)
    db.setlimit(sqlite3.SQLITE_LIMIT_LENGTH, 2 * MAX_BODY + 65536)
    began = time.monotonic()
    ticks = 0

    def progress():
        nonlocal ticks
        ticks += 1
        return int(ticks > 10000 or time.monotonic() - began > MAX_SECONDS)

    db.set_progress_handler(progress, 1000)
    try:
        db.execute("pragma query_only=on")
        db.execute("pragma trusted_schema=off")
        db.execute("pragma temp_store=memory")
        db.execute("begin")
        schema = _schema(db, request["adapter"])
        table = "message" if request["adapter"] == "imessage-v1" else "ZWAMESSAGE"
        key = "ROWID" if table == "message" else "Z_PK"
        date_column = "date" if table == "message" else "ZMESSAGEDATE"
        if db.execute(
            "select 1 from "
            + table
            + " where typeof("
            + date_column
            + ") not in ('integer','real') limit 1"
        ).fetchone():
            raise Refused("date schema contains unclassifiable rows")
        scale = 10**9 if table == "message" else 1
        lower_date = (start - APPLE_EPOCH) * scale
        upper_date = (end - APPLE_EPOCH) * scale
        upper = request["upper"]
        current = db.execute("select max(" + key + ") from " + table).fetchone()[0] or 0
        if upper is None:
            upper = current
        if upper > current or request["after"] > upper:
            raise Refused("snapshot truncated")
        if table == "message":
            sql = """select m.ROWID,m.guid,m.date,m.is_from_me,h.id,
            m.associated_message_type,m.cache_has_attachments,
            (select count(*) from chat_message_join j where j.message_id=m.ROWID),
            (select c.chat_identifier from chat_message_join j join chat c on c.ROWID=j.chat_id where j.message_id=m.ROWID limit 1),
            (select count(*) from chat_handle_join cj where cj.chat_id=(select j.chat_id from chat_message_join j where j.message_id=m.ROWID limit 1)),
            length(cast(m.text as blob)),length(m.attributedBody),
            null,null
            from message m left join handle h on h.ROWID=m.handle_id
            where m.ROWID>? and m.ROWID<=? and m.date>=? and m.date<? order by m.ROWID limit ?"""
            raw = db.execute(
                sql,
                (request["after"], upper, lower_date, upper_date, request["page_size"]),
            ).fetchall()
        else:
            sql = """select m.Z_PK,m.ZSTANZAID,m.ZMESSAGEDATE,m.ZISFROMME,m.ZFROMJID,
            0,m.ZMESSAGETYPE,(select count(*) from ZWACHATSESSION c where c.Z_PK=m.ZCHATSESSION),
            c.ZCONTACTJID,case when c.ZSESSIONTYPE=1 then 2 when c.ZSESSIONTYPE=0 then 1 else -1 end,
            length(cast(m.ZTEXT as blob)),0,null,null
            from ZWAMESSAGE m left join ZWACHATSESSION c on c.Z_PK=m.ZCHATSESSION
            where m.Z_PK>? and m.Z_PK<=? and m.ZMESSAGEDATE>=? and m.ZMESSAGEDATE<? order by m.Z_PK limit ?"""
            raw = db.execute(
                sql,
                (request["after"], upper, lower_date, upper_date, request["page_size"]),
            ).fetchall()
        notes = []
        skips = Counter()
        gaps = []
        after = request["after"]
        for row in raw:
            (
                rowid,
                guid,
                date,
                mine,
                sender,
                reaction,
                media,
                joins,
                chat,
                members,
                ntext,
                nbody,
                text,
                body,
            ) = row
            after = rowid
            if not isinstance(chat, str) or joins != 1 or members < 1:
                gaps.append({"row": rowid, "reason": "ambiguous chat attribution"})
                continue
            if chat in request["excluded_chats"]:
                skips["excluded-chat"] += 1
                continue
            if "@broadcast" in chat or chat == "status@broadcast":
                skips["status-broadcast"] += 1
                continue
            if reaction:
                skips["reaction"] += 1
                continue
            if (
                type(mine) is not int
                or mine not in (0, 1)
                or not isinstance(guid, str)
                or not guid
            ):
                gaps.append({"row": rowid, "reason": "ambiguous message identity"})
                continue
            if not mine and (not isinstance(sender, str) or not sender):
                gaps.append({"row": rowid, "reason": "sender unknown"})
                continue
            if not mine and re.fullmatch(r"\d{3,6}", sender):
                skips["short-code"] += 1
                continue
            if type(date) not in (int, float) or not math.isfinite(date):
                gaps.append({"row": rowid, "reason": "invalid date"})
                continue
            stamp = APPLE_EPOCH + (date / 10**9 if table == "message" else date)
            if not -62135596800 <= stamp <= 253402300799:
                gaps.append({"row": rowid, "reason": "date out of range"})
                continue
            if not start <= stamp < end:
                skips["outside-window"] += 1
                continue
            if media and not ntext and not nbody:
                skips["media-only"] += 1
                continue
            if (ntext or 0) > MAX_BODY or (nbody or 0) > MAX_BODY:
                gaps.append({"row": rowid, "reason": "body byte bound"})
                continue
            if any(
                not isinstance(v, str) or len(v.encode()) > 8192 for v in (guid, chat)
            ):
                gaps.append({"row": rowid, "reason": "pointer byte bound"})
                continue
            if table == "message":
                text, body = db.execute(
                    "select text,attributedBody from message where ROWID=?", (rowid,)
                ).fetchone()
            else:
                text, body = db.execute(
                    "select ZTEXT,null from ZWAMESSAGE where Z_PK=?", (rowid,)
                ).fetchone()
            try:
                content = decode_body(text, body)
            except Refused as exc:
                gaps.append({"row": rowid, "reason": str(exc)})
                continue
            if members > 1 and not any(
                re.search(r"(?<!\w)" + re.escape(n) + r"(?!\w)", content, re.I)
                for n in request["self_names"]
            ):
                skips["group-not-addressed"] += 1
                continue
            classification, reason = _classify(content, bool(mine))
            if reason:
                skips[reason] += 1
                continue
            pointer = {
                "app": request["adapter"],
                "database": str(path),
                "id": guid,
                "row": rowid,
                "chat": chat,
            }
            notes.append(
                {
                    "id": digest(pointer),
                    "pointer": pointer,
                    "sender": "self" if mine else sender,
                    "at": datetime.fromtimestamp(stamp, timezone.utc).isoformat(),
                    "class": classification,
                    "note": "Review the source for this "
                    + classification.replace("-candidate", "")
                    + ".",
                    "media_present": bool(media),
                    "untrusted_source": True,
                    "meaning": "candidate only; no unanswered/completion/calendar claim",
                }
            )
        if _identity(path) != identity or generation(path) != admitted:
            raise Refused("database generation changed during page")
        return {
            "schema": 1,
            "sqlite_version": sqlite3.sqlite_version,
            "database_identity": identity,
            "source_generation": admitted,
            "schema_digest": schema,
            "notes": notes,
            "coverage": {
                "window": [request["start"], request["end"]],
                "after": after,
                "upper": upper,
                "examined": len(raw),
                "skipped": dict(skips),
                "gaps": gaps,
                "complete": not gaps
                and (after == upper or len(raw) < request["page_size"]),
                "scope": "one SQLite snapshot page; ROWID range, not history of edits/deletions or unseen schemas",
            },
        }
    except sqlite3.Error as exc:
        raise Refused("SQLite snapshot unavailable: " + str(exc)) from exc
    finally:
        db.close()


def existing_owner(skill, name):
    scripts = Path(__file__).resolve().parents[2] / skill / "scripts"
    if str(scripts) not in sys.path:
        sys.path.insert(0, str(scripts))
    sys.dont_write_bytecode = True
    module = importlib.import_module(name)
    if Path(module.__file__).resolve() != scripts / (name + ".py"):
        raise Refused("existing owner import origin mismatch")
    return module


def run_page(request, worker):
    validate(request)
    worker = Path(worker)
    if worker.exists() or worker.is_symlink():
        raise Refused("fresh worker directory required")
    physical(worker.parent, True)
    worker.mkdir(mode=0o700)
    source = Path(__file__).resolve()
    body = source.read_bytes()
    stage = worker / "reader.py"
    stage.write_bytes(body)
    stage.chmod(0o400)
    payload = worker / "request.json"
    payload.write_bytes(canonical(request))
    payload.chmod(0o400)
    sandbox = existing_owner("synthesis-autopilot", "evaluation_artifacts")
    owner = existing_owner("synthesis-project-management", "coordination_process")
    command, backend = sandbox._sandbox_command(
        physical(request["database"]).parent,
        worker,
        stage,
        ["--worker", str(payload), "--request-digest", digest(request)],
    )
    command.insert(command.index("-I"), "-B")
    # Execute captured public source bytes, never reopen the writable staged script.
    position = command.index(str(stage))
    command[position : position + 1] = ["-c", body.decode("utf-8")]
    result = owner.run(command, cwd=worker, timeout=15, output_bytes=1024 * 1024)
    (worker / "process-result.json").write_bytes(
        canonical(
            {
                "returncode": result.returncode,
                "stdout": result.stdout,
                "backend": backend,
            }
        )
    )
    if source.read_bytes() != body or stage.read_bytes() != body:
        raise Refused("reader source changed")
    if result.returncode:
        raise Refused("confined reader unavailable: " + result.stdout[-1000:])
    response = json.loads(result.stdout, object_pairs_hook=unique)
    response["confinement"] = backend
    return response


class OwnedDirectory:
    def __init__(self, path, fd):
        self.path, self.fd = path, fd

    def __fspath__(self):
        return str(self.path)

    def __truediv__(self, name):
        self.verify()
        return self.path / name

    def verify(self):
        now = physical(self.path, True).stat()
        opened = os.fstat(self.fd)
        if (
            (now.st_dev, now.st_ino) != (opened.st_dev, opened.st_ino)
            or now.st_uid != os.getuid()
            or stat.S_IMODE(now.st_mode) != 0o700
        ):
            raise Refused("state directory identity changed")


@contextmanager
def state_lock(home):
    home = Path(home)
    physical(home.parent, True)
    if not home.exists():
        home.mkdir(mode=0o700)
    physical(home, True)
    info = home.stat()
    if info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != 0o700:
        raise Refused("state directory must be owned and0700")
    directory = os.open(home, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    owned = OwnedDirectory(home, directory)
    fd = None
    try:
        owned.verify()
        fd = os.open(
            ".lock", os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600, dir_fd=directory
        )
        s = os.fstat(fd)
        if (
            s.st_uid != os.getuid()
            or s.st_nlink != 1
            or not stat.S_ISREG(s.st_mode)
            or stat.S_IMODE(s.st_mode) != 0o600
        ):
            raise Refused("unsafe state lock")
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise Refused("state busy") from exc
        yield owned
    finally:
        if fd is not None:
            os.close(fd)
        os.close(directory)


def atomic_state(home, name, value):
    if not isinstance(home, OwnedDirectory) or not re.fullmatch(
        r"[A-Za-z0-9_.-]+", name
    ):
        raise Refused("descriptor-owned state destination required")
    home.verify()
    dest = home / name
    if dest.exists() or dest.is_symlink():
        physical(dest)
        s = dest.stat()
        if (
            s.st_uid != os.getuid()
            or s.st_nlink != 1
            or stat.S_IMODE(s.st_mode) != 0o600
        ):
            raise Refused("unowned state destination")
    tmp = ".prepared-" + uuid.uuid4().hex
    fd = os.open(
        tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=home.fd
    )
    try:
        raw = canonical(value)
        done = 0
        while done < len(raw):
            done += os.write(fd, raw[done:])
        os.fsync(fd)
    finally:
        os.close(fd)
    home.verify()
    os.replace(tmp, name, src_dir_fd=home.fd, dst_dir_fd=home.fd)
    os.fsync(home.fd)
    home.verify()


def scan(request, home):
    validate(request)
    if request["after"] != 0 or request["upper"] is not None:
        raise Refused("managed scan starts at zero; owner supplies cursor")
    binding = {
        "request": digest(request),
        "database_identity": _identity(request["database"]),
    }
    with state_lock(home) as home:
        marker = home / "owner.json"
        if marker.exists():
            if file_json(marker) != binding:
                raise Refused("watermark belongs to different request/source")
        else:
            with os.scandir(home) as entries:
                for entry in entries:
                    if entry.name != ".lock":
                        raise Refused("unowned state directory is not adopted")
            atomic_state(home, "owner.json", binding)
        checkpoint = home / "checkpoint.json"
        query = dict(request)
        if checkpoint.exists():
            previous = file_json(checkpoint)
            if previous.get("binding") != binding or previous.get("digest") != digest(
                previous.get("page")
            ):
                raise Refused("checkpoint corrupted")
            page = previous["page"]
            if page.get("source_generation") != generation(request["database"]):
                raise Refused(
                    "source generation changed; retained pages are historical, start a new window state"
                )
            if page["coverage"]["complete"]:
                return page
            query.update(
                after=page["coverage"]["after"], upper=page["coverage"]["upper"]
            )
        page = run_page(query, home / ("attempt-" + uuid.uuid4().hex))
        if (
            checkpoint.exists()
            and page["source_generation"] != previous["page"]["source_generation"]
        ):
            raise Refused("source generation changed between pages")
        if not page["coverage"]["gaps"]:
            # Persist each pointer page before advancing. A lost stdout never loses notes.
            receipt = (
                "page-"
                + digest({"after": query["after"], "upper": page["coverage"]["upper"]})
                + ".json"
            )
            if (home / receipt).exists():
                saved = file_json(home / receipt)
                if saved != page:
                    raise Refused(
                        "previous page receipt differs; reconcile source changes"
                    )
            else:
                atomic_state(home, receipt, page)
            atomic_state(
                home,
                "checkpoint.json",
                {"binding": binding, "page": page, "digest": digest(page)},
            )
        return page


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--worker", help=argparse.SUPPRESS)
    p.add_argument("--request-digest", help=argparse.SUPPRESS)
    p.add_argument("--request")
    p.add_argument("--state")
    args = p.parse_args()
    try:
        if args.worker:
            request = file_json(Path(args.worker))
            if args.request_digest != digest(request):
                raise Refused("worker request binding changed")
            result = read_page(request)
        elif args.request and args.state:
            result = scan(file_json(Path(args.request)), Path(args.state))
        else:
            raise Refused("explicit request and owned state directory required")
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return 0
    except (Refused, OSError, ValueError) as exc:
        print(json.dumps({"status": "REFUSED", "reason": str(exc)}))
        return 2


if __name__ == "__main__":
    sys.dont_write_bytecode = True
    raise SystemExit(main())
