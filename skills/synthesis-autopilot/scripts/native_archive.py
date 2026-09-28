"""Explicit, lossless native evidence under the existing run journal owner.

This is an archive codec, not source authentication, semantic privacy review,
model memory, an authority ledger or automatic collection. The managed entry
requires current PM admission plus a source-backed exact routing authorization.
Raw blocks use journal_storage's existing bounded immutable store. Pure archive
functions below also support isolated/offline callers who own their own action
permission; their return values never supply that permission.
"""

from __future__ import annotations

from copy import deepcopy
import hashlib
import io
import os
from pathlib import Path
import re
import stat

import journal_storage as storage
import native_observations as native

SCHEMA = 1
MAX_SOURCE_BYTES = 64 * 1024 * 1024
MAX_ATTACHMENT_BYTES = 16 * 1024 * 1024
MAX_ATTACHMENTS = 128
MAX_RECORDS = 16384
CHUNK_BYTES = 64 * 1024
INLINE_RECORD_BYTES = 256 * 1024
MAX_EXPORT_BYTES = 3 * MAX_SOURCE_BYTES + 2 * MAX_ATTACHMENT_BYTES
MAX_MANIFEST_BYTES = 2 * 1024 * 1024
MAX_ARCHIVE_BYTES = 2 * MAX_SOURCE_BYTES
ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}\Z")
SHA = re.compile(r"[0-9a-f]{64}\Z")


def digest(value):
    return hashlib.sha256(storage.canonical(value)).hexdigest()


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _keys(value, keys):
    if not isinstance(value, dict) or set(value) != set(keys):
        raise ValueError("archive object has missing or unsupported fields")


def _id(value):
    if not isinstance(value, str) or ID.fullmatch(value) is None:
        raise ValueError("invalid archive identity")
    return value


def _hash(value):
    if not isinstance(value, str) or SHA.fullmatch(value) is None:
        raise ValueError("invalid archive digest")
    return value


def _size(value, maximum, *, zero=False):
    if type(value) is not int or not (0 if zero else 1) <= value <= maximum:
        raise ValueError("archive exceeds its finite byte/count bound")
    return value


def _route(route, binding):
    _keys(
        route,
        (
            "schema_version",
            "project_id",
            "privacy_domain",
            "retention_class",
            "classification",
            "source_domains",
            "source_generation",
            "reviewed_bytes",
            "reviewed_sha256",
            "attachments",
        ),
    )
    if type(route["schema_version"]) is not int or route["schema_version"] != SCHEMA:
        raise ValueError("unsupported routing schema")
    for key in ("project_id", "privacy_domain"):
        _id(route[key])
    if (
        route["retention_class"] not in {"permanent", "engagement"}
        or route["classification"] != "single-domain-reviewed"
        or route["source_domains"] != [route["privacy_domain"]]
        or route["source_generation"] != binding["generation"]
    ):
        raise ValueError("unknown, mixed, or changed privacy routing refuses raw copy")
    _size(route["reviewed_bytes"], MAX_SOURCE_BYTES)
    _hash(route["reviewed_sha256"])
    if (
        not isinstance(route["attachments"], list)
        or len(route["attachments"]) > MAX_ATTACHMENTS
    ):
        raise ValueError("attachment inventory exceeds bound")
    seen = set()
    total = 0
    for item in route["attachments"]:
        if (
            not isinstance(item, dict)
            or item.get("privacy_domain") != route["privacy_domain"]
        ):
            raise ValueError("attachment crosses privacy domain")
        identity = _id(item.get("id"))
        if identity in seen:
            raise ValueError("duplicate attachment identity")
        seen.add(identity)
        if item.get("status") == "capture":
            _keys(item, ("id", "privacy_domain", "status", "path", "bytes", "sha256"))
            if (
                not isinstance(item["path"], str)
                or not Path(item["path"]).is_absolute()
            ):
                raise ValueError("attachment requires explicit absolute path")
            total += _size(item["bytes"], MAX_ATTACHMENT_BYTES, zero=True)
            _hash(item["sha256"])
        elif item.get("status") in {
            "not-provided",
            "not-authorized",
            "unavailable",
            "opaque",
        }:
            _keys(item, ("id", "privacy_domain", "status"))
        else:
            raise ValueError("attachment needs explicit coverage disposition")
    if total > MAX_ATTACHMENT_BYTES:
        raise ValueError("aggregate attachment byte bound")


def _fingerprint(info):
    return (
        info.st_dev,
        info.st_ino,
        info.st_mode,
        info.st_nlink,
        info.st_size,
        info.st_mtime_ns,
        info.st_ctime_ns,
    )


