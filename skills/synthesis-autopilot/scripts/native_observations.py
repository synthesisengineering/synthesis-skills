#!/usr/bin/env python3
"""Bounded native source observations; no admission, receipt, journal or scheduler.

The controller must join these *file observations* to current PM/conformance
admission before using them as native evidence. ``mode='native'`` is a caller
claim, never authentication. Even a matching header does not authenticate a
producer. Synthetic observations remain labeled through every projection.

``enroll_source`` returns a binding and an initial serializable cursor.
``read_page`` returns a proposed batch; the existing run transaction commits
the batch and cursor together. Losing an uncommitted batch is harmless.
``reduce_observations`` is a pure, rebuildable locator/pair/usage projection.
The cursor's custody comes from that journal, not from its shape or a cached
locator file; structural validation here cannot authenticate a supplied cursor.
``revalidate_observations`` reopens exact positive source ranges and normalizes
them again. Cached digests, cursors and projections alone establish no current
source facts. Interval scans carry explicit bounds/times, never atomicity.

Input memory is bounded by Limits. Oversized frames are validated incrementally
using the bounded string-run technique from live_receipt._TranscriptJSON. A
fixed projection identifies ignored nonmaterial records. Other oversized bodies
produce a source gap/reference requiring structured owner readback. Physical
scan progress can cross gaps; trusted coverage cannot.
No source transcript or auxiliary database is written by this module.
"""
from __future__ import annotations

import base64
import codecs
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import re
import stat
from typing import Literal, TypedDict

import native_codex
import native_claude
import native_muse
import native_cursor
import native_copilot
import native_opencode


ADAPTER_VERSION = "native-observations-v3"
ADAPTER_SHA256 = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
MAX_INDEX_ENTRIES = 10000
MAX_PROJECTION_BYTES = 2 * 1024 * 1024
MAX_HEADER_BYTES = 1024 * 1024
MAX_VALIDATOR_BYTES = 64 * 1024
_DIALECTS = {"codex": native_codex, "claude": native_claude, "muse": native_muse,
             "cursor": native_cursor, "copilot": native_copilot, "opencode": native_opencode}
_DIALECT_HASHES = {client: hashlib.sha256(Path(module.__file__).read_bytes()).hexdigest()
                   for client, module in _DIALECTS.items()}
SUPPORTED_SCHEMAS = {client: list(module.SUPPORTED_SCHEMAS) for client, module in _DIALECTS.items()}
BASELINE_GAPS = {
    "history-beyond-tail": {"owner": "native_observations"},
    "pair-across-tail-boundary": {"owner": "native_observations"},
    "positive-discovery-scan-amplification": {"owner": "native_observations"},
    "productive-observations-8": {"owner": "persistence_policy"},
    "productive-observations-20": {"owner": "persistence_policy"},
    "genuine-child-native-control": {"owner": "PM/conformance"},
}


class SourceError(ValueError):
    """Source identity, framing, or an observation contract is unverifiable."""


@dataclass(frozen=True)
class Limits:
    page_bytes: int = 1024 * 1024
    payload_bytes: int = 256 * 1024
    events: int = 512
    depth: int = 32

    def __post_init__(self):
        for key, maximum in (("page_bytes", 4 * 1024 * 1024),
                             ("payload_bytes", 1024 * 1024), ("events", 512), ("depth", 64)):
            value = getattr(self, key)
            if type(value) is not int or not 1 <= value <= maximum:
                raise SourceError(f"invalid {key} bound")


class SourceBinding(TypedDict):
    schema_version: int
    path: str
    source_handle: str
    generation: str
    device: int
    inode: int
    header_length: int
    header_sha256: str
    producer: dict
    mode: Literal["synthetic", "native"]
    authentication: str


class Cursor(TypedDict):
    schema_version: int
    generation: str
    enrolled_from: int
    offset: int
    frame_start: int
    ordinal: int
    trusted_through: int
    first_gap: int | None
    pending: str
    oversized: bool
    validator: dict | None
    last_sequence: int | None


class ObservationBatch(TypedDict):
    schema_version: int
    source_generation: str
    events: list[dict]
    cursor: Cursor
    coverage: dict
    gaps: list[dict]
    diagnostics: list[dict]
    bytes_read: int
    source_bytes_read: int
    frame_revalidation_bytes: int


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _canonical(value) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
                      allow_nan=False).encode("ascii")


def _digest(value) -> str:
    return _sha(_canonical(value))


def _unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise SourceError("duplicate JSON field")
        result[key] = value
    return result


def _json(raw: bytes, depth: int = 32):
    def check(value, level=0):
        if level > depth:
            raise SourceError("JSON depth exceeds bound")
        if isinstance(value, float) and not math.isfinite(value):
            raise SourceError("nonfinite JSON number")
        if isinstance(value, dict):
            for item in value.values():
                check(item, level + 1)
        elif isinstance(value, list):
            for item in value:
                check(item, level + 1)
    try:
        value = json.loads(raw.decode("utf-8", errors="strict"), object_pairs_hook=_unique,
                           parse_constant=lambda _: (_ for _ in ()).throw(SourceError("nonfinite JSON")))
        check(value)
    except (ValueError, UnicodeError, RecursionError) as exc:
        raise SourceError(str(exc)) from exc
    if not isinstance(value, dict):
        raise SourceError("native record must be an object")
    return value


# Runs, rather than individual characters, keep ignored large strings cheap.
_STRING_RUN = re.compile(r'[^"\\\x00-\x1f]+')
_NUMBER = re.compile(r'-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?\Z')
_IGNORED_PROJECTION = {("type",), ("ordinal",), ("payload", "type"), ("thread_id",), ("session_id",),
                       ("payload", "thread_id"), ("payload", "session_id"), ("sequence",), ("schema_version",),
                       ("payload_schema_version",), ("payload_type",), ("stream", "kind"), ("stream", "id"),
                       ("payload", "kind"), ("payload", "event", "kind")}


