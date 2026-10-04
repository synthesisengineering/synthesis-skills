"""Lossless bounded content-addressed snapshots for the existing run journal.

Events still commit last and retain their original logical digests. This is a
storage codec, never another state, ownership or mutation authority. Immutable
blocks are durable before an event references them. Interrupted unreferenced
blocks remain inert and count against the run's storage budget.
"""

from __future__ import annotations

from collections import OrderedDict
from contextlib import contextmanager
from contextvars import ContextVar

import base64
import errno
import fcntl
import hashlib
import json
import marshal
import os
from pathlib import Path
from operator import itemgetter
from itertools import chain
import sys
import re
import stat
import time
from threading import RLock
import uuid
import zlib

INLINE_BYTES = 1024 * 1024
LEAF_BYTES = 64 * 1024
INLINE_NODE_BYTES = 4096
BLOCK_PREFIX = b"\x00SZ1"
MAX_BLOCK_BYTES = 128 * 1024
MAX_LOGICAL_BYTES = 64 * 1024 * 1024
MAX_BLOCKS = 16384
MAX_DEPTH = 64
MAX_STORE_BYTES = 512 * 1024 * 1024
MAX_STORE_ENTRIES = 32768
STORE_READ_LOCK_SECONDS = 0.1
STORE_WRITE_LOCK_SECONDS = 5.0
MARKER = "synthesis_run_storage"
FIELDS = {MARKER, "root", "sha256", "logical_bytes"}
DIGEST = re.compile(r"[0-9a-f]{64}")
_JSON_NON_BRACKETS = bytes(value for value in range(256) if value not in b"[]{}")


class DecodedEvent(dict):
    """Per-read digest of the verified logical event; never persistent caching."""

    def __init__(self, value, raw):
        super().__init__(value)
        # The canonical top-level position is derived from parsed keys, rather
        # than searching nested or caller-authored text for a digest string.
        preceding = [(key, value[key]) for key in sorted(value) if key < "digest"]
        offset = 1 + sum(
            len(canonical(key)) + 1 + len(canonical(item)) + 1
            for key, item in preceding
        )
        field = canonical("digest") + b":" + canonical(value["digest"])
        if (
            raw[offset : offset + len(field)] != field
            or raw[offset + len(field) : offset + len(field) + 1] != b","
        ):
            raise ValueError("snapshot event canonical digest position is invalid")
        digest = hashlib.sha256()
        digest.update(raw[:offset])
        digest.update(raw[offset + len(field) + 1 : -1])
        self.verified_body_digest = digest.hexdigest()


class VerifiedEventProjection:
    """Explicit authenticated owner view; never an ordinary complete event."""
    __slots__ = ("header", "identity", "verified_body_digest", "full_state")

    def __init__(self, event, body_digest, full_state=None):
        if not isinstance(body_digest, str) or not DIGEST.fullmatch(body_digest):
            raise ValueError("projection has no complete event body authentication")
        self.header = {key: value for key, value in event.items() if key != "state"}
        self.identity = event.get("state")
        self.verified_body_digest = body_digest
        self.full_state = full_state


class _Selection:
    __slots__ = ("value", "kind", "keys", "length")

    def __init__(self, value, kind, keys=(), length=0):
        self.value, self.kind, self.keys, self.length = value, kind, keys, length


def _selection_key(selection, key):
    if selection is None:
        return None
    fields = {
        "event": {"state": "state", "digest": None, "previous_digest": None,
                  "revision": None, "schema_version": None, "command_id": None},
        "state": {"run_id": None, "revision": None, "schema_version": None,
                  "status": None, "successor": None, "extensions": "extensions"},
        "extensions": {"journal_storage": None, "workflow": "workflow"},
        "workflow": {"progress": None},
    }
    return fields.get(selection, {}).get(key, "skip")


def _select_value(value, selection):
    if selection is None:
        return value
    kind = "dict" if isinstance(value, dict) else "list" if isinstance(value, list) else "str" if isinstance(value, str) else "scalar"
    keys = tuple(value) if kind == "dict" else ()
    if selection == "skip":
        selected = None
    elif kind == "dict":
        selected = {}
        for key, item in value.items():
            child_selection = _selection_key(selection, key)
            if child_selection != "skip":
                child = _select_value(item, child_selection)
                selected[key] = child.value if isinstance(child, _Selection) else child
    else:
        selected = value
    return _Selection(selected, kind, keys, len(value) if kind != "scalar" else 0)


class _PlanCache(OrderedDict):
    """Exact pure-plan residency; callers hold the existing shared pool lock."""

    def __init__(self, *args, **kwargs):
        self._retained_bytes = 0
        super().__init__()
        self.update(*args, **kwargs)

    @property
    def retained_bytes(self):
        return self._retained_bytes

    def __setitem__(self, key, value):
        cost = value[-1]
        if type(cost) is not int or cost < 0:
            raise ValueError("snapshot plan has invalid residency cost")
        old = self.get(key)
        super().__setitem__(key, value)
        self._retained_bytes += cost - (old[-1] if old is not None else 0)

    def __delitem__(self, key):
        cost = self[key][-1]
        super().__delitem__(key)
        self._retained_bytes -= cost

    def pop(self, key, *default):
        if len(default) > 1:
            raise TypeError("pop expected at most two arguments")
        if key not in self:
            if default:
                return default[0]
            raise KeyError(key)
        value = self[key]
        del self[key]
        return value

    def popitem(self, last=True):
        if not self:
            raise KeyError("dictionary is empty")
        key = next(reversed(self)) if last else next(iter(self))
        return key, self.pop(key)

    def clear(self):
        super().clear()
        self._retained_bytes = 0

    def update(self, *args, **kwargs):
        if len(args) > 1:
            raise TypeError("update expected at most one argument")
        if args:
            source = args[0]
            entries = ((key, source[key]) for key in source.keys()) if hasattr(source, "keys") else source
            for key, value in entries:
                self[key] = value
        for key, value in kwargs.items():
            self[key] = value

    def setdefault(self, key, default=None):
        if key not in self:
            self[key] = default
        return self[key]

    def __ior__(self, other):
        self.update(other)
        return self

    def copy(self):
        return type(self)(self)


def _remember_canonical_plan(memo, key, result, raw, ranges, dependencies,
                             references, parsed, expanded, depth):
    # No full historical mutable value serialization. Shape is sufficient only
    # on the explicit skipped branch; selected/full readers have different keys.
    with memo["budget"]["lock"]:
        compiler = _COMPILATION.get()
        cb = compiler["bytes"] if compiler is not None else 0
        cc = len(compiler["entries"]) if compiler is not None else 0
        removable = memo["plans"].retained_bytes
        if (memo["closed"] or memo["budget"]["bytes"] - removable + cb + len(raw) > MAX_LOGICAL_BYTES
                or memo["budget"]["count"] - len(memo["plans"]) + cc >= MAX_BLOCKS):
            return
    payload = marshal.dumps((result.kind, result.keys, result.length), 4)
    metadata = (ranges, dependencies, references, parsed, expanded, depth)
    indexed = _member_span_leaf(raw, ranges)
    cost = len(key[0]) + len(key[1]) + len(payload) + len(raw) + len(marshal.dumps(metadata, 4)) + _entry_index_cost(indexed)
    with memo["budget"]["lock"]:
        if memo["closed"] or key in memo["plans"]:
            return
        compiler = _COMPILATION.get()
        cb = compiler["bytes"] if compiler is not None else 0
        cc = len(compiler["entries"]) if compiler is not None else 0
        if cost > MAX_LOGICAL_BYTES - cb:
            return
        while (memo["budget"]["bytes"] + cb + cost > MAX_LOGICAL_BYTES
               or memo["budget"]["count"] + cc >= MAX_BLOCKS):
            if not memo["plans"]:
                return
            _, old = memo["plans"].popitem(last=False)
            memo["bytes"] -= old[-1]
            memo["budget"]["bytes"] -= old[-1]
            memo["budget"]["count"] -= 1
        memo["plans"][key] = (payload, raw, ranges, dependencies, references,
                               parsed, expanded, depth, indexed, cost)
        memo["bytes"] += cost
        memo["budget"]["bytes"] += cost
        memo["budget"]["count"] += 1


def decode_event_projection(path, descriptor, *, include_full_state=False, _identities=None):
    if include_full_state or not isinstance(descriptor, dict) or descriptor.get(MARKER) != 1:
        event = decode(path, descriptor, _identities=_identities)
        if not isinstance(event, dict):
            raise ValueError("event must be an object")
        body = event.verified_body_digest if isinstance(event, DecodedEvent) else _hash(canonical({key: value for key, value in event.items() if key != "digest"}))
        return VerifiedEventProjection(event, body, event.get("state") if include_full_state else None)
    return _decode(path, descriptor, _identities=_identities, _selection="event")


def canonical(value):
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode()


def _hash(raw):
    return hashlib.sha256(raw).hexdigest()


def home_for(path):
    path = Path(path).absolute()
    if path.name == "current.json":
        home = path.parent
    elif path.parent.name == "events" and re.fullmatch(r"\d{12}\.json", path.name):
        home = path.parent.parent
    else:
        raise ValueError("snapshot descriptor is not at a run-owned snapshot path")
    if home.parent.name != "autopilot-runs" or str(uuid.UUID(home.name)) != home.name:
        raise ValueError("snapshot descriptor has no canonical run directory")
    return home


def _safe_directory(path, *, create=False):
    """No-follow handles prevent ancestor/link replacement during operations."""
    path = Path(path).absolute()
    fd = os.open("/", os.O_RDONLY | os.O_DIRECTORY)
    try:
        for part in path.parts[1:]:
            if create:
                try:
                    os.mkdir(part, 0o700, dir_fd=fd)
                except FileExistsError:
                    pass
                # Existing entries may be leftovers from a failed prior fsync.
                # A retry must confirm every ancestor before an event can commit.
                os.fsync(fd)
            child = os.open(
                part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd
            )
            os.close(fd)
            fd = child
        return fd
    except BaseException:
        os.close(fd)
        raise


def _lock_store(fd, *, exclusive):
    """Coordinate publication on the no-follow directory handle, without a lock file.

    Keep the strict content/metadata read fence: a hardlink's legitimate ctime
    transition must finish before readers inspect it. Writers hold this lock
    through capacity admission, link/unlink publication and directory fsync.
    Failure to acquire is bounded and fails closed; close(fd) releases it.
    """
    budget = STORE_WRITE_LOCK_SECONDS if exclusive else STORE_READ_LOCK_SECONDS
    deadline = time.monotonic() + budget
    operation = (fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH) | fcntl.LOCK_NB
    # The attempt bound also terminates under a stalled or substituted clock.
    for _ in range(max(1, int(budget / 0.01) + 1)):
        try:
            fcntl.flock(fd, operation)
            return
        except OSError as exc:
            if exc.errno not in {errno.EAGAIN, errno.EWOULDBLOCK}:
                raise
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            break
        time.sleep(min(0.01, remaining))
    raise ValueError("snapshot store is busy; bounded lock wait exhausted")


def _file_fingerprint(st):
    return (st.st_dev, st.st_ino, st.st_mode, st.st_nlink, st.st_size,
            st.st_mtime_ns, st.st_ctime_ns)


class _HandleChanged(ValueError):
    pass