def _source_pass(path, count):
    """No-follow descriptor walk and two named/opened identity checks."""
    path = Path(path)
    if not path.is_absolute() or ".." in path.parts:
        raise ValueError("source path must be absolute without traversal")
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
                or before.st_size < count
            ):
                raise ValueError(
                    "source must be a unique regular file covering the approved prefix"
                )
            raw = stream.read(count)
            after = os.fstat(stream.fileno())
            named = os.stat(path.name, dir_fd=parent, follow_symlinks=False)
            if (
                len(raw) != count
                or _fingerprint(before) != _fingerprint(after)
                or _fingerprint(after) != _fingerprint(named)
            ):
                raise ValueError("source changed, truncated or replaced during capture")
            storage._same_directory(path.parent, parent)
            # lstat(final parent) alone follows earlier ancestors. Rewalk the
            # entire no-follow chain and bind its final open identity as well.
            repeated_parent = storage._safe_directory(path.parent)
            try:
                opened, repeated = os.fstat(parent), os.fstat(repeated_parent)
                if (opened.st_dev, opened.st_ino) != (repeated.st_dev, repeated.st_ino):
                    raise ValueError("source ancestry changed during capture")
            finally:
                os.close(repeated_parent)
            return raw, _fingerprint(after)
    finally:
        os.close(parent)


def _chunks(raw, blocks):
    result = []
    for start in range(0, len(raw), CHUNK_BYTES):
        part = raw[start : start + CHUNK_BYTES]
        key = _sha(part)
        blocks[key] = part
        result.append({"offset": start, "bytes": len(part), "sha256": key})
    return result


def _chunk_bytes(home, chunks, count, expected):
    _size(count, MAX_SOURCE_BYTES, zero=True)
    _hash(expected)
    if (
        not isinstance(chunks, list)
        or len(chunks) > MAX_SOURCE_BYTES // CHUNK_BYTES + 1
    ):
        raise ValueError("archive chunk count bound")
    output = bytearray()
    for item in chunks:
        _keys(item, ("offset", "bytes", "sha256"))
        if type(item["offset"]) is not int or item["offset"] != len(output):
            raise ValueError("archive chunk gap, overlap or invalid offset")
        _size(item["bytes"], CHUNK_BYTES)
        _hash(item["sha256"])
        raw = storage.read_regular(
            Path(home) / "state-blocks/v1" / (item["sha256"] + ".json"), CHUNK_BYTES
        )
        if len(raw) != item["bytes"] or _sha(raw) != item["sha256"]:
            raise ValueError("archived block digest or length differs")
        output.extend(raw)
        if len(output) > count:
            raise ValueError("archive expands beyond admitted count")
    if len(output) != count or _sha(output) != expected:
        raise ValueError("archived prefix is incomplete or corrupt")
    return bytes(output)


def _validate_manifest(manifest):
    _keys(
        manifest,
        (
            "schema_version",
            "kind",
            "binding",
            "route",
            "source_bytes",
            "source_sha256",
            "source_stat",
            "chunks",
            "complete_prefix_bytes",
            "partial_tail_bytes",
            "attachments",
            "previous_manifest_sha256",
            "codec_sha256",
            "normalizer_sha256",
            "authority_granted",
            "attachment_discovery",
            "captured_mode",
        ),
    )
    if (
        manifest["schema_version"] != SCHEMA
        or type(manifest["schema_version"]) is not int
        or manifest["kind"] != "native-evidence-archive"
    ):
        raise ValueError("unsupported archive schema")
    native._validate_binding(manifest["binding"])
    _route(manifest["route"], manifest["binding"])
    if (
        manifest["authority_granted"] is not False
        or manifest["attachment_discovery"] != "UNKNOWN"
        or manifest["captured_mode"] != manifest["binding"]["mode"]
        or manifest["source_bytes"] != manifest["route"]["reviewed_bytes"]
        or manifest["source_sha256"] != manifest["route"]["reviewed_sha256"]
    ):
        raise ValueError("archive cannot change source custody or grant authority")
    for key in ("codec_sha256", "normalizer_sha256"):
        _hash(manifest[key])
    if manifest["previous_manifest_sha256"] is not None:
        _hash(manifest["previous_manifest_sha256"])
    _size(manifest["complete_prefix_bytes"], manifest["source_bytes"], zero=True)
    _size(manifest["partial_tail_bytes"], manifest["source_bytes"], zero=True)
    if (
        manifest["complete_prefix_bytes"] + manifest["partial_tail_bytes"]
        != manifest["source_bytes"]
    ):
        raise ValueError("invalid archive frame coverage")
    if (
        not isinstance(manifest["source_stat"], (list, tuple))
        or len(manifest["source_stat"]) != 7
        or any(type(x) is not int for x in manifest["source_stat"])
    ):
        raise ValueError("invalid source snapshot identity")
    if manifest["source_stat"][:2] != [
        manifest["binding"]["device"],
        manifest["binding"]["inode"],
    ]:
        raise ValueError("source snapshot does not match its native binding")
    if manifest["source_bytes"] < manifest["binding"]["header_length"]:
        raise ValueError("archive does not cover its enrolled header")
    if not isinstance(manifest["attachments"], list) or len(
        manifest["attachments"]
    ) != len(manifest["route"]["attachments"]):
        raise ValueError("attachment inventory is incomplete")
    for retained, approved in zip(
        manifest["attachments"], manifest["route"]["attachments"]
    ):
        if not isinstance(retained, dict):
            raise ValueError("invalid retained attachment")
        if approved["status"] == "capture":
            if set(retained) != set(approved) | {"chunks"} or any(
                retained[k] != v for k, v in approved.items()
            ):
                raise ValueError("attachment archive differs from approved routing")
        elif retained != approved:
            raise ValueError("attachment coverage disposition changed")
    if len(storage.canonical(manifest)) > MAX_MANIFEST_BYTES:
        raise ValueError("archive manifest byte bound")


