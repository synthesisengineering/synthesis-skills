"""Lossless bounded content-addressed snapshots for the existing run journal.

Events still commit last and retain their original logical digests. This is a
storage codec, never another state, ownership or mutation authority. Immutable
blocks are durable before an event references them. Interrupted unreferenced
blocks remain inert and count against the run's storage budget.
"""
from __future__ import annotations

from copy import deepcopy
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

INLINE_BYTES = 1024 * 1024
LEAF_BYTES = 64 * 1024
MAX_BLOCK_BYTES = 128 * 1024
MAX_LOGICAL_BYTES = 64 * 1024 * 1024
MAX_BLOCKS = 16384
MAX_DEPTH = 64
MAX_STORE_BYTES = 512 * 1024 * 1024
MAX_STORE_ENTRIES = 32768
STORE_READ_LOCK_SECONDS = 0.1
STORE_WRITE_LOCK_SECONDS = 5.0
MARKER = 'synthesis_run_storage'
FIELDS = {MARKER, 'root', 'sha256', 'logical_bytes'}
DIGEST = re.compile(r'[0-9a-f]{64}')


class DecodedEvent(dict):
    """Per-read digest of the verified logical event; never persistent caching."""
    def __init__(self, value, raw):
        super().__init__(value)
        # The canonical top-level position is derived from parsed keys, rather
        # than searching nested or caller-authored text for a digest string.
        preceding = [(key, value[key]) for key in sorted(value) if key < 'digest']
        offset = 1 + sum(len(canonical(key)) + 1 + len(canonical(item)) + 1 for key, item in preceding)
        field = canonical('digest') + b':' + canonical(value['digest'])
        if raw[offset:offset + len(field)] != field or raw[offset + len(field):offset + len(field) + 1] != b',':
            raise ValueError('snapshot event canonical digest position is invalid')
        digest = hashlib.sha256()
        digest.update(raw[:offset]); digest.update(raw[offset + len(field) + 1:-1])
        self.verified_body_digest = digest.hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False).encode()


def _hash(raw):
    return hashlib.sha256(raw).hexdigest()


def home_for(path):
    path = Path(path).absolute()
    if path.name == 'current.json':
        home = path.parent
    elif path.parent.name == 'events' and re.fullmatch(r'\d{12}\.json', path.name):
        home = path.parent.parent
    else:
        raise ValueError('snapshot descriptor is not at a run-owned snapshot path')
    if home.parent.name != 'autopilot-runs' or str(uuid.UUID(home.name)) != home.name:
        raise ValueError('snapshot descriptor has no canonical run directory')
    return home


def _safe_directory(path, *, create=False):
    """No-follow handles prevent ancestor/link replacement during operations."""
    path = Path(path).absolute()
    fd = os.open('/', os.O_RDONLY | os.O_DIRECTORY)
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
            child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
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
    raise ValueError('snapshot store is busy; bounded lock wait exhausted')


def _read_at(parent, name, limit):
    if type(limit) is not int or limit < 0:
        raise ValueError('snapshot read byte budget exhausted')
    fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent)
    with os.fdopen(fd, 'rb') as stream:
        before = os.fstat(stream.fileno())
        if not stat.S_ISREG(before.st_mode) or before.st_size > limit:
            raise ValueError('snapshot file is not a bounded regular file')
        raw = stream.read(before.st_size + 1)
        after = os.fstat(stream.fileno())
        present = os.stat(name, dir_fd=parent, follow_symlinks=False)
        fingerprint = lambda st: (st.st_dev, st.st_ino, st.st_size, st.st_mtime_ns, st.st_ctime_ns)
        if len(raw) > limit or fingerprint(before) != fingerprint(after) or fingerprint(after) != fingerprint(present):
            raise ValueError('snapshot file changed during read')
        return raw