class _StreamJSON:
    """Resumable bounded JSON validator for a frame that exceeds retention.

    Cursor state contains only container states, bounded object keys and a
    partial UTF-8 codepoint. It never retains ignored values. Excessive key
    inventories are an explicit validation gap, not an allocation escape.
    """
    def __init__(self, state=None, depth=32):
        self.s = deepcopy(state) if state else {
            "stack": [], "root": "value", "lex": None, "token": "", "key": False,
            "escape": False, "unicode": 0, "utf8": "", "error": None, "depth": depth, "key_bytes": 0,
            "capture": None, "projection": {}}
        self.decoder = codecs.getincrementaldecoder("utf-8")("strict")
        self.decoder.setstate((base64.b64decode(self.s["utf8"]), 0))

    def _done(self):
        if not self.s["stack"]:
            self.s["root"] = "end"
        else:
            self.s["stack"][-1]["expect"] = "comma_or_end"

    def _path(self):
        if not self.s["stack"]:
            return []
        frame = self.s["stack"][-1]
        if frame["kind"] != "object" or frame["path"] is None:
            return None
        return frame["path"] + [frame["key"]]

    def _finish_token(self):
        s, token = self.s, self.s["token"]
        if s["lex"] == "number":
            if not _NUMBER.fullmatch(token) or not math.isfinite(float(token)):
                raise SourceError("invalid or nonfinite JSON number")
        elif s["lex"] == "literal" and token not in {"true", "false", "null"}:
            raise SourceError("invalid JSON literal")
        if s["capture"]:
            s["projection"][".".join(s["capture"])] = json.loads(token)
        s["lex"], s["token"], s["capture"] = None, "", None
        self._done()

    def feed(self, raw: bytes):
        if self.s["error"]:
            return
        try:
            self._text(self.decoder.decode(raw))
        except (UnicodeError, ValueError) as exc:
            self.s["error"] = str(exc)
        self.s["utf8"] = base64.b64encode(self.decoder.getstate()[0]).decode("ascii")

    def _text(self, text):
        s, i = self.s, 0
        while i < len(text):
            c = text[i]
            if s["lex"] == "string":
                if s["key"] or s["capture"]:
                    s["token"] += c
                    if len(s["token"]) > 512:
                        raise SourceError("JSON key exceeds validation bound")
                if s["unicode"]:
                    if c not in "0123456789abcdefABCDEF":
                        raise SourceError("invalid unicode escape")
                    s["unicode"] -= 1
                elif s["escape"]:
                    s["escape"] = False
                    if c == "u":
                        s["unicode"] = 4
                    elif c not in '\\"/bfnrt':
                        raise SourceError("invalid JSON escape")
                elif c == '"':
                    if s["key"]:
                        key = json.loads('"' + s["token"])
                        parent = s["stack"][-1]
                        if key in parent["keys"]:
                            raise SourceError("duplicate JSON field")
                        if len(parent["keys"]) >= 256:
                            raise SourceError("JSON key inventory exceeds validation bound")
                        s["key_bytes"] += len(key.encode("utf-8", errors="surrogatepass"))
                        if s["key_bytes"] > MAX_VALIDATOR_BYTES // 2:
                            raise SourceError("JSON key inventory exceeds total validation bound")
                        parent["keys"].append(key)
                        parent["key"] = key
                        parent["expect"] = "colon"
                    else:
                        if s["capture"]:
                            s["projection"][".".join(s["capture"])] = json.loads('"' + s["token"])
                        self._done()
                    s["lex"], s["token"], s["capture"] = None, "", None
                elif c == "\\":
                    s["escape"] = True
                elif ord(c) < 32:
                    raise SourceError("unescaped JSON control character")
                elif not s["key"] and not s["capture"]:
                    match = _STRING_RUN.match(text, i)
                    i = match.end()
                    continue
                i += 1
                continue
            if s["lex"] in {"number", "literal"}:
                if c in " \t\r,]}":
                    self._finish_token()
                    continue
                s["token"] += c
                if len(s["token"]) > 128:
                    raise SourceError("JSON scalar exceeds validation bound")
                i += 1
                continue
            if c in " \t\r":
                i += 1
                continue
            frame = s["stack"][-1] if s["stack"] else None
            expected = frame["expect"] if frame else s["root"]
            if frame and c == ("}" if frame["kind"] == "object" else "]"):
                if expected not in {"key_or_end", "value_or_end", "comma_or_end"}:
                    raise SourceError("unexpected JSON container end")
                s["stack"].pop()
                i += 1
                continue
            if expected == "colon":
                if c != ":":
                    raise SourceError("missing JSON colon")
                frame["expect"] = "value"
            elif expected == "comma_or_end":
                if c != ",":
                    raise SourceError("missing JSON separator")
                frame["expect"] = "key" if frame["kind"] == "object" else "value"
            elif expected in {"key", "key_or_end"}:
                if c != '"':
                    raise SourceError("JSON object key is not a string")
                s.update(lex="string", token="", key=True, capture=None)
            elif expected in {"value", "value_or_end"}:
                path = self._path()
                selected = path is not None and tuple(path) in _IGNORED_PROJECTION
                if selected:
                    s["projection"][".".join(path)] = None
                if c in "{[":
                    self._done()
                    if len(s["stack"]) >= s["depth"]:
                        raise SourceError("JSON depth exceeds bound")
                    s["stack"].append({"kind": "object" if c == "{" else "array",
                                       "expect": "key_or_end" if c == "{" else "value_or_end", "keys": [],
                                       "path": path, "key": None})
                elif c == '"':
                    s.update(lex="string", token="", key=False,
                             capture=path if selected else None)
                elif c in "-0123456789":
                    s.update(lex="number", token=c, capture=path if selected else None)
                elif c in "tfn":
                    s.update(lex="literal", token=c, capture=path if selected else None)
                else:
                    raise SourceError("invalid JSON value")
            else:
                raise SourceError("JSON trailing content")
            i += 1

    def finish(self):
        try:
            if self.s["error"]:
                return False
            self._text(self.decoder.decode(b"", final=True))
            if self.s["lex"] in {"number", "literal"}:
                self._finish_token()
            if self.s["lex"] or self.s["stack"] or self.s["root"] != "end":
                raise SourceError("incomplete JSON frame")
        except (UnicodeError, ValueError) as exc:
            self.s["error"] = str(exc)
        return not self.s["error"]


def _ignored_projection(projected, producer):
    """Only the client owner's explicitly nonmaterial grammar may be ignored."""
    return _DIALECTS[producer["client"]].is_ignored_projection(projected, producer)


def _open(path, binding=None):
    path = Path(path)
    named = path.lstat()
    if not stat.S_ISREG(named.st_mode):
        raise SourceError("source must be a regular nonsymlink file")
    stream = path.open("rb", buffering=0)
    try:
        opened = os.fstat(stream.fileno())
        identity = (opened.st_dev, opened.st_ino)
        if identity != (named.st_dev, named.st_ino) or not stat.S_ISREG(opened.st_mode):
            raise SourceError("source changed while opening")
        if binding and identity != (binding["device"], binding["inode"]):
            raise SourceError("source rotation requires a new generation")
    except BaseException:
        stream.close()
        raise
    return stream, opened


def _stable_read(stream, path, start, length, identity, minimum_size):
    stream.seek(start)
    raw = stream.read(length)
    stream.seek(start)
    repeat = stream.read(length)
    current = Path(path).lstat()
    opened = os.fstat(stream.fileno())
    if (len(raw) != length or raw != repeat or current.st_size < minimum_size
            or opened.st_size < minimum_size or not stat.S_ISREG(current.st_mode)
            or (current.st_dev, current.st_ino) != identity):
        raise SourceError("source bytes changed, truncated or rotated during read")
    return raw