def recover_bytes(home, manifest):
    """Exact available bytes; does not need or open the original native file."""
    _validate_manifest(manifest)
    raw = _chunk_bytes(
        home, manifest["chunks"], manifest["source_bytes"], manifest["source_sha256"]
    )
    if (
        _sha(raw[: manifest["binding"]["header_length"]])
        != manifest["binding"]["header_sha256"]
    ):
        raise ValueError("archive does not retain its enrolled header")
    if raw.rfind(b"\n") + 1 != manifest["complete_prefix_bytes"]:
        raise ValueError("archived frame coverage differs from bytes")
    return raw


def capture(home, binding, route, *, previous=None):
    """Copy only an explicitly reviewed prefix, never follow transcript hints."""
    native._validate_binding(binding)
    _route(route, binding)
    count = route["reviewed_bytes"]
    raw, identity = _source_pass(binding["path"], count)
    if (
        identity[:2] != (binding["device"], binding["inode"])
        or _sha(raw) != route["reviewed_sha256"]
        or _sha(raw[: binding["header_length"]]) != binding["header_sha256"]
    ):
        raise ValueError("approved source identity/header/prefix changed")
    if previous is not None:
        prior = recover_bytes(home, previous)
        if (
            previous["binding"] != binding
            or any(
                previous["route"][k] != route[k]
                for k in (
                    "project_id",
                    "privacy_domain",
                    "retention_class",
                    "source_domains",
                )
            )
            or not raw.startswith(prior)
        ):
            raise ValueError(
                "incremental archive cannot replace, truncate or reroute its prior prefix"
            )
    blocks = {}
    chunks = _chunks(raw, blocks)
    attachments = []
    attachment_reads = []
    for item in route["attachments"]:
        row = deepcopy(item)
        if item["status"] == "capture":
            body, stamp = _source_pass(item["path"], item["bytes"])
            if stamp[4] != item["bytes"] or _sha(body) != item["sha256"]:
                raise ValueError("attachment differs from explicitly reviewed bytes")
            row["chunks"] = _chunks(body, blocks)
            attachment_reads.append((item, body, stamp))
        attachments.append(row)
    repeat, after = _source_pass(binding["path"], count)
    if repeat != raw or identity != after:
        raise ValueError("source changed between capture passes")
    for item, body, stamp in attachment_reads:
        if _source_pass(item["path"], item["bytes"]) != (body, stamp):
            raise ValueError("attachment changed between capture passes")
    manifest = {
        "schema_version": SCHEMA,
        "kind": "native-evidence-archive",
        "binding": deepcopy(binding),
        "route": deepcopy(route),
        "source_bytes": count,
        "source_sha256": _sha(raw),
        "source_stat": list(identity),
        "chunks": chunks,
        "complete_prefix_bytes": raw.rfind(b"\n") + 1,
        "partial_tail_bytes": count - (raw.rfind(b"\n") + 1),
        "attachments": attachments,
        "previous_manifest_sha256": digest(previous) if previous is not None else None,
        "codec_sha256": _sha(Path(__file__).read_bytes()),
        "normalizer_sha256": native.ADAPTER_SHA256,
        "authority_granted": False,
        "attachment_discovery": "UNKNOWN",
        "captured_mode": binding["mode"],
    }
    _validate_manifest(manifest)
    # Bound the derived view before any copy. Large/unknown bodies remain exact
    # raw references; they are not dropped or guessed into normalized events.
    _portable_size(raw, manifest)
    storage.materialize(home, blocks)
    if recover_bytes(home, manifest) != raw:
        raise ValueError("archive readback differs")
    return manifest