def read_regular(path, limit):
    parent = _safe_directory(Path(path).parent)
    try:
        if Path(path).parent.name == 'v1' and Path(path).parent.parent.name == 'state-blocks':
            _lock_store(parent, exclusive=False)
        return _read_at(parent, Path(path).name, limit)
    finally:
        os.close(parent)


def _same_directory(path, fd):
    current = Path(path).lstat()
    opened = os.fstat(fd)
    if not stat.S_ISDIR(current.st_mode) or (current.st_dev, current.st_ino) != (opened.st_dev, opened.st_ino):
        raise ValueError('snapshot store changed during operation')


def encode(value):
    raw = canonical(value) + b'\n'
    if len(raw) > MAX_LOGICAL_BYTES:
        raise ValueError('run snapshot logical capacity reached; no event committed')
    if len(raw) <= INLINE_BYTES:
        return raw, {}
    blocks = {}; expansion_bytes = 0; references = 0
    def put(node):
        data = canonical(node) + b'\n'
        if len(data) > MAX_BLOCK_BYTES:
            raise ValueError('snapshot block exceeds its byte bound')
        digest = _hash(data)
        blocks.setdefault(digest, data)
        if len(blocks) > MAX_BLOCKS:
            raise ValueError('snapshot exceeds its block count bound')
        return digest
    def visit(item, depth=0):
        nonlocal expansion_bytes, references
        references += 1
        if references > MAX_BLOCKS:
            raise ValueError('snapshot exceeds its reference count bound')
        if depth > MAX_DEPTH:
            raise ValueError('snapshot exceeds its depth bound')
        size = len(canonical(item))
        if size <= LEAF_BYTES:
            expansion_bytes += size
            if expansion_bytes > MAX_LOGICAL_BYTES:
                raise ValueError('snapshot expanded fragments exceed their byte bound')
            return put(['leaf', item])
        if isinstance(item, dict):
            if len(item) <= 32:
                expansion_bytes += sum(len(canonical(key)) for key in item)
                if expansion_bytes > MAX_LOGICAL_BYTES:
                    raise ValueError('snapshot expanded keys exceed their byte bound')
                return put(['object', [[key, visit(child, depth + 1)] for key, child in sorted(item.items())]])
            groups = {}
            for key, child in item.items():
                slot = hashlib.sha256(key.encode()).hexdigest()[depth % 64]
                groups.setdefault(slot, {})[key] = child
            if len(groups) == 1:
                keys = sorted(item)
                groups = {0: {k: item[k] for k in keys[:len(keys)//2]},
                          1: {k: item[k] for k in keys[len(keys)//2:]}}
            return put(['map', [visit(groups[key], depth + 1) for key in sorted(groups)]])
        if isinstance(item, list):
            if len(item) == 1:
                return put(['array', [visit(item[0], depth + 1)]])
            middle = len(item) // 2
            return put(['list', [visit(item[:middle], depth + 1), visit(item[middle:], depth + 1)]])
        if isinstance(item, str):
            middle = len(item) // 2
            return put(['text', [visit(item[:middle], depth + 1), visit(item[middle:], depth + 1)]])
        raise ValueError('snapshot scalar exceeds its byte bound')
    root = visit(value)
    descriptor = {MARKER: 1, 'root': root, 'sha256': _hash(raw), 'logical_bytes': len(raw)}
    return canonical(descriptor) + b'\n', blocks


def block_paths(home, blocks):
    return {Path(home) / 'state-blocks/v1' / (digest + '.json'): raw for digest, raw in blocks.items()}


def materialize(home, blocks):
    if not blocks:
        return
    directory = Path(home) / 'state-blocks/v1'
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
                    raise ValueError('run snapshot store entry capacity reached')
                info = entry.stat(follow_symlinks=False)
                if not stat.S_ISREG(info.st_mode) or info.st_size > MAX_BLOCK_BYTES:
                    raise ValueError('snapshot store contains an unsafe entry')
                total += info.st_size
                names.add(entry.name)
        new = {d: raw for d, raw in blocks.items() if d + '.json' not in names}
        # During no-overwrite hardlink publication the staging and final names
        # coexist. Reserve that one additional entry and its largest payload so
        # even the transient namespace stays within the same store ceilings.
        staging_entries = 1 if new else 0
        staging_bytes = max(map(len, new.values()), default=0)
        if (count + len(new) + staging_entries > MAX_STORE_ENTRIES
                or total + sum(map(len, new.values())) + staging_bytes > MAX_STORE_BYTES):
            raise ValueError('run snapshot store byte or entry capacity reached')
        for digest, raw in blocks.items():
            if not DIGEST.fullmatch(digest) or _hash(raw) != digest or len(raw) > MAX_BLOCK_BYTES:
                raise ValueError('invalid snapshot block installation')
            name = digest + '.json'
            if name in names:
                if _read_at(fd, name, MAX_BLOCK_BYTES) != raw:
                    raise ValueError('existing immutable snapshot block changed')
                continue
            stage = '.stage-' + uuid.uuid4().hex
            created = None
            try:
                stagefd = os.open(stage, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=fd)
                with os.fdopen(stagefd, 'wb') as stream:
                    created = os.fstat(stream.fileno())
                    stream.write(raw); stream.flush(); os.fsync(stream.fileno())
                try:
                    os.link(stage, name, src_dir_fd=fd, dst_dir_fd=fd, follow_symlinks=False)
                except FileExistsError:
                    if _read_at(fd, name, MAX_BLOCK_BYTES) != raw:
                        raise ValueError('concurrent snapshot block differs')
                else:
                    published = os.stat(name, dir_fd=fd, follow_symlinks=False)
                    if (not stat.S_ISREG(published.st_mode)
                            or (published.st_dev, published.st_ino) != (created.st_dev, created.st_ino)
                            or _read_at(fd, name, MAX_BLOCK_BYTES) != raw):
                        raise ValueError('snapshot publication no longer matches its staged content')
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
                        if (not stat.S_ISREG(present.st_mode)
                                or (present.st_dev, present.st_ino) != (created.st_dev, created.st_ino)):
                            raise ValueError('snapshot stage changed before owned cleanup')
                        os.unlink(stage, dir_fd=fd)
        # The final name may already exist after an interrupted link/fsync.
        # Successful retry must make all verified entries durable as well.
        os.fsync(fd)
        current = directory.lstat()
        opened = os.fstat(fd)
        if (current.st_dev, current.st_ino) != (opened.st_dev, opened.st_ino):
            raise ValueError('snapshot store changed during installation')
    finally:
        os.close(fd)


def decode(path, descriptor):
    if not isinstance(descriptor, dict) or MARKER not in descriptor:
        return descriptor
    if (set(descriptor) != FIELDS or type(descriptor[MARKER]) is not int or descriptor[MARKER] != 1
            or type(descriptor['logical_bytes']) is not int or not 0 < descriptor['logical_bytes'] <= MAX_LOGICAL_BYTES
            or any(not isinstance(descriptor[k], str) or not DIGEST.fullmatch(descriptor[k]) for k in ('root', 'sha256'))):
        raise ValueError('invalid snapshot descriptor')
    home = home_for(path)
    directory = home / 'state-blocks/v1'
    block_fd = _safe_directory(directory)
    cache = {}; active = set(); expanded = 0; expanded_bytes = 0
    def visit(digest, depth=0):
        nonlocal expanded, expanded_bytes
        expanded += 1
        if depth > MAX_DEPTH or expanded > MAX_BLOCKS:
            raise ValueError('snapshot expansion exceeds depth or reference bound')
        if not isinstance(digest, str) or not DIGEST.fullmatch(digest) or digest in active:
            raise ValueError('invalid or cyclic snapshot block reference')
        active.add(digest)
        if digest not in cache:
            raw = _read_at(block_fd, digest + '.json', MAX_BLOCK_BYTES)
            if _hash(raw) != digest:
                raise ValueError('snapshot block digest mismatch')
            cache[digest] = json.loads(raw, parse_constant=lambda _: (_ for _ in ()).throw(ValueError('nonfinite JSON')))
        node = cache[digest]
        if not isinstance(node, list) or len(node) != 2:
            raise ValueError('invalid snapshot block shape')
        kind, body = node
        if kind == 'leaf':
            if len(canonical(body)) > LEAF_BYTES:
                raise ValueError('snapshot leaf exceeds byte bound')
            expanded_bytes += len(canonical(body))
            if expanded_bytes > MAX_LOGICAL_BYTES:
                raise ValueError('snapshot expanded content exceeds its byte bound')
            result = deepcopy(body)
        elif kind == 'object' and isinstance(body, list):
            result = {}
            for pair in body:
                if not isinstance(pair, list) or len(pair) != 2 or not isinstance(pair[0], str) or pair[0] in result:
                    raise ValueError('snapshot object has invalid or duplicate keys')
                expanded_bytes += len(canonical(pair[0]))
                if expanded_bytes > MAX_LOGICAL_BYTES:
                    raise ValueError('snapshot expanded keys exceed their byte bound')
                result[pair[0]] = visit(pair[1], depth + 1)
        elif kind in {'map', 'list', 'array', 'text'} and isinstance(body, list):
            result = {} if kind == 'map' else '' if kind == 'text' else []
            for ref in body:
                child = visit(ref, depth + 1)
                if kind == 'map':
                    if not isinstance(child, dict) or set(result) & set(child):
                        raise ValueError('snapshot map overlaps or has invalid type')
                    result.update(child)
                elif kind == 'array': result.append(child)
                elif kind == 'list':
                    if not isinstance(child, list): raise ValueError('invalid snapshot list segment')
                    result.extend(child)
                else:
                    if not isinstance(child, str): raise ValueError('invalid snapshot text segment')
                    result += child
        else:
            raise ValueError('unknown snapshot node encoding')
        active.remove(digest)
        return result
    try:
        _lock_store(block_fd, exclusive=False)
        value = visit(descriptor['root'])
        raw = canonical(value) + b'\n'
        if len(raw) != descriptor['logical_bytes'] or _hash(raw) != descriptor['sha256']:
            raise ValueError('snapshot logical content digest or size mismatch')
        _same_directory(directory, block_fd)
        if isinstance(value, dict) and 'state' in value and 'digest' in value and 'schema_version' in value:
            return DecodedEvent(value, raw)
        return value
    finally:
        os.close(block_fd)


def component(path, keys, *, max_bytes):
    """Read an exact component, charging every authenticated block read.

    The caller must compare the returned component's digest against its current
    journal index. This bounded lookup does not attest the rest of a historical
    snapshot or replace full-chain validation by the run owner.
    """
    used = 0; visits = 0; expanded_bytes = 0; cache = {}
    def read(file, limit):
        nonlocal used
        raw = read_regular(file, min(limit, max_bytes - used))
        used += len(raw)
        if used > max_bytes:
            raise ValueError('selected journal component exceeds its byte bound')
        return json.loads(raw, parse_constant=lambda _: (_ for _ in ()).throw(ValueError('nonfinite JSON')))
    value = read(path, 4 * 1024 * 1024)
    if not isinstance(value, dict) or MARKER not in value:
        for key in keys:
            value = value[key]
        return value, used
    if (set(value) != FIELDS or type(value[MARKER]) is not int or value[MARKER] != 1 or type(value['logical_bytes']) is not int
            or not 0 < value['logical_bytes'] <= MAX_LOGICAL_BYTES
            or any(not isinstance(value[k], str) or not DIGEST.fullmatch(value[k]) for k in ('root', 'sha256'))):
        raise ValueError('invalid selected snapshot descriptor')
    home = home_for(path)
    directory = home / 'state-blocks/v1'
    block_fd = _safe_directory(directory)
    missing = object()
    active = set()
    def node(digest, remaining, depth=0):
        nonlocal visits, used, expanded_bytes
        visits += 1
        if depth > MAX_DEPTH or visits > MAX_BLOCKS or not isinstance(digest, str) or not DIGEST.fullmatch(digest) or digest in active:
            raise ValueError('invalid or excessive selected snapshot reference')
        if digest not in cache:
            raw = _read_at(block_fd, digest + '.json', min(MAX_BLOCK_BYTES, max_bytes - used))
            used += len(raw)
            if used > max_bytes or _hash(raw) != digest:
                raise ValueError('selected snapshot block exceeds bound or fails digest')
            cache[digest] = json.loads(raw, parse_constant=lambda _: (_ for _ in ()).throw(ValueError('nonfinite JSON')))
        block = cache[digest]
        if not isinstance(block, list) or len(block) != 2:
            raise ValueError('invalid selected snapshot block')
        kind, body = block
        active.add(digest)
        try:
            if kind == 'leaf':
                result = deepcopy(body)
                for key in remaining:
                    if not isinstance(result, dict) or key not in result:
                        return missing
                    result = result[key]
                expanded_bytes += len(canonical(result))
                if expanded_bytes > max_bytes:
                    raise ValueError('selected component expansion exceeds its byte bound')
                return result
            if remaining:
                key, rest = remaining[0], remaining[1:]
                if kind == 'object':
                    if not isinstance(body, list) or any(not isinstance(row, list) or len(row) != 2 or not isinstance(row[0], str) for row in body):
                        raise ValueError('invalid selected object keys')
                    if len({row[0] for row in body}) != len(body):
                        raise ValueError('duplicate selected object keys')
                    matches = [row[1] for row in body if row[0] == key]
                    return node(matches[0], rest, depth + 1) if matches else missing
                if kind == 'map':
                    result = missing
                    if not isinstance(body, list): raise ValueError('invalid selected map')
                    for child in body:
                        candidate = node(child, remaining, depth + 1)
                        if candidate is not missing:
                            if result is not missing: raise ValueError('overlapping selected map keys')
                            result = candidate
                    return result
                raise ValueError('selected snapshot path crosses a non-object')
            if kind == 'object':
                result = {}
                for row in body:
                    if not isinstance(row, list) or len(row) != 2 or not isinstance(row[0], str) or row[0] in result:
                        raise ValueError('invalid selected object')
                    expanded_bytes += len(canonical(row[0]))
                    if expanded_bytes > max_bytes:
                        raise ValueError('selected component keys exceed their byte bound')
                    result[row[0]] = node(row[1], (), depth + 1)
            elif kind in {'map', 'list', 'array', 'text'} and isinstance(body, list):
                result = {} if kind == 'map' else '' if kind == 'text' else []
                for childref in body:
                    child = node(childref, (), depth + 1)
                    if kind == 'map':
                        if not isinstance(child, dict) or set(result) & set(child): raise ValueError('invalid selected map')
                        result.update(child)
                    elif kind == 'list':
                        if not isinstance(child, list): raise ValueError('invalid selected list')
                        result.extend(child)
                    elif kind == 'array': result.append(child)
                    else:
                        if not isinstance(child, str): raise ValueError('invalid selected text')
                        result += child
            else:
                raise ValueError('unknown selected node encoding')
            if len(canonical(result)) > max_bytes:
                raise ValueError('selected component expansion exceeds its byte bound')
            return result
        finally:
            active.remove(digest)
    try:
        _lock_store(block_fd, exclusive=False)
        result = node(value['root'], tuple(keys))
        if result is missing:
            raise ValueError('selected snapshot component is absent')
        _same_directory(directory, block_fd)
        return result, used
    finally:
        os.close(block_fd)
