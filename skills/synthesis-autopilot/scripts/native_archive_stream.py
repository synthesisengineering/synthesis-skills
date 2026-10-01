"""Bounded one-generation native evidence segments under the existing journal.

This codec never enrolls a native process or grants authority. The managed
commands bind an exact reviewed snapshot and an explicitly finite allowance.
Each partition is owned by journal_storage; journal events remain the only
mutation authority. No global storage or product quota is raised.
"""

from __future__ import annotations
from contextlib import contextmanager
from copy import deepcopy
import hashlib
import os
from pathlib import Path
import stat
import time
import native_archive as a
import native_observations as native
import journal_storage as storage

MAX_SNAPSHOT_BYTES = 16 * 1024**3
DEFAULT_CAPACITY_BYTES = a.MAX_ARCHIVE_BYTES
MAX_SEGMENTS = 4096
MIN_SEGMENT_BYTES = a.CHUNK_BYTES
MAX_SEGMENT_BYTES = a.MAX_SOURCE_BYTES
MAX_STREAMS = 64
MAX_SECONDS = 120
MAX_PHYSICAL_MEMBERS = 1048576


def _deadline(seconds=MAX_SECONDS):
    if type(seconds) not in (int, float) or not 0 < seconds <= MAX_SECONDS:
        raise ValueError("finite archive operation deadline required")
    return time.monotonic() + seconds


def _tick(deadline):
    if time.monotonic() >= deadline:
        raise ValueError(
            "bounded archive operation deadline exhausted; evidence retained"
        )


@contextmanager
def _opened(binding):
    native._validate_binding(binding)
    path = Path(binding["path"])
    if not path.is_absolute() or ".." in path.parts:
        raise ValueError("absolute source without traversal required")
    parent = storage._safe_directory(path.parent)
    try:
        fd = os.open(
            path.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent
        )
        with os.fdopen(fd, "rb", buffering=0) as stream:
            before = os.fstat(stream.fileno())
            if (
                not stat.S_ISREG(before.st_mode)
                or before.st_nlink != 1
                or (before.st_dev, before.st_ino)
                != (binding["device"], binding["inode"])
            ):
                raise ValueError("source identity, alias or type changed")
            header = stream.read(binding["header_length"])
            if a._sha(header) != binding["header_sha256"]:
                raise ValueError("enrolled source header changed")
            yield stream, before
            after = os.fstat(stream.fileno())
            named = os.stat(path.name, dir_fd=parent, follow_symlinks=False)
            if a._fingerprint(before) != a._fingerprint(after) or a._fingerprint(
                after
            ) != a._fingerprint(named):
                raise ValueError("source changed during bounded read")
            storage._same_directory(path.parent, parent)
            repeated = storage._safe_directory(path.parent)
            try:
                if (os.fstat(repeated).st_dev, os.fstat(repeated).st_ino) != (
                    os.fstat(parent).st_dev,
                    os.fstat(parent).st_ino,
                ):
                    raise ValueError("source ancestry changed")
            finally:
                os.close(repeated)
    finally:
        os.close(parent)


def describe(
    binding, *, target_bytes, segment_bytes=MAX_SEGMENT_BYTES, seconds=MAX_SECONDS
):
    """Streaming proposal only. Its returned digests do not authorize a copy."""
    a._size(target_bytes, MAX_SNAPSHOT_BYTES)
    a._size(segment_bytes, MAX_SEGMENT_BYTES)
    if segment_bytes < MIN_SEGMENT_BYTES or target_bytes < binding["header_length"]:
        raise ValueError("segment/header lower bound")
    if (target_bytes + segment_bytes - 1) // segment_bytes > MAX_SEGMENTS:
        raise ValueError("snapshot segment inventory bound")
    end = _deadline(seconds)
    segments = []
    full = hashlib.sha256()
    offset = 0
    line_ordinal = 0
    previous = 10
    with _opened(binding) as (stream, stamp):
        if stamp.st_size < target_bytes:
            raise ValueError("source does not cover snapshot")
        stream.seek(0)
        while offset < target_bytes:
            _tick(end)
            count = min(segment_bytes, target_bytes - offset)
            body = stream.read(count)
            if len(body) != count:
                raise ValueError("short snapshot source")
            full.update(body)
            segments.append(
                {
                    "index": len(segments),
                    "offset": offset,
                    "bytes": count,
                    "sha256": a._sha(body),
                    "starts_at_line": offset == 0 or previous == 10,
                    "line_ordinal": line_ordinal,
                }
            )
            previous = body[-1]
            offset += count
            line_ordinal += body.count(b"\n")
        _tick(end)
    result = {
        "schema_version": 1,
        "kind": "native-evidence-snapshot",
        "binding": deepcopy(binding),
        "target_bytes": target_bytes,
        "target_sha256": full.hexdigest(),
        "segments": segments,
        "source_stat": list(a._fingerprint(stamp)),
        "observed_bytes": stamp.st_size,
        "codec_sha256": a._sha(Path(__file__).read_bytes()),
        "authority_granted": False,
    }
    _snapshot(result)
    return result


