"""Versioned report boundary; observations remain evidence, never permissions.

The shared JSON Schema is bundled byte-identically in Console. This dependency-
free validator supports exactly the schema keywords used here and rejects others.
Identity binds the local machine/home, selection and five exact source artifacts;
it is not a signature or a claim that every source-tree byte was audited.
"""

from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import re
import socket
import stat
from datetime import datetime, timedelta, timezone

SCHEMA_PATH = (
    Path(__file__).resolve().parents[1] / "references/conformance-report-v1.schema.json"
)
SCHEMA_ID = "https://synthesisengineering.org/schemas/conformance-report/v1"
PLANES = ("source", "installed", "native", "continuity", "capability")
BINDING_PATHS = (
    ".claude-plugin/plugin.json",
    ".codex-plugin/plugin.json",
    "skills/synthesis-agent-conformance/scripts/conformance.py",
    "skills/synthesis-agent-conformance/scripts/report_contract.py",
    "skills/synthesis-agent-conformance/references/conformance-report-v1.schema.json",
)
MAX_BYTES = 4 * 1024 * 1024
TTL_SECONDS = 4 * 3600


class ReportError(ValueError):
    pass


def _sig(st):
    return (
        st.st_dev,
        st.st_ino,
        st.st_mode,
        st.st_size,
        st.st_mtime_ns,
        st.st_ctime_ns,
        st.st_nlink,
    )


def read_bytes(path, limit=MAX_BYTES):
    path = Path(path)
    ancestry = []
    for parent in path.parents:
        st = parent.lstat()
        if not stat.S_ISDIR(st.st_mode):
            raise ReportError("report path ancestry must be directories")
        ancestry.append((parent, (st.st_dev, st.st_ino, st.st_mode)))
    before = path.lstat()
    if (
        not stat.S_ISREG(before.st_mode)
        or before.st_nlink != 1
        or before.st_size > limit
    ):
        raise ReportError("report input must be a bounded single-link regular file")
    fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW)
    try:
        if _sig(before) != _sig(os.fstat(fd)):
            raise ReportError("report input replaced before read")
        data = bytearray()
        while True:
            part = os.read(fd, min(65536, limit + 1 - len(data)))
            if not part:
                break
            data.extend(part)
            if len(data) > limit:
                raise ReportError("report input grew beyond bound")
        if _sig(before) != _sig(os.fstat(fd)) or _sig(before) != _sig(path.lstat()):
            raise ReportError("report input changed during read")
        for parent, sig in ancestry:
            st = parent.lstat()
            if (st.st_dev, st.st_ino, st.st_mode) != sig:
                raise ReportError("report path ancestry changed")
        return bytes(data)
    finally:
        os.close(fd)


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ReportError("duplicate JSON property")
        result[key] = value
    return result


def decode(raw):
    if len(raw) > MAX_BYTES:
        raise ReportError("report exceeds byte ceiling")
    try:
        value = json.loads(
            raw,
            object_pairs_hook=unique,
            parse_float=lambda _: (_ for _ in ()).throw(ReportError("noninteger JSON")),
            parse_constant=lambda _: (_ for _ in ()).throw(
                ReportError("nonfinite JSON")
            ),
        )
    except (RecursionError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ReportError("invalid or excessive report JSON") from exc
    pending = [(value, 0)]
    count = 0
    while pending:
        item, depth = pending.pop()
        count += 1
        if count > 100000 or depth > 32:
            raise ReportError("report JSON nesting or node bound")
        children = (
            item.values()
            if isinstance(item, dict)
            else item
            if isinstance(item, list)
            else ()
        )
        pending.extend((child, depth + 1) for child in children)
    return value


def timestamp(value):
    if not isinstance(value, str) or not re.fullmatch(
        r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d{1,6})?(?:Z|\+00:00)", value
    ):
        raise ReportError("UTC ISO timestamp required")
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ReportError("invalid UTC date") from exc


def schema_validate(value, schema):
    allowed = {
        "$schema",
        "$id",
        "type",
        "const",
        "enum",
        "anyOf",
        "additionalProperties",
        "required",
        "properties",
        "minLength",
        "maxLength",
        "pattern",
        "format",
        "minItems",
        "maxItems",
        "items",
    }
    if set(schema) - allowed:
        raise ReportError("unsupported schema keyword")
    if "anyOf" in schema:
        for choice in schema["anyOf"]:
            try:
                schema_validate(value, choice)
                return
            except ReportError:
                pass
        raise ReportError("no schema variant matches")
    types = {
        "object": lambda x: isinstance(x, dict),
        "array": lambda x: isinstance(x, list),
        "integer": lambda x: type(x) is int,
        "boolean": lambda x: type(x) is bool,
        "string": lambda x: isinstance(x, str),
        "null": lambda x: x is None,
    }
    wanted = schema.get("type", [])
    wanted = wanted if isinstance(wanted, list) else [wanted]
    if wanted and not any(types[t](value) for t in wanted):
        raise ReportError("schema type mismatch")
    if "const" in schema and (
        type(value) is not type(schema["const"]) or value != schema["const"]
    ):
        raise ReportError("schema constant mismatch")
    if "enum" in schema and value not in schema["enum"]:
        raise ReportError("schema enum mismatch")
    if isinstance(value, dict):
        props = schema.get("properties", {})
        if set(schema.get("required", [])) - set(value) or (
            schema.get("additionalProperties") is False and set(value) - set(props)
        ):
            raise ReportError("missing or unknown report property")
        for key in value:
            schema_validate(value[key], props[key])
    if isinstance(value, str):
        if (
            not schema.get("minLength", 0)
            <= len(value)
            <= schema.get("maxLength", MAX_BYTES)
        ):
            raise ReportError("report string length exceeded")
        if "pattern" in schema and not re.search(schema["pattern"], value):
            raise ReportError("report string pattern mismatch")
        if schema.get("format") == "date-time":
            timestamp(value)
    if isinstance(value, list):
        if not schema.get("minItems", 0) <= len(value) <= schema.get("maxItems", 4096):
            raise ReportError("report item bound exceeded")
        for item in value:
            schema_validate(item, schema["items"])


