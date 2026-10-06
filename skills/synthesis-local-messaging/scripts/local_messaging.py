# SPDX-License-Identifier: Apache-2.0
"""Read one explicitly selected iMessage or WhatsApp window into pointer-only notes.

Run: python3 local_messaging.py --request REQUEST.json --state STATE_DIR

The database is opened read-only inside the OS sandbox (os_sandbox.py); a reader that can
open the database for writing refuses before SQLite runs. Each run reads one page of the
window and prints it as JSON: candidate notes that point at a message (app, database,
message id, row, chat) without copying its text, plus coverage (rows examined, skips by
reason, gaps). Pages are saved in STATE_DIR before the cursor moves; a page with a gap does
not move it. Exit 0 with the page, or 2 with {"status": "REFUSED", "reason": ...}.
"""

from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import errno
import fcntl
import hashlib
import json
import math
import os
from pathlib import Path
import plistlib
import re
import sqlite3
import stat
import subprocess
import sys
import tempfile
import time

MAX_BODY = 256 * 1024
MAX_PAGE = 100
MAX_SECONDS = 5
APPLE_EPOCH = 978307200
REQUEST_KEYS = {"schema", "adapter", "database", "start", "end", "page_size", "excluded_chats", "self_names"}


class Refused(ValueError):
    """Incomplete or unsafe input never becomes complete coverage."""


def digest(value) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
    return hashlib.sha256(raw.encode()).hexdigest()


def physical(path) -> Path:
    """An explicit absolute path to a regular file, reached through no symlink."""
    path = Path(path)
    if not path.is_absolute() or ".." in path.parts:
        raise Refused("explicit physical absolute path required")
    for item in (path, *path.parents):
        if stat.S_ISLNK(item.lstat().st_mode):
            raise Refused("symlink path refused")
    if not stat.S_ISREG(path.stat().st_mode):
        raise Refused("wrong file type")
    return path


def instant(value) -> float:
    if not isinstance(value, str):
        raise Refused("timestamp must be ISO8601")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise Refused("invalid timestamp") from exc
    if parsed.tzinfo is None:
        raise Refused("timestamp timezone required")
    return parsed.timestamp()


def validate(request, page_keys=False):
    keys = REQUEST_KEYS | ({"after", "upper"} if page_keys else set())
    if not isinstance(request, dict) or set(request) != keys or type(request["schema"]) is not int or request["schema"] != 1:
        raise Refused("unknown request schema")
    if request["adapter"] not in ("imessage-v1", "whatsapp-v1"):
        raise Refused("unsupported adapter")
    if type(request["page_size"]) is not int or not 1 <= request["page_size"] <= MAX_PAGE:
        raise Refused("page bound exceeded")
    if page_keys:
        after, upper = request["after"], request["upper"]
        if type(after) is not int or not 0 <= after < 2**63:
            raise Refused("integer page bound required")
        if upper is not None and (type(upper) is not int or not after <= upper < 2**63):
            raise Refused("invalid snapshot upper bound")
    start, end = instant(request["start"]), instant(request["end"])
    if not 0 < end - start <= 366 * 86400:
        raise Refused("window must be positive and at most 366 days")
    for key in ("excluded_chats", "self_names"):
        value = request[key]
        if (not isinstance(value, list) or len(value) > 1000 or len(value) != len(set(value))
                or any(not isinstance(v, str) or not v.strip() or len(v) > 200 for v in value)):
            raise Refused("invalid bounded selection")
    if not isinstance(request["database"], str):
        raise Refused("explicit database path required")
    physical(request["database"])
    return start, end