def _snapshot(value):
    a._keys(
        value,
        (
            "schema_version",
            "kind",
            "binding",
            "target_bytes",
            "target_sha256",
            "segments",
            "source_stat",
            "observed_bytes",
            "codec_sha256",
            "authority_granted",
        ),
    )
    if (
        type(value["schema_version"]) is not int
        or value["schema_version"] != 1
        or value["kind"] != "native-evidence-snapshot"
        or value["authority_granted"] is not False
    ):
        raise ValueError("invalid snapshot schema or authority")
    native._validate_binding(value["binding"])
    a._size(value["target_bytes"], MAX_SNAPSHOT_BYTES)
    a._hash(value["target_sha256"])
    a._hash(value["codec_sha256"])
    a._size(value["observed_bytes"], 2**63 - 1)
    if (
        value["observed_bytes"] < value["target_bytes"]
        or value["target_bytes"] < value["binding"]["header_length"]
    ):
        raise ValueError("snapshot coverage bound")
    stamp = value["source_stat"]
    if (
        not isinstance(stamp, list)
        or len(stamp) != 7
        or any(type(x) is not int for x in stamp)
        or stamp[:2] != [value["binding"]["device"], value["binding"]["inode"]]
        or stamp[4] != value["observed_bytes"]
    ):
        raise ValueError("snapshot source identity differs")
    if (
        not isinstance(value["segments"], list)
        or not 1 <= len(value["segments"]) <= MAX_SEGMENTS
    ):
        raise ValueError("snapshot segment count bound")
    offset = 0
    for index, item in enumerate(value["segments"]):
        a._keys(
            item,
            ("index", "offset", "bytes", "sha256", "starts_at_line", "line_ordinal"),
        )
        if (
            type(item["index"]) is not int
            or item["index"] != index
            or type(item["offset"]) is not int
            or item["offset"] != offset
            or type(item["starts_at_line"]) is not bool
        ):
            raise ValueError("snapshot has gap/overlap/noncausal range")
        a._size(item["bytes"], MAX_SEGMENT_BYTES)
        a._hash(item["sha256"])
        a._size(item["line_ordinal"], MAX_SNAPSHOT_BYTES, zero=True)
        offset += item["bytes"]
    if (
        offset != value["target_bytes"]
        or value["segments"][0]["starts_at_line"] is not True
        or value["segments"][0]["line_ordinal"] != 0
    ):
        raise ValueError("snapshot target coverage differs")
    if len(storage.canonical(value)) > a.MAX_MANIFEST_BYTES:
        raise ValueError("snapshot descriptor byte bound")


def plan(snapshot, route, *, additional_capacity_bytes=0):
    result = {
        "schema_version": 1,
        "kind": "native-evidence-stream-plan",
        "snapshot": deepcopy(snapshot),
        "route": deepcopy(route),
        "additional_capacity_bytes": additional_capacity_bytes,
        "attachment_discovery": "UNKNOWN",
        "authority_granted": False,
    }
    validate_plan(result)
    return result


def validate_plan(value):
    a._keys(
        value,
        (
            "schema_version",
            "kind",
            "snapshot",
            "route",
            "additional_capacity_bytes",
            "attachment_discovery",
            "authority_granted",
        ),
    )
    if (
        type(value["schema_version"]) is not int
        or value["schema_version"] != 1
        or value["kind"] != "native-evidence-stream-plan"
        or value["authority_granted"] is not False
        or value["attachment_discovery"] != "UNKNOWN"
    ):
        raise ValueError("stream cannot infer discovery or authority")
    _snapshot(value["snapshot"])
    a._size(
        value["additional_capacity_bytes"],
        MAX_SNAPSHOT_BYTES - DEFAULT_CAPACITY_BYTES,
        zero=True,
    )
    route = value["route"]
    a._keys(
        route,
        (
            "schema_version",
            "project_id",
            "privacy_domain",
            "retention_class",
            "classification",
            "source_domains",
            "source_generation",
        ),
    )
    # Reuse exactly the existing routing owner for common privacy semantics.
    a._route(
        {**route, "reviewed_bytes": 1, "reviewed_sha256": "0" * 64, "attachments": []},
        value["snapshot"]["binding"],
    )
    if len(storage.canonical(value)) > a.MAX_MANIFEST_BYTES:
        raise ValueError("stream plan manifest bound")


def _streams(state):
    values = state.get("extensions", {}).get("native_archive_streams", {})
    if not isinstance(values, dict) or len(values) > MAX_STREAMS:
        raise ValueError("stream inventory bound")
    return values


def admit_capacity(state, new_plan=None):
    streams = _streams(state)
    plans = [row["plan"] for row in streams.values()]
    if new_plan is not None:
        plans.append(new_plan)
    if len(plans) > MAX_STREAMS:
        raise ValueError("stream identity capacity exhausted")
    admitted = DEFAULT_CAPACITY_BYTES
    logical = 0
    domain = None
    for p in plans:
        validate_plan(p)
        admitted += p["additional_capacity_bytes"]
        logical += p["snapshot"]["target_bytes"]
        route = tuple(
            p["route"][k] for k in ("project_id", "privacy_domain", "retention_class")
        )
        if domain is not None and domain != route:
            raise ValueError("stream crosses privacy/deletion domain")
        domain = route
    for entry in state.get("extensions", {}).get("native_archives", {}).values():
        m = entry["manifest"]
        a._validate_manifest(m)
        logical += m["source_bytes"] + sum(x.get("bytes", 0) for x in m["attachments"])
        route = tuple(
            m["route"][k] for k in ("project_id", "privacy_domain", "retention_class")
        )
        if domain is not None and domain != route:
            raise ValueError("stream crosses existing archive domain")
    if admitted > MAX_SNAPSHOT_BYTES or logical > admitted:
        raise ValueError("explicit aggregate archive capacity exhausted")
    return admitted