def portable_rows(raw, manifest):
    """Source-order view; native timestamps never reorder causality or forks."""
    offset = 0
    for ordinal, frame in enumerate(io.BytesIO(raw)):
        if ordinal >= MAX_RECORDS:
            raise ValueError("portable record count bound")
        row = {
            "schema_version": 1,
            "ordinal": ordinal,
            "offset": offset,
            "bytes": len(frame),
            "raw_sha256": _sha(frame),
            "source_generation": manifest["binding"]["generation"],
            "producer": manifest["binding"]["producer"],
            "authority_granted": False,
            "status": "partial-tail" if not frame.endswith(b"\n") else "external-body",
            "record": None,
            "events": [],
        }
        if frame.endswith(b"\n") and len(frame) <= INLINE_RECORD_BYTES:
            try:
                original = native._json(frame)
                row["record"] = original
                row["status"] = "unknown"
                try:
                    events = native._events(
                        original,
                        manifest["binding"],
                        offset,
                        len(frame),
                        _sha(frame),
                        ordinal,
                        now="archive:source-order",
                    )
                    row["events"] = events
                    if events:
                        row["status"] = "interpreted"
                except (
                    ValueError,
                    TypeError,
                    KeyError,
                    AttributeError,
                    RecursionError,
                ) as exc:
                    row["interpretation_error"] = str(exc)[:1024]

                def opaque(value, depth=0):
                    if depth > 32:
                        return False
                    if isinstance(value, dict):
                        return any(
                            k in {"encrypted_content", "encryptedContent"}
                            or opaque(v, depth + 1)
                            for k, v in value.items()
                        )
                    return isinstance(value, list) and any(
                        opaque(v, depth + 1) for v in value
                    )

                if opaque(original):
                    row["status"] = "opaque"
            except (ValueError, UnicodeError, RecursionError):
                row["status"] = "malformed"
        yield row
        offset += len(frame)


def _portable_size(raw, manifest, *, retain=False):
    """Enforce the output bound while streaming, before accumulating it."""
    total = manifest["source_bytes"] + sum(
        x.get("bytes", 0) for x in manifest["attachments"]
    )
    body = bytearray() if retain else None
    for row in portable_rows(raw, manifest):
        encoded = storage.canonical(row) + b"\n"
        total += len(encoded)
        if total > MAX_EXPORT_BYTES:
            raise ValueError("portable export byte bound")
        if body is not None:
            body.extend(encoded)
    return bytes(body) if body is not None else total


def _write_new(path, raw):
    parent = storage._safe_directory(Path(path).parent)
    try:
        fd = os.open(
            Path(path).name,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
            0o600,
            dir_fd=parent,
        )
        with os.fdopen(fd, "wb") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        os.fsync(parent)
        storage._same_directory(Path(path).parent, parent)
    finally:
        os.close(parent)


def export(home, manifest, target):
    """Explicit fresh-directory export. Final manifest is the commit marker.

    An interrupted directory is retained and never overwritten/retried as a
    success. The caller supplies a new destination after inspecting custody.
    """
    raw = recover_bytes(home, manifest)
    files = {"native.jsonl": raw}
    for item in manifest["attachments"]:
        if item["status"] == "capture":
            files["attachments/" + item["id"]] = _chunk_bytes(
                home, item["chunks"], item["bytes"], item["sha256"]
            )
    view = _portable_size(raw, manifest, retain=True)
    files["portable.jsonl"] = view
    if sum(map(len, files.values())) > MAX_EXPORT_BYTES:
        raise ValueError("export byte bound")
    target = Path(target)
    if not target.is_absolute() or ".." in target.parts:
        raise ValueError("export requires explicit absolute path")
    parent = storage._safe_directory(target.parent)
    try:
        os.mkdir(target.name, 0o700, dir_fd=parent)
        storage._same_directory(target.parent, parent)
        os.fsync(parent)
    finally:
        os.close(parent)
    if any(k.startswith("attachments/") for k in files):
        fd = storage._safe_directory(target / "attachments", create=True)
        os.close(fd)
    listing = {}
    for name, body in files.items():
        _write_new(target / name, body)
        listing[name] = {"bytes": len(body), "sha256": _sha(body)}
    envelope = {
        "schema_version": 1,
        "kind": "portable-native-evidence",
        "archive": manifest,
        "archive_sha256": digest(manifest),
        "files": listing,
        "authority_granted": False,
        "semantic_privacy_review": "owner-authorized route, not inferred from bytes",
        "codec_at_export": _sha(Path(__file__).read_bytes()),
        "normalizer_at_export": native.ADAPTER_SHA256,
    }
    encoded = storage.canonical(envelope) + b"\n"
    if len(encoded) > MAX_MANIFEST_BYTES:
        raise ValueError("export manifest bound")
    _write_new(target / "manifest.json", encoded)
    result = verify_export(target)
    return {**result, "manifest_sha256": _sha(encoded), "path": str(target)}


