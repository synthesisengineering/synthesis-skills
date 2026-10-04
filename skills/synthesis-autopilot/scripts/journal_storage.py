"""Lossless bounded content-addressed snapshots for the existing run journal.

Events still commit last and retain their original logical digests. This is a
storage codec, never another state, ownership or mutation authority. Immutable
blocks are durable before an event references them. Interrupted unreferenced
blocks remain inert and count against the run's storage budget.
"""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar

import base64
import errno
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import time
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


def _read_at(parent, name, limit, *, _identity=None):
    if type(limit) is not int or limit < 0:
        raise ValueError("snapshot read byte budget exhausted")
    fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent)
    with os.fdopen(fd, "rb") as stream:
        before = os.fstat(stream.fileno())
        if not stat.S_ISREG(before.st_mode) or before.st_size > limit:
            raise ValueError("snapshot file is not a bounded regular file")
        raw = stream.read(before.st_size + 1)
        after = os.fstat(stream.fileno())
        present = os.stat(name, dir_fd=parent, follow_symlinks=False)

        def fingerprint(st):
            return (st.st_dev, st.st_ino, st.st_mode, st.st_nlink, st.st_size, st.st_mtime_ns, st.st_ctime_ns)

        if (
            len(raw) > limit
            or fingerprint(before) != fingerprint(after)
            or fingerprint(after) != fingerprint(present)
        ):
            raise ValueError("snapshot file changed during read")
        if _identity is not None:
            _identity.append(fingerprint(after))
        return raw


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
        if cost <= MAX_LOGICAL_BYTES:
            while (memo["bytes"] + cost > MAX_LOGICAL_BYTES
                   or len(memo["entries"]) >= MAX_BLOCKS):
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


def _compressed_json_bounds(raw):
    """Bound parser nesting/work before parsing a new compressed leaf.

    Existing MAX_DEPTH/MAX_BLOCKS also bound graph traversal separately. Plain
    historical leaves keep their original <=LEAF_BYTES representation semantics.
    JSON syntax and canonical identity are checked by the JSON parser afterward.
    """
    # Replace strings in the C regex engine, then count separators in C. Only
    # brackets need sequential depth work; scalar/key tokens do not need a
    # Python iteration each. The same conservative token bound is retained.
    masked, strings = re.subn(rb'"[^"\\]*(?:\\.[^"\\]*)*"', b'""', raw)
    work = strings + sum(masked.count(bytes([c])) for c in (91, 123, 44, 58))
    if work > MAX_BLOCKS:
        raise ValueError("compressed snapshot leaf exceeds JSON work bound")
    depth = 0
    for token in re.finditer(rb'[\[\]{}]', masked):
        if token.group()[0] in (91, 123):
            depth += 1
            if depth > MAX_DEPTH:
                raise ValueError("compressed snapshot leaf exceeds JSON depth bound")
        else:
            depth -= 1


def _leaf(kind, body, limit=LEAF_BYTES, *, _charge=None):
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
        _compressed_json_bounds(raw)
        body = json.loads(raw, parse_constant=lambda _: (_ for _ in ()).throw(
            ValueError("nonfinite JSON")))
        if canonical(body) != raw:
            raise ValueError("compressed snapshot leaf is not canonical JSON")
        size = len(raw)
    else:
        size = len(canonical(body))
    if size > min(LEAF_BYTES, limit):
        raise ValueError("snapshot leaf exceeds byte bound")
    if _charge is not None:
        _charge.append(size)
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
        _compressed_json_bounds(data)
    else:
        data = raw
    if len(data) > limit:
        raise ValueError("snapshot block parsing work exceeds byte bound")
    node = json.loads(data, parse_constant=lambda _: (_ for _ in ()).throw(
        ValueError("nonfinite JSON")))
    if raw.startswith(BLOCK_PREFIX) and canonical(node) + b"\n" != data:
        raise ValueError("compressed snapshot block is not canonical JSON")
    return node, len(data)