def partition(home, identity, p, index):
    a._id(identity)
    validate_plan(p)
    if type(index) is not int or not 0 <= index < len(p["snapshot"]["segments"]):
        raise ValueError("segment index bound")
    return (
        Path(home) / "native-archive-streams" / identity / a.digest(p) / f"{index:06}"
    )


def _physical(home, admitted, *, extra=0):
    """Count actual retained partitions, including crash leftovers, before write."""
    root = Path(home) / "native-archive-streams"
    if not root.exists():
        if extra > admitted + a.CHUNK_BYTES:
            raise ValueError("physical archive capacity exhausted")
        return
    end = _deadline()
    total = 0
    count = 0

    # Directory handles/no-follow prevent special nodes and symlink traversal.
    def walk(path, depth):
        nonlocal total, count
        _tick(end)
        if depth > 6:
            raise ValueError("unexpected archive partition depth")
        fd = storage._safe_directory(path)
        try:
            for item in os.scandir(fd):
                count += 1
                if count > MAX_PHYSICAL_MEMBERS:
                    raise ValueError("archive physical member bound")
                info = item.stat(follow_symlinks=False)
                if stat.S_ISDIR(info.st_mode):
                    walk(path / item.name, depth + 1)
                elif stat.S_ISREG(info.st_mode) and info.st_nlink == 1:
                    total += info.st_size
                    if total + extra > admitted + a.CHUNK_BYTES:
                        raise ValueError("physical archive capacity exhausted")
                else:
                    raise ValueError("unsafe retained archive partition member")
            storage._same_directory(path, fd)
        finally:
            os.close(fd)

    walk(root, 0)


def capture_segment(home, identity, p, index, *, admitted=None):
    validate_plan(p)
    spec = p["snapshot"]["segments"][index]
    binding = p["snapshot"]["binding"]
    admitted = (
        DEFAULT_CAPACITY_BYTES + p["additional_capacity_bytes"]
        if admitted is None
        else admitted
    )
    a._size(admitted, MAX_SNAPSHOT_BYTES)
    with _opened(binding) as (stream, stamp):
        if stamp.st_size < p["snapshot"]["target_bytes"]:
            raise ValueError("snapshot source truncated")
        if spec["offset"]:
            stream.seek(spec["offset"] - 1)
            if (stream.read(1) == b"\n") != spec["starts_at_line"]:
                raise ValueError("reviewed line boundary differs")
        stream.seek(spec["offset"])
        raw = stream.read(spec["bytes"])
        if len(raw) != spec["bytes"] or a._sha(raw) != spec["sha256"]:
            raise ValueError("reviewed native range changed")
        if (
            spec["offset"] == 0
            and a._sha(raw[: binding["header_length"]]) != binding["header_sha256"]
        ):
            raise ValueError("segment lacks native header")
    blocks = {}
    chunks = a._chunks(raw, blocks)
    part = partition(home, identity, p, index)
    # Reserve actual new objects, not logical duplicated references. Orphaned
    # content stays charged; exact retries reuse existing immutable objects.
    extra = sum(
        len(v)
        for k, v in blocks.items()
        if not (part / "state-blocks/v1" / (k + ".json")).exists()
    )
    _physical(home, admitted, extra=extra + a.CHUNK_BYTES)
    storage.materialize(part, blocks)
    entry = {
        "schema_version": 1,
        "index": index,
        "plan_sha256": a.digest(p),
        "spec": deepcopy(spec),
        "chunks": chunks,
        "source_stat": list(a._fingerprint(stamp)),
        "authority_granted": False,
    }
    if segment_bytes(home, identity, p, entry) != raw:
        raise ValueError("segment readback differs")
    return entry


def _entry(p, e):
    a._keys(
        e,
        (
            "schema_version",
            "index",
            "plan_sha256",
            "spec",
            "chunks",
            "source_stat",
            "authority_granted",
        ),
    )
    index = e["index"]
    if (
        type(e["schema_version"]) is not int
        or e["schema_version"] != 1
        or type(index) is not int
        or not 0 <= index < len(p["snapshot"]["segments"])
        or e["plan_sha256"] != a.digest(p)
        or e["spec"] != p["snapshot"]["segments"][index]
        or e["authority_granted"] is not False
    ):
        raise ValueError("segment receipt does not match its exact plan/range")
    if (
        not isinstance(e["source_stat"], list)
        or len(e["source_stat"]) != 7
        or any(type(x) is not int for x in e["source_stat"])
        or e["source_stat"][:2]
        != [p["snapshot"]["binding"]["device"], p["snapshot"]["binding"]["inode"]]
    ):
        raise ValueError("segment source identity differs")


def segment_bytes(home, identity, p, e):
    validate_plan(p)
    _entry(p, e)
    return a._chunk_bytes(
        partition(home, identity, p, e["index"]),
        e["chunks"],
        e["spec"]["bytes"],
        e["spec"]["sha256"],
    )