def _custody_snapshot(target, *, max_entries=MAX_ATTACHMENTS + 5, max_depth=1):
    """Bounded no-follow identities around a verification read interval.

    This detects added/removed/replaced/aliased members and changed directory or
    file metadata. It is not a filesystem snapshot, lock on an external writer,
    or a claim that bytes cannot change after the verified interval returns.
    """
    target = Path(target)
    if not target.is_absolute() or ".." in target.parts:
        raise ValueError("absolute custody directory required")
    if type(max_entries) is not int or not 1 <= max_entries <= 20000:
        raise ValueError("custody member bound")
    if type(max_depth) is not int or not 0 <= max_depth <= 3:
        raise ValueError("custody directory depth bound")
    result = {}

    def walk(path, depth):
        if depth > max_depth:
            raise ValueError("unlisted custody directory depth")
        fd = storage._safe_directory(path)
        try:
            before = os.fstat(fd)
            result[path.relative_to(target).as_posix()] = _fingerprint(before)
            for entry in os.scandir(fd):
                if len(result) >= max_entries:
                    raise ValueError("custody member inventory bound")
                info = entry.stat(follow_symlinks=False)
                member = path / entry.name
                if stat.S_ISDIR(info.st_mode):
                    walk(member, depth + 1)
                elif stat.S_ISREG(info.st_mode) and info.st_nlink == 1:
                    result[member.relative_to(target).as_posix()] = _fingerprint(info)
                else:
                    raise ValueError("unsafe or aliased custody member")
            if _fingerprint(os.fstat(fd)) != _fingerprint(before):
                raise ValueError("custody directory changed during enumeration")
            storage._same_directory(path, fd)
            repeated = storage._safe_directory(path)
            try:
                if _fingerprint(os.fstat(repeated)) != _fingerprint(before):
                    raise ValueError("custody directory ancestry changed")
            finally:
                os.close(repeated)
        finally:
            os.close(fd)

    walk(target, 0)
    return result


def verify_export(target):
    """Independent integrity verification without source/harness or admission."""
    target = Path(target)
    custody = _custody_snapshot(target)
    raw = storage.read_regular(target / "manifest.json", MAX_MANIFEST_BYTES)
    envelope = native._json(raw)
    _keys(
        envelope,
        (
            "schema_version",
            "kind",
            "archive",
            "archive_sha256",
            "files",
            "authority_granted",
            "semantic_privacy_review",
            "codec_at_export",
            "normalizer_at_export",
        ),
    )
    if (
        type(envelope["schema_version"]) is not int
        or envelope["schema_version"] != 1
        or envelope["kind"] != "portable-native-evidence"
        or envelope["authority_granted"] is not False
    ):
        raise ValueError("invalid portable archive envelope")
    _hash(envelope["codec_at_export"])
    _hash(envelope["normalizer_at_export"])
    if (
        envelope["semantic_privacy_review"]
        != "owner-authorized route, not inferred from bytes"
    ):
        raise ValueError("portable archive privacy representation differs")
    manifest = envelope["archive"]
    _validate_manifest(manifest)
    if digest(manifest) != envelope["archive_sha256"]:
        raise ValueError("archive manifest differs")
    expected = {"native.jsonl", "portable.jsonl"} | {
        "attachments/" + x["id"]
        for x in manifest["attachments"]
        if x["status"] == "capture"
    }
    if not isinstance(envelope["files"], dict) or set(envelope["files"]) != expected:
        raise ValueError("portable export membership differs")
    actual = set()
    total = 0
    fd = storage._safe_directory(target)
    try:
        for entry in os.scandir(fd):
            info = entry.stat(follow_symlinks=False)
            if entry.name == "attachments" and any(
                p.startswith("attachments/") for p in expected
            ):
                afd = storage._safe_directory(target / "attachments")
                try:
                    for child in os.scandir(afd):
                        if len(actual) > MAX_ATTACHMENTS + 3:
                            raise ValueError("portable membership bound")
                        actual.add("attachments/" + child.name)
                finally:
                    os.close(afd)
            elif stat.S_ISREG(info.st_mode) and info.st_nlink == 1:
                actual.add(entry.name)
            else:
                raise ValueError("portable archive contains unsafe member")
            if len(actual) > MAX_ATTACHMENTS + 3:
                raise ValueError("portable membership bound")
        storage._same_directory(target, fd)
    finally:
        os.close(fd)
    if actual != expected | {"manifest.json"}:
        raise ValueError("unlisted or missing export member")
    for name, spec in envelope["files"].items():
        _keys(spec, ("bytes", "sha256"))
        _size(spec["bytes"], MAX_EXPORT_BYTES, zero=True)
        _hash(spec["sha256"])
        info = (target / name).lstat()
        if info.st_nlink != 1:
            raise ValueError("aliased export member")
        data = storage.read_regular(target / name, spec["bytes"])
        total += len(data)
        if (
            total > MAX_EXPORT_BYTES
            or len(data) != spec["bytes"]
            or _sha(data) != spec["sha256"]
        ):
            raise ValueError("export content or bound differs")
        if name == "native.jsonl" and (
            len(data) != manifest["source_bytes"]
            or _sha(data) != manifest["source_sha256"]
        ):
            raise ValueError("native export differs from captured source")
        if name.startswith("attachments/"):
            original = next(
                x for x in manifest["attachments"] if x["id"] == name.split("/")[1]
            )
            if (
                spec["bytes"] != original["bytes"]
                or spec["sha256"] != original["sha256"]
            ):
                raise ValueError("attachment export differs from captured bytes")
    if storage.read_regular(target / "manifest.json", MAX_MANIFEST_BYTES) != raw:
        raise ValueError("export manifest changed during verification")
    if _custody_snapshot(target) != custody:
        raise ValueError("export member or directory changed during verification")
    return {
        "status": "PASS",
        "exact_bytes": manifest["source_bytes"],
        "authority_granted": False,
        "attachment_discovery": "UNKNOWN",
        "native_acceptance": "UNKNOWN",
        "captured_mode": manifest["captured_mode"],
        "source_required": False,
    }