def _read_at(parent, name, limit, *, _identity=None, _fd=None, _opened=None):
    if type(limit) is not int or limit < 0:
        raise ValueError("snapshot read byte budget exhausted")
    fd = _fd if _fd is not None else os.open(
        name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent)
    try:
        before = os.fstat(fd)
        if _opened is not None and _file_fingerprint(before) != _opened:
            raise _HandleChanged("snapshot handle metadata changed")
        if not stat.S_ISREG(before.st_mode) or before.st_size > limit:
            raise ValueError("snapshot file is not a bounded regular file")
        chunks, size = [], 0
        if _fd is None:
            # This call owns the newly opened descriptor and its stream offset.
            # Unbuffered reads consume at most the declared bytes plus the one
            # refusal byte. Keep the ordinary stream boundary, while finally
            # remains the sole descriptor owner even if stream setup fails.
            with os.fdopen(fd, "rb", buffering=0, closefd=False) as stream:
                while size <= before.st_size:
                    chunk = stream.read(before.st_size + 1 - size)
                    if not chunk:
                        break
                    chunks.append(chunk)
                    size += len(chunk)
                    if size == before.st_size:
                        break
        else:
            # Borrowed handles may have another consumer's seek offset. Each
            # occurrence performs fresh positional reads without changing it.
            while size <= before.st_size:
                chunk = os.pread(fd, before.st_size + 1 - size, size)
                if not chunk:
                    break
                chunks.append(chunk)
                size += len(chunk)
                if size == before.st_size:
                    break
        raw = chunks[0] if len(chunks) == 1 else b"".join(chunks)
        after = os.fstat(fd)
        present = os.stat(name, dir_fd=parent, follow_symlinks=False)
        if (len(raw) != before.st_size or len(raw) > limit
                or _file_fingerprint(before) != _file_fingerprint(after)
                or _file_fingerprint(after) != _file_fingerprint(present)):
            raise ValueError("snapshot file changed during read")
        if _identity is not None:
            _identity.append(_file_fingerprint(after))
        return raw
    finally:
        if _fd is None:
            os.close(fd)


_DIRECTORY_IDENTITY = ContextVar("journal_open_directory_identity", default=None)


def _evict_handle(budget):
    # Probation absorbs one-use scans. Frequently reused descriptors survive
    # those scans, under the same shared 256-handle and byte/count ceilings.
    for queue in ("handle_probation", "handle_protected"):
        for owner in budget["memos"]:
            selected = owner[queue]
            if selected:
                key, _ = selected.popitem(last=False)
                fd, cost, _ = owner["handles"].pop(key)
                os.close(fd)
                owner["bytes"] -= cost
                budget["bytes"] -= cost
                budget["count"] -= 1
                return True
    return False