def coverage(home, identity, p, entries, *, seconds=MAX_SECONDS):
    validate_plan(p)
    end = _deadline(seconds)
    if not isinstance(entries, dict) or len(entries) > len(p["snapshot"]["segments"]):
        raise ValueError("segment receipt inventory bound")
    expected = {str(i) for i in range(len(p["snapshot"]["segments"]))}
    if set(entries) - expected:
        raise ValueError("unlisted segment receipt")
    full = hashlib.sha256()
    count = 0
    lines = 0
    previous = 10
    prefix = True
    len_verified = 0
    for key in sorted(entries, key=int):
        _tick(end)
        entry = entries[key]
        if entry.get("index") != int(key):
            raise ValueError("segment identity differs")
        raw = segment_bytes(home, identity, p, entry)
        if int(key) != len_verified:
            prefix = False
        if prefix and (
            entry["spec"]["line_ordinal"] != lines
            or entry["spec"]["starts_at_line"] != (previous == 10)
        ):
            raise ValueError("lineage/framing continuity differs")
        full.update(raw)
        count += len(raw)
        lines += raw.count(b"\n")
        previous = raw[-1]
        len_verified += 1
    complete = set(entries) == expected
    if complete and (
        count != p["snapshot"]["target_bytes"]
        or full.hexdigest() != p["snapshot"]["target_sha256"]
    ):
        raise ValueError("whole snapshot digest differs")
    return {
        "status": "COMPLETE" if complete else "INCOMPLETE",
        "verified_bytes": count,
        "snapshot_bytes": p["snapshot"]["target_bytes"],
        "snapshot_sha256": p["snapshot"]["target_sha256"],
        "missing_segments": sorted(expected - set(entries), key=int),
        "current_source_eof": "NOT_CLAIMED",
        "authority_granted": False,
        "native_acceptance": "UNKNOWN",
    }


def _portable(raw, p, spec):
    """Bounded segment view, retaining explicit fragments and unparsed ranges."""
    offset = 0
    ordinal = 0
    parts = []
    total = 0
    while offset < len(raw):
        if ordinal >= a.MAX_RECORDS:
            frame = raw[offset:]
            row = {
                "status": "unparsed-range",
                "offset": spec["offset"] + offset,
                "bytes": len(frame),
                "raw_sha256": a._sha(frame),
                "authority_granted": False,
            }
            parts.append(storage.canonical(row) + b"\n")
            break
        newline = raw.find(b"\n", offset)
        finish = len(raw) if newline < 0 else newline + 1
        frame = raw[offset:finish]
        if (offset == 0 and not spec["starts_at_line"]) or not frame.endswith(b"\n"):
            row = {
                "status": "boundary-fragment",
                "offset": spec["offset"] + offset,
                "bytes": len(frame),
                "raw_sha256": a._sha(frame),
                "authority_granted": False,
                "events": [],
                "record": None,
            }
        else:
            row = next(a.portable_rows(frame, {"binding": p["snapshot"]["binding"]}))
            row["offset"] = spec["offset"] + offset
            row["ordinal"] = spec["line_ordinal"] + ordinal
            if row["record"] is not None:
                try:
                    row["events"] = native._events(
                        row["record"],
                        p["snapshot"]["binding"],
                        row["offset"],
                        len(frame),
                        a._sha(frame),
                        row["ordinal"],
                        now="archive:source-order",
                    )
                except (
                    ValueError,
                    TypeError,
                    KeyError,
                    AttributeError,
                    RecursionError,
                ):
                    row["events"] = []
            row["ordinal_qualification"] = (
                "bound by complete snapshot framing verification"
            )
        encoded = storage.canonical(row) + b"\n"
        total += len(encoded)
        if total > a.MAX_EXPORT_BYTES:
            raise ValueError("segment portable expansion bound")
        parts.append(encoded)
        offset = finish
        ordinal += 1
    return b"".join(parts)


def _new_directory(path):
    path = Path(path)
    if not path.is_absolute() or ".." in path.parts:
        raise ValueError("absolute export directory required")
    parent = storage._safe_directory(path.parent)
    try:
        os.mkdir(path.name, 0o700, dir_fd=parent)
        os.fsync(parent)
        storage._same_directory(path.parent, parent)
    finally:
        os.close(parent)


def export_segment(home, identity, p, e, target):
    raw = segment_bytes(home, identity, p, e)
    target = Path(target) / f"segment-{e['index']:06}"
    view = _portable(raw, p, e["spec"])
    _new_directory(target)
    a._write_new(target / "native.bin", raw)
    a._write_new(target / "portable.jsonl", view)
    record = {
        "schema_version": 1,
        "kind": "native-evidence-segment",
        "plan_sha256": a.digest(p),
        "entry": e,
        "files": {
            "native.bin": {"bytes": len(raw), "sha256": a._sha(raw)},
            "portable.jsonl": {"bytes": len(view), "sha256": a._sha(view)},
        },
        "codec_sha256": a._sha(Path(__file__).read_bytes()),
        "normalizer_sha256": native.ADAPTER_SHA256,
        "authority_granted": False,
    }
    a._write_new(target / "manifest.json", storage.canonical(record) + b"\n")
    _verify_segment(p, target, e["index"])
    return record


def _members(path, expected):
    fd = storage._safe_directory(path)
    try:
        actual = set()
        for e in os.scandir(fd):
            if len(actual) > MAX_SEGMENTS + 2:
                raise ValueError("export membership bound")
            actual.add(e.name)
        if actual != set(expected):
            raise ValueError("missing or unlisted portable member")
        storage._same_directory(path, fd)
    finally:
        os.close(fd)


def _manifest(path):
    path = Path(path)
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
        raise ValueError("portable manifest is special or aliased")
    return storage.read_regular(path, a.MAX_MANIFEST_BYTES)


