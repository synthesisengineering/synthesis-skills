"""Advisory JSONL projections shared by Stop detectors.

Every reuse hashes the entire consumed prefix: inode/size/mtime alone cannot
prove that old provenance remains present. Only complete physical records are
durable; a valid unterminated record is projected onto a transient copy. Cache
failure or contention falls back to the same read-only scan. No hook authority
or detector decisions live in this cache.
"""

from __future__ import annotations

from contextlib import contextmanager
from copy import deepcopy
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import uuid


SCHEMA = 1
ENGINE_REVISION = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
NEWLINES = re.compile(rb"\r\n|\r|\n")


def _encoded(value):
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode()


def _identity(value):
    return (value.st_dev, value.st_ino, value.st_size, value.st_mtime_ns, value.st_ctime_ns)


def _private_regular(value):
    return (stat.S_ISREG(value.st_mode) and value.st_uid == os.getuid()
            and not value.st_mode & 0o077 and value.st_nlink == 1)


def _cache_directory(root):
    """Open each component without following symlinks; create only the leaf."""
    root = Path(os.path.abspath(os.fspath(root)))
    descriptor = os.open(root.anchor, os.O_RDONLY | os.O_DIRECTORY)
    try:
        for index, part in enumerate(root.parts[1:]):
            leaf = index == len(root.parts) - 2
            try:
                child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                                dir_fd=descriptor)
            except FileNotFoundError:
                if not leaf:
                    raise
                os.mkdir(part, mode=0o700, dir_fd=descriptor)
                child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                                dir_fd=descriptor)
            os.close(descriptor)
            descriptor = child
        metadata = os.fstat(descriptor)
        if metadata.st_uid != os.getuid() or metadata.st_mode & 0o077:
            raise OSError("cache directory is not private")
        return descriptor
    except Exception:
        os.close(descriptor)
        raise


def _read_cache(directory, name):
    try:
        descriptor = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK,
                             dir_fd=directory)
    except FileNotFoundError:
        return None
    with os.fdopen(descriptor, "rb") as handle:
        before = os.fstat(handle.fileno())
        if not _private_regular(before):
            raise OSError("unsafe cache file")
        raw = handle.read()
        if _identity(before) != _identity(os.fstat(handle.fileno())):
            raise OSError("cache changed while reading")
    try:
        return json.loads(raw)
    except Exception:
        return None


@contextmanager
def _cache(root, key):
    """A nonblocking transaction; never wait for another native hook."""
    directory = lock = None
    acquired = False
    transaction = None
    try:
        directory = _cache_directory(root)
        lock_name = key + ".lock"
        lock = os.open(lock_name, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_NONBLOCK,
                       0o600, dir_fd=directory)
        metadata = os.fstat(lock)
        if not _private_regular(metadata):
            raise OSError("unsafe cache lock")
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        acquired = True
        if _identity(metadata) != _identity(os.stat(lock_name, dir_fd=directory,
                                                  follow_symlinks=False)):
            raise OSError("cache lock replaced")
        name = key + ".json"
        document = _read_cache(directory, name)
        transaction = (directory, name, document)
    except Exception:
        pass
    try:
        yield transaction
    finally:
        if lock is not None:
            if acquired:
                try:
                    fcntl.flock(lock, fcntl.LOCK_UN)
                except OSError:
                    pass
            os.close(lock)
        if directory is not None:
            os.close(directory)


def _publish(directory, name, document):
    """Publish only inside the opened private directory, under its key lock."""
    temporary = descriptor = None
    try:
        try:
            metadata = os.stat(name, dir_fd=directory, follow_symlinks=False)
        except FileNotFoundError:
            metadata = None
        if metadata is not None and not _private_regular(metadata):
            return
        document["checksum"] = hashlib.sha256(_encoded(document)).hexdigest()
        temporary = "." + name + "." + uuid.uuid4().hex + ".tmp"
        descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                             0o600, dir_fd=directory)
        with os.fdopen(descriptor, "wb") as handle:
            descriptor = None
            handle.write(_encoded(document))
        # Cooperative writers hold the same lock. Also preserve an unexpected
        # replacement observed before publication instead of overwriting it.
        try:
            current = os.stat(name, dir_fd=directory, follow_symlinks=False)
        except FileNotFoundError:
            current = None
        if ((metadata is None) != (current is None)
                or metadata is not None and _identity(metadata) != _identity(current)):
            return
        os.replace(temporary, name, src_dir_fd=directory, dst_dir_fd=directory)
        temporary = None
    except Exception:
        pass
    finally:
        if descriptor is not None:
            os.close(descriptor)
        if temporary is not None:
            try:
                os.unlink(temporary, dir_fd=directory)
            except OSError:
                pass


def _checkpoint(document, binding, metadata, validate):
    if not isinstance(document, dict):
        return None
    try:
        body = {key: value for key, value in document.items() if key != "checksum"}
        if (type(document.get("schema")) is not int or document["schema"] != SCHEMA
                or document.get("checksum") != hashlib.sha256(_encoded(body)).hexdigest()
                or document.get("binding") != binding
                or document.get("identity") != [metadata.st_dev, metadata.st_ino]
                or type(document.get("offset")) is not int
                or not 0 <= document["offset"] <= metadata.st_size
                or not isinstance(document.get("prefix_sha256"), str)
                or not validate(document.get("state"))):
            return None
        return document
    except Exception:
        return None