def restore_export(home, target, *, expected_manifest_sha256=None):
    """Restore captured evidence, never native configuration or run authority."""
    target = Path(target)
    verify_export(target)
    custody = _custody_snapshot(target)
    before = storage.read_regular(target / "manifest.json", MAX_MANIFEST_BYTES)
    if expected_manifest_sha256 is not None:
        _hash(expected_manifest_sha256)
        if _sha(before) != expected_manifest_sha256:
            raise ValueError("approved portable manifest changed before restore")
    envelope = native._json(before)
    manifest = envelope["archive"]
    blocks = {}
    raw = storage.read_regular(target / "native.jsonl", MAX_SOURCE_BYTES)
    if _sha(raw) != manifest["source_sha256"] or len(raw) != manifest["source_bytes"]:
        raise ValueError("export source changed before restore")
    if _chunks(raw, blocks) != manifest["chunks"]:
        raise ValueError("export cannot reconstruct its exact original chunks")
    for item in manifest["attachments"]:
        if item["status"] == "capture":
            body = storage.read_regular(
                target / "attachments" / item["id"], MAX_ATTACHMENT_BYTES
            )
            if (
                _sha(body) != item["sha256"]
                or len(body) != item["bytes"]
                or _chunks(body, blocks) != item["chunks"]
            ):
                raise ValueError("export attachment changed before restore")
    verify_export(target)
    if storage.read_regular(target / "manifest.json", MAX_MANIFEST_BYTES) != before:
        raise ValueError("export manifest changed before restore")
    if _custody_snapshot(target) != custody:
        raise ValueError("export member or directory changed before restore")
    storage.materialize(home, blocks)
    if recover_bytes(home, manifest) != raw:
        raise ValueError("restored evidence readback differs")
    return manifest


def _domain_invariant(state, route):
    for entry in state.get("extensions", {}).get("native_archives", {}).values():
        existing = entry["manifest"]["route"]
        if any(
            existing[key] != route[key]
            for key in ("privacy_domain", "retention_class", "project_id")
        ):
            raise ValueError(
                "one run archive store cannot deduplicate across privacy/deletion domains"
            )


def _authorization(context, payload, action):
    """An exact native user receipt, not recalled prose or a manifest flag."""
    from run_admission import read_admission_observation
    import run_state

    read_admission_observation(context)
    receipt = run_state._receipt(
        context, context["state"], payload["authorization"], "authority"
    )
    expected = {
        "approved": True,
        "action": action,
        "request_sha256": digest(
            {k: v for k, v in payload.items() if k != "authorization"}
        ),
    }
    actual = {k: v for k, v in receipt["data"].items() if k != "source"}
    if actual != expected:
        raise ValueError(
            "archive permission must bind this exact action and routing request"
        )