def _verify_segment(p, path, index):
    path = Path(path)
    custody = a._custody_snapshot(path, max_entries=4, max_depth=0)
    _members(path, ("native.bin", "portable.jsonl", "manifest.json"))
    raw = _manifest(path / "manifest.json")
    record = native._json(raw)
    a._keys(
        record,
        (
            "schema_version",
            "kind",
            "plan_sha256",
            "entry",
            "files",
            "codec_sha256",
            "normalizer_sha256",
            "authority_granted",
        ),
    )
    if (
        type(record["schema_version"]) is not int
        or record["schema_version"] != 1
        or record["kind"] != "native-evidence-segment"
        or record["plan_sha256"] != a.digest(p)
        or record["authority_granted"] is not False
    ):
        raise ValueError("portable segment schema/plan differs")
    a._hash(record["codec_sha256"])
    a._hash(record["normalizer_sha256"])
    _entry(p, record["entry"])
    if record["entry"]["index"] != index:
        raise ValueError("portable range index differs")
    a._keys(record["files"], ("native.bin", "portable.jsonl"))
    bodies = {}
    for name, spec in record["files"].items():
        a._keys(spec, ("bytes", "sha256"))
        a._size(spec["bytes"], a.MAX_EXPORT_BYTES, zero=True)
        a._hash(spec["sha256"])
        info = (path / name).lstat()
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
            raise ValueError("portable special or aliased member")
        body = storage.read_regular(path / name, spec["bytes"])
        if len(body) != spec["bytes"] or a._sha(body) != spec["sha256"]:
            raise ValueError("portable member digest differs")
        bodies[name] = body
    body = bodies["native.bin"]
    spec = p["snapshot"]["segments"][index]
    if len(body) != spec["bytes"] or a._sha(body) != spec["sha256"]:
        raise ValueError("portable source range differs")
    blocks = {}
    if a._chunks(body, blocks) != record["entry"]["chunks"]:
        raise ValueError("portable chunk reconstruction differs")
    if _manifest(path / "manifest.json") != raw:
        raise ValueError("portable segment changed during verification")
    if a._custody_snapshot(path, max_entries=4, max_depth=0) != custody:
        raise ValueError("portable segment member/directory changed")
    return record, body


def export_manifest(p, entries, target):
    validate_plan(p)
    target = Path(target)
    expected = {str(i) for i in range(len(p["snapshot"]["segments"]))}
    if set(entries) != expected:
        raise ValueError("cannot publish incomplete snapshot export")
    _members(target, [f"segment-{int(k):06}" for k in expected])
    full = hashlib.sha256()
    end = _deadline()
    listing = {}
    lines = 0
    previous = 10
    for key in sorted(expected, key=int):
        _tick(end)
        path = target / f"segment-{int(key):06}"
        record, body = _verify_segment(p, path, int(key))
        if record["entry"] != entries[key]:
            raise ValueError("segment export differs from retained receipt")
        spec = p["snapshot"]["segments"][int(key)]
        if spec["line_ordinal"] != lines or spec["starts_at_line"] != (previous == 10):
            raise ValueError("export framing differs")
        lines += body.count(b"\n")
        previous = body[-1]
        full.update(body)
        listing[key] = a._sha(_manifest(path / "manifest.json"))
    if full.hexdigest() != p["snapshot"]["target_sha256"]:
        raise ValueError("export whole snapshot digest differs")
    record = {
        "schema_version": 1,
        "kind": "portable-native-stream",
        "plan": p,
        "plan_sha256": a.digest(p),
        "segments": listing,
        "authority_granted": False,
    }
    a._write_new(target / "manifest.json", storage.canonical(record) + b"\n")
    return verify_bundle(target)


def verify_bundle(target, *, seconds=MAX_SECONDS):
    target = Path(target)
    end = _deadline(seconds)
    custody = a._custody_snapshot(target, max_entries=MAX_SEGMENTS * 4 + 2, max_depth=1)
    raw = _manifest(target / "manifest.json")
    record = native._json(raw)
    a._keys(
        record,
        (
            "schema_version",
            "kind",
            "plan",
            "plan_sha256",
            "segments",
            "authority_granted",
        ),
    )
    if (
        type(record["schema_version"]) is not int
        or record["schema_version"] != 1
        or record["kind"] != "portable-native-stream"
        or record["authority_granted"] is not False
    ):
        raise ValueError("portable stream schema/authority differs")
    p = record["plan"]
    validate_plan(p)
    if a.digest(p) != record["plan_sha256"]:
        raise ValueError("portable plan digest differs")
    expected = {str(i) for i in range(len(p["snapshot"]["segments"]))}
    if not isinstance(record["segments"], dict) or set(record["segments"]) != expected:
        raise ValueError("portable stream range inventory differs")
    _members(target, {"manifest.json"} | {f"segment-{int(k):06}" for k in expected})
    full = hashlib.sha256()
    lines = 0
    previous = 10
    for key in sorted(expected, key=int):
        _tick(end)
        path = target / f"segment-{int(key):06}"
        a._hash(record["segments"][key])
        if a._sha(_manifest(path / "manifest.json")) != record["segments"][key]:
            raise ValueError("portable segment receipt changed")
        _, body = _verify_segment(p, path, int(key))
        spec = p["snapshot"]["segments"][int(key)]
        if spec["line_ordinal"] != lines or spec["starts_at_line"] != (previous == 10):
            raise ValueError("portable framing differs")
        lines += body.count(b"\n")
        previous = body[-1]
        full.update(body)
    if full.hexdigest() != p["snapshot"]["target_sha256"]:
        raise ValueError("portable whole-source digest differs")
    if _manifest(target / "manifest.json") != raw:
        raise ValueError("portable final manifest changed")
    if (
        a._custody_snapshot(target, max_entries=MAX_SEGMENTS * 4 + 2, max_depth=1)
        != custody
    ):
        raise ValueError("portable stream member/directory changed")
    return {
        "status": "COMPLETE",
        "snapshot_bytes": p["snapshot"]["target_bytes"],
        "snapshot_sha256": p["snapshot"]["target_sha256"],
        "source_required": False,
        "authority_granted": False,
        "native_acceptance": "UNKNOWN",
        "current_source_eof": "NOT_CLAIMED",
        "manifest_sha256": a._sha(raw),
    }