def decode(path, descriptor, *, _physical=None, _identities=None):
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

    def visit(digest, depth=0):
        nonlocal expanded, expanded_bytes, parsed_bytes
        expanded += 1
        if depth > MAX_DEPTH or expanded > MAX_BLOCKS:
            raise ValueError("snapshot expansion exceeds depth or reference bound")
        if isinstance(digest, str):
            if not DIGEST.fullmatch(digest) or digest in active:
                raise ValueError("invalid or cyclic snapshot block reference")
            active.add(digest)
            if digest not in cache:
                identity = []
                raw = _read_at(block_fd, digest + ".json", MAX_BLOCK_BYTES, _identity=identity)
                if _identities is not None:
                    _identities[directory / (digest + ".json")] = identity[0]
                if _hash(raw) != digest:
                    raise ValueError("snapshot block digest mismatch")
                cache[digest] = raw
            # Only authenticated bytes are cached, never decoded mutable nodes.
            node, charge = _block_node(cache[digest], limit=MAX_LOGICAL_BYTES - parsed_bytes)
            parsed_bytes += charge
        else:
            node = digest
        if not isinstance(node, list) or len(node) != 2 or not isinstance(node[0], str):
            raise ValueError("invalid snapshot block shape")
        kind, body = node
        if kind in {"leaf", "zleaf"}:
            charge = []
            body = _leaf(kind, body, _charge=charge)
            leaf_bytes = charge[0]
            if leaf_bytes > LEAF_BYTES:
                raise ValueError("snapshot leaf exceeds byte bound")
            expanded_bytes += leaf_bytes
            if expanded_bytes > MAX_LOGICAL_BYTES:
                raise ValueError("snapshot expanded content exceeds its byte bound")
            result = body
        elif kind == "object" and isinstance(body, list):
            result = {}
            for pair in body:
                if (
                    not isinstance(pair, list)
                    or len(pair) != 2
                    or not isinstance(pair[0], str)
                    or pair[0] in result
                ):
                    raise ValueError("snapshot object has invalid or duplicate keys")
                expanded_bytes += len(canonical(pair[0]))
                if expanded_bytes > MAX_LOGICAL_BYTES:
                    raise ValueError("snapshot expanded keys exceed their byte bound")
                result[pair[0]] = visit(pair[1], depth + 1)
        elif kind in {"map", "list", "array", "text"} and isinstance(body, list):
            result = {} if kind == "map" else "" if kind == "text" else []
            for ref in body:
                child = visit(ref, depth + 1)
                if kind == "map":
                    if not isinstance(child, dict) or set(result) & set(child):
                        raise ValueError("snapshot map overlaps or has invalid type")
                    result.update(child)
                elif kind == "array":
                    result.append(child)
                elif kind == "list":
                    if not isinstance(child, list):
                        raise ValueError("invalid snapshot list segment")
                    result.extend(child)
                else:
                    if not isinstance(child, str):
                        raise ValueError("invalid snapshot text segment")
                    result += child
        else:
            raise ValueError("unknown snapshot node encoding")
        if isinstance(digest, str):
            active.remove(digest)
        return result

    try:
        _lock_store(block_fd, exclusive=False)
        value = visit(descriptor["root"])
        raw = canonical(value) + b"\n"
        if (
            len(raw) != descriptor["logical_bytes"]
            or _hash(raw) != descriptor["sha256"]
        ):
            raise ValueError("snapshot logical content digest or size mismatch")
        if codec_for(value) != descriptor[MARKER] and isinstance(value, dict) and ("run_id" in value or "state" in value):
            raise ValueError("snapshot codec differs from authenticated state")
        _same_directory(directory, block_fd)
        if _physical is not None:
            _physical.update(block_paths(home, cache))
        if (
            isinstance(value, dict)
            and "state" in value
            and "digest" in value
            and "schema_version" in value
        ):
            return DecodedEvent(value, raw)
        return value
    finally:
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