def _prepare_capture(context, payload):
    from observation_bridge import _extension, _admitted_source
    import run_state

    _keys(payload, ("archive_id", "source_id", "route", "authorization"))
    identity = _id(payload["archive_id"])
    _authorization(context, payload, "native.archive.capture")
    if not isinstance(payload["route"], dict):
        raise ValueError("routing must be an object")
    if payload["route"].get("project_id") != context["state"]["project_id"]:
        raise ValueError("archive cannot change the resolved project")
    sources = _extension(context["state"])["sources"]
    if payload["source_id"] not in sources:
        raise ValueError("archive requires an enrolled native source")
    source = sources[payload["source_id"]]
    _admitted_source(context, payload["source_id"], source)
    archived = context["state"].get("extensions", {}).get("native_archives", {})
    if identity not in archived and len(archived) >= 64:
        raise ValueError("archive count capacity reached")
    _route(payload["route"], source["binding"])
    _domain_invariant(context["state"], payload["route"])
    logical = sum(
        e["manifest"]["source_bytes"]
        + sum(x.get("bytes", 0) for x in e["manifest"]["attachments"])
        for key, e in archived.items()
        if key != identity
    )
    logical += payload["route"]["reviewed_bytes"] + sum(
        x.get("bytes", 0) for x in payload["route"]["attachments"]
    )
    if logical > MAX_ARCHIVE_BYTES:
        raise ValueError("aggregate archive byte bound")
    import native_archive_stream

    native_archive_stream.admit_legacy_capacity(
        context["state"], payload["route"], logical
    )
    previous = archived.get(identity, {}).get("manifest")
    home = run_state._home(context["project"], context["state"]["run_id"])
    manifest = capture(home, source["binding"], payload["route"], previous=previous)
    # Revalidate action/owner after the bounded copy. A failed commit retains
    # inert CAS blocks; it cannot turn the copy into journal success.
    _authorization(context, payload, "native.archive.capture")
    return {
        "archive_id": identity,
        "source_id": payload["source_id"],
        "manifest": manifest,
        "manifest_sha256": digest(manifest),
        "export": None,
        "authority_granted": False,
    }


def _prepare_export(context, payload):
    from run_admission import admit_paths, safe_path
    import run_state

    _keys(payload, ("archive_id", "manifest_sha256", "authorization"))
    identity = _id(payload["archive_id"])
    _hash(payload["manifest_sha256"])
    _authorization(context, payload, "native.archive.export")
    record = (
        context["state"].get("extensions", {}).get("native_archives", {}).get(identity)
    )
    if record is None or digest(record["manifest"]) != payload["manifest_sha256"]:
        raise ValueError("export requires the exact journal-owned archive")
    project = Path(context["project"])
    parent = safe_path(project / "resources/evidence/native-archives", project)
    target = parent / (identity + "-" + payload["manifest_sha256"])
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
        raise ValueError("export owner changed")
    fd = storage._safe_directory(parent, create=True)
    os.close(fd)
    result = export(
        run_state._home(project, context["state"]["run_id"]), record["manifest"], target
    )
    _authorization(context, payload, "native.archive.export")
    return {**deepcopy(record), "archive_id": identity, "export": result}


def _prepare_restore(context, payload):
    from run_admission import safe_path
    import run_state

    _keys(
        payload,
        ("archive_id", "manifest_artifact_id", "manifest_sha256", "authorization"),
    )
    _hash(payload["manifest_sha256"])
    identity = _id(payload["archive_id"])
    _authorization(context, payload, "native.archive.restore")
    artifacts = context["artifacts"]
    if payload["manifest_artifact_id"] not in artifacts:
        raise ValueError("restore requires a current registered portable manifest")
    artifact = artifacts[payload["manifest_artifact_id"]]
    path = safe_path(
        Path(context["project"]) / artifact["path"], Path(context["project"])
    )
    raw = storage.read_regular(path, MAX_MANIFEST_BYTES)
    if (
        path.name != "manifest.json"
        or _sha(raw) != artifact["digest"]
        or artifact["digest"] != payload["manifest_sha256"]
    ):
        raise ValueError("registered portable manifest changed")
    envelope = native._json(raw)
    manifest = envelope.get("archive")
    _validate_manifest(manifest)
    if manifest["route"]["project_id"] != context["state"]["project_id"]:
        raise ValueError("restore cannot silently migrate a project or privacy route")
    _domain_invariant(context["state"], manifest["route"])
    archived = context["state"].get("extensions", {}).get("native_archives", {})
    if identity in archived or len(archived) >= 64:
        raise ValueError("restore requires a new archive identity within capacity")
    logical = sum(
        e["manifest"]["source_bytes"]
        + sum(x.get("bytes", 0) for x in e["manifest"]["attachments"])
        for e in archived.values()
    )
    logical += manifest["source_bytes"] + sum(
        x.get("bytes", 0) for x in manifest["attachments"]
    )
    if logical > MAX_ARCHIVE_BYTES:
        raise ValueError("aggregate archive restore byte bound")
    import native_archive_stream

    native_archive_stream.admit_legacy_capacity(
        context["state"], manifest["route"], logical
    )
    restored = restore_export(
        run_state._home(context["project"], context["state"]["run_id"]),
        path.parent,
        expected_manifest_sha256=payload["manifest_sha256"],
    )
    _authorization(context, payload, "native.archive.restore")
    return {
        "archive_id": identity,
        "source_id": "retained:" + identity,
        "manifest": restored,
        "manifest_sha256": digest(restored),
        "export": None,
        "authority_granted": False,
    }