def _bundle_custody(target, envelope):
    """Closed root plus every segment's membership, without rereading bodies."""
    current = a._custody_snapshot(target, max_entries=MAX_SEGMENTS * 4 + 2, max_depth=1)
    expected = {".", "manifest.json"}
    for index in range(len(envelope["plan"]["snapshot"]["segments"])):
        directory = f"segment-{index:06}"
        expected.add(directory)
        expected.update(
            f"{directory}/{name}"
            for name in ("manifest.json", "native.bin", "portable.jsonl")
        )
    if set(current) != expected:
        raise ValueError("missing or unlisted portable bundle member")
    return current


def restore_bundle(home, identity, target, *, admitted=None):
    """Offline bounded codec; managed caller must separately authorize restore."""
    verify_bundle(target)
    target = Path(target)
    before = _manifest(target / "manifest.json")
    envelope = native._json(before)
    p = envelope["plan"]
    custody = _bundle_custody(target, envelope)
    entries = {}
    end = _deadline()
    admitted = (
        DEFAULT_CAPACITY_BYTES + p["additional_capacity_bytes"]
        if admitted is None
        else admitted
    )
    for index in range(len(p["snapshot"]["segments"])):
        _tick(end)
        record, body = _verify_segment(p, target / f"segment-{index:06}", index)
        blocks = {}
        a._chunks(body, blocks)
        part = partition(home, identity, p, index)
        extra = sum(
            len(v)
            for k, v in blocks.items()
            if not (part / "state-blocks/v1" / (k + ".json")).exists()
        )
        _physical(home, admitted, extra=extra + a.CHUNK_BYTES)
        if _bundle_custody(target, envelope) != custody:
            raise ValueError("restore bundle members changed before write")
        storage.materialize(part, blocks)
        entries[str(index)] = record["entry"]
    if _manifest(target / "manifest.json") != before:
        raise ValueError("portable manifest changed during restore")
    if _bundle_custody(target, envelope) != custody:
        raise ValueError("portable bundle changed during restore")
    coverage(home, identity, p, entries)
    return entries


def _home(context):
    import run_state

    return run_state._home(context["project"], context["state"]["run_id"])


def _current(context, payload, action):
    a._authorization(context, payload, action)


def _get(context, payload):
    a._id(payload["stream_id"])
    a._hash(payload["plan_sha256"])
    record = _streams(context["state"]).get(payload["stream_id"])
    if record is None or a.digest(record["plan"]) != payload["plan_sha256"]:
        raise ValueError("exact journal-owned stream plan required")
    if record["plan"]["route"]["project_id"] != context["state"]["project_id"]:
        raise ValueError("stream project changed")
    return record


def _plan_authority(context, record):
    action = record["admission_action"]
    request = record["admission_request"]
    if action not in {
        "native.archive.stream.plan",
        "native.archive.stream.restore.plan",
    }:
        raise ValueError("invalid stream authority owner")
    if request["stream_id"] != record["stream_id"]:
        raise ValueError("stream permission identity differs")
    if action == "native.archive.stream.plan" and request["plan"] != record["plan"]:
        raise ValueError("stream plan changed after exact approval")
    _current(context, request, action)


def _prepare_plan(context, payload):
    from observation_bridge import _extension, _admitted_source

    a._keys(payload, ("stream_id", "source_id", "plan", "authorization"))
    a._id(payload["stream_id"])
    _current(context, payload, "native.archive.stream.plan")
    validate_plan(payload["plan"])
    if payload["stream_id"] in _streams(context["state"]):
        raise ValueError("stream identity already reserved")
    if payload["plan"]["route"]["project_id"] != context["state"]["project_id"]:
        raise ValueError("stream project route differs")
    sources = _extension(context["state"])["sources"]
    if payload["source_id"] not in sources:
        raise ValueError("stream requires enrolled source")
    source = sources[payload["source_id"]]
    _admitted_source(context, payload["source_id"], source)
    if source["binding"] != payload["plan"]["snapshot"]["binding"]:
        raise ValueError("snapshot is not the enrolled generation")
    admit_capacity(context["state"], payload["plan"])
    return {
        "stream_id": payload["stream_id"],
        "source_id": payload["source_id"],
        "plan": deepcopy(payload["plan"]),
        "segments": {},
        "exports": {},
        "bundle": None,
        "admission_action": "native.archive.stream.plan",
        "admission_request": deepcopy(payload),
        "authority_granted": False,
    }


def _prepare_segment(context, payload):
    from observation_bridge import _extension, _admitted_source

    a._keys(payload, ("stream_id", "plan_sha256", "index"))
    record = _get(context, payload)
    _plan_authority(context, record)
    if record["admission_action"] != "native.archive.stream.plan":
        raise ValueError("restore authority cannot capture a native source")
    source = _extension(context["state"])["sources"].get(record["source_id"])
    if source is None or source["binding"] != record["plan"]["snapshot"]["binding"]:
        raise ValueError("stream enrollment changed")
    _admitted_source(context, record["source_id"], source)
    index = payload["index"]
    partition(_home(context), record["stream_id"], record["plan"], index)
    if str(index) in record["segments"]:
        raise ValueError("segment already captured; use journal command replay")
    entry = capture_segment(
        _home(context),
        record["stream_id"],
        record["plan"],
        index,
        admitted=admit_capacity(context["state"]),
    )
    _plan_authority(context, record)
    result = deepcopy(record)
    result["segments"][str(index)] = entry
    return result