def _lines(handle):
    # Binary iteration splits LF; the second split supplies text-mode universal
    # newline behavior without confusing byte offsets with Unicode lengths.
    for slab in handle:
        start = 0
        for match in NEWLINES.finditer(slab):
            yield slab[start:match.end()], True
            start = match.end()
        if start < len(slab):
            yield slab[start:], False


def _apply(state, raw, reduce):
    line = raw.decode("utf-8").strip()
    if not line:
        return
    try:
        event = json.loads(line)
    except Exception:
        return
    reduce(state, event)


def project_jsonl(path, *, namespace, revision, context, initial, reduce, validate,
                  cache_root=None):
    """Return a verified projection; exceptions retain the caller's semantics."""
    path = Path(os.path.abspath(os.fspath(path)))
    binding = {"path": str(path), "namespace": namespace, "revision": revision,
               "engine": ENGINE_REVISION, "context": context}
    key = hashlib.sha256(_encoded(binding)).hexdigest()
    if cache_root is None:
        cache_root = os.environ.get("SYNTHESIS_TRANSCRIPT_CACHE_DIR") or (
            Path(os.environ.get("SYNTHESIS_HOME", str(Path.home() / ".synthesis")))
            / "transcript-cache")
    with _cache(cache_root, key) as transaction:
        document = transaction[2] if transaction else None
        for _attempt in range(2):
            descriptor = os.open(path, os.O_RDONLY | os.O_NONBLOCK)
            with os.fdopen(descriptor, "rb") as handle:
                before = os.fstat(handle.fileno())
                if not stat.S_ISREG(before.st_mode):
                    raise OSError("transcript is not a regular file")
                checkpoint = _checkpoint(document, binding, before, validate)
                digest = hashlib.sha256()
                offset = 0
                state = initial()
                if checkpoint:
                    remaining = checkpoint["offset"]
                    last = b""
                    while remaining:
                        chunk = handle.read(min(1024 * 1024, remaining))
                        if not chunk:
                            break
                        digest.update(chunk)
                        last = chunk[-1:]
                        remaining -= len(chunk)
                    if (remaining == 0 and (not checkpoint["offset"] or last in (b"\n", b"\r"))
                            and digest.hexdigest() == checkpoint["prefix_sha256"]):
                        offset = checkpoint["offset"]
                        state = deepcopy(checkpoint["state"])
                    else:
                        handle.seek(0)
                        digest = hashlib.sha256()
                transient = None
                for raw, complete in _lines(handle):
                    if complete:
                        _apply(state, raw, reduce)
                        digest.update(raw)
                        offset += len(raw)
                    else:
                        transient = deepcopy(state)
                        _apply(transient, raw, reduce)
                after = os.fstat(handle.fileno())
                try:
                    current = path.stat()
                except OSError:
                    continue
                if _identity(before) != _identity(after) or _identity(after) != _identity(current):
                    continue
            if transaction:
                _publish(transaction[0], transaction[1], {
                    "schema": SCHEMA, "binding": binding,
                    "identity": [before.st_dev, before.st_ino], "offset": offset,
                    "prefix_sha256": digest.hexdigest(), "state": state,
                })
            return state if transient is None else transient
    raise OSError("transcript changed during both scan attempts")


def _message_initial():
    return {"assistant": "", "user": "", "assistant_failed": False, "user_failed": False}


def _message_valid(state):
    return (isinstance(state, dict) and set(state) == set(_message_initial())
            and all(isinstance(state[role], str) and type(state[role + "_failed"]) is bool
                    for role in ("assistant", "user")))


def _message_reduce(state, event):
    # The old readers failed independently over the whole history. Keep those
    # semantics even when a later valid message follows an invalid event shape.
    for role in ("assistant", "user"):
        if state[role + "_failed"]:
            continue
        try:
            if event.get("type") != role:
                continue
            content = event.get("message", {}).get("content", [] if role == "assistant" else "")
            if role == "user" and isinstance(content, str):
                state[role] = content
            elif isinstance(content, list):
                texts = [block.get("text", "") for block in content
                         if isinstance(block, dict) and block.get("type") == "text"
                         and (role == "user" or block.get("text"))]
                if texts:
                    state[role] = "\n".join(texts)
        except Exception:
            state[role] = ""
            state[role + "_failed"] = True


def last_messages(path, *, cache_root=None):
    try:
        state = project_jsonl(path, namespace="claude-last-messages", revision="1", context={},
                              initial=_message_initial, reduce=_message_reduce,
                              validate=_message_valid, cache_root=cache_root)
        return state["assistant"], state["user"]
    except Exception:
        return "", ""


def provenance_state_valid(state):
    """Validate the shared storage shape; clients retain their own reducers."""
    return (isinstance(state, dict) and set(state) == {"seen", "written"}
            and isinstance(state["seen"], dict)
            and all(isinstance(key, str) and re.fullmatch(r"\d{10}\.\d{6}", key)
                    and value is True for key, value in state["seen"].items())
            and isinstance(state["written"], list)
            and all(isinstance(row, dict) and set(row) == {"tool", "file", "added_tses"}
                    and isinstance(row["tool"], str) and isinstance(row["file"], str)
                    and isinstance(row["added_tses"], list)
                    and all(isinstance(ts, str) and re.fullmatch(r"\d{10}\.\d{6}", ts)
                            for ts in row["added_tses"])
                    for row in state["written"]))