def _read_block(parent, name, limit, memo, identity):
    """Reuse only handles; re-read and revalidate current path identity each time."""
    if memo is None:
        return _read_at(parent, name, limit, _identity=identity)
    with memo["budget"]["lock"]:
        if memo["closed"]:
            return _read_at(parent, name, limit, _identity=identity)
        bound = _DIRECTORY_IDENTITY.get()
        if bound is not None and bound[0] == parent and bound[2]:
            directory_key = bound[1]
        else:
            directory = os.fstat(parent)
            directory_key = (directory.st_dev, directory.st_ino)
        key = (*directory_key, name)
        handles = memo["handles"]
        probation, protected = memo["handle_probation"], memo["handle_protected"]
        compiler = _COMPILATION.get()
        compiled_bytes = compiler["bytes"] if compiler is not None else 0
        compiled_count = len(compiler["entries"]) if compiler is not None else 0
        found = handles.get(key)
        if found is None:
            while (sum(len(item["handles"]) for item in memo["budget"]["memos"])
                    >= min(256, MAX_BLOCKS)
                    or memo["budget"]["count"] + compiled_count >= MAX_BLOCKS):
                if not _evict_handle(memo["budget"]):
                    break
            # Include the two queue references in the existing byte accounting.
            cost = len(name) + 96
            if (not MAX_BLOCKS or memo["budget"]["count"] + compiled_count >= MAX_BLOCKS
                    or memo["budget"]["bytes"] + compiled_bytes + cost > MAX_LOGICAL_BYTES):
                return _read_at(parent, name, limit, _identity=identity)
            try:
                fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK,
                             dir_fd=parent)
            except OSError as exc:
                if exc.errno not in {errno.EMFILE, errno.ENFILE}:
                    raise
                while _evict_handle(memo["budget"]):
                    pass
                return _read_at(parent, name, limit, _identity=identity)
            try:
                found = (fd, cost, _file_fingerprint(os.fstat(fd)))
            except BaseException:
                os.close(fd)
                raise
            memo["bytes"] += cost
            memo["budget"]["bytes"] += cost
            memo["budget"]["count"] += 1
            handles[key] = found
            # Charged pure normalization records prior use, not file authority.
            # Include retained subtrees: recurring object/list/map blocks must
            # not restart probation merely because their proof is a plan rather
            # than a leaf. The fresh open/read/fingerprint/hash still runs.
            digest = name[:-5] if name.endswith(".json") else None
            known = digest in memo["entries"] or (
                (digest, False) in memo["plans"]
                or (digest, True) in memo["plans"]
                or (digest, "canonical-skip") in memo["plans"])
            if known:
                protected[key] = None
            else:
                probation[key] = None
        else:
            probation.pop(key, None)
            protected.pop(key, None)
            protected[key] = None
        # Both ceilings are shared by nested owners. No extra history or ghost
        # metadata is retained; the two existing queue references stay charged.
        owners = memo["budget"]["memos"]
        protected_count = (len(owners[0]["handle_protected"]) if len(owners) == 1 else
                           sum(len(owner["handle_protected"]) for owner in owners))
        while protected_count > min(192, max(0, MAX_BLOCKS * 3 // 4)):
            for owner in owners:
                if owner["handle_protected"]:
                    demoted, _ = owner["handle_protected"].popitem(last=False)
                    owner["handle_probation"][demoted] = None
                    protected_count -= 1
                    break
        try:
            return _read_at(parent, name, limit, _identity=identity,
                            _fd=found[0], _opened=found[2])
        except BaseException as exc:
            handles.pop(key)
            probation.pop(key, None)
            protected.pop(key, None)
            os.close(found[0])
            memo["bytes"] -= found[1]
            memo["budget"]["bytes"] -= found[1]
            memo["budget"]["count"] -= 1
            if isinstance(exc, _HandleChanged):
                # A fresh open enforces any changed access/ACL permissions.
                return _read_at(parent, name, limit, _identity=identity)
            raise


def read_regular(path, limit, *, _identities=None):
    parent = _safe_directory(Path(path).parent)
    try:
        if (
            Path(path).parent.name == "v1"
            and Path(path).parent.parent.name == "state-blocks"
        ):
            _lock_store(parent, exclusive=False)
        identity = []
        raw = _read_at(parent, Path(path).name, limit, _identity=identity)
        if _identities is not None:
            _identities[Path(path)] = identity[0]
        return raw
    finally:
        os.close(parent)


def _same_directory(path, fd):
    current = Path(path).lstat()
    opened = os.fstat(fd)
    if not stat.S_ISDIR(current.st_mode) or (current.st_dev, current.st_ino) != (
        opened.st_dev,
        opened.st_ino,
    ):
        raise ValueError("snapshot store changed during operation")


def codec_for(value):
    """Codec authority is part of the existing authenticated logical state."""
    state = value.get("state", value) if isinstance(value, dict) else value
    if isinstance(state, dict) and {"run_id", "revision", "schema_version"} <= set(state):
        extensions = state.get("extensions", {})
        if not isinstance(extensions, dict):
            raise ValueError("invalid authenticated journal storage extensions")
        if "journal_storage" not in extensions:
            return 1
        binding = extensions["journal_storage"]
        if (not isinstance(binding, dict) or set(binding) != {"codec"}
                or type(binding["codec"]) is not int or binding["codec"] != 2):
            raise ValueError("invalid authenticated journal storage codec")
    return 2


def _encode_legacy(value):
    raw = canonical(value) + b"\n"
    if len(raw) > MAX_LOGICAL_BYTES:
        raise ValueError("run snapshot logical capacity reached; no event committed")
    if len(raw) <= INLINE_BYTES:
        return raw, {}
    blocks = {}
    expansion_bytes = 0
    references = 0

    def put(node):
        data = canonical(node) + b"\n"
        if len(data) > MAX_BLOCK_BYTES:
            raise ValueError("snapshot block exceeds its byte bound")
        digest = _hash(data)
        blocks.setdefault(digest, data)
        if len(blocks) > MAX_BLOCKS:
            raise ValueError("snapshot exceeds its block count bound")
        return digest

    def visit(item, depth=0):
        nonlocal expansion_bytes, references
        references += 1
        if references > MAX_BLOCKS:
            raise ValueError("snapshot exceeds its reference count bound")
        if depth > MAX_DEPTH:
            raise ValueError("snapshot exceeds its depth bound")
        size = len(canonical(item))
        if size <= LEAF_BYTES:
            expansion_bytes += size
            if expansion_bytes > MAX_LOGICAL_BYTES:
                raise ValueError("snapshot expanded fragments exceed their byte bound")
            return put(["leaf", item])
        if isinstance(item, dict):
            if len(item) <= 32:
                expansion_bytes += sum(len(canonical(key)) for key in item)
                if expansion_bytes > MAX_LOGICAL_BYTES:
                    raise ValueError("snapshot expanded keys exceed their byte bound")
                return put(
                    [
                        "object",
                        [
                            [key, visit(child, depth + 1)]
                            for key, child in sorted(item.items())
                        ],
                    ]
                )
            groups = {}
            for key, child in item.items():
                slot = hashlib.sha256(key.encode()).hexdigest()[depth % 64]
                groups.setdefault(slot, {})[key] = child
            if len(groups) == 1:
                keys = sorted(item)
                groups = {
                    0: {k: item[k] for k in keys[: len(keys) // 2]},
                    1: {k: item[k] for k in keys[len(keys) // 2 :]},
                }
            return put(
                ["map", [visit(groups[key], depth + 1) for key in sorted(groups)]]
            )
        if isinstance(item, list):
            if len(item) == 1:
                return put(["array", [visit(item[0], depth + 1)]])
            middle = len(item) // 2
            return put(
                [
                    "list",
                    [visit(item[:middle], depth + 1), visit(item[middle:], depth + 1)],
                ]
            )
        if isinstance(item, str):
            middle = len(item) // 2
            return put(
                [
                    "text",
                    [visit(item[:middle], depth + 1), visit(item[middle:], depth + 1)],
                ]
            )
        raise ValueError("snapshot scalar exceeds its byte bound")

    root = visit(value)
    descriptor = {
        MARKER: 1,
        "root": root,
        "sha256": _hash(raw),
        "logical_bytes": len(raw),
    }
    return canonical(descriptor) + b"\n", blocks


_COMPILATION = ContextVar("journal_compilation", default=None)


@contextmanager
def compilation_scope():
    """Bounded pure compiler reuse, never a filesystem or admission proof.

    The key is the complete canonical input hash. Cached nodes are serialized
    immutable bytes, copied on use; all depth/reference/expansion bounds still
    apply in the caller's enclosing graph. No entry survives this operation.
    """
    if _COMPILATION.get() is not None:
        yield
        return
    token = _COMPILATION.set({"entries": {}, "bytes": 0})
    try:
        yield
    finally:
        _COMPILATION.reset(token)



_NORMALIZATION = ContextVar("journal_legacy_normalization", default=None)
_PURE_CACHE_LOCK = RLock()


def _normalization_policy():
    return (LEAF_BYTES, MAX_BLOCK_BYTES, MAX_LOGICAL_BYTES, MAX_BLOCKS, MAX_DEPTH)


@contextmanager
def normalization_scope():
    """Fresh bounded pure codec1 normalization, never retained authority.

    Every physical read/hash and per-reference charge still runs. The only binary
    values loaded here are self-produced marshal bytes of the standard JSON
    decoder's builtin values; no binary input is read from storage or a caller.
    Nested scopes have fresh entries and share the same finite residency budget.
    """
    parent = _NORMALIZATION.get()
    if parent is not None and parent["closed"]:
        parent = None
    budget = parent["budget"] if parent is not None else {"bytes": 0, "count": 0, "memos": [], "lock": _PURE_CACHE_LOCK}
    memo = {"entries": {}, "plans": _PlanCache(), "handles": OrderedDict(), "handle_probation": OrderedDict(), "handle_protected": OrderedDict(), "bytes": 0, "budget": budget, "policy": _normalization_policy(), "closed": False}
    with budget["lock"]:
        budget["memos"].append(memo)
    token = _NORMALIZATION.set(memo)
    try:
        yield
    finally:
        try:
            with budget["lock"]:
                budget["bytes"] -= memo["bytes"]
                budget["count"] -= len(memo["entries"]) + len(memo["handles"]) + len(memo["plans"])
                for fd, _, _ in memo["handles"].values():
                    os.close(fd)
                memo["handles"].clear()
                memo["handle_probation"].clear()
                memo["handle_protected"].clear()
                memo["entries"].clear()
                memo["plans"].clear()
                memo["bytes"] = 0
                memo["closed"] = True
                budget["memos"][:] = [item for item in budget["memos"] if item is not memo]
        finally:
            _NORMALIZATION.reset(token)


def _normalization_memo():
    memo = _NORMALIZATION.get()
    if memo is not None and memo["closed"]:
        return None
    if memo is not None:
        with memo["budget"]["lock"]:
            policy = _normalization_policy()
            compiler = _COMPILATION.get()
            compiled_bytes = compiler["bytes"] if compiler is not None else 0
            compiled_count = len(compiler["entries"]) if compiler is not None else 0
            if (any(item["policy"] != policy for item in memo["budget"]["memos"])
                    or memo["budget"]["bytes"] + compiled_bytes > MAX_LOGICAL_BYTES
                    or memo["budget"]["count"] + compiled_count > MAX_BLOCKS):
                # A nested policy change cannot leave outer optional residency above
                # the new bound. These are pure caches, so discard all active entries.
                for item in memo["budget"]["memos"]:
                    item["entries"].clear()
                    item["plans"].clear()
                    for fd, _, _ in item["handles"].values():
                        os.close(fd)
                    item["handles"].clear()
                    item["handle_probation"].clear()
                    item["handle_protected"].clear()
                    item["bytes"] = 0
                    item["policy"] = policy
                memo["budget"]["bytes"] = memo["budget"]["count"] = 0
                if compiler is not None:
                    compiler["entries"].clear()
                    compiler["bytes"] = 0
    return memo


def _remember_plan(memo, key, result, raw, members, dependencies,
                   references, parsed, expanded, depth, *, _ranges=None):
    """Retain pure compilation only; current filesystem proofs never enter it."""
    # Admission is optional. Large, changing event ancestors must not spend
    # repeated serialization work or evict common smaller subtrees. Refuse
    # before constructing payloads; the ordinary decoder remains authoritative.
    if parsed > LEAF_BYTES * 8 or raw is None and members is None:
        return raw
    if raw is None:
        raw = b"{" + b",".join(members[name] for name in sorted(members)) + b"}"
    payload = marshal.dumps(result, 4)
    # One canonical backing buffer plus offsets; no per-member byte copies.
    # Ordinary callers still reconstruct a fresh independent mutable value.
    member_items = _ranges
    if member_items is None and members is not None:
        member_items = _canonical_members(result, raw)
    metadata = (member_items, dependencies, references, parsed, expanded, depth)
    indexed = _member_span_leaf(raw, member_items)
    cost = len(key[0]) + len(payload) + len(raw) + len(marshal.dumps(metadata, 4)) + _entry_index_cost(indexed)
    with memo["budget"]["lock"]:
        if memo["closed"] or key in memo["plans"]:
            return raw
        compiler = _COMPILATION.get()
        compiled_bytes = compiler["bytes"] if compiler is not None else 0
        compiled_count = len(compiler["entries"]) if compiler is not None else 0
        plan_allowance = MAX_LOGICAL_BYTES // 4
        if cost > plan_allowance:
            return raw
        plan_bytes = memo["plans"].retained_bytes
        while (plan_bytes + cost > plan_allowance
               or memo["budget"]["bytes"] + compiled_bytes + cost > MAX_LOGICAL_BYTES
               or memo["budget"]["count"] + compiled_count >= MAX_BLOCKS):
            if not memo["plans"]:
                return raw
            _, old = memo["plans"].popitem(last=False)
            memo["bytes"] -= old[-1]
            memo["budget"]["bytes"] -= old[-1]
            memo["budget"]["count"] -= 1
            plan_bytes -= old[-1]
        memo["plans"][key] = (payload, raw, member_items, dependencies,
                               references, parsed, expanded, depth, indexed, cost)
        memo["bytes"] += cost
        memo["budget"]["bytes"] += cost
        memo["budget"]["count"] += 1
    return raw


def _normalization_resident():
    memo = _normalization_memo()
    return (memo["budget"]["bytes"], memo["budget"]["count"]) if memo is not None else (0, 0)


def _canonical_members(value, raw):
    """Offsets into self-produced canonical dict bytes, never external framing."""
    text = raw.decode("utf-8")
    decoder = json.JSONDecoder()
    position, byte_position = 1, 1
    members = []
    for key in sorted(value):
        start = position
        observed, end = decoder.raw_decode(text, position)
        if observed != key or text[end:end + 1] != ":":
            return None
        _, position = decoder.raw_decode(text, end + 1)
        size = len(text[start:position].encode("utf-8"))
        members.append((key, byte_position, byte_position + size))
        byte_position += size
        if text[position:position + 1] == ",":
            position += 1
            byte_position += 1
        elif text[position:] != "}":
            return None
    if text[position:] != "}" or byte_position != len(raw) - 1:
        return None
    return tuple(members)

def encode(value, *, codec=None):
    selected = codec_for(value) if codec is None else codec
    if selected == 1:
        return _encode_legacy(value)
    if selected != 2:
        raise ValueError("unsupported journal storage codec")
    raw = canonical(value) + b"\n"
    if len(raw) > MAX_LOGICAL_BYTES:
        raise ValueError("run snapshot logical capacity reached; no event committed")
    if len(raw) <= INLINE_BYTES:
        return raw, {}
    blocks = {}
    expansion_bytes = 0
    references = 0
    maximum_depth = 0
    depth_marks = []

    def seen_depth(value):
        nonlocal maximum_depth
        maximum_depth = max(maximum_depth, value)
        for mark in depth_marks:
            mark[0] = max(mark[0], value)

    def put(node, *, force=False):
        data = canonical(node) + b"\n"
        if len(data) > MAX_BLOCK_BYTES:
            # Only reference positions may be externalized; caller-authored
            # leaf JSON is never interpreted as storage metadata.
            if node[0] == "object":
                slots = [(pair, 1) for pair in node[1]]
            elif node[0] in {"map", "array", "list", "text"}:
                slots = [(node[1], index) for index in range(len(node[1]))]
            else:
                slots = []
            for parent, index in slots:
                if isinstance(parent[index], list):
                    parent[index] = put(parent[index], force=True)
            data = canonical(node) + b"\n"
            if len(data) > MAX_BLOCK_BYTES:
                raise ValueError("snapshot block exceeds its byte bound")
        if not force and len(data) <= INLINE_NODE_BYTES:
            return node
        packed = BLOCK_PREFIX + zlib.compress(data)
        if len(packed) < len(data):
            try:
                _compressed_json_bounds(data)
            except ValueError:
                pass  # Historical plain blocks retain their admitted semantics.
            else:
                data = packed
        digest = _hash(data)
        blocks.setdefault(digest, data)
        if len(blocks) > MAX_BLOCKS:
            raise ValueError("snapshot exceeds its block count bound")
        return digest

    def compile_node(item, depth=0, raw_item=None):
        nonlocal expansion_bytes, references, maximum_depth
        seen_depth(depth)
        references += 1
        if references > MAX_BLOCKS:
            raise ValueError("snapshot exceeds its reference count bound")
        if depth > MAX_DEPTH:
            raise ValueError("snapshot exceeds its depth bound")
        raw_item = canonical(item) if raw_item is None else raw_item
        size = len(raw_item)
        if size <= LEAF_BYTES:
            expansion_bytes += size
            if expansion_bytes > MAX_LOGICAL_BYTES:
                raise ValueError("snapshot expanded fragments exceed their byte bound")
            # Compression changes only physical bytes. Both readers charge the
            # original leaf length and bound decompression before JSON parsing.
            plain_size = len(raw_item) + len(b'["leaf",]\n')
            packed = zlib.compress(raw_item)
            node = ["zleaf", base64.b64encode(packed).decode("ascii")]
            if len(canonical(node)) + 1 < plain_size:
                try:
                    _compressed_json_bounds(raw_item)
                except ValueError:
                    pass  # Retain the admitted plain-leaf encoding.
                else:
                    return put(node)
            return put(["leaf", item])
        if isinstance(item, dict):
            if len(item) <= 32:
                expansion_bytes += sum(len(canonical(key)) for key in item)
                if expansion_bytes > MAX_LOGICAL_BYTES:
                    raise ValueError("snapshot expanded keys exceed their byte bound")
                return put(
                    [
                        "object",
                        [
                            [key, visit(child, depth + 1)]
                            for key, child in sorted(item.items())
                        ],
                    ]
                )
            # Calculate each member once. Intermediate partitions need only
            # their exact canonical size; serializing the same children at every
            # routing level multiplied append work without changing any bytes.
            members = {key: (canonical(key) + b":" + canonical(child),
                             hashlib.sha256(key.encode()).digest())
                       for key, child in item.items()}
            def segments(group, level, bit, group_raw=None):
                nonlocal maximum_depth
                seen_depth(level)
                if level > MAX_DEPTH:
                    raise ValueError("snapshot exceeds its depth bound")
                size = 2 + max(0, len(group) - 1) + sum(len(members[key][0]) for key in group)
                if len(group) <= 32 or size <= LEAF_BYTES:
                    group_raw = (b"{" + b",".join(members[key][0] for key in sorted(group)) + b"}")
                    return [visit(group, level, group_raw)]
                groups = {}
                for key, child in group.items():
                    digest = members[key][1]
                    slot = (digest[(bit // 8) % len(digest)] >> (bit % 8)) & 1
                    groups.setdefault(slot, {})[key] = child
                if len(groups) == 1:
                    keys = sorted(group)
                    groups = {
                        0: {key: group[key] for key in keys[:len(keys) // 2]},
                        1: {key: group[key] for key in keys[len(keys) // 2:]},
                    }
                return [ref for slot in sorted(groups)
                        for ref in segments(groups[slot], level + 1, bit + 1)]

            # Partition bits are relative to this map, so the same state map
            # shares bytes inside an event and its standalone projection. The
            # independent absolute depth guard above remains unchanged.
            # The partition boundaries are stable under append; intermediary
            # binary routing nodes do not each need their own immutable file.
            # Bounded reference pages retain the same expansion/depth limits.
            refs = segments(item, depth + 1, 0, raw_item)
            while len(refs) > 16:
                next_refs = []
                for start in range(0, len(refs), 16):
                    references += 1
                    if references > MAX_BLOCKS:
                        raise ValueError("snapshot exceeds its reference count bound")
                    next_refs.append(put(["map", refs[start:start + 16]]))
                refs = next_refs
            return put(["map", refs])
        if isinstance(item, list):
            if len(item) == 1:
                return put(["array", [visit(item[0], depth + 1)]])
            # Prefix-aligned segments do not repartition every earlier element
            # when one element is appended. Oversized elements are still split
            # by the ordinary recursive owner with the same reference bounds.
            if len(item) <= 64:
                return put(["array", [visit(child, depth + 1) for child in item]])
            return put(
                ["list", [visit(item[start:start + 64], depth + 1)
                          for start in range(0, len(item), 64)]]
            )
        if isinstance(item, str):
            middle = len(item) // 2
            return put(
                [
                    "text",
                    [visit(item[:middle], depth + 1), visit(item[middle:], depth + 1)],
                ]
            )
        raise ValueError("snapshot scalar exceeds its byte bound")

    def dependencies(node):
        selected = {}
        visits = 0
        def walk(current):
            nonlocal visits
            visits += 1
            if visits > MAX_BLOCKS:
                raise ValueError("compiled subtree exceeds reference bound")
            if isinstance(current, str):
                if current in selected:
                    return
                selected[current] = blocks[current]
                current, _ = _block_node(blocks[current], limit=MAX_BLOCK_BYTES)
            kind, body = current
            if kind == "object":
                for _, child in body:
                    walk(child)
            elif kind in {"map", "array", "list", "text"}:
                for child in body:
                    walk(child)
        walk(node)
        return selected

    def visit(item, depth=0, raw_item=None):
        nonlocal expansion_bytes, references, maximum_depth
        memo = _COMPILATION.get()
        # Immutable content keys allow unchanged structured leaves to be reused
        # across appends in the same finite operation. No object identity, file
        # metadata, admission proof or decoded caller value is cached here.
        eligible = memo is not None and isinstance(item, (dict, list, str))
        if not eligible:
            return compile_node(item, depth, raw_item)
        raw_item = canonical(item) if raw_item is None else raw_item
        if len(raw_item) < 2048:
            return compile_node(item, depth, raw_item)
        key = _hash(raw_item)
        with _PURE_CACHE_LOCK:
            found = memo["entries"].get(key)
            if found is not None:
                # Keep recently useful leaf blocks while old full-state entries
                # leave the same aggregate physical-byte allowance first.
                del memo["entries"][key]
                memo["entries"][key] = found
                node_raw, child_blocks, child_refs, child_bytes, child_depth = found
                if (references + child_refs > MAX_BLOCKS or expansion_bytes + child_bytes > MAX_LOGICAL_BYTES
                        or depth + child_depth > MAX_DEPTH):
                    raise ValueError("compiled subtree exceeds enclosing snapshot bounds")
                references += child_refs
                expansion_bytes += child_bytes
                seen_depth(depth + child_depth)
                blocks.update(child_blocks)
                if len(blocks) > MAX_BLOCKS:
                    raise ValueError("snapshot exceeds its block count bound")
                return json.loads(node_raw)
        before_refs, before_bytes = references, expansion_bytes
        mark = [depth]
        depth_marks.append(mark)
        try:
            result = compile_node(item, depth, raw_item)
        finally:
            depth_marks.pop()
        try:
            child_blocks = dependencies(result)
        except ValueError:
            return result  # Optional compile reuse cannot narrow encoding.
        node_raw = canonical(result)
        cost = len(node_raw) + sum(map(len, child_blocks.values()))
        with _PURE_CACHE_LOCK:
            if key in memo["entries"]:
                return result
            normal_bytes, normal_count = _normalization_resident()
            if cost <= MAX_LOGICAL_BYTES - normal_bytes:
                while (memo["bytes"] + cost + normal_bytes > MAX_LOGICAL_BYTES
                       or len(memo["entries"]) + normal_count >= MAX_BLOCKS):
                    if not memo["entries"]:
                        return result
                    oldest = next(iter(memo["entries"]))
                    old_node, old_blocks, *_ = memo["entries"].pop(oldest)
                    memo["bytes"] -= len(old_node) + sum(map(len, old_blocks.values()))
                memo["entries"][key] = (node_raw, child_blocks, references - before_refs,
                                        expansion_bytes - before_bytes, mark[0] - depth)
                memo["bytes"] += cost
        return result

    root = visit(value, raw_item=raw[:-1])
    if isinstance(root, list):
        root = put(root, force=True)
    descriptor = {
        MARKER: 2,
        "root": root,
        "sha256": _hash(raw),
        "logical_bytes": len(raw),
    }
    return canonical(descriptor) + b"\n", blocks


def block_paths(home, blocks):
    return {
        Path(home) / "state-blocks/v1" / (digest + ".json"): raw
        for digest, raw in blocks.items()
    }


def materialize(home, blocks):
    if not blocks:
        return
    directory = Path(home) / "state-blocks/v1"
    fd = _safe_directory(directory, create=True)
    try:
        _lock_store(fd, exclusive=True)
        _same_directory(directory, fd)
        total = count = 0
        names = set()
        with os.scandir(fd) as entries:
            for entry in entries:
                count += 1
                if count > MAX_STORE_ENTRIES:
                    raise ValueError("run snapshot store entry capacity reached")
                info = entry.stat(follow_symlinks=False)
                if not stat.S_ISREG(info.st_mode) or info.st_size > MAX_BLOCK_BYTES:
                    raise ValueError("snapshot store contains an unsafe entry")
                total += info.st_size
                names.add(entry.name)
        new = {d: raw for d, raw in blocks.items() if d + ".json" not in names}
        # During no-overwrite hardlink publication the staging and final names
        # coexist. Reserve that one additional entry and its largest payload so
        # even the transient namespace stays within the same store ceilings.
        staging_entries = 1 if new else 0
        staging_bytes = max(map(len, new.values()), default=0)
        if (
            count + len(new) + staging_entries > MAX_STORE_ENTRIES
            or total + sum(map(len, new.values())) + staging_bytes > MAX_STORE_BYTES
        ):
            raise ValueError("run snapshot store byte or entry capacity reached")
        for digest, raw in blocks.items():
            if (
                not DIGEST.fullmatch(digest)
                or _hash(raw) != digest
                or len(raw) > MAX_BLOCK_BYTES
            ):
                raise ValueError("invalid snapshot block installation")
            name = digest + ".json"
            if name in names:
                if _read_at(fd, name, MAX_BLOCK_BYTES) != raw:
                    raise ValueError("existing immutable snapshot block changed")
                continue
            stage = ".stage-" + uuid.uuid4().hex
            created = None
            try:
                stagefd = os.open(
                    stage,
                    os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                    0o600,
                    dir_fd=fd,
                )
                with os.fdopen(stagefd, "wb") as stream:
                    created = os.fstat(stream.fileno())
                    stream.write(raw)
                    stream.flush()
                    os.fsync(stream.fileno())
                try:
                    os.link(
                        stage, name, src_dir_fd=fd, dst_dir_fd=fd, follow_symlinks=False
                    )
                except FileExistsError:
                    if _read_at(fd, name, MAX_BLOCK_BYTES) != raw:
                        raise ValueError("concurrent snapshot block differs")
                else:
                    published = os.stat(name, dir_fd=fd, follow_symlinks=False)
                    if (
                        not stat.S_ISREG(published.st_mode)
                        or (published.st_dev, published.st_ino)
                        != (created.st_dev, created.st_ino)
                        or _read_at(fd, name, MAX_BLOCK_BYTES) != raw
                    ):
                        raise ValueError(
                            "snapshot publication no longer matches its staged content"
                        )
                os.fsync(fd)
            finally:
                # Exclusive creation failure does not confer custody of an
                # existing name. Preserve substituted or orphaned evidence.
                if created is not None:
                    try:
                        present = os.stat(stage, dir_fd=fd, follow_symlinks=False)
                    except FileNotFoundError:
                        pass
                    else:
                        if not stat.S_ISREG(present.st_mode) or (
                            present.st_dev,
                            present.st_ino,
                        ) != (created.st_dev, created.st_ino):
                            raise ValueError(
                                "snapshot stage changed before owned cleanup"
                            )
                        os.unlink(stage, dir_fd=fd)
        # The final name may already exist after an interrupted link/fsync.
        # Successful retry must make all verified entries durable as well.
        os.fsync(fd)
        current = directory.lstat()
        opened = os.fstat(fd)
        if (current.st_dev, current.st_ino) != (opened.st_dev, opened.st_ino):
            raise ValueError("snapshot store changed during installation")
    finally:
        os.close(fd)


def _compressed_json_bounds(raw, *, _canonical=False):
    """Bound parser nesting/work before parsing a new compressed leaf.

    Existing MAX_DEPTH/MAX_BLOCKS also bound graph traversal separately. Plain
    historical leaves keep their original <=LEAF_BYTES representation semantics.
    JSON syntax and canonical identity are checked by the JSON parser afterward.
    """
    # Most canonical native-history leaves contain no escapes. Splitting at
    # quotes then masking the odd spans is exactly the existing string mask
    # for that case, without scanning every string byte in the regex engine.
    # Odd quote counts and escaped strings keep the original lexer.
    quotes = raw.count(b'"')
    if b"\\" not in raw and quotes % 2 == 0:
        strings = quotes // 2
        if strings > MAX_BLOCKS:
            raise ValueError("compressed snapshot leaf exceeds JSON work bound")
        masked = b'""'.join(raw.split(b'"')[::2])
    else:
        masked, strings = re.subn(rb'"[^"\\]*(?:\\.[^"\\]*)*"', b'""', raw)
    if _canonical:
        if any(char in masked for char in (b" ", b"\t", b"\r", b"\n")):
            raise ValueError("compressed snapshot is not canonical JSON")
        # The standard ensure_ascii=False encoder escapes only quotes,
        # backslashes and these control characters. Removing exact escape
        # pairs also distinguishes a literal backslash followed by 'u'.
        if b"\\" in raw and b"\\" in re.sub(
            rb'\\(?:["\\bfnrt]|u00(?:0[0-7bef]|1[0-9a-f]))', b"", raw
        ):
            raise ValueError("compressed snapshot is not canonical JSON")
    work = strings + sum(masked.count(bytes([c])) for c in (91, 123, 44, 58))
    if work > MAX_BLOCKS:
        raise ValueError("compressed snapshot leaf exceeds JSON work bound")
    if _canonical and b"-0" in masked and re.search(rb'(?:^|[:,\[])-0(?=[,}\]]|$)', masked):
        raise ValueError("compressed snapshot is not canonical JSON")
    depth = 0
    # The byte filter retains exactly the old bracket matches, in order.
    for token in masked.translate(None, _JSON_NON_BRACKETS):
        if token in (91, 123):
            depth += 1
            if depth > MAX_DEPTH:
                raise ValueError("compressed snapshot leaf exceeds JSON depth bound")
        else:
            depth -= 1
    # After successful JSON syntax parsing, every outside-string colon is one
    # object member. A discarded duplicate lowers the decoded member total.
    return masked.count(b":") if _canonical else None


def _canonical_json(raw):
    """Validate the existing canonical grammar during the bounded JSON parse.

    Every accepted string token is already the standard encoder's UTF-8 form.
    The bounded lexical member count and standard decoder dictionaries jointly
    check uniqueness; key ordering and number spelling remain checked. Only
    immutable key shapes are reused inside this one parse. No decoded value or
    validation result survives it; physical and logical hashes remain fresh.
    """
    expected_members = _compressed_json_bounds(raw, _canonical=True)
    decoded_members = 0
    ordered_shapes = set()

    def ordered(value):
        nonlocal decoded_members
        decoded_members += len(value)
        keys = tuple(value)
        # This set belongs to one bounded parse. Its total key positions cannot
        # exceed the lexer's MAX_BLOCKS work budget; values are never retained.
        if keys not in ordered_shapes:
            if keys != tuple(sorted(keys)):
                raise ValueError("compressed snapshot is not canonical JSON")
            ordered_shapes.add(keys)
        return value

    def real(token):
        value = float(token)
        if repr(value) != token:
            raise ValueError("compressed snapshot is not canonical JSON")
        return value

    # The standard decoder constructs every dictionary once, before calling
    # object_hook. Counting all decoded members catches duplicates even in a
    # discarded value: each duplicate key loses one member, never gains one.
    # Integer spelling -0 was refused by the same bounded lexical pass above.
    # Explicit UTF-8 and existing number/escape guards retain canonical grammar.
    value = json.loads(
        raw.decode("utf-8"), object_hook=ordered, parse_float=real,
        parse_constant=lambda _: (_ for _ in ()).throw(ValueError("nonfinite JSON")),
    )
    if decoded_members != expected_members:
        raise ValueError("compressed snapshot is not canonical JSON")
    return value


def _leaf(kind, body, limit=LEAF_BYTES, *, _charge=None, _raw=None):
    if kind == "zleaf":
        if not isinstance(body, str):
            raise ValueError("invalid compressed snapshot leaf")
        try:
            packed = base64.b64decode(body, validate=True)
            stream = zlib.decompressobj()
            raw = stream.decompress(packed, min(LEAF_BYTES, limit) + 1)
        except (ValueError, zlib.error) as exc:
            raise ValueError("invalid compressed snapshot leaf") from exc
        if (len(raw) > min(LEAF_BYTES, limit) or not stream.eof
                or stream.unconsumed_tail or stream.unused_data):
            raise ValueError("compressed snapshot leaf exceeds bound or has trailing data")
        body = _canonical_json(raw)
        size = len(raw)
    else:
        raw = canonical(body)
        size = len(raw)
    if size > min(LEAF_BYTES, limit):
        raise ValueError("snapshot leaf exceeds byte bound")
    if _charge is not None:
        _charge.append(size)
    if _raw is not None:
        _raw.append(raw)
    return body


def _block_node(raw, *, limit):
    """Bound physical-block expansion and parser work before allocating JSON."""
    if raw.startswith(BLOCK_PREFIX):
        try:
            stream = zlib.decompressobj()
            data = stream.decompress(raw[len(BLOCK_PREFIX):], min(MAX_BLOCK_BYTES, limit) + 1)
        except zlib.error as exc:
            raise ValueError("invalid compressed snapshot block") from exc
        if (len(data) > min(MAX_BLOCK_BYTES, limit) or not stream.eof
                or stream.unconsumed_tail or stream.unused_data):
            raise ValueError("snapshot block expansion exceeds bound or has trailing data")
    else:
        data = raw
    if len(data) > limit:
        raise ValueError("snapshot block parsing work exceeds byte bound")
    if raw.startswith(BLOCK_PREFIX):
        if not data.endswith(b"\n"):
            raise ValueError("compressed snapshot block is not canonical JSON")
        node = _canonical_json(data[:-1])
    else:
        node = json.loads(data, parse_constant=lambda _: (_ for _ in ()).throw(
            ValueError("nonfinite JSON")))
    return node, len(data)


def _indexed_leaf(raw, ranges):
    """Pure field references owned and charged by their existing cache entry."""
    if ranges is None:
        return "leaf", raw, ranges
    fields = tuple((key, raw, None, start, end) for key, start, end in ranges)
    return "leaf", raw, ranges, fields


def _summarized_leaf(raw, ranges):
    """Derive pure byte/width metadata from already authenticated leaf framing.

    Two-member maps need at most two width comparisons, so retain their smaller
    index representation. Larger maps amortize an immutable summary over uses.
    This changes representation only; all retention admission limits still apply.
    """
    stream = _indexed_leaf(raw, ranges)
    if ranges is None or len(ranges) <= 2:
        return stream
    summary = (len(raw), len(ranges), max(end - start + 1 for _, start, end in ranges))
    return (*stream, summary)


class _MemberParts(tuple):
    """Owned immutable member bytes; the existing entry charges every object."""
    __slots__ = ()


def _member_span_leaf(raw, ranges):
    """Prepare repeated member joins without retaining physical authority.

    Keep small leaves' direct backing references. For summarized maps, each
    canonical member is copied once into owned immutable bytes. The entry still
    owns its complete raw leaf; the copied payload, object headers, new offsets
    and all tuple slots are additional residency, admitted by the same owner.
    """
    if ranges is None or len(ranges) <= 2:
        return _summarized_leaf(raw, ranges)
    fields = _MemberParts((key, raw[start:end], None, 0, end - start)
                          for key, start, end in ranges)
    summary = (len(raw), len(ranges), max(end - start + 1 for _, start, end in ranges))
    return "leaf", raw, ranges, fields, summary


def _leaf_summary(stream):
    if len(stream) == 5:
        return stream[4]
    raw, ranges = stream[1:3]
    return (len(raw), len(ranges),
            max((end - start + 1 for _, start, end in ranges), default=1))


def _index_cost(stream):
    # Key/range objects already belong to the existing entry. Charge every new
    # tuple/reference slot and summary integer conservatively, including interned
    # integers; owned member buffers and their offsets are charged below.
    cost = sys.getsizeof(stream)
    if len(stream) >= 4:
        cost += sys.getsizeof(stream[3]) + sum(map(sys.getsizeof, stream[3]))
    if len(stream) == 5:
        cost += sys.getsizeof(stream[4]) + sum(map(sys.getsizeof, stream[4]))
    if len(stream) >= 4 and type(stream[3]) is _MemberParts:
        # Distinct bytes own their payload/header, even when contents repeat.
        # New offset integers are charged conservatively, including interned 0.
        cost += sum(sys.getsizeof(raw) + sys.getsizeof(start) + sys.getsizeof(end)
                    for _, raw, _, start, end in stream[3])
    return cost


def _entry_index_cost(stream):
    # Both retained leaf and plan tuples gained exactly one reference slot.
    return _index_cost(stream) + sys.getsizeof((None,)) - sys.getsizeof(())


def _stream_index(node):
    """Transfer immutable member references, without copying canonical bytes."""
    kind, data, extra = node[:3]
    if kind == "leaf":
        if len(node) >= 4:
            return node[3]
        if extra is None:
            raise ValueError("snapshot map has no canonical member framing")
        return [(key, data, None, start, end) for key, start, end in extra]
    if kind == "cached":
        if extra is None:
            raise ValueError("cached snapshot map has no member framing")
        return [(key, raw, None, 0, len(raw)) for key, raw in extra]
    if kind == "members":
        return data
    if kind == "map-spans":
        return [field for child in data for field in _stream_index(child)]
    if kind == "map-chunks":
        return extra
    raise ValueError("snapshot map has invalid canonical type")


def _stream_member(key, encoded, child):
    yield encoded
    yield b":"
    yield from _stream_value(child)


def _stream_members(node):
    """Sorted immutable member views for top-level event digest selection."""
    for key, raw, child, start, end in _stream_index(node):
        if child is None:
            yield key, (memoryview(raw)[start:end],)
        else:
            yield key, _stream_member(key, raw, child)


def _stream_interior(parts):
    # Retain at most one chunk to remove the two proven container delimiters.
    first = True
    previous = None
    for part in parts:
        if not part:
            continue
        if first:
            part = memoryview(part)[1:]
            first = False
        if previous is not None:
            yield previous
        previous = part
    if previous is None:
        raise ValueError("empty canonical container stream")
    yield memoryview(previous)[:-1]


def _stream_tokens(node):
    """One nonrecursive frame; child tuples are consumed by the outer walk."""
    kind, data, extra = node[:3]
    interior = kind == "interior"
    if interior:
        kind, data, extra = data[:3]
    if kind in {"leaf", "cached"}:
        yield memoryview(data)[1:-1] if interior else data
    elif kind == "map-chunks":
        for index, part in enumerate(data):
            start = 1 if interior and index == 0 else 0
            end = len(part) - (1 if interior and index == len(data) - 1 else 0)
            yield memoryview(part)[start:end]
    elif kind == "members":
        if not interior:
            yield b"{"
        # Coalesce here, before member tokens traverse the outer generator
        # layers. Retain only one leaf-sized byte batch, never a whole state.
        pending, size = [], 0
        index = 0
        while index < len(data):
            if index:
                if size == LEAF_BYTES:
                    yield pending[0] if len(pending) == 1 else b"".join(pending)
                    pending, size = [], 0
                pending.append(b",")
                size += 1
            _, raw, child, start, end = data[index]
            index += 1
            if child is None:
                # Equality of bytes is insufficient: only adjacent offsets in
                # the same authenticated backing buffer may share one span.
                while index < len(data):
                    _, next_raw, next_child, next_start, next_end = data[index]
                    if next_child is not None or next_raw is not raw or next_start != end + 1:
                        break
                    end = next_end
                    index += 1
                length = end - start
                if size + length > LEAF_BYTES:
                    if pending:
                        yield pending[0] if len(pending) == 1 else b"".join(pending)
                        pending, size = [], 0
                part = memoryview(raw)[start:end]
                if length >= LEAF_BYTES:
                    yield part
                else:
                    pending.append(part)
                    size += length
            else:
                if pending:
                    yield pending[0] if len(pending) == 1 else b"".join(pending)
                    pending, size = [], 0
                yield raw
                yield b":"
                yield child
        if pending:
            yield pending[0] if len(pending) == 1 else b"".join(pending)
        if not interior:
            yield b"}"
    elif kind in {"array", "list", "text", "map-spans"}:
        if not interior:
            yield b"{" if kind == "map-spans" else b'"' if kind == "text" else b"["
        first = True
        for child in data:
            if not first and kind != "text":
                yield b","
            first = False
            yield ("interior", child, None) if kind in {"list", "text", "map-spans"} else child
        if not interior:
            yield b"}" if kind == "map-spans" else b'"' if kind == "text" else b"]"
    else:
        raise ValueError("snapshot has invalid canonical stream type")


def _stream_value(node):
    # Stack depth is already bounded by physical traversal. Map routing layers
    # were flattened by that traversal, so they cause no generator re-entry.
    stack = [iter(_stream_tokens(node))]
    while stack:
        part = next(stack[-1], None)
        if part is None:
            stack.pop()
        elif isinstance(part, tuple):
            stack.append(iter(_stream_tokens(part)))
        else:
            yield part


def _join_canonical(parts, size):
    if size > MAX_LOGICAL_BYTES:
        raise ValueError("snapshot logical content exceeds its byte bound")
    return b"".join(parts)


def _pack_stream(node):
    """Compile one bounded canonical buffer and member offsets in one walk."""
    if node[0] in {"leaf", "cached"}:
        raw = node[1]
        if node[0] == "leaf" or node[2] is None:
            return raw, node[2]
        position, ranges = 1, []
        for key, member in node[2]:
            ranges.append((key, position, position + len(member)))
            position += len(member) + 1
        return raw, tuple(ranges)
    if node[0] == "map-spans":
        return _pack_map(node[1])
    if node[0] == "map-chunks":
        return _pack_stream(("members", node[2], None))
    if node[0] != "members":
        kind, children, _ = node[:3]
        if all(child[0] == "leaf" for child in children):
            if kind in {"list", "text"}:
                chunks = [memoryview(child[1])[1:-1] for child in children]
            else:
                chunks = [child[1] for child in children]
            separator = b"" if kind == "text" else b","
            size = 2 + sum(map(len, chunks)) + max(0, len(chunks) - 1) * len(separator)
            if size > MAX_LOGICAL_BYTES:
                raise ValueError("snapshot logical content exceeds its byte bound")
            middle = separator.join(chunks)
            return ((b'"' + middle + b'"') if kind == "text" else
                    b"[" + middle + b"]"), None
        parts = list(_stream_value(node))
        return _join_canonical(parts, sum(map(len, parts))), None
    parts = [b"{"]
    size, ranges = 1, []
    for key, raw, child, start, end in node[1]:
        if ranges:
            parts.append(b",")
            size += 1
        begin = size
        if child is None:
            parts.append(memoryview(raw)[start:end])
            size += end - start
        else:
            parts.extend((raw, b":"))
            size += len(raw) + 1
            if child[0] == "leaf":
                parts.append(child[1])
                size += len(child[1])
            else:
                for part in _stream_value(child):
                    parts.append(part)
                    size += len(part)
        ranges.append((key, begin, size))
    parts.append(b"}")
    return _join_canonical(parts, size + 1), tuple(ranges)


def _map_stream(children, *, _budget=None):
    """Borrow whole ordered map interiors; retain no cross-read authority.

    Disjoint sorted child key ranges already prove canonical ordering. Keep
    references to their authenticated buffers instead of expanding every member
    into a Python token recipe only to coalesce it again at the digest sink.
    Interleaved or structured children keep the complete member-order path.
    """
    if all(child[0] == "leaf" and child[2] is not None for child in children):
        ordered = sorted((child for child in children if child[2]),
                         key=lambda child: child[2][0][0])
        if all(left[2][-1][0] < right[2][0][0]
               for left, right in zip(ordered, ordered[1:])):
            return "map-spans", tuple(ordered), None
    fields = tuple(sorted(chain.from_iterable(map(_stream_index, children)),
                          key=itemgetter(0)))
    owned_parts = all(len(child) >= 4 and type(child[3]) is _MemberParts
                      for child in children)
    if _budget is not None and all(child[0] == "leaf" for child in children):
        # One-use canonical payload, never a resident plan. Reserve the complete
        # map before allocating its first leaf-sized chunk. The monotonic ledger
        # is shared by every map in this descriptor, including live ancestors.
        # Child lengths already include their braces and internal commas.
        # Ordering interleaved disjoint keys cannot change member byte lengths.
        # Fold summaries over children, not every field in each retained leaf.
        interior_bytes, nonempty, width = 0, 0, 1
        for child in children:
            child_bytes, member_count, child_width = _leaf_summary(child)
            if member_count:
                interior_bytes += child_bytes - 2
                nonempty += 1
                width = max(width, child_width)
        size = 2 + interior_bytes + max(0, nonempty - 1)
        if size <= _budget[0] - _budget[1] and width <= LEAF_BYTES:
            _budget[1] += size
            # Largest member width determines a conservative batch cardinality.
            # Each group adds one leading delimiter and at most count-1 commas;
            # the final brace is its own one-byte chunk. No join exceeds LEAF.
            count = max(1, LEAF_BYTES // width)
            chunks = []
            for offset in range(0, len(fields), count):
                group = fields[offset:offset + count]
                parts = (map(itemgetter(1), group) if owned_parts else
                         (memoryview(raw)[start:end] for _, raw, _, start, end in group))
                middle = b",".join(parts)
                chunks.append((b"{" if offset == 0 else b",") + middle)
            if not fields:
                chunks.append(b"{")
            chunks.append(b"}")
            return "map-chunks", tuple(chunks), fields
    return "members", fields, None


def _pack_map(children):
    """Join disjoint ordered map spans directly, with an interleaving fallback."""
    nonempty = [child for child in children if child[2]]
    if not nonempty:
        return b"{}", ()
    nonempty.sort(key=lambda child: child[2][0][0])
    if all(left[2][-1][0] < right[2][0][0]
           for left, right in zip(nonempty, nonempty[1:])):
        parts, ranges, size = [b"{"], [], 1
        for child in nonempty:
            if ranges:
                parts.append(b",")
                size += 1
            raw, child_ranges = child[1:3]
            offset = size - 1
            ranges.extend((key, start + offset, end + offset)
                          for key, start, end in child_ranges)
            parts.append(memoryview(raw)[1:-1])
            size += len(raw) - 2
        parts.append(b"}")
        return _join_canonical(parts, size + 1), tuple(ranges)
    fields = []
    for child in children:
        fields.extend(_stream_index(child))
    fields.sort(key=itemgetter(0))
    return _pack_stream(("members", fields, None))


def _plan_preflight(memo, references, parsed, expanded):
    """Check optional bounded residency before compiling canonical buffers."""
    if references < 4 or max(parsed, expanded) > LEAF_BYTES * 8:
        return False
    with memo["budget"]["lock"]:
        compiler = _COMPILATION.get()
        compiled_bytes = compiler["bytes"] if compiler is not None else 0
        compiled_count = len(compiler["entries"]) if compiler is not None else 0
        removable = memo["plans"].retained_bytes
        remaining_count = memo["budget"]["count"] - len(memo["plans"]) + compiled_count
        remaining_bytes = memo["budget"]["bytes"] - removable + compiled_bytes
        # This is only a conservative early decline, never a grant. The exact
        # payload/buffer/offset/dependency cost is checked again on admission.
        return (not memo["closed"] and remaining_count < MAX_BLOCKS
                and remaining_bytes + expanded < MAX_LOGICAL_BYTES
                and expanded <= MAX_LOGICAL_BYTES // 4)


def _stream_batches(parts):
    """Coalesce small authenticated chunks with one leaf-sized transient buffer."""
    pending, size = [], 0
    for part in parts:
        if not part:
            continue
        if len(part) >= LEAF_BYTES:
            if pending:
                yield b"".join(pending)
                pending, size = [], 0
            yield part
            continue
        if size + len(part) > LEAF_BYTES:
            yield b"".join(pending)
            pending, size = [], 0
        pending.append(part)
        size += len(part)
    if pending:
        yield b"".join(pending)


def _authenticate_stream(value, stream, descriptor):
    """Hash canonical spans with one indexed walk and one bounded byte batch."""
    digest = hashlib.sha256()
    total = 0
    event = (isinstance(value, dict) and "state" in value and "digest" in value
             and "schema_version" in value)
    body = hashlib.sha256() if event else None
    pending, size = [], 0
    included = True

    def consume(chunk, include_body=True):
        nonlocal total
        total += len(chunk)
        if total > descriptor["logical_bytes"] or total > MAX_LOGICAL_BYTES:
            raise ValueError("snapshot logical content exceeds its byte bound")
        digest.update(chunk)
        if include_body and body is not None:
            body.update(chunk)

    def flush():
        nonlocal pending, size
        if pending:
            consume(b"".join(pending), included)
            pending, size = [], 0

    def emit(part):
        nonlocal size
        length = len(part)
        if not length:
            return
        if length >= LEAF_BYTES:
            flush()
            consume(part, included)
        else:
            if size + length > LEAF_BYTES:
                flush()
            pending.append(part)
            size += length

    def walk(node):
        # Frames index children in their admitted graph rather than eagerly
        # pushing every child. Interior wrappers occupy the same frame, so
        # stack depth cannot exceed the physical traversal's existing bound.
        stack = [[node, -1, False]]
        while stack:
            frame = stack[-1]
            kind, data, _ = frame[0][:3]
            if kind == "interior":
                frame[0], frame[2] = data, True
                continue
            interior = frame[2]
            if kind in {"leaf", "cached"}:
                emit(memoryview(data)[1:-1] if interior else data)
                stack.pop()
                continue
            if kind == "map-chunks":
                index = max(0, frame[1])
                if index == len(data):
                    stack.pop()
                    continue
                part = data[index]
                start = 1 if interior and index == 0 else 0
                end = len(part) - (1 if interior and index == len(data) - 1 else 0)
                emit(memoryview(part)[start:end])
                frame[1] = index + 1
                continue
            if kind not in {"members", "array", "list", "text", "map-spans"}:
                raise ValueError("snapshot has invalid canonical stream type")
            if frame[1] < 0:
                if not interior:
                    emit(b"{" if kind in {"members", "map-spans"} else b'"' if kind == "text" else b"[")
                frame[1] = 0
            index = frame[1]
            if index == len(data):
                if not interior:
                    emit(b"}" if kind in {"members", "map-spans"} else b'"' if kind == "text" else b"]")
                stack.pop()
                continue
            if kind == "members":
                # Batch member fragments before sink dispatch: interleaved maps
                # must not call emit separately for every field and separator.
                # Payload and fragment references are bounded by LEAF_BYTES;
                # a large existing span takes the uncopied direct path below.
                parts, batch_bytes, next_index = [], 0, index
                while next_index < len(data):
                    _, raw, child, start, end = data[next_index]
                    after = next_index + 1
                    if child is None:
                        while after < len(data):
                            _, next_raw, next_child, next_start, next_end = data[after]
                            if next_child is not None or next_raw is not raw or next_start != end + 1:
                                break
                            end = next_end
                            after += 1
                        width = end - start
                    elif child[0] in {"leaf", "cached"}:
                        width = len(raw) + 1 + len(child[1])
                    else:
                        break
                    needed = width + (1 if next_index else 0)
                    if batch_bytes + needed > LEAF_BYTES:
                        break
                    if next_index:
                        parts.append(b",")
                    if child is None:
                        parts.append(memoryview(raw)[start:end])
                    else:
                        parts.extend((raw, b":", child[1]))
                    batch_bytes += needed
                    next_index = after
                if parts:
                    frame[1] = next_index
                    emit(b"".join(parts))
                    continue
            if index and kind != "text":
                emit(b",")
            if kind == "members":
                _, raw, child, start, end = data[index]
                index += 1
                if child is None:
                    # Coalesce only neighboring ranges in the very same
                    # authenticated backing buffer; equal bytes are not enough.
                    while index < len(data):
                        _, next_raw, next_child, next_start, next_end = data[index]
                        if next_child is not None or next_raw is not raw or next_start != end + 1:
                            break
                        end = next_end
                        index += 1
                    frame[1] = index
                    emit(memoryview(raw)[start:end])
                else:
                    frame[1] = index
                    emit(raw)
                    emit(b":")
                    stack.append([child, -1, False])
            else:
                frame[1] = index + 1
                stack.append([data[index], -1, kind in {"list", "text", "map-spans"}])

    if event:
        consume(b"{")
        first = first_body = True
        for key, raw, child, start, end in _stream_index(stream):
            if not first:
                consume(b",", False)
            first = False
            included = key != "digest"
            if included and not first_body:
                body.update(b",")
            if included:
                first_body = False
            if child is None:
                emit(memoryview(raw)[start:end])
            else:
                emit(raw)
                emit(b":")
                walk(child)
            # Inclusion changes only between top-level members. Never carry
            # pending bytes across that boundary or the two digest comma rules.
            flush()
        consume(b"}")
    else:
        walk(stream)
        flush()
    consume(b"\n", False)
    if total != descriptor["logical_bytes"] or digest.hexdigest() != descriptor["sha256"]:
        raise ValueError("snapshot logical content digest or size mismatch")
    return body.hexdigest() if body is not None else None


def decode(path, descriptor, *, _physical=None, _identities=None):
    return _decode(path, descriptor, _physical=_physical, _identities=_identities)


def _decode(path, descriptor, *, _physical=None, _identities=None, _selection=None):
    if not isinstance(descriptor, dict) or MARKER not in descriptor:
        return descriptor
    if (
        set(descriptor) != FIELDS
        or type(descriptor[MARKER]) is not int
        or descriptor[MARKER] not in {1, 2}
        or type(descriptor["logical_bytes"]) is not int
        or not 0 < descriptor["logical_bytes"] <= MAX_LOGICAL_BYTES
        or any(
            not isinstance(descriptor[k], str) or not DIGEST.fullmatch(descriptor[k])
            for k in ("root", "sha256")
        )
    ):
        raise ValueError("invalid snapshot descriptor")
    home = home_for(path)
    directory = home / "state-blocks/v1"
    block_fd = _safe_directory(directory)
    cache = {}
    active = set()
    expanded = 0
    expanded_bytes = 0
    parsed_bytes = 0
    legacy = descriptor[MARKER] == 1
    memo = _normalization_memo() if legacy else None
    physical_trace, depth_trace = [], []
    compaction_budget = [min(descriptor["logical_bytes"], MAX_LOGICAL_BYTES), 0]

    def visit(digest, depth=0, need_members=False, selection=None):
        nonlocal expanded, expanded_bytes, parsed_bytes
        before_refs, before_parsed, before_expanded = expanded, parsed_bytes, expanded_bytes
        trace_start, depth_start = len(physical_trace), len(depth_trace)
        depth_trace.append(depth)
        expanded += 1
        if depth > MAX_DEPTH or expanded > MAX_BLOCKS:
            raise ValueError("snapshot expansion exceeds depth or reference bound")
        retained = None
        physical_raw = None
        if isinstance(digest, str):
            if not DIGEST.fullmatch(digest) or digest in active:
                raise ValueError("invalid or cyclic snapshot block reference")
            active.add(digest)
            physical_trace.append(digest)
            if digest not in cache:
                identity = []
                raw = _read_block(block_fd, digest + ".json", MAX_BLOCK_BYTES, memo, identity)
                if _identities is not None:
                    _identities[directory / (digest + ".json")] = identity[0]
                if _hash(raw) != digest:
                    raise ValueError("snapshot block digest mismatch")
                cache[digest] = raw
            # Exact current bytes are authenticated above even when pure leaf
            # normalization can be reused. No physical proof is memoized.
            physical_raw = cache[digest]
            plan = None
            if memo is not None:
                with memo["budget"]["lock"]:
                    key = (digest, "canonical-skip") if selection == "skip" else (digest, need_members)
                    if selection not in {None, "skip"}:
                        key = (digest, "projection-uncached")
                    plan = memo["plans"].pop(key, None)
                    if plan is not None:
                        memo["plans"][key] = plan
            if plan is not None:
                payload, logical, member_items, dependencies, refs, parsed, content, height, indexed, _ = plan
                if (depth + height > MAX_DEPTH or expanded + refs - 1 > MAX_BLOCKS
                        or parsed_bytes + parsed > MAX_LOGICAL_BYTES
                        or expanded_bytes + content > MAX_LOGICAL_BYTES):
                    raise ValueError("snapshot expansion exceeds cached subtree bounds")
                if any(item != digest and item in active for item in dependencies):
                    raise ValueError("invalid or cyclic snapshot block reference")
                # The plan authenticates no file. Every dependency is freshly
                # read/hashed once in this descriptor, exactly as the raw cache
                # did on the ordinary recursive path.
                for item in dependencies:
                    if item not in cache:
                        identity = []
                        raw = _read_block(block_fd, item + ".json", MAX_BLOCK_BYTES, memo, identity)
                        if _identities is not None:
                            _identities[directory / (item + ".json")] = identity[0]
                        if _hash(raw) != item:
                            raise ValueError("snapshot block digest mismatch")
                        cache[item] = raw
                expanded += refs - 1
                parsed_bytes += parsed
                expanded_bytes += content
                physical_trace.extend(dependencies[1:])
                depth_trace.append(depth + height)
                if selection == "skip":
                    shape, keys, length = marshal.loads(payload)
                    result = _Selection(None, shape, keys, length)
                else:
                    result = marshal.loads(payload)
                members = None
                active.remove(digest)
                stream = indexed
                return result, logical, members, stream
            retained = memo["entries"].get(digest) if memo is not None else None
            if retained is not None:
                payload, leaf_raw, member_ranges, charge, _cost, shape, indexed = retained
                if charge > MAX_LOGICAL_BYTES - parsed_bytes:
                    raise ValueError("snapshot block parsing work exceeds byte bound")
                node = ["leaf", shape if selection == "skip" else marshal.loads(payload)]
            else:
                node, charge = _block_node(physical_raw, limit=MAX_LOGICAL_BYTES - parsed_bytes)
            parsed_bytes += charge
        else:
            node = digest
        if not isinstance(node, list) or len(node) != 2 or not isinstance(node[0], str):
            raise ValueError("invalid snapshot block shape")
        kind, body = node
        if kind in {"leaf", "zleaf"}:
            admitted_index = None
            charge = []
            raw_leaf = [] if legacy else None
            if retained is not None:
                leaf_bytes = len(leaf_raw)
                if leaf_bytes > LEAF_BYTES:
                    raise ValueError("snapshot leaf exceeds byte bound")
            else:
                body = _leaf(kind, body, _charge=charge, _raw=raw_leaf)
                leaf_bytes = charge[0]
                leaf_raw = raw_leaf[0] if legacy else None
                member_ranges = None
                if legacy and type(body) is dict:
                    member_ranges = _canonical_members(body, leaf_raw)
                # Only plain physical leaves parsed by the standard JSON owner
                # enter this private cache. Marshal bytes are never external.
                if (memo is not None and kind == "leaf" and physical_raw is not None
                        and not physical_raw.startswith(BLOCK_PREFIX)):
                    payload = marshal.dumps(body, 4)
                    shape = _select_value(body, "skip")
                    indexed = _member_span_leaf(leaf_raw, member_ranges)
                    cost = len(payload) + len(leaf_raw) + len(marshal.dumps(member_ranges, 4)) + len(digest) + len(marshal.dumps((shape.kind, shape.keys, shape.length), 4)) + _entry_index_cost(indexed)
                    with memo["budget"]["lock"]:
                        compiler = _COMPILATION.get()
                        compiled_bytes = compiler["bytes"] if compiler is not None else 0
                        compiled_count = len(compiler["entries"]) if compiler is not None else 0
                        if (not memo["closed"] and digest not in memo["entries"]
                                and memo["budget"]["bytes"] + compiled_bytes + cost <= MAX_LOGICAL_BYTES
                                and memo["budget"]["count"] + compiled_count < MAX_BLOCKS):
                            memo["entries"][digest] = (payload, leaf_raw, member_ranges, len(physical_raw), cost, shape, indexed)
                            admitted_index = indexed
                            memo["bytes"] += cost
                            memo["budget"]["bytes"] += cost
                            memo["budget"]["count"] += 1
            if leaf_bytes > LEAF_BYTES:
                raise ValueError("snapshot leaf exceeds byte bound")
            expanded_bytes += leaf_bytes
            if expanded_bytes > MAX_LOGICAL_BYTES:
                raise ValueError("snapshot expanded content exceeds its byte bound")
            result = body if isinstance(body, _Selection) else _select_value(body, selection)
            # Reuse the pure representation on the admitting read too. Its full
            # metadata cost was charged above; physical and logical checks still
            # precede every use. Refused admissions keep the uncached framing.
            stream = (indexed if retained is not None else admitted_index
                      if admitted_index is not None else ("leaf", leaf_raw, member_ranges)) if legacy else None
            raw_value, members = leaf_raw, None
        elif kind == "object" and isinstance(body, list):
            result, members = {}, {}
            complete_keys = set()
            stream_children = []
            for pair in body:
                if (not isinstance(pair, list) or len(pair) != 2
                        or not isinstance(pair[0], str) or pair[0] in complete_keys):
                    raise ValueError("snapshot object has invalid or duplicate keys")
                complete_keys.add(pair[0])
                key_raw = canonical(pair[0])
                expanded_bytes += len(key_raw)
                if expanded_bytes > MAX_LOGICAL_BYTES:
                    raise ValueError("snapshot expanded keys exceed their byte bound")
                child_selection = _selection_key(selection, pair[0])
                child, child_raw, _, child_stream = visit(pair[1], depth + 1, selection=child_selection)
                if child_selection != "skip":
                    result[pair[0]] = child.value if isinstance(child, _Selection) else child
                if legacy:
                    stream_children.append((pair[0], key_raw, child_stream, 0, 0))
            if selection is not None:
                result = _Selection(None if selection == "skip" else result, "dict", tuple(complete_keys), len(complete_keys))
            raw_value = None
            stream = ("members", tuple(sorted(stream_children, key=itemgetter(0))), None) if legacy else None
        elif kind in {"map", "list", "array", "text"} and isinstance(body, list):
            result = {} if kind == "map" else "" if kind == "text" else []
            complete_keys, logical_length = set(), 0
            members = None
            stream_children = []
            for ref in body:
                child_selection = selection if kind == "map" else ("skip" if selection == "skip" else None)
                child, child_raw, child_members, child_stream = visit(ref, depth + 1, kind == "map", child_selection)
                shape = child.kind if isinstance(child, _Selection) else "dict" if isinstance(child, dict) else "list" if isinstance(child, list) else "str" if isinstance(child, str) else "scalar"
                value = child.value if isinstance(child, _Selection) else child
                length = child.length if isinstance(child, _Selection) else len(child) if shape != "scalar" else 0
                if legacy and kind != "map" and (kind != "list" or length):
                    stream_children.append(child_stream)
                if kind == "map":
                    keys = child.keys if isinstance(child, _Selection) else child.keys() if shape == "dict" else ()
                    if shape != "dict" or complete_keys.intersection(keys):
                        raise ValueError("snapshot map overlaps or has invalid type")
                    complete_keys.update(keys)
                    if selection != "skip":
                        result.update(value)
                    if legacy:
                        stream_children.append(child_stream)
                elif kind == "array":
                    logical_length += 1
                    if selection != "skip":
                        result.append(value)
                elif kind == "list":
                    if shape != "list":
                        raise ValueError("invalid snapshot list segment")
                    logical_length += length
                    if selection != "skip":
                        result.extend(value)
                else:
                    if shape != "str":
                        raise ValueError("invalid snapshot text segment")
                    logical_length += length
                    if selection != "skip":
                        result += value
            if selection is not None:
                shape = "dict" if kind == "map" else "str" if kind == "text" else "list"
                result = _Selection(None if selection == "skip" else result, shape, tuple(complete_keys), len(complete_keys) if kind == "map" else logical_length)
            if legacy and kind == "map":
                if _selection is None:
                    raw_value, ranges = _pack_map(stream_children)
                    stream = ("leaf", raw_value, ranges)
                else:
                    stream = _map_stream(stream_children, _budget=compaction_budget)
                    raw_value = None
            else:
                stream = (kind, tuple(stream_children), None) if legacy else None
                raw_value = None
        else:
            raise ValueError("unknown snapshot node encoding")
        if legacy and _selection is None and kind not in {"leaf", "zleaf"} and stream[0] != "leaf":
            raw_value, ranges = _pack_stream(stream)
            stream = ("leaf", raw_value, ranges)
        if isinstance(digest, str):
            active.remove(digest)
            if (memo is not None and selection == "skip" and kind not in {"leaf", "zleaf"}
                    and _plan_preflight(memo, expanded - before_refs,
                                        parsed_bytes - before_parsed,
                                        expanded_bytes - before_expanded)):
                raw_value, ranges = _pack_stream(stream)
                stream = ("leaf", raw_value, ranges)
                _remember_canonical_plan(memo, (digest, "canonical-skip"), result,
                    raw_value, stream[2], tuple(dict.fromkeys(physical_trace[trace_start:])),
                    expanded - before_refs, parsed_bytes - before_parsed,
                    expanded_bytes - before_expanded, max(depth_trace[depth_start:]) - depth)
            if (memo is not None and selection is None and kind not in {"leaf", "zleaf"}
                    and _plan_preflight(memo, expanded - before_refs,
                                        parsed_bytes - before_parsed,
                                        expanded_bytes - before_expanded)):
                raw_value, ranges = _pack_stream(stream)
                raw_value = _remember_plan(
                    memo, (digest, need_members), result, raw_value,
                    None,
                    tuple(dict.fromkeys(physical_trace[trace_start:])),
                    expanded - before_refs, parsed_bytes - before_parsed,
                    expanded_bytes - before_expanded,
                    max(depth_trace[depth_start:]) - depth, _ranges=ranges,
                )
                # Use this freshly authenticated compilation immediately, even
                # when optional retention declined it. Rewalking the old token
                # graph would discard the work just performed above.
                stream = ("leaf", raw_value, ranges)
        return result, raw_value, members if need_members else None, stream

    directory_binding = directory_token = None
    try:
        directory_stat = os.fstat(block_fd)
        directory_binding = [block_fd, (directory_stat.st_dev, directory_stat.st_ino), True]
        directory_token = _DIRECTORY_IDENTITY.set(directory_binding)
        _lock_store(block_fd, exclusive=False)
        value, raw_value, _, stream = visit(descriptor["root"], selection=_selection)
        if isinstance(value, _Selection):
            value = value.value
        body_digest = None
        if legacy:
            body_digest = _authenticate_stream(value, stream, descriptor)
        else:
            raw = canonical(value) + b"\n"
            if len(raw) != descriptor["logical_bytes"] or _hash(raw) != descriptor["sha256"]:
                raise ValueError("snapshot logical content digest or size mismatch")
        if codec_for(value) != descriptor[MARKER] and isinstance(value, dict) and ("run_id" in value or "state" in value):
            raise ValueError("snapshot codec differs from authenticated state")
        _same_directory(directory, block_fd)
        if _physical is not None:
            _physical.update(block_paths(home, cache))
        if _selection is not None:
            if not isinstance(value, dict):
                raise ValueError("event must be an object")
            return VerifiedEventProjection(value, body_digest)
        if (
            isinstance(value, dict)
            and "state" in value
            and "digest" in value
            and "schema_version" in value
        ):
            if legacy:
                result = DecodedEvent.__new__(DecodedEvent)
                dict.__init__(result, value)
                result.verified_body_digest = body_digest
                return result
            return DecodedEvent(value, raw)
        return value
    finally:
        if directory_binding is not None:
            directory_binding[2] = False
        if directory_token is not None:
            _DIRECTORY_IDENTITY.reset(directory_token)
        os.close(block_fd)


def retained_snapshot_bytes(path, value, *, max_bytes):
    """Attribute only deterministic bytes selected by authenticated state.

    Historical states have no codec binding and retain the exact original
    compiler. New states bind codec2 before the existing event hash is computed.
    Equivalent foreign JSON, partitions, compression or descriptors confer no
    authorship, even when their expanded logical value happens to match.
    """
    home = home_for(path)
    expected, blocks = encode(value)
    if read_regular(path, max_bytes) != expected:
        raise ValueError("retained snapshot has a noncanonical or foreign representation")
    physical = {Path(path): expected}
    for target, raw in block_paths(home, blocks).items():
        if read_regular(target, MAX_BLOCK_BYTES) != raw:
            raise ValueError("retained snapshot block differs from deterministic encoding")
        physical[target] = raw
    return physical


class ComponentAbsent(ValueError):
    """A parsed, bounded lookup found no component; read costs remain charged."""

    def __init__(self, used):
        super().__init__("selected snapshot component is absent")
        self.charged_bytes = used


def component(path, keys, *, max_bytes):
    """Read an exact component, charging every authenticated block read.

    The caller must compare the returned component's digest against its current
    journal index. This bounded lookup does not attest the rest of a historical
    snapshot or replace full-chain validation by the run owner.
    """
    used = 0
    visits = 0
    expanded_bytes = 0
    parsed_bytes = 0
    cache = {}

    def read(file, limit):
        nonlocal used
        raw = read_regular(file, min(limit, max_bytes - used))
        used += len(raw)
        if used > max_bytes:
            raise ValueError("selected journal component exceeds its byte bound")
        return json.loads(
            raw,
            parse_constant=lambda _: (_ for _ in ()).throw(
                ValueError("nonfinite JSON")
            ),
        )

    value = read(path, 4 * 1024 * 1024)
    if not isinstance(value, dict) or MARKER not in value:
        for key in keys:
            if isinstance(value, dict) and key not in value:
                raise ComponentAbsent(used)
            value = value[key]
        return value, used
    if (
        set(value) != FIELDS
        or type(value[MARKER]) is not int
        or value[MARKER] not in {1, 2}
        or type(value["logical_bytes"]) is not int
        or not 0 < value["logical_bytes"] <= MAX_LOGICAL_BYTES
        or any(
            not isinstance(value[k], str) or not DIGEST.fullmatch(value[k])
            for k in ("root", "sha256")
        )
    ):
        raise ValueError("invalid selected snapshot descriptor")
    home = home_for(path)
    directory = home / "state-blocks/v1"
    block_fd = _safe_directory(directory)
    missing = object()
    active = set()

    def node(digest, remaining, depth=0):
        nonlocal visits, used, expanded_bytes, parsed_bytes
        visits += 1
        if depth > MAX_DEPTH or visits > MAX_BLOCKS:
            raise ValueError("invalid or excessive selected snapshot reference")
        if isinstance(digest, str):
            if not DIGEST.fullmatch(digest) or digest in active:
                raise ValueError("invalid or excessive selected snapshot reference")
            if digest not in cache:
                raw = _read_at(block_fd, digest + ".json", min(MAX_BLOCK_BYTES, max_bytes - used))
                used += len(raw)
                if used > max_bytes or _hash(raw) != digest:
                    raise ValueError("selected snapshot block exceeds bound or fails digest")
                cache[digest] = raw
            block, charge = _block_node(cache[digest], limit=max_bytes - parsed_bytes)
            parsed_bytes += charge
        else:
            block = digest
        if not isinstance(block, list) or len(block) != 2 or not isinstance(block[0], str):
            raise ValueError("invalid selected snapshot block")
        kind, body = block
        if isinstance(digest, str):
            active.add(digest)
        try:
            if kind in {"leaf", "zleaf"}:
                charge = []
                result = _leaf(kind, body, max_bytes - expanded_bytes, _charge=charge)
                expanded_bytes += charge[0]
                if expanded_bytes > max_bytes:
                    raise ValueError("selected component expansion exceeds its byte bound")
                for key in remaining:
                    if not isinstance(result, dict) or key not in result:
                        return missing
                    result = result[key]
                return result
            if remaining:
                key, rest = remaining[0], remaining[1:]
                if kind == "object":
                    if not isinstance(body, list) or any(
                        not isinstance(row, list)
                        or len(row) != 2
                        or not isinstance(row[0], str)
                        for row in body
                    ):
                        raise ValueError("invalid selected object keys")
                    if len({row[0] for row in body}) != len(body):
                        raise ValueError("duplicate selected object keys")
                    matches = [row[1] for row in body if row[0] == key]
                    return node(matches[0], rest, depth + 1) if matches else missing
                if kind == "map":
                    result = missing
                    if not isinstance(body, list):
                        raise ValueError("invalid selected map")
                    for child in body:
                        candidate = node(child, remaining, depth + 1)
                        if candidate is not missing:
                            if result is not missing:
                                raise ValueError("overlapping selected map keys")
                            result = candidate
                    return result
                raise ValueError("selected snapshot path crosses a non-object")
            if kind == "object":
                result = {}
                for row in body:
                    if (
                        not isinstance(row, list)
                        or len(row) != 2
                        or not isinstance(row[0], str)
                        or row[0] in result
                    ):
                        raise ValueError("invalid selected object")
                    expanded_bytes += len(canonical(row[0]))
                    if expanded_bytes > max_bytes:
                        raise ValueError(
                            "selected component keys exceed their byte bound"
                        )
                    result[row[0]] = node(row[1], (), depth + 1)
            elif kind in {"map", "list", "array", "text"} and isinstance(body, list):
                result = {} if kind == "map" else "" if kind == "text" else []
                for childref in body:
                    child = node(childref, (), depth + 1)
                    if kind == "map":
                        if not isinstance(child, dict) or set(result) & set(child):
                            raise ValueError("invalid selected map")
                        result.update(child)
                    elif kind == "list":
                        if not isinstance(child, list):
                            raise ValueError("invalid selected list")
                        result.extend(child)
                    elif kind == "array":
                        result.append(child)
                    else:
                        if not isinstance(child, str):
                            raise ValueError("invalid selected text")
                        result += child
            else:
                raise ValueError("unknown selected node encoding")
            if len(canonical(result)) > max_bytes:
                raise ValueError("selected component expansion exceeds its byte bound")
            return result
        finally:
            if isinstance(digest, str):
                active.remove(digest)

    try:
        _lock_store(block_fd, exclusive=False)
        result = node(value["root"], tuple(keys))
        _same_directory(directory, block_fd)
        if result is missing:
            raise ComponentAbsent(used)
        return result, used
    finally:
        os.close(block_fd)