def _target(context, record):
    from run_admission import admit_paths, safe_path

    project = Path(context["project"])
    parent = safe_path(project / "resources/evidence/native-archive-streams", project)
    target = parent / (record["stream_id"] + "-" + a.digest(record["plan"]))
    proof = admit_paths(
        Path(context["actor"]["board"]),
        context["state"]["project_id"],
        project,
        [target],
        context["actor"]["native_payload"],
        expected_claim_hash=context["binding"]["claim_hash"],
        readonly=True,
    )
    if proof["session_uuid"] != context["binding"]["session_uuid"]:
        raise ValueError("stream export owner changed")
    return target


def _prepare_export_segment(context, payload):
    a._keys(payload, ("stream_id", "plan_sha256", "index", "authorization"))
    _current(context, payload, "native.archive.stream.export.segment")
    record = _get(context, payload)
    index = payload["index"]
    partition(_home(context), record["stream_id"], record["plan"], index)
    if str(index) not in record["segments"] or str(index) in record["exports"]:
        raise ValueError("retained unexported segment required")
    target = _target(context, record)
    if not target.exists():
        fd = storage._safe_directory(target.parent, create=True)
        os.close(fd)
        _new_directory(target)
    output = export_segment(
        _home(context),
        record["stream_id"],
        record["plan"],
        record["segments"][str(index)],
        target,
    )
    _current(context, payload, "native.archive.stream.export.segment")
    result = deepcopy(record)
    result["exports"][str(index)] = {
        "path": str(target / f"segment-{index:06}"),
        "manifest_sha256": a._sha(storage.canonical(output) + b"\n"),
    }
    return result


def _prepare_publish(context, payload):
    a._keys(payload, ("stream_id", "plan_sha256", "authorization"))
    _current(context, payload, "native.archive.stream.publish")
    record = _get(context, payload)
    report = coverage(
        _home(context), record["stream_id"], record["plan"], record["segments"]
    )
    if report["status"] != "COMPLETE" or set(record["exports"]) != set(
        record["segments"]
    ):
        raise ValueError("whole current retained/exported coverage required")
    target = _target(context, record)
    bundle = export_manifest(record["plan"], record["segments"], target)
    _current(context, payload, "native.archive.stream.publish")
    result = deepcopy(record)
    result["bundle"] = {**bundle, "path": str(target)}
    return result


def _restore_artifact(context, artifact_id, manifest_sha256):
    from run_admission import safe_path

    a._hash(manifest_sha256)
    if artifact_id not in context["artifacts"]:
        raise ValueError("current registered stream manifest required")
    artifact = context["artifacts"][artifact_id]
    path = safe_path(
        Path(context["project"]) / artifact["path"], Path(context["project"])
    )
    custody = a._custody_snapshot(
        path.parent, max_entries=MAX_SEGMENTS * 4 + 2, max_depth=1
    )
    raw = storage.read_regular(path, a.MAX_MANIFEST_BYTES)
    if (
        path.name != "manifest.json"
        or a._sha(raw) != artifact["digest"]
        or artifact["digest"] != manifest_sha256
    ):
        raise ValueError("registered stream manifest changed")
    value = native._json(raw)
    a._keys(
        value,
        (
            "schema_version",
            "kind",
            "plan",
            "plan_sha256",
            "segments",
            "authority_granted",
        ),
    )
    if (
        type(value["schema_version"]) is not int
        or value["schema_version"] != 1
        or value["kind"] != "portable-native-stream"
        or value["authority_granted"] is not False
    ):
        raise ValueError("invalid stream restoration envelope")
    validate_plan(value["plan"])
    if value["plan_sha256"] != a.digest(value["plan"]):
        raise ValueError("restore plan digest differs")
    expected = {str(i) for i in range(len(value["plan"]["snapshot"]["segments"]))}
    if not isinstance(value["segments"], dict) or set(value["segments"]) != expected:
        raise ValueError("restore source segment inventory differs")
    if _bundle_custody(path.parent, value) != custody:
        raise ValueError("restore source bundle changed during manifest read")
    return path, value


def _prepare_restore_plan(context, payload):
    a._keys(
        payload,
        ("stream_id", "manifest_artifact_id", "manifest_sha256", "authorization"),
    )
    a._id(payload["stream_id"])
    _current(context, payload, "native.archive.stream.restore.plan")
    if payload["stream_id"] in _streams(context["state"]):
        raise ValueError("new restoration stream identity required")
    path, envelope = _restore_artifact(
        context, payload["manifest_artifact_id"], payload["manifest_sha256"]
    )
    p = envelope["plan"]
    if p["route"]["project_id"] != context["state"]["project_id"]:
        raise ValueError("restore cannot migrate project/privacy route")
    admit_capacity(context["state"], p)
    return {
        "stream_id": payload["stream_id"],
        "source_id": "retained:" + payload["stream_id"],
        "plan": deepcopy(p),
        "segments": {},
        "exports": {},
        "bundle": None,
        "admission_action": "native.archive.stream.restore.plan",
        "admission_request": deepcopy(payload),
        "authority_granted": False,
    }