def decode_body(text, body) -> str:
    """Plain text, or the newer iMessage body format (a keyed archive of one string)."""
    if text is not None and not isinstance(text, str):
        raise Refused("non-text body")
    if text:
        if len(text.encode()) > MAX_BODY:
            raise Refused("body exceeds limit")
        return text
    if not isinstance(body, bytes) or not body or len(body) > MAX_BODY:
        raise Refused("missing/oversized attributed body")
    if not body.startswith(b"bplist00") or len(body) < 40:
        raise Refused("unsupported attributedBody encoding; typedstream is not unarchived")
    # Bound the binary plist allocation before the parser allocates object tables.
    if not 1 <= int.from_bytes(body[-24:-16], "big") <= 2048:
        raise Refused("binary plist object count exceeds limit")
    try:
        data = plistlib.loads(body)
    except Exception as exc:
        raise Refused("malformed attributedBody") from exc
    if not isinstance(data, dict) or data.get("$archiver") != "NSKeyedArchiver" or data.get("$version") != 100000:
        raise Refused("unsupported keyed archive")
    objects, top = data.get("$objects"), data.get("$top")
    if not isinstance(objects, list) or not 1 <= len(objects) <= 2048 or not isinstance(top, dict) or set(top) != {"root"}:
        raise Refused("archive object bound/root")
    seen = set()

    def value(item, depth=0):
        if depth > 8:
            raise Refused("archive depth")
        if isinstance(item, plistlib.UID):
            if item.data in seen or not 0 <= item.data < len(objects):
                raise Refused("archive cycle/reference")
            seen.add(item.data)
            return value(objects[item.data], depth + 1)
        if isinstance(item, str):
            return item
        if isinstance(item, dict):
            strings = [k for k in ("NSString", "NS.string") if k in item]
            if len(strings) != 1 or set(item) - {"NSString", "NS.string", "$class", "NS.attributes"}:
                raise Refused("unsupported attributed-string fields")
            return value(item[strings[0]], depth + 1)
        raise Refused("unsupported archive object")

    result = value(top["root"])
    if not result or len(result.encode()) > MAX_BODY:
        raise Refused("empty/oversized decoded body")
    return result


def _require_confined(path) -> None:
    """Observe a denied write-open on each input; an inherited claim of confinement is not enough."""
    for p in (Path(path), Path(str(path) + "-wal"), Path(str(path) + "-shm")):
        if not p.exists():
            continue
        physical(p)
        try:
            fd = os.open(p, os.O_WRONLY | os.O_NOFOLLOW)
        except OSError as error:
            # Read-only mounts deny with EROFS; sandbox policy with EPERM or EACCES.
            # Other failures do not prove confinement.
            if error.errno in (errno.EPERM, errno.EACCES, errno.EROFS):
                continue
            raise
        else:
            os.close(fd)
            raise Refused("OS read-only confinement is required before SQLite access")


SCHEMAS = {
    "imessage-v1": {
        "message": {"guid", "text", "attributedBody", "date", "is_from_me", "handle_id",
                    "associated_message_type", "cache_has_attachments"},
        "handle": {"id"}, "chat": {"chat_identifier"},
        "chat_message_join": {"chat_id", "message_id"}, "chat_handle_join": {"chat_id", "handle_id"}},
    "whatsapp-v1": {
        "ZWAMESSAGE": {"Z_PK", "ZSTANZAID", "ZTEXT", "ZMESSAGEDATE", "ZISFROMME", "ZFROMJID",
                       "ZCHATSESSION", "ZMESSAGETYPE"},
        "ZWACHATSESSION": {"Z_PK", "ZCONTACTJID", "ZSESSIONTYPE"}},
}
QUERIES = {
    "imessage-v1": """select m.ROWID,m.guid,m.date,m.is_from_me,h.id,m.associated_message_type,m.cache_has_attachments,
        (select count(*) from chat_message_join j where j.message_id=m.ROWID),
        (select c.chat_identifier from chat_message_join j join chat c on c.ROWID=j.chat_id where j.message_id=m.ROWID limit 1),
        (select count(*) from chat_handle_join cj where cj.chat_id=(select j.chat_id from chat_message_join j where j.message_id=m.ROWID limit 1)),
        length(cast(m.text as blob)),length(m.attributedBody)
        from message m left join handle h on h.ROWID=m.handle_id
        where m.ROWID>? and m.ROWID<=? and m.date>=? and m.date<? order by m.ROWID limit ?""",
    "whatsapp-v1": """select m.Z_PK,m.ZSTANZAID,m.ZMESSAGEDATE,m.ZISFROMME,m.ZFROMJID,0,m.ZMESSAGETYPE,
        (select count(*) from ZWACHATSESSION c where c.Z_PK=m.ZCHATSESSION),c.ZCONTACTJID,
        case when c.ZSESSIONTYPE=1 then 2 when c.ZSESSIONTYPE=0 then 1 else -1 end,length(cast(m.ZTEXT as blob)),0
        from ZWAMESSAGE m left join ZWACHATSESSION c on c.Z_PK=m.ZCHATSESSION
        where m.Z_PK>? and m.Z_PK<=? and m.ZMESSAGEDATE>=? and m.ZMESSAGEDATE<? order by m.Z_PK limit ?""",
}


def _classify(text, mine):
    lowered = text.casefold()
    if re.search(r"\b(verification|security|one.time|login|authentication)\s+code\b|\bOTP\b", text, re.I):
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