def _producer(row, client, root, thread, parent=None, agent=None, dialect=None, invocation_id=None):
    module = _DIALECTS.get(client)
    if module is None:
        raise SourceError("unsupported native client source grammar")
    try:
        if dialect is not None:
            if dialect != {"codex": "codex.exec_json", "claude": "claude.print_stream"}.get(client) or thread != root or parent is not None or agent is not None:
                raise SourceError("unsupported captured transport identity or dialect")
            producer = module.qualify_transport(row, expected_session_id=root, invocation_id=invocation_id)
        else:
            if invocation_id is not None: raise SourceError("invocation identity requires an explicit transport dialect")
            producer = module.qualify_source(row, expected_root_session_id=root,
                expected_thread_id=thread, expected_parent_thread_id=parent, expected_agent_id=agent)
    except ValueError as exc:
        raise SourceError(str(exc)) from exc
    return {**producer, "adapter_sha256": _DIALECT_HASHES[client],
            "normalizer_version": ADAPTER_VERSION, "normalizer_sha256": ADAPTER_SHA256}


def _generation(binding):
    material = {k: binding[k] for k in ("device", "inode", "header_sha256", "producer", "mode")}
    if binding.get("source_epoch") is not None:
        material["source_epoch"] = binding["source_epoch"]
    return _digest(material)


def _validate_binding(binding):
    if (binding.get("schema_version") != 1 or binding.get("mode") not in {"native", "synthetic"}
            or binding.get("authentication") != "owner_admission_required"
            or type(binding.get("header_length")) is not int
            or not 1 <= binding["header_length"] <= MAX_HEADER_BYTES
            or not isinstance(binding.get("path"), str) or not Path(binding["path"]).is_absolute()
            or not isinstance(binding.get("source_handle"), str) or not 1 <= len(binding["source_handle"]) <= 512
            or not isinstance(binding.get("producer"), dict)
            or type(binding.get("device")) is not int or type(binding.get("inode")) is not int
            or binding.get("source_epoch") is not None and (not isinstance(binding["source_epoch"], str)
                or re.fullmatch(r"[0-9a-f]{64}", binding["source_epoch"]) is None)
            or binding.get("generation") != _generation(binding)):
        raise SourceError("invalid source binding; enrollment/admission must be re-established")