def _reduce(state, prepared, context):
    value = deepcopy(state)
    value.setdefault("extensions", {}).setdefault("native_archives", {})[
        prepared["archive_id"]
    ] = deepcopy(prepared)
    return value


def verify_archives(project, state):
    """Current retained bytes, not a descriptor-only completion assertion."""
    import run_state

    rows = state.get("extensions", {}).get("native_archives", {})
    issues = []
    verified = []
    logical = 0
    if not isinstance(rows, dict) or len(rows) > 64:
        return {
            "status": "FAIL",
            "verified": [],
            "issues": [
                {"archive_id": None, "reason": "archive inventory capacity or shape"}
            ],
        }
    home = run_state._home(Path(project), state["run_id"])
    for identity, entry in rows.items():
        try:
            _id(identity)
            if not isinstance(entry, dict) or entry.get("archive_id") != identity:
                raise ValueError("archive journal identity differs")
            manifest = entry["manifest"]
            _validate_manifest(manifest)
            if (
                digest(manifest) != entry["manifest_sha256"]
                or manifest["route"]["project_id"] != state["project_id"]
            ):
                raise ValueError(
                    "archive descriptor differs from current project/journal"
                )
            logical += manifest["source_bytes"] + sum(
                x.get("bytes", 0) for x in manifest["attachments"]
            )
            if logical > MAX_ARCHIVE_BYTES:
                raise ValueError("aggregate archive verification byte bound")
            recover_bytes(home, manifest)
            for item in manifest["attachments"]:
                if item["status"] == "capture":
                    _chunk_bytes(home, item["chunks"], item["bytes"], item["sha256"])
            if entry.get("export") is not None:
                exported = entry["export"]
                target = Path(exported["path"])
                from run_admission import safe_path

                safe_path(target, Path(project))
                verify_export(target)
                if (
                    _sha(
                        storage.read_regular(
                            target / "manifest.json", MAX_MANIFEST_BYTES
                        )
                    )
                    != exported["manifest_sha256"]
                ):
                    raise ValueError(
                        "export manifest no longer matches journal receipt"
                    )
            verified.append(
                {
                    "archive_id": identity,
                    "manifest_sha256": entry["manifest_sha256"],
                    "source_bytes": manifest["source_bytes"],
                    "authority_granted": False,
                }
            )
        except (ValueError, OSError, KeyError, TypeError) as exc:
            issues.append({"archive_id": identity, "reason": str(exc)[:2048]})
    import native_archive_stream

    streamed = native_archive_stream.verify_streams(project, state)
    issues.extend(streamed["issues"])
    return {
        "status": "FAIL" if issues else "PASS",
        "verified": verified,
        "streams_verified": streamed["verified"],
        "issues": issues,
    }


def validate_command(state, command, payload, context):
    if command == "close" and payload.get("status") == "completed":
        report = verify_archives(Path(context["binding"]["project_root"]), state)
        if report["status"] != "PASS":
            raise ValueError("native evidence archive retention is unresolved")


def register(engine):
    import native_archive_stream

    native_archive_stream.register(engine)
    engine.register_constraint("native.archive.retention", validate_command)
    engine.register_command("native.archive.restore", _reduce, terminal_safe=True)
    engine.register_preparer("native.archive.restore", _prepare_restore)
    engine.register_command("native.archive.capture", _reduce, terminal_safe=True)
    engine.register_preparer("native.archive.capture", _prepare_capture)
    engine.register_command("native.archive.export", _reduce, terminal_safe=True)
    engine.register_preparer("native.archive.export", _prepare_export)