def read_page(page) -> dict:
    """The worker: runs inside the sandbox and reads one page of the window."""
    start, end = validate(page, page_keys=True)
    path = physical(page["database"])
    _require_confined(path)
    if Path(str(path) + "-wal").exists() and not Path(str(path) + "-shm").is_file():
        raise Refused("WAL shared-memory sidecar unavailable")  # never create sidecars
    adapter, imessage = page["adapter"], page["adapter"] == "imessage-v1"
    db = sqlite3.connect(path.as_uri() + "?mode=ro", uri=True, timeout=0.5)
    began, ticks = time.monotonic(), [0]

    def progress():
        ticks[0] += 1
        return int(ticks[0] > 10000 or time.monotonic() - began > MAX_SECONDS)

    db.set_progress_handler(progress, 1000)
    try:
        for pragma in ("query_only=on", "trusted_schema=off", "temp_store=memory"):
            db.execute("pragma " + pragma)
        db.execute("begin")
        for table, columns in SCHEMAS[adapter].items():
            if db.execute("select type from sqlite_master where name=?", (table,)).fetchall() != [("table",)]:
                raise Refused("missing/ambiguous table schema")
            if not columns <= {r[1] for r in db.execute('pragma table_info("' + table + '")')}:
                raise Refused("unsupported schema columns")
        table, key, date_column = ("message", "ROWID", "date") if imessage else ("ZWAMESSAGE", "Z_PK", "ZMESSAGEDATE")
        if db.execute(f"select 1 from {table} where typeof({date_column}) not in ('integer','real') limit 1").fetchone():
            raise Refused("date schema contains unclassifiable rows")
        scale = 10**9 if imessage else 1
        current = db.execute(f"select max({key}) from {table}").fetchone()[0] or 0
        upper = current if page["upper"] is None else page["upper"]
        if upper > current or page["after"] > upper:
            raise Refused("snapshot truncated")
        raw = db.execute(QUERIES[adapter], (page["after"], upper, (start - APPLE_EPOCH) * scale,
                                            (end - APPLE_EPOCH) * scale, page["page_size"])).fetchall()
        notes, skips, gaps, after = [], Counter(), [], page["after"]
        for rowid, guid, date, mine, sender, reaction, media, joins, chat, members, ntext, nbody in raw:
            after = rowid
            reason = None
            if not isinstance(chat, str) or joins != 1 or members < 1:
                gaps.append({"row": rowid, "reason": "ambiguous chat attribution"})
                continue
            if chat in page["excluded_chats"]:
                reason = "excluded-chat"  # never decoded
            elif "@broadcast" in chat:
                reason = "status-broadcast"
            elif reaction:
                reason = "reaction"
            elif type(mine) is not int or mine not in (0, 1) or not isinstance(guid, str) or not guid:
                gaps.append({"row": rowid, "reason": "ambiguous message identity"})
                continue
            elif not mine and (not isinstance(sender, str) or not sender):
                gaps.append({"row": rowid, "reason": "sender unknown"})
                continue
            elif not mine and re.fullmatch(r"\d{3,6}", sender):
                reason = "short-code"
            if reason:
                skips[reason] += 1
                continue
            if type(date) not in (int, float) or not math.isfinite(date):
                gaps.append({"row": rowid, "reason": "invalid date"})
                continue
            stamp = APPLE_EPOCH + date / scale
            if not start <= stamp < end:
                skips["outside-window"] += 1
                continue
            if media and not ntext and not nbody:
                skips["media-only"] += 1
                continue
            if (ntext or 0) > MAX_BODY or (nbody or 0) > MAX_BODY or len(guid.encode()) > 8192 or len(chat.encode()) > 8192:
                gaps.append({"row": rowid, "reason": "body or pointer byte bound"})
                continue
            if imessage:
                text, body = db.execute("select text,attributedBody from message where ROWID=?", (rowid,)).fetchone()
            else:
                text, body = db.execute("select ZTEXT,null from ZWAMESSAGE where Z_PK=?", (rowid,)).fetchone()
            try:
                content = decode_body(text, body)
            except Refused as exc:
                gaps.append({"row": rowid, "reason": str(exc)})
                continue
            if members > 1 and not any(re.search(r"(?<!\w)" + re.escape(n) + r"(?!\w)", content, re.I)
                                       for n in page["self_names"]):
                skips["group-not-addressed"] += 1
                continue
            classification, reason = _classify(content, bool(mine))
            if reason:
                skips[reason] += 1
                continue
            pointer = {"app": adapter, "database": str(path), "id": guid, "row": rowid, "chat": chat}
            notes.append({
                "id": digest(pointer), "pointer": pointer, "sender": "self" if mine else sender,
                "at": datetime.fromtimestamp(stamp, timezone.utc).isoformat(), "class": classification,
                "note": "Review the source for this " + classification.replace("-candidate", "") + ".",
                "media_present": bool(media), "untrusted_source": True,
                "meaning": "candidate only; no unanswered/completion/calendar claim"})
        return {"schema": 1, "notes": notes, "coverage": {
            "window": [page["start"], page["end"]], "after": after, "upper": upper, "examined": len(raw),
            "skipped": dict(skips), "gaps": gaps,
            "complete": not gaps and (after == upper or len(raw) < page["page_size"]),
            "scope": "one SQLite snapshot page; ROWID range, not history of edits/deletions or unseen schemas"}}
    except sqlite3.Error as exc:
        raise Refused("SQLite snapshot unavailable: " + str(exc)) from exc
    finally:
        db.close()