def _validate_cursor(binding, cursor, limits):
    lanes = cursor.get("dialect_sequences", {})
    if (not isinstance(lanes, dict) or len(lanes) > 8
            or any(not isinstance(k, str) or len(k) > 64 or type(v) is not int or v < 0 for k, v in lanes.items())):
        raise SourceError("invalid cursor dialect sequences")
    if cursor.get("schema_version") != 1 or cursor.get("generation") != binding["generation"]:
        raise SourceError("cursor generation mismatch")
    for key in ("enrolled_from", "offset", "frame_start", "ordinal", "trusted_through"):
        if type(cursor.get(key)) is not int or cursor[key] < 0:
            raise SourceError("invalid source cursor integers")
    if not cursor["enrolled_from"] <= cursor["trusted_through"] <= cursor["frame_start"] <= cursor["offset"]:
        raise SourceError("invalid source cursor boundaries")
    if cursor.get("first_gap") is not None and (type(cursor["first_gap"]) is not int
                                               or cursor["first_gap"] != cursor["trusted_through"]):
        raise SourceError("invalid source cursor gap")
    if cursor.get("transport_state") not in {None, "ready", "running", "terminal"}:
        raise SourceError("invalid transport phase")
    if not isinstance(cursor.get("pending"), str) or len(cursor["pending"]) > 4 * (limits.payload_bytes // 3 + 2):
        raise SourceError("pending cursor exceeds retention bound")
    try:
        pending = base64.b64decode(cursor["pending"], validate=True)
    except ValueError as exc:
        raise SourceError("invalid pending cursor encoding") from exc
    if b"\n" in pending or len(pending) > limits.payload_bytes or type(cursor.get("oversized")) is not bool:
        raise SourceError("invalid partial frame cursor")
    if cursor["oversized"]:
        if pending or not isinstance(cursor.get("validator"), dict) or len(_canonical(cursor["validator"])) > MAX_VALIDATOR_BYTES:
            raise SourceError("invalid oversized frame validation cursor")
    elif len(pending) != cursor["offset"] - cursor["frame_start"] or cursor.get("validator") is not None:
        raise SourceError("cursor pending bytes disagree with frame boundaries")


def enroll_source(path, *, client, expected_root_session_id, expected_thread_id=None,
                  expected_parent_thread_id=None, expected_agent_id=None,
                  source_handle=None, mode="synthetic", start_offset=0, source_epoch=None, limits=Limits(), dialect=None, invocation_id=None):
    """Validate source/header consistency, not native authenticity or admission."""
    path = Path(path).absolute()
    thread = expected_thread_id or expected_root_session_id
    if (mode not in {"native", "synthetic"} or type(start_offset) is not int or start_offset < 0
            or not all(isinstance(v, str) and 0 < len(v) <= 512 for v in (thread, expected_root_session_id))):
        raise SourceError("invalid source enrollment")
    stream, info = _open(path)
    with stream:
        raw = stream.readline(limits.payload_bytes + 1)
        if not raw.endswith(b"\n") or len(raw) > limits.payload_bytes:
            raise SourceError("incomplete or oversized source header")
        raw = _stable_read(stream, path, 0, len(raw), (info.st_dev, info.st_ino), info.st_size)
        producer = _producer(_json(raw, limits.depth), client, expected_root_session_id, thread,
                             expected_parent_thread_id, expected_agent_id, dialect,
                             invocation_id or (_digest([str(path), info.st_dev, info.st_ino, _sha(raw)]) if dialect else None))
        if start_offset > info.st_size:
            raise SourceError("enrollment boundary exceeds source")
        if start_offset:
            boundary = _stable_read(stream, path, start_offset - 1, 1,
                                    (info.st_dev, info.st_ino), info.st_size)
            if boundary != b"\n":
                raise SourceError("enrollment boundary is not a complete frame")
    binding = {"schema_version": 1, "path": str(path), "device": info.st_dev, "inode": info.st_ino,
               "header_length": len(raw), "header_sha256": _sha(raw), "producer": producer,
               "mode": mode, "authentication": "owner_admission_required"}
    if source_epoch is not None:
        binding["source_epoch"] = source_epoch
    binding["generation"] = _generation(binding)
    binding["source_handle"] = source_handle or _digest([str(path), binding["generation"]])
    _validate_binding(binding)
    cursor = {"schema_version": 1, "generation": binding["generation"], "enrolled_from": start_offset,
              "offset": start_offset, "frame_start": start_offset, "ordinal": 0, "trusted_through": start_offset,
              "first_gap": None, "pending": "", "oversized": False, "validator": None, "last_sequence": None, "transport_state": None}
    return binding, cursor


def _header(stream, binding, size):
    raw = _stable_read(stream, binding["path"], 0, binding["header_length"],
                       (binding["device"], binding["inode"]), size)
    if _sha(raw) != binding["header_sha256"]:
        raise SourceError("source header changed; new generation required")
    producer = binding["producer"]
    if _producer(_json(raw), producer["client"], producer["root_session_id"], producer["thread_id"],
                 producer.get("expected_parent_thread_id", producer.get("parent_thread_id")),
                 producer.get("agent_id") if producer["client"] == "claude" else producer.get("agent_path"),
                 producer.get("dialect"), producer.get("invocation_id")) != producer:
        raise SourceError("source producer binding changed")





def _events(row, binding, start, length, digest, ordinal, *, run_id=None, task_id=None, attempt_id=None, now=None):
    events = []
    locator = {"source_handle": binding["source_handle"], "generation": binding["generation"],
               "offset": start, "length": length, "sha256": digest}
    module = _DIALECTS[binding["producer"]["client"]]
    if binding["producer"].get("dialect"):
        candidates = module.decode_wire(row, {"producer": binding["producer"], "mode": binding["mode"],
            "source_locator": locator, "dialect": binding["producer"]["dialect"],
            "invocation_id": binding["producer"]["invocation_id"]})
    else:
        candidates = module.decode_record(row, binding["producer"], mode=binding["mode"], source_locator=locator)
    for candidate in candidates:
        kind, status, data = (candidate[key] for key in ("kind", "status", "data"))
        native = {**candidate["native"], **locator}
        record_id, subrecord, call_id = (native.get(key) for key in ("record_id", "subrecord", "call_id"))
        event_id = "sha256:" + _digest([binding["generation"], start, length, subrecord, record_id])
        semantic = [binding["producer"]["client"], binding["producer"]["thread_id"], call_id, kind] if call_id else None
        if semantic is not None and native.get("call_scope") is not None:
            semantic.append(native["call_scope"])
        if kind == "usage.snapshot" and data.get("measurement_id"):
            semantic = [data["measurement_id"], kind]
        event = {"schema_version": 1, "event_id": event_id, "run_id": run_id, "task_id": task_id, "attempt_id": attempt_id,
                 "producer": deepcopy(binding["producer"]), "native": native, "kind": kind, "status": status,
                 "native_timestamp": candidate.get("native_timestamp"), "ingested_at": now or _now(), "data": data,
                 "artifact_digests": {}, "coverage_ref": _digest([binding["generation"], start, length, digest]),
                 "conflict_refs": [], "semantic_key": _digest(semantic) if semantic else None,
                 "semantic_digest": _digest([kind, status, data]), "mode": binding["mode"],
                 "authentication": "owner_admission_required"}
        events.append(event)
    return events


def _coverage(binding, cursor, size, ranges, now):
    return {"source_generation": binding["generation"], "enrolled_from": cursor["enrolled_from"],
            "historically_ingested_through": cursor["trusted_through"], "scanned_through": cursor["offset"],
            "source_size_at_snapshot": size, "current_verified_ranges": ranges,
            "pending_bytes": cursor["offset"] - cursor["frame_start"], "backlog_bytes": max(0, size - cursor["offset"]),
            "first_gap": cursor["first_gap"], "negative_coverage": "UNKNOWN", "revalidated_at": now,
            "supported_schemas": SUPPORTED_SCHEMAS[binding["producer"]["client"]],
            "atomic_snapshot": False, "unobservable": ["effects outside observed interfaces", "owner admission not supplied",
                                                        "unlisted client schemas and counter scopes"]
            + (["work before enrollment"] if cursor["enrolled_from"] else [])}


def _dialect_sequence_gaps(cursor, row, producer, start):
    """Independent transport/native sequence lanes under the same journal cursor."""
    module = _DIALECTS[producer["client"]]
    decoder = getattr(module, "record_sequences", None)
    if decoder is None:
        return _row_sequence_gap(cursor, row, producer, start)
    sequences = decoder(row, producer)
    if (not isinstance(sequences, dict) or len(sequences) > 8
            or any(not isinstance(key, str) or len(key) > 64 for key in sequences)):
        raise SourceError("invalid dialect sequence lanes")
    saved = cursor.setdefault("dialect_sequences", {})
    first_gap = None
    for lane, sequence in sequences.items():
        one = {"last_sequence": saved.get(lane)}
        gap = _sequence_gap(one, sequence, start)
        saved[lane] = one["last_sequence"]
        if gap is not None and first_gap is None:
            first_gap = {**gap, "lane": lane}
    return first_gap


def _sequence_gap(cursor, sequence, start):
    if sequence is None:
        return None
    if type(sequence) is not int or sequence < 0:
        raise SourceError("invalid native ordinal")
    previous = cursor["last_sequence"]
    if previous is not None and sequence <= previous:
        raise SourceError("nonmonotonic native ordinal")
    cursor["last_sequence"] = sequence
    if previous is not None and sequence != previous + 1:
        return {"code": "native_sequence_gap", "offset": start, "length": 0,
                "sha256": None, "after_sequence": previous, "before_sequence": sequence,
                "obligation": "source sequence reconciliation required"}
    return None


def _row_sequence_gap(cursor, row, producer, start):
    sequences = native_muse.source_sequences(row) if producer["client"] == "muse" else [row.get("ordinal")]
    gap = None
    for sequence in sequences:
        observed = _sequence_gap(cursor, sequence, start)
        gap = gap or observed
    return gap


def _transport_transition(cursor, row, producer):
    dialect = producer.get("dialect")
    if dialect is None: return
    phase = cursor.get("transport_state")
    kind = row.get("type")
    if dialect == "codex.exec_json":
        if kind == "thread.started":
            if phase is not None: raise SourceError("duplicate transport thread initialization")
            phase = "ready"
        elif kind == "turn.started":
            if phase != "ready": raise SourceError("exec turn start has no unique invocation")
            phase = "running"
        elif kind in {"turn.completed", "turn.failed"}:
            if phase != "running": raise SourceError("exec terminal outside the admitted invocation")
            phase = "terminal"
        elif kind == "error":
            if phase is None: raise SourceError("exec error has no session")
        elif phase != "running": raise SourceError("exec item outside its running invocation")
    elif dialect == "claude.print_stream":
        if kind == "system" and row.get("subtype") in {"hook_started", "hook_response"}:
            if phase == "terminal": raise SourceError("hook event after print terminal")
        elif kind == "system" and row.get("subtype") == "init":
            if phase is not None: raise SourceError("duplicate print initialization")
            phase = "running"
        elif kind == "result":
            if phase != "running": raise SourceError("print terminal outside initialized session")
            phase = "terminal"
        elif phase != "running": raise SourceError("print message outside initialized session")
    cursor["transport_state"] = phase


def read_page(binding: SourceBinding, cursor: Cursor, *, run_id=None, task_id=None, attempt_id=None,
              limits=Limits()) -> ObservationBatch:
    """One bounded read; caller commits the returned batch and cursor together.

    A frame can span arbitrarily many pages without an unbounded retained body.
    Scan progress crosses a rejected frame with an explicit gap; the trusted
    watermark stops at the first gap. Notifications are hints, never evidence.
    ``page_bytes`` bounds new input. One retained frame spanning a prior page
    additionally rechecks at most ``payload_bytes``; ``bytes_read`` counts both
    reads of those bytes and the bounded header. Idle polling reads no bytes.
    """
    _validate_binding(binding)
    _validate_cursor(binding, cursor, limits)
    now, next_cursor = _now(), deepcopy(cursor)
    result = {"schema_version": 1, "source_generation": binding["generation"], "events": [], "cursor": next_cursor,
              "gaps": [], "diagnostics": [], "bytes_read": 0, "source_bytes_read": 0, "frame_revalidation_bytes": 0,
              "consumed_range": None}
    size, ranges = cursor["offset"], []
    try:
        stream, info = _open(binding["path"], binding)
        with stream:
            size = info.st_size
            if size < cursor["offset"]:
                raise SourceError("source truncation requires a new generation")
            if size == cursor["offset"]:
                result["coverage"] = _coverage(binding, cursor, size, [], now)
                return result
            _header(stream, binding, size)
            count = min(limits.page_bytes, size - cursor["offset"])
            raw = _stable_read(stream, binding["path"], cursor["offset"], count,
                               (binding["device"], binding["inode"]), size)
            result["source_bytes_read"], result["bytes_read"] = len(raw), 2 * (len(raw) + binding["header_length"])
        ranges = [[0, binding["header_length"]], [cursor["offset"], cursor["offset"] + len(raw)]]
        position, completed = 0, 0
        while position < len(raw) and completed < limits.events:
            end = raw.find(b"\n", position)
            complete = end >= 0
            end = end + 1 if complete else len(raw)
            part = raw[position:end]
            pending = base64.b64decode(next_cursor["pending"])
            validator = _StreamJSON(next_cursor["validator"], limits.depth) if next_cursor["oversized"] else None
            if not next_cursor["oversized"] and len(pending) + len(part) > limits.payload_bytes:
                validator = _StreamJSON(depth=limits.depth)
                validator.feed(pending)
                next_cursor.update(oversized=True, pending="")
            if next_cursor["oversized"]:
                validator.feed(part[:-1] if complete else part)
                next_cursor["validator"] = validator.s
            else:
                pending += part
                next_cursor["pending"] = base64.b64encode(pending).decode("ascii")
            next_cursor["offset"] += len(part)
            position = end
            if not complete:
                break
            completed += 1
            start, length = next_cursor["frame_start"], next_cursor["offset"] - next_cursor["frame_start"]
            gap = None
            if next_cursor["oversized"]:
                valid = validator.finish()
                ignored = valid and _ignored_projection(validator.s["projection"], binding["producer"])
                if ignored:
                    try:
                        gap = _sequence_gap(next_cursor, validator.s["projection"].get("sequence") if binding["producer"]["client"] == "muse" else validator.s["projection"].get("ordinal"), start)
                    except SourceError as exc:
                        ignored = False
                        validator.s["error"] = str(exc)
                if not ignored:
                    gap = {"code": "oversized_record", "offset": start, "length": length,
                           "sha256": None, "json_valid": valid, "detail": validator.s["error"],
                           "validation_scope": "incremental historical bytes; current interval remains unknown",
                           "obligation": "structured source readback required; body was not retained"}
            else:
                try:
                    if start < cursor["offset"]:
                        # This frame contains bytes saved by an earlier call.
                        # Reopen its entire bounded range before normalization;
                        # serializable pending bytes are not evidence caches.
                        reopened, present = _open(binding["path"], binding)
                        with reopened:
                            current_frame = _stable_read(reopened, binding["path"], start, length,
                                                         (binding["device"], binding["inode"]), present.st_size)
                        result["frame_revalidation_bytes"] += length
                        result["bytes_read"] += 2 * length
                        if current_frame != pending:
                            raise SourceError("frame changed between source pages")
                        ranges.append([start, start + length])
                    row = _json(pending, limits.depth)
                    sequence_gap = _dialect_sequence_gaps(next_cursor, row, binding["producer"], start)
                    _transport_transition(next_cursor, row, binding["producer"])
                    events = _events(row, binding, start, length, _sha(pending), next_cursor["ordinal"],
                                     run_id=run_id, task_id=task_id, attempt_id=attempt_id, now=now)
                    if len(result["events"]) + len(events) > limits.events:
                        raise SourceError("normalized event count exceeds page bound")
                    result["events"].extend(events)
                    gap = sequence_gap
                except (ValueError, TypeError, KeyError) as exc:
                    gap = {"code": "unobservable_record", "offset": start, "length": length,
                           "sha256": _sha(pending), "detail": str(exc), "obligation": "source owner reconciliation required"}
            if gap:
                gap.update(source_generation=binding["generation"], source_handle=binding["source_handle"])
                result["gaps"].append(gap)
                if next_cursor["first_gap"] is None:
                    next_cursor["first_gap"] = start
            if next_cursor["first_gap"] is None:
                next_cursor["trusted_through"] = next_cursor["offset"]
            next_cursor.update(frame_start=next_cursor["offset"], ordinal=next_cursor["ordinal"] + 1,
                               pending="", oversized=False, validator=None)
        consumed = next_cursor["offset"] - cursor["offset"]
        if consumed:
            result["consumed_range"] = {"offset": cursor["offset"], "length": consumed, "sha256": _sha(raw[:consumed])}
    except (OSError, SourceError) as exc:
        result["consumed_range"] = None
        result["cursor"] = deepcopy(cursor)
        next_cursor = result["cursor"]
        result["events"], result["gaps"], ranges = [], [], []
        result["diagnostics"].append({"code": "source_unavailable", "detail": str(exc),
                                      "obligation": "requalify source generation; preserve prior observations"})
    result["coverage"] = _coverage(binding, next_cursor, size, ranges, now)
    return result


def empty_projection() -> dict:
    return {"schema_version": 1, "events": {}, "semantic": {}, "pairs": {}, "usage": {},
            "gaps": [], "diagnostics": [], "coverage": {}, "aggregate_tree_usage": None,
            "authentication": "owner_admission_required", "pending_call_count": 0,
            "unresolved_pair_count": 0}


def _ref(event):
    return {"event_id": event["event_id"], "digest": event["semantic_digest"], "native": event["native"],
            "status": event["status"], "mode": event["mode"]}


def _pair_status(pair):
    calls, results = pair["calls"], pair["results"]
    if any(not row["native"].get("call_id") for row in calls + results):
        pair["status"] = "missing_identity"
    elif len({_digest(row["native"].get("call_scope")) for row in calls + results}) > 1:
        pair["status"] = "unlinked_native_scopes"
    elif len(calls) > 1 or len(results) > 1:
        pair["status"] = "conflict" if any(len({r["digest"] for r in rows}) > 1 for rows in (calls, results)) else "duplicate"
    elif not calls:
        pair["status"] = "pending_call"
    elif not results:
        pair["status"] = "pending_result"
    elif calls[0]["native"]["generation"] != results[0]["native"]["generation"]:
        pair["status"] = "unlinked_generations"
    elif (calls[0]["native"]["offset"], calls[0]["native"]["subrecord"]) >= (results[0]["native"]["offset"], results[0]["native"]["subrecord"]):
        pair["status"] = "out_of_order"
    else:
        pair["status"] = "paired"


def _add_counts(target, values):
    for key, value in values.items():
        target[key] = target.get(key, 0) + value


def _usage(projection, event):
    data, native = event["data"], event["native"]
    key = _digest([data["scope"], data["grammar"], event["mode"]])
    lane = projection["usage"].setdefault(key, {
        "scope": data["scope"], "grammar": data["grammar"], "mode": event["mode"],
        "generation": native["generation"], "epoch": None, "epoch_count": 0,
        "baseline": None, "latest": None, "known_delta": {}, "unknown_measurements": 0,
        "reconciliation_required": False, "responses": {}, "response_usage_sum": {}, "last_locator": None,
        "scope_nonoverlap": "UNKNOWN", "billing_cost": None, "complete": False})
    measurement = data.get("measurement_id")
    if measurement is not None:
        identity = _digest(measurement)
        previous = lane["responses"].get(identity)
        current = {"phase": data.get("phase"), "digest": data.get("counters_digest"),
                   "countable": data.get("countable") is True, "event_id": event["event_id"]}
        if previous and previous["countable"]:
            if current["countable"] and current["digest"] != previous["digest"]:
                lane["reconciliation_required"] = True
                projection["diagnostics"].append({"code": "conflicting_response_usage", "event_id": event["event_id"]})
        elif current["countable"]:
            # Native terminal usage replaces a provisional measurement. It is
            # counted once; cumulative views below remain a separate lane.
            lane["responses"][identity] = current
            _add_counts(lane["response_usage_sum"], data["last"])
        elif previous is None or previous.get("phase") != "final":
            lane["responses"][identity] = current
        if not current["countable"]:
            lane["unknown_measurements"] += 1
    totals = data["totals"]
    if totals is None:
        if measurement is None:
            lane["unknown_measurements"] += 1
        return
    previous = lane["latest"]
    old_location = lane["last_locator"]
    if old_location and native["generation"] == lane["generation"] and native["offset"] <= old_location["offset"]:
        lane["reconciliation_required"] = True
        projection["diagnostics"].append({"code": "out_of_order_usage_delivery", "event_id": event["event_id"]})
        return
    changed_epoch = previous is not None and (native["generation"] != lane["generation"]
        or set(previous) != set(totals) or any(totals[k] < previous[k] for k in totals if k in previous))
    if previous is None or changed_epoch:
        lane["epoch_count"] += 1
        lane["epoch"] = _digest([native["generation"], data["scope"], native["offset"], data["grammar"]])
        lane["baseline"] = totals
        if changed_epoch:
            lane["reconciliation_required"] = True
    else:
        _add_counts(lane["known_delta"], {k: totals[k] - previous[k] for k in totals})
    lane["latest"], lane["generation"], lane["last_locator"] = totals, native["generation"], native


def reduce_observations(projection: dict, batch: ObservationBatch) -> dict:
    """Pure projection for the existing journal. Never admit work or authority."""
    if len(_canonical(projection)) > MAX_PROJECTION_BYTES:
        raise SourceError("observation projection exceeds storage bound")
    result = deepcopy(projection)
    for event in sorted(batch["events"], key=lambda e: (e["native"]["generation"], e["native"]["offset"], e["native"]["subrecord"])):
        ident = event["event_id"]
        fingerprint = _digest({k: v for k, v in event.items() if k != "ingested_at"})
        if ident in result["events"]:
            if result["events"][ident] != fingerprint:
                raise SourceError("same source event has conflicting normalized bytes")
            continue
        if len(result["events"]) >= MAX_INDEX_ENTRIES:
            raise SourceError("observation projection capacity reached; journal owner compaction required")
        result["events"][ident] = fingerprint
        semantic = event["semantic_key"]
        if semantic:
            result["semantic"].setdefault(semantic, []).append(_ref(event))
        if event["kind"] in {"tool.call", "tool.result"}:
            # A missing native ID is retained as its own unresolved observation.
            # Position, equal arguments, timestamps and adjacency cannot supply it.
            native = event["native"]
            identity = [event["producer"]["client"], event["producer"]["thread_id"], native.get("call_id"), event["mode"]]
            if native.get("call_scope") is not None: identity.append(native["call_scope"])
            if not native.get("call_id"): identity.append(ident)
            key = _digest(identity)
            pair = result["pairs"].setdefault(key, {"calls": [], "results": [], "status": "pending_call"})
            pair["calls" if event["kind"] == "tool.call" else "results"].append(_ref(event))
            _pair_status(pair)
        if event["kind"] == "usage.snapshot":
            _usage(result, event)
    for label in ("gaps", "diagnostics"):
        for item in batch[label]:
            if item not in result[label]:
                result[label].append(deepcopy(item))
    for pair in result["pairs"].values():
        _pair_status(pair)
        if pair["status"] == "paired":
            call, output = pair["calls"][0]["native"], pair["results"][0]["native"]
            if any(gap["source_generation"] == call["generation"]
                   and call["offset"] <= gap["offset"] < output["offset"] + output["length"]
                   for gap in result["gaps"]):
                pair["status"] = "coverage_gap"
    result["pending_call_count"] = sum(p["status"] in {"pending_call", "pending_result"} for p in result["pairs"].values())
    result["unresolved_pair_count"] = sum(p["status"] != "paired" for p in result["pairs"].values())
    result["coverage"][batch["source_generation"]] = deepcopy(batch["coverage"])
    if (len(result["events"]) + len(result["gaps"]) + len(result["diagnostics"]) > MAX_INDEX_ENTRIES
            or len(_canonical(result)) > MAX_PROJECTION_BYTES):
        raise SourceError("observation projection capacity reached; journal owner compaction required")
    return result


def _event_material(event):
    # Attribution to a run/task and ingestion timestamps are journal-owned.
    return {k: event[k] for k in ("event_id", "producer", "native", "kind", "status", "native_timestamp",
                                  "data", "semantic_key", "semantic_digest", "mode", "authentication")}


def revalidate_observations(binding, events, *, projection=None, required_interval=None,
                            max_bytes=1024 * 1024, prior_sequence=None, prior_sequences=None) -> dict:
    """Re-read exact source bytes and re-derive every selected positive claim.

    ``current`` establishes selected current file bytes only. Known pair
    contradictions revoke positive use. Absence of later invalidation remains
    UNKNOWN unless the exact current interval is completely read and validated;
    even that is a bounded, non-atomic observation, never provider immutability.
    ``interval_events`` exposes cancellation/user/lifecycle observations to the
    existing owners. ``prior_sequences`` carries owner-verified dialect lanes at
    the interval boundary; callers cannot derive it from an untrusted request.
    Complete coverage never means those owners found no
    invalidation; interpreting those events is expressly not this parser's job.
    """
    result = {"status": "unknown", "current_verified_ranges": [], "diagnostics": [], "events": [],
              "negative_coverage": "UNKNOWN", "revalidated_at": _now(), "atomic_snapshot": False,
              "authentication": "owner_admission_required", "bytes_read": 0, "interval": None,
              "covers_through_source_snapshot": False, "interval_events": [],
              "invalidation_status": "owner_evaluation_required"}
    if type(max_bytes) is not int or not 1 <= max_bytes <= 16 * 1024 * 1024:
        raise SourceError("invalid revalidation byte bound")
    try:
        _validate_binding(binding)
        if len(events) > Limits().events:
            raise SourceError("selected observation count exceeds bound")
        refs = {}
        for event in events:
            ref = event["native"]
            if (ref["generation"] != binding["generation"] or ref["source_handle"] != binding["source_handle"]
                    or type(ref["offset"]) is not int or type(ref["length"]) is not int
                    or ref["offset"] < 0 or ref["length"] <= 0):
                raise SourceError("observation source locator mismatch")
            key = (ref["offset"], ref["length"])
            if key in refs and refs[key] != ref["sha256"]:
                raise SourceError("conflicting selected source locators")
            refs[key] = ref["sha256"]
        required = sum(length for _, length in refs) + binding["header_length"]
        if required_interval is not None:
            start, end = required_interval
            if type(start) is not int or type(end) is not int or not 0 <= start <= end:
                raise SourceError("invalid requested interval")
            required += end - start
        if required > max_bytes:
            result["diagnostics"].append({"code": "revalidation_bound", "required_bytes": required,
                                          "obligation": "bounded backfill or fresh owner readback"})
            return result
        stream, info = _open(binding["path"], binding)
        with stream:
            result["source_size_at_snapshot"] = info.st_size
            _header(stream, binding, info.st_size)
            result["bytes_read"] += 2 * binding["header_length"]
            parsed = {}
            for (start, length), digest in refs.items():
                raw = _stable_read(stream, binding["path"], start, length,
                                   (binding["device"], binding["inode"]), info.st_size)
                result["bytes_read"] += 2 * length
                if _sha(raw) != digest or not raw.endswith(b"\n"):
                    raise SourceError("source_bytes_changed")
                parsed[(start, length)] = _json(raw)
                result["current_verified_ranges"].append([start, start + length])
            for event in events:
                ref = event["native"]
                candidates = _events(parsed[(ref["offset"], ref["length"])], binding, ref["offset"], ref["length"],
                                     ref["sha256"], ref["ordinal"])
                actual = next((value for value in candidates if value["event_id"] == event["event_id"]), None)
                if actual is None or _event_material(actual) != _event_material(event):
                    raise SourceError("normalized observation differs from current source")
                result["events"].append(actual)
            if projection:
                wanted = {event["event_id"] for event in events}
                for pair in projection["pairs"].values():
                    if pair["status"] in {"duplicate", "conflict", "out_of_order", "unlinked_generations", "coverage_gap"}:
                        if wanted.intersection(ref["event_id"] for ref in pair["calls"] + pair["results"]):
                            raise SourceError("known native pair contradiction")
            if required_interval is not None:
                start, end = required_interval
                if end > info.st_size:
                    raise SourceError("requested interval exceeds current source")
                if refs and (start > min(offset for offset, _ in refs)
                             or end < max(offset + length for offset, length in refs)):
                    raise SourceError("requested interval does not cover selected evidence")
                if start:
                    stream.seek(start - 1)
                    if stream.read(1) != b"\n":
                        raise SourceError("interval does not begin at frame boundary")
                raw = _stable_read(stream, binding["path"], start, end - start,
                                   (binding["device"], binding["inode"]), info.st_size)
                result["bytes_read"] += 2 * len(raw)
                if raw and not raw.endswith(b"\n"):
                    raise SourceError("interval ends in a partial frame")
                offset = start
                interval_events = []
                if prior_sequence is not None and (type(prior_sequence) is not int or prior_sequence < 0):
                    raise SourceError("invalid prior interval sequence")
                if prior_sequences is not None and (not isinstance(prior_sequences, dict) or len(prior_sequences) > 8
                        or any(not isinstance(k, str) or len(k) > 64 or type(v) is not int or v < 0
                               for k, v in prior_sequences.items())):
                    raise SourceError("invalid prior dialect sequence lanes")
                sequence_cursor = {"last_sequence": prior_sequence, "transport_state": None,
                                   "dialect_sequences": deepcopy(prior_sequences or {})}
                for ordinal, line in enumerate(raw.splitlines(keepends=True)):
                    if len(line) > Limits().payload_bytes:
                        raise SourceError("interval contains oversized payload requiring owner readback")
                    row = _json(line)
                    gap = _dialect_sequence_gaps(sequence_cursor, row, binding["producer"], offset)
                    if start == 0: _transport_transition(sequence_cursor, row, binding["producer"])
                    if gap is not None:
                        result["diagnostics"].append(gap)
                        raise SourceError("current interval contains a native sequence gap")
                    if (offset, len(line)) in refs and _sha(line) != refs[(offset, len(line))]:
                        raise SourceError("source_bytes_changed")
                    interval_events.extend(_events(row, binding, offset, len(line), _sha(line), ordinal))
                    if len(interval_events) > Limits().events:
                        raise SourceError("interval semantic count exceeds bound")
                    offset += len(line)
                result["interval_events"] = interval_events
                interval_projection = reduce_observations(empty_projection(), {
                    "events": interval_events, "gaps": [], "diagnostics": [], "coverage": {}, "source_generation": binding["generation"]})
                wanted_calls = {e["native"]["call_id"] for e in events if e["native"]["call_id"]}
                for pair in interval_projection["pairs"].values():
                    if pair["status"] in {"duplicate", "conflict", "out_of_order"} and any(
                            r["native"]["call_id"] in wanted_calls for r in pair["calls"] + pair["results"]):
                        raise SourceError("current interval contains a native pair contradiction")
                result["current_verified_ranges"].append([start, end])
                result["interval"] = [start, end]
                result["covers_through_source_snapshot"] = end == info.st_size
                if end == info.st_size:
                    result["negative_coverage"] = "CURRENT_BOUNDED_INTERVAL"
        result["status"] = "current"
    except (OSError, ValueError, TypeError, KeyError) as exc:
        result["status"] = "invalid"
        result["events"] = []
        result["negative_coverage"] = "UNKNOWN"
        result["diagnostics"].append({"code": "source_bytes_changed" if str(exc) == "source_bytes_changed" else "source_invalid",
                                      "detail": str(exc), "obligation": "preserve prior evidence and reconcile current source"})
    return result


def revalidate_muse_page(binding, message, connection_binding, locators, *, max_bytes=1024 * 1024):
    """Corroborate opaque page ranges from current raw bytes; no wire authenticity.

    Locators are lookup hints, never proof. The entire bounded interval between
    each pair of endpoints is reopened and parsed. A page does not grant absence
    coverage, cursor advancement, native permission, or a semantic outcome.
    """
    _validate_binding(binding)
    if binding["producer"]["client"] != "muse" or binding["producer"].get("dialect"):
        raise SourceError("MSP range joins require a durable Muse raw source")
    if (not isinstance(locators, dict) or len(locators) > 512 or type(max_bytes) is not int
            or not 1 <= max_bytes <= 16 * 1024 * 1024):
        raise SourceError("invalid bounded source range locator inventory")
    if not isinstance(connection_binding, dict):
        raise SourceError("page connection binding must be an object")
    supplied = deepcopy(connection_binding)
    if (not isinstance(supplied.get("producer"), dict)
            or supplied["producer"].get("thread_id") != binding["producer"]["thread_id"]):
        raise SourceError("page producer does not match enrolled source")
    supplied.update(producer=binding["producer"], mode=binding["mode"])
    candidates = native_muse.decode_wire(message, supplied)
    pages = [value for value in candidates if value["kind"] == "coverage.page"]
    if len(pages) != 1: raise SourceError("range reconciliation needs one exact view/page response")
    # This call alone owns the cache. Every later call must reopen current
    # bytes. Charge each interval's header and each distinct endpoint so the
    # requested byte bound covers actual corroboration work, not just the
    # union of page hints.
    by_interval, endpoint_rows, joins, total, bytes_read = {}, {}, [], 0, 0
    for candidate in candidates[1:]:
        span = candidate["native"].get("source_range")
        if span is None:
            joins.append({"subrecord": candidate["native"]["subrecord"], "status": "UNKNOWN", "reason": "source_range_absent"})
            continue
        bounds = []
        for endpoint in ("first", "last"):
            point = span[endpoint]; locator = locators.get(point["id"])
            if (not isinstance(locator, dict) or set(locator) != {"offset", "length", "sha256"}
                    or type(locator["offset"]) is not int or locator["offset"] < 0
                    or type(locator["length"]) is not int or not 0 < locator["length"] <= Limits().payload_bytes
                    or not isinstance(locator["sha256"], str) or not re.fullmatch(r"[0-9a-f]{64}", locator["sha256"])):
                raise SourceError("page endpoint lacks an exact bounded source locator")
            bounds.append(locator)
        first, last = bounds
        interval = (first["offset"], last["offset"] + last["length"])
        if interval[0] > last["offset"]: raise SourceError("page endpoint source positions are reversed")
        if interval not in by_interval:
            total += binding["header_length"] + interval[1] - interval[0]
            if total > max_bytes: raise SourceError("page source ranges exceed bounded current read; paginate")
            verdict = revalidate_observations(binding, [], required_interval=interval, max_bytes=max_bytes)
            if verdict["status"] != "current": raise SourceError("page source range is not current and complete")
            bytes_read += verdict["bytes_read"] + int(interval[0] > 0)
            by_interval[interval] = verdict
        for endpoint, locator in zip(("first", "last"), bounds):
            key = locator["offset"], locator["length"], locator["sha256"]
            if key not in endpoint_rows:
                total += locator["length"]
                if total > max_bytes: raise SourceError("page endpoint corroboration exceeds bounded current read; paginate")
                stream, info = _open(binding["path"], binding)
                with stream:
                    raw = _stable_read(stream, binding["path"], locator["offset"], locator["length"],
                                       (binding["device"], binding["inode"]), info.st_size)
                bytes_read += 2 * locator["length"]
                if _sha(raw) != locator["sha256"]:
                    raise SourceError("page source range endpoint differs from current raw bytes")
                endpoint_rows[key] = _json(raw)
            row = endpoint_rows[key]
            if (row.get("id") != span[endpoint]["id"] or row.get("sequence") != span[endpoint]["sequence"]
                    or row.get("stream") != span["stream"]):
                raise SourceError("page source range endpoint differs from current raw bytes")
        actual = by_interval[interval]["interval_events"]
        semantic = "NOT_ASSERTED"
        if candidate["kind"] == "usage.snapshot":
            measurements = [event for event in actual if event["kind"] == "usage.snapshot"
                and event["data"]["measurement_id"] == candidate["data"]["measurement_id"]]
            if len(measurements) != 1 or measurements[0]["data"]["counters_digest"] != candidate["data"]["counters_digest"]:
                raise SourceError("page usage differs from its raw native measurement")
            semantic = "CURRENT_RESPONSE_COUNTERS"
        joins.append({"subrecord": candidate["native"]["subrecord"], "status": "CURRENT_RAW_RANGE",
                      "source_range": deepcopy(span), "interval": list(interval), "semantic_match": semantic})
    return {"schema_version": 1, "status": "current" if all(row["status"] != "UNKNOWN" for row in joins) else "unknown",
        "source_generation": binding["generation"], "status_scope": "raw_range_currentness",
        "wire_authentication": "UNKNOWN", "page_candidates_are_evidence": False, "authority_granted": False,
        "negative_coverage": "UNKNOWN", "page": deepcopy(pages[0]["data"]), "range_joins": joins,
        "raw_events": list({event["event_id"]: event for value in by_interval.values()
                            for event in value["interval_events"]}.values()), "required_bytes": total,
        "bytes_read": bytes_read, "physical_read_bound": 2 * total + sum(start > 0 for start, _ in by_interval)}
