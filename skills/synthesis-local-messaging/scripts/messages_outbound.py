# SPDX-License-Identifier: Apache-2.0
"""Confined, bounded outbound observation. Matching rows never establish causality."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import sqlite3
import stat
import sys
import time

import local_messaging as lm

SCHEMA = "imessage-outbound-v1"
REQUIRED = {
    "message": {
        "ROWID",
        "guid",
        "text",
        "attributedBody",
        "date",
        "is_from_me",
        "handle_id",
        "service",
        "error",
        "is_sent",
    },
    "chat": {"ROWID", "guid", "service_name", "account_id"},
    "handle": {"ROWID", "id"},
    "chat_message_join": {"chat_id", "message_id"},
    "chat_handle_join": {"chat_id", "handle_id"},
}


def source_bytes(path, limit=1024 * 1024):
    path = lm.physical(path)
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    try:
        before = os.fstat(fd)
        if before.st_size > limit or before.st_nlink != 1:
            raise lm.Refused("source bound or hardlink")
        raw = os.read(fd, limit + 1)
        if (
            len(raw) != before.st_size
            or lm.stable_stat(before) != lm.stable_stat(os.fstat(fd))
            or lm.stable_stat(before) != lm.stable_stat(lm.physical(path).stat())
        ):
            raise lm.Refused("source changed during capture")
        return raw
    finally:
        os.close(fd)


def source_identity(path):
    s = lm.physical(path).stat()
    return [s.st_dev, s.st_ino, stat.S_IMODE(s.st_mode), s.st_uid]


def _schema(db):
    result = {}
    for table, columns in REQUIRED.items():
        definition = db.execute(
            "select type,sql from sqlite_master where name=?", (table,)
        ).fetchall()
        if len(definition) != 1 or definition[0][0] != "table":
            raise lm.Refused("qualified outbound table schema unavailable")
        info = db.execute('pragma table_info("' + table + '")').fetchall()
        # ROWID may be implicit in native SQLite tables.
        names = {r[1] for r in info} | {"ROWID"}
        if not columns <= names:
            raise lm.Refused("qualified outbound columns unavailable")
        result[table] = [definition[0][1], info]
    return lm.digest(result)


def query(request):
    if (
        not isinstance(request, dict)
        or set(request)
        != {
            "schema",
            "route",
            "destination",
            "text_sha256",
            "request_digest",
            "baseline",
        }
        or request["schema"] != SCHEMA
    ):
        raise lm.Refused("exact outbound query required")
    route = request["route"]
    if not isinstance(route, dict) or route.get("service") != "iMessage":
        raise lm.Refused("explicit iMessage route required")
    path = lm.physical(route["database"])
    lm._require_confined(path)
    admitted, identity = lm.generation(path), source_identity(path)
    if admitted["-wal"] is None or admitted["-shm"] is None:
        raise lm.Refused(
            "existing WAL and SHM required; no source sidecars may be created"
        )
    db = sqlite3.connect(path.as_uri() + "?mode=ro", uri=True, timeout=1)
    db.setlimit(sqlite3.SQLITE_LIMIT_LENGTH, 1024 * 1024)
    deadline = time.monotonic() + 5
    db.set_progress_handler(lambda: int(time.monotonic() > deadline), 1000)
    try:
        db.execute("pragma query_only=on")
        db.execute("pragma trusted_schema=off")
        db.execute("pragma temp_store=memory")
        db.execute("begin")
        schema = _schema(db)
        chats = db.execute(
            "select ROWID,service_name,account_id from chat where guid=? limit 2",
            (route["chat_id"],),
        ).fetchall()
        if len(chats) != 1 or chats[0][1:] != (
            "iMessage",
            route["database_account_id"],
        ):
            raise lm.Refused("database account/chat route differs")
        chat = chats[0][0]
        members = db.execute(
            "select h.ROWID,h.id from chat_handle_join j join handle h on h.ROWID=j.handle_id where j.chat_id=? limit 3",
            (chat,),
        ).fetchall()
        if len(members) != 1 or members[0][1] != request["destination"]:
            raise lm.Refused("database recipient membership differs")
        upper = db.execute("select coalesce(max(ROWID),0) from message").fetchone()[0]
        if type(upper) is not int or not 0 <= upper < 2**63:
            raise lm.Refused("outbound cursor bound")
        anchor = (
            db.execute("select guid from message where ROWID=?", (upper,)).fetchone()
            if upper
            else None
        )
        if upper and (
            not isinstance(anchor[0], str) or not anchor[0] or len(anchor[0]) > 8192
        ):
            raise lm.Refused("outbound cursor identity unknown")
        baseline = request["baseline"]
        current = {
            "identity": identity,
            "schema_digest": schema,
            "upper": upper,
            "anchor": anchor[0] if anchor else None,
        }
        observations = []
        if baseline is not None:
            if (
                not isinstance(baseline, dict)
                or set(baseline) != set(current)
                or baseline["identity"] != identity
                or baseline["schema_digest"] != schema
                or type(baseline["upper"]) is not int
                or not 0 <= baseline["upper"] <= upper
            ):
                raise lm.Refused(
                    "outbound source replaced, changed schema or regressed cursor"
                )
            prior = (
                db.execute(
                    "select guid from message where ROWID=?", (baseline["upper"],)
                ).fetchone()
                if baseline["upper"]
                else None
            )
            if (prior[0] if prior else None) != baseline["anchor"]:
                raise lm.Refused("outbound cursor anchor changed")
            rows = db.execute(
                "select ROWID,guid,is_from_me,service,error,is_sent,date,length(cast(text as blob)),length(attributedBody) from message where ROWID>? order by ROWID limit 101",
                (baseline["upper"],),
            ).fetchall()
            if len(rows) > 100:
                raise lm.Refused("outbound observation exceeds 100-row bound")
            for rowid, guid, mine, service, error, sent, date, ntext, nbody in rows:
                if mine != 1:
                    continue
                if any(
                    type(n) is not int or not 0 <= n <= lm.MAX_BODY
                    for n in (ntext or 0, nbody or 0)
                ):
                    raise lm.Refused("outbound body bound")
                text, body = db.execute(
                    "select text,attributedBody from message where ROWID=?", (rowid,)
                ).fetchone()
                content = lm.decode_body(text, body)
                if (
                    hashlib.sha256(content.encode()).hexdigest()
                    != request["text_sha256"]
                ):
                    continue
                joins = db.execute(
                    "select chat_id from chat_message_join where message_id=? limit 3",
                    (rowid,),
                ).fetchall()
                if joins != [(chat,)] or service != "iMessage":
                    raise lm.Refused("matching text has ambiguous or different route")
                if (
                    not isinstance(guid, str)
                    or not guid
                    or len(guid.encode()) > 8192
                    or any(type(n) is not int for n in (error, sent, date))
                    or sent not in (0, 1)
                ):
                    raise lm.Refused("outbound identity/status unavailable")
                observations.append(
                    {
                        "row": rowid,
                        "native_id": guid,
                        "error": error,
                        "is_sent": sent,
                        "date": date,
                    }
                )
        if source_identity(path) != identity or lm.generation(path) != admitted:
            raise lm.Refused("outbound source generation changed during snapshot")
        return {
            "schema": SCHEMA,
            "request_digest": request["request_digest"],
            "query_digest": lm.digest(request),
            "baseline": current,
            "source_generation": admitted,
            "observations": observations,
            "acknowledgement": "UNKNOWN",
        }
    except sqlite3.Error as exc:
        raise lm.Refused("outbound SQLite snapshot unavailable: " + str(exc)) from exc
    finally:
        db.close()


def run_query(request, worker, *, expected_sources=None):
    """Execute captured readers, bound to the attempt when one is supplied.

    A standalone read has no prior native-attempt qualification. Native attempt
    callers must pass that qualification's identities, never recalculate them
    from the newly captured source.
    """
    names = ("local_messaging.py", "messages_outbound.py")
    expected = None
    if expected_sources is not None:
        if not isinstance(expected_sources, dict) or any(
            not isinstance(expected_sources.get(name), str)
            or len(expected_sources[name]) != 64
            or any(c not in "0123456789abcdef" for c in expected_sources[name])
            for name in names
        ):
            raise lm.Refused("qualified reader source identities required")
        expected = {name: expected_sources[name] for name in names}
    worker = Path(worker)
    if worker.exists() or worker.is_symlink():
        raise lm.Refused("fresh outbound worker required")
    lm.physical(worker.parent, True)
    worker.mkdir(mode=0o700)
    paths = [Path(lm.__file__), Path(__file__)]
    captured = [source_bytes(p) for p in paths]
    if expected is not None and any(
        hashlib.sha256(raw).hexdigest() != expected[name]
        for name, raw in zip(names, captured)
    ):
        raise lm.Refused("captured reader differs from qualified implementation")
    stage = worker / "reader.py"
    program = (
        "import sys,types\nm=types.ModuleType('local_messaging')\nsys.modules['local_messaging']=m\nexec("
        + repr(captured[0].decode())
        + ",m.__dict__)\nexec("
        + repr(captured[1].decode())
        + ",globals())\n"
    )
    stage.write_text(program)
    stage.chmod(0o400)
    payload = worker / "query.json"
    payload.write_bytes(lm.canonical(request))
    payload.chmod(0o400)
    sandbox = lm.existing_owner("synthesis-autopilot", "evaluation_artifacts")
    owner = lm.existing_owner("synthesis-project-management", "coordination_process")
    command, backend = sandbox._sandbox_command(
        lm.physical(request["route"]["database"]).parent,
        worker,
        stage,
        [str(payload), lm.digest(request)],
    )
    command.insert(command.index("-I"), "-B")
    i = command.index(str(stage))
    command[i : i + 1] = ["-c", program]
    result = owner.run(command, cwd=worker, timeout=15, output_bytes=1024 * 1024)
    (worker / "process-result.json").write_bytes(
        lm.canonical(
            {
                "returncode": result.returncode,
                "stdout": result.stdout,
                "backend": backend,
            }
        )
    )
    if (
        any(source_bytes(p) != raw for p, raw in zip(paths, captured))
        or source_bytes(stage) != program.encode()
    ):
        raise lm.Refused("captured outbound reader changed")
    if result.returncode:
        raise lm.Refused(
            "confined outbound reader unavailable: " + result.stdout[-1000:]
        )
    response = json.loads(result.stdout, object_pairs_hook=lm.unique)
    if not isinstance(response, dict) or response.get("query_digest") != lm.digest(
        request
    ):
        raise lm.Refused("outbound response binding differs")
    response["confinement"] = backend
    return response


if __name__ == "__main__":
    incoming = lm.file_json(Path(sys.argv[1]))
    if lm.digest(incoming) != sys.argv[2]:
        raise lm.Refused("outbound query changed")
    print(lm.canonical(query(incoming)).decode())