def run_page(page) -> dict:
    """Run the worker on one page inside the OS sandbox; the database folder is read-only there."""
    validate(page, page_keys=True)
    here = str(Path(__file__).resolve().parent)
    if here not in sys.path:
        sys.path.insert(0, here)
    import os_sandbox
    with tempfile.TemporaryDirectory(prefix="local-messaging-") as name:
        scratch = Path(name).resolve()
        stage = scratch / "reader.py"
        stage.write_bytes(Path(__file__).read_bytes())
        (scratch / "page.json").write_text(json.dumps(page), encoding="utf-8")
        command, backend = os_sandbox._sandbox_command(Path(page["database"]).parent, scratch, stage,
                                                       ["--worker", str(scratch / "page.json")])
        command.insert(command.index("-I"), "-B")
        env = {"PATH": os.defpath, "LANG": "C.UTF-8", "PYTHONDONTWRITEBYTECODE": "1", "TMPDIR": str(scratch)}
        try:
            result = subprocess.run(command, cwd=scratch, env=env, capture_output=True, timeout=15)
        except subprocess.TimeoutExpired as exc:
            raise Refused("confined reader timed out") from exc
    out = result.stdout.decode("utf-8", "replace")
    if result.returncode or len(result.stdout) > 1024 * 1024:
        raise Refused("confined reader unavailable: " + (out or result.stderr.decode("utf-8", "replace"))[-1000:])
    response = json.loads(out)
    response["confinement"] = backend
    return response


def _write(path: Path, value) -> None:
    tmp = path.with_name("." + path.name + ".tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        json.dump(value, handle, ensure_ascii=False, sort_keys=True)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(tmp, path)


def scan(request, state) -> dict:
    """Read the next page of the window; save it, then move the cursor. A gap leaves the cursor."""
    validate(request)
    state = Path(state)
    if state.is_symlink():
        raise Refused("symlink path refused")
    state.mkdir(mode=0o700, exist_ok=True)
    info = Path(request["database"]).stat()
    binding = {"request": digest(request), "database": [info.st_dev, info.st_ino]}
    with open(state / ".lock", "a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise Refused("state busy") from exc
        cursor_file = state / "cursor.json"
        cursor = json.loads(cursor_file.read_text(encoding="utf-8")) if cursor_file.exists() else None
        if cursor is None and any(not re.fullmatch(r"\.lock|page-\d{12}-\d{12}\.json|\..+\.tmp", p.name)
                                  for p in state.iterdir()):
            raise Refused("state directory holds files this reader did not write")
        if cursor is not None and cursor.get("binding") != binding:
            raise Refused("this state belongs to another window or database; use one state directory per window")
        if cursor is not None and cursor["complete"]:
            return json.loads((state / cursor["last"]).read_text(encoding="utf-8"))
        after = cursor["after"] if cursor else 0
        page = run_page({**request, "after": after, "upper": cursor["upper"] if cursor else None})
        coverage = page["coverage"]
        if coverage["gaps"]:
            return page  # reported, and the window does not advance past it
        name = f"page-{after:012d}-{coverage['after']:012d}.json"
        _write(state / name, page)  # notes are saved before the cursor moves
        _write(cursor_file, {"binding": binding, "after": coverage["after"], "upper": coverage["upper"],
                             "complete": coverage["complete"], "last": name})
        return page


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0], allow_abbrev=False)
    parser.add_argument("--request", help="explicit read-only request JSON")
    parser.add_argument("--state", help="this window's own state directory")
    parser.add_argument("--worker", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    try:
        if args.worker:
            result = read_page(json.loads(Path(args.worker).read_text(encoding="utf-8")))
        elif args.request and args.state:
            result = scan(json.loads(physical(Path(args.request).absolute()).read_text(encoding="utf-8")), args.state)
        else:
            raise Refused("explicit request and state directory required")
    except (Refused, OSError, ValueError) as exc:
        print(json.dumps({"status": "REFUSED", "reason": str(exc)}))
        return 2
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.dont_write_bytecode = True
    sys.exit(main())