def _prepare_restore_segment(context, payload):
    a._keys(payload, ("stream_id", "plan_sha256", "index"))
    record = _get(context, payload)
    _plan_authority(context, record)
    if record["admission_action"] != "native.archive.stream.restore.plan":
        raise ValueError("separate restoration authority required")
    path, envelope = _restore_artifact(
        context,
        record["admission_request"]["manifest_artifact_id"],
        record["admission_request"]["manifest_sha256"],
    )
    if envelope["plan"] != record["plan"]:
        raise ValueError("restored plan changed")
    index = payload["index"]
    part = partition(_home(context), record["stream_id"], record["plan"], index)
    if str(index) in record["segments"]:
        raise ValueError("segment already restored; use journal replay")
    target = path.parent / f"segment-{index:06}"
    custody = _bundle_custody(path.parent, envelope)
    if a._sha(_manifest(target / "manifest.json")) != envelope["segments"][str(index)]:
        raise ValueError("restore segment manifest changed")
    entry, body = _verify_segment(record["plan"], target, index)
    blocks = {}
    a._chunks(body, blocks)
    extra = sum(
        len(v)
        for k, v in blocks.items()
        if not (part / "state-blocks/v1" / (k + ".json")).exists()
    )
    _physical(
        _home(context), admit_capacity(context["state"]), extra=extra + a.CHUNK_BYTES
    )
    _restore_artifact(
        context,
        record["admission_request"]["manifest_artifact_id"],
        record["admission_request"]["manifest_sha256"],
    )
    _plan_authority(context, record)
    if _bundle_custody(path.parent, envelope) != custody:
        raise ValueError("restore source bundle changed before write")
    storage.materialize(part, blocks)
    if (
        segment_bytes(
            _home(context), record["stream_id"], record["plan"], entry["entry"]
        )
        != body
    ):
        raise ValueError("restored segment readback differs")
    _plan_authority(context, record)
    _restore_artifact(
        context,
        record["admission_request"]["manifest_artifact_id"],
        record["admission_request"]["manifest_sha256"],
    )
    result = deepcopy(record)
    result["segments"][str(index)] = entry["entry"]
    return result


def _reduce(state, prepared, context):
    result = deepcopy(state)
    result.setdefault("extensions", {}).setdefault("native_archive_streams", {})[
        prepared["stream_id"]
    ] = deepcopy(prepared)
    return result


def verify_streams(project, state):
    import run_state

    home = run_state._home(Path(project), state["run_id"])
    issues = []
    verified = []
    try:
        admitted = admit_capacity(state)
        _physical(home, admitted)
    except (ValueError, OSError, KeyError, TypeError) as exc:
        return {
            "status": "FAIL",
            "verified": [],
            "issues": [{"stream_id": None, "reason": str(exc)[:2048]}],
        }
    for identity, record in _streams(state).items():
        try:
            a._id(identity)
            if (
                record["stream_id"] != identity
                or record["plan"]["route"]["project_id"] != state["project_id"]
            ):
                raise ValueError("stream journal identity/project differs")
            report = coverage(home, identity, record["plan"], record["segments"])
            if report["status"] != "COMPLETE":
                raise ValueError(
                    "snapshot coverage incomplete: " + str(report["missing_segments"])
                )
            for key, spec in record["exports"].items():
                from run_admission import safe_path

                path = safe_path(Path(spec["path"]), Path(project))
                _verify_segment(record["plan"], path, int(key))
                if a._sha(_manifest(path / "manifest.json")) != spec["manifest_sha256"]:
                    raise ValueError("journaled segment export changed")
            if record["bundle"] is not None:
                path = safe_path(Path(record["bundle"]["path"]), Path(project))
                bundle = verify_bundle(path)
                if bundle["manifest_sha256"] != record["bundle"]["manifest_sha256"]:
                    raise ValueError("journaled stream bundle changed")
            verified.append({"stream_id": identity, **report})
        except (ValueError, OSError, KeyError, TypeError) as exc:
            issues.append({"stream_id": identity, "reason": str(exc)[:2048]})
    return {
        "status": "FAIL" if issues else "PASS",
        "verified": verified,
        "issues": issues,
    }


def register(engine):
    for name, prepare in {
        "plan": _prepare_plan,
        "capture": _prepare_segment,
        "export.segment": _prepare_export_segment,
        "publish": _prepare_publish,
        "restore.plan": _prepare_restore_plan,
        "restore.segment": _prepare_restore_segment,
    }.items():
        command = "native.archive.stream." + name
        engine.register_command(command, _reduce, terminal_safe=True)
        engine.register_preparer(command, prepare)


def admit_legacy_capacity(state, route, legacy_logical):
    admitted = DEFAULT_CAPACITY_BYTES
    logical = legacy_logical
    domain = tuple(
        route[k] for k in ("project_id", "privacy_domain", "retention_class")
    )
    for record in _streams(state).values():
        p = record["plan"]
        validate_plan(p)
        admitted += p["additional_capacity_bytes"]
        logical += p["snapshot"]["target_bytes"]
        if (
            tuple(
                p["route"][k]
                for k in ("project_id", "privacy_domain", "retention_class")
            )
            != domain
        ):
            raise ValueError("legacy copy crosses stream privacy domain")
    if admitted > MAX_SNAPSHOT_BYTES or logical > admitted:
        raise ValueError("aggregate legacy/stream archive capacity exhausted")