def plane_status(checks):
    if not checks:
        return "UNKNOWN"
    required = [x for x in checks if x["required"]]
    if any(x["status"] == "FAIL" for x in required):
        return "FAIL"
    if any(x["status"] != "PASS" for x in required):
        return "UNKNOWN"
    if required:
        return "PASS"
    if all(x["status"] == "UNSUPPORTED" for x in checks):
        return "UNSUPPORTED"
    if any(x["status"] == "WARN" for x in checks):
        return "WARN"
    return "UNKNOWN"


def identity(
    source_root,
    producer,
    project=None,
    repo_root=None,
    profile="public",
    home=None,
    hostname=None,
):
    root = Path(source_root).resolve(strict=True)
    files = [[name, digest(read_bytes(root / name))] for name in BINDING_PATHS]
    home = str(Path(home or Path.home()).resolve(strict=True))
    return {
        "machine_sha256": digest(
            ((hostname or socket.gethostname()) + "\0" + home).encode()
        ),
        "source_root": str(root),
        "source_binding_sha256": digest(
            json.dumps(files, separators=(",", ":")).encode()
        ),
        "producer_sha256": digest(read_bytes(producer)),
        "project": str(Path(project).resolve()) if project else None,
        "repo_root": str(Path(repo_root).resolve()) if repo_root else None,
        "profile": profile,
    }


def validate(report, *, expected=None, now=None, fresh=False):
    # Match the actual pretty-printed producer, including its final newline.
    try:
        encoded = (json.dumps(report, indent=2, allow_nan=False) + "\n").encode()
    except (ValueError, TypeError, RecursionError) as exc:
        raise ReportError("report cannot be encoded") from exc
    if len(encoded) > MAX_BYTES:
        raise ReportError("report exceeds producer byte ceiling")
    schema_bytes = read_bytes(SCHEMA_PATH)
    schema_validate(report, decode(schema_bytes))
    if report["schema_sha256"] != digest(schema_bytes):
        raise ReportError("report schema bytes mismatch")
    checked = timestamp(report["checked_at"])
    expires = timestamp(report["expires_at"])
    if (expires - checked).total_seconds() != TTL_SECONDS:
        raise ReportError("report expiry is not the contract TTL")
    if expected is not None and report["identity"] != expected:
        raise ReportError("report machine, project, source or profile identity changed")
    if fresh:
        now = now or datetime.now(timezone.utc)
        if checked > now + timedelta(seconds=5) or now >= expires:
            raise ReportError("report is stale or from a future clock")
    names = set()
    for check in report["checks"]:
        if check["name"] in names:
            raise ReportError("duplicate check identity")
        names.add(check["name"])
        status = check["status"]
        ok = check["ok"]
        if (
            status == "PASS"
            and ok is not True
            or status in {"FAIL", "WARN"}
            and ok is not False
            or status in {"UNKNOWN", "UNSUPPORTED"}
            and ok is not None
            or status == "WARN"
            and check["required"]
            or status == "UNSUPPORTED"
            and check["required"]
            or check["outcome"] is not None
            and check["outcome"] != status
        ):
            raise ReportError("check outcome contradicts its observed evidence")
    planes = {
        p: plane_status([c for c in report["checks"] if c["plane"] == p])
        for p in PLANES
    }
    status = plane_status(report["checks"])
    if status not in {"PASS", "FAIL"}:
        status = "UNKNOWN"
    if (
        report["command"] == "all"
        and any(planes[p] != "PASS" for p in PLANES)
        and status == "PASS"
    ):
        status = "UNKNOWN"
    if (
        planes != report["planes"]
        or report["status"] != status
        or report["ok"] != (status == "PASS")
    ):
        raise ReportError("report aggregate contradicts its checks")
    return report


def build(checks, binding, command="partial", now=None):
    now = now or datetime.now(timezone.utc)
    items = [dict(c) for c in checks]
    for check in items:
        if check["plane"] == "live":
            check["plane"] = "native"
    planes = {p: plane_status([c for c in items if c["plane"] == p]) for p in PLANES}
    status = plane_status(items)
    if (
        status not in {"PASS", "FAIL"}
        or command == "all"
        and status == "PASS"
        and any(value != "PASS" for value in planes.values())
    ):
        status = "UNKNOWN"
    report = {
        "schema_id": SCHEMA_ID,
        "schema_version": 1,
        "schema_sha256": digest(read_bytes(SCHEMA_PATH)),
        "checked_at": now.isoformat(),
        "expires_at": (now + timedelta(seconds=TTL_SECONDS)).isoformat(),
        "command": command,
        "identity": binding,
        "ok": status == "PASS",
        "status": status,
        "planes": planes,
        "checks": items,
    }
    return validate(report)
