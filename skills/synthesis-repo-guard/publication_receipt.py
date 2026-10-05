"""Exact-session publication evidence; Stop reads locally and never publishes.

The existing checkpoint-sync owner produces receipts only after its remote checks.
This reader revalidates the exact local files, commit and tracking refs. A receipt
is historical remote evidence, never a claim that the remote was contacted now.
"""
from __future__ import annotations

import base64
import hashlib
import json
import math
import os
from pathlib import Path
import stat
import subprocess
import time

MAX_PATHS = 256
MAX_MANIFEST = 256 * 1024
MAX_RECEIPT = 2 * 1024 * 1024
MAX_CONTENT = 32 * 1024 * 1024
PUBLISHED = {"clean", "committed-pushed", "pushed-stranded", "source-remote-ready"}
OWNER = "checkpoint_sync.py --flush-session"


class ProofError(ValueError):
    pass


def _remaining(deadline):
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise ProofError("publication evidence exceeded its bounded observation time")
    return remaining


def _path(value):
    if not isinstance(value, str):
        raise ProofError("publication path is not a string")
    path = Path(value)
    if not path.is_absolute() or str(path) != value or path.resolve(strict=False) != path:
        raise ProofError("publication path is not canonical")
    if any(part.is_symlink() for part in (path, *path.parents)):
        raise ProofError("publication path crosses a symlink")
    return path


def _identity(value):
    return (value.st_dev, value.st_ino, value.st_mode, value.st_nlink,
            value.st_size, value.st_mtime_ns, value.st_ctime_ns)


def _read(path, limit, deadline):
    _remaining(deadline)
    _path(str(path))
    ancestors = {parent: _identity(parent.stat()) for parent in path.parents}
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, "rb") as stream:
        before = os.fstat(stream.fileno())
        if not stat.S_ISREG(before.st_mode) or before.st_size > limit:
            raise ProofError("publication evidence is non-regular or over its byte limit")
        raw = stream.read(limit + 1)
        after = os.fstat(stream.fileno())
    if (len(raw) > limit or _identity(before) != _identity(after)
            or _identity(after) != _identity(path.lstat())
            or any(_identity(parent.stat()) != identity for parent, identity in ancestors.items())):
        raise ProofError("publication evidence changed during observation")
    _remaining(deadline)
    return raw, _identity(after)


def _json(raw):
    def pairs(items):
        value = {}
        for key, item in items:
            if key in value:
                raise ProofError("duplicate publication JSON field")
            value[key] = item
        return value
    def invalid_constant(_value):
        raise ProofError("non-finite publication JSON number")
    value = json.loads(raw, object_pairs_hook=pairs, parse_constant=invalid_constant)
    if not isinstance(value, dict):
        raise ProofError("publication JSON must be an object")
    return value


def _git(repo, deadline, *args):
    # All callers use finite read-only local commands; no fetch/push is allowed.
    result = subprocess.run(["git", "-C", str(repo), *args], capture_output=True,
                            timeout=_remaining(deadline), check=False)
    _remaining(deadline)
    if result.returncode:
        raise ProofError("local publication Git evidence is unavailable")
    return result.stdout.rstrip(b"\n")


def _manifest(path, raw, native):
    if len(raw) > MAX_MANIFEST:
        raise ProofError("publication manifest exceeds byte bound")
    from pending_manifest import decode_pending_manifest
    try:
        data = decode_pending_manifest(_json(raw))
    except ValueError as exc:
        raise ProofError("invalid pending path representation") from exc
    expected = hashlib.sha256(native.encode()).hexdigest() + ".json"
    if (not native or data.get("session_id") != native or path.name != expected
            or path.parent.name != "pending" or type(data.get("schema_version")) is not int
            or data["schema_version"] not in {1, 2}):
        raise ProofError("publication manifest does not bind the exact native session")
    values = data.get("paths")
    remote = data.get("remote_paths", values)
    if (not isinstance(values, list) or not isinstance(remote, list) or not values
            or len(values) + len(remote) > MAX_PATHS * 2
            or any(not isinstance(value, str) for value in [*values, *remote])):
        raise ProofError("publication manifest has invalid path coverage")
    paths = sorted(set(values) | set(remote))
    if len(paths) > MAX_PATHS or len(set(values)) != len(values) or len(set(remote)) != len(remote):
        raise ProofError("publication path coverage is duplicate or over bound")
    return [_path(value) for value in paths]


def _snapshot(paths, deadline):
    files, repos, identities, consumed = [], {}, {}, 0
    for path in paths:
        parent = path.parent
        while not parent.exists():
            if parent == parent.parent:
                raise ProofError("publication repository no longer exists")
            parent = parent.parent
        repo = _path(_git(parent, deadline, "rev-parse", "--show-toplevel").decode())
        if not path.is_relative_to(repo) or path == repo:
            raise ProofError("publication path is outside repository")
        if str(repo) not in repos:
            branch = _git(repo, deadline, "branch", "--show-current").decode()
            head = _git(repo, deadline, "rev-parse", "HEAD").decode()
            upstream = _git(repo, deadline, "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{upstream}").decode()
            upstream_head = _git(repo, deadline, "rev-parse", "@{upstream}").decode()
            if not branch or head != upstream_head:
                raise ProofError("current local commit is not the verified tracking commit")
            remote = _git(repo, deadline, "config", "--get", f"branch.{branch}.remote").decode()
            if not remote or remote == ".":
                raise ProofError("publication remote identity is unavailable")
            remote_url = _git(repo, deadline, "remote", "get-url", remote).decode()
            repos[str(repo)] = {"branch": branch, "head": head, "upstream": upstream,
                                "remote": remote, "remote_url_sha256": hashlib.sha256(remote_url.encode()).hexdigest()}
        rel = path.relative_to(repo).as_posix()
        literal = ":(top,literal)" + rel
        tree = _git(repo, deadline, "ls-tree", "-z", "HEAD", "--", literal)
        index = _git(repo, deadline, "ls-files", "--stage", "-z", "--", literal)
        item = {"path": str(path), "repo": str(repo)}
        if not path.exists():
            if tree or index or not _git(repo, deadline, "log", "-1", "--format=%H", "--diff-filter=D", "HEAD", "--", literal):
                raise ProofError("missing publication path is not a committed deletion")
            item["state"] = "deleted"
        else:
            raw, identity = _read(path, MAX_CONTENT - consumed, deadline)
            consumed += len(raw)
            mode = "100755" if identity[2] & 0o111 else "100644"
            fields = tree.removesuffix(b"\0").split(b"\t", 1)
            meta = fields[0].split()
            if (len(fields) != 2 or fields[1] != rel.encode() or len(meta) != 3
                    or meta[:2] != [mode.encode(), b"blob"]
                    or index != meta[0] + b" " + meta[2] + b" 0\t" + rel.encode() + b"\0"
                    or _git(repo, deadline, "hash-object", "--no-filters", "--", rel) != meta[2]):
                raise ProofError("current publication bytes or mode do not equal committed content")
            item.update(state="present", sha256=hashlib.sha256(raw).hexdigest(), size=len(raw), mode=mode)
            identities[path] = identity
        files.append(item)
    for repo, expected in repos.items():
        if (_git(Path(repo), deadline, "rev-parse", "HEAD").decode() != expected["head"]
                or _git(Path(repo), deadline, "rev-parse", "@{upstream}").decode() != expected["head"]
                or _git(Path(repo), deadline, "branch", "--show-current").decode() != expected["branch"]
                or _git(Path(repo), deadline, "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{upstream}").decode() != expected["upstream"]
                or _git(Path(repo), deadline, "config", "--get", f"branch.{expected['branch']}.remote").decode() != expected["remote"]
                or hashlib.sha256(_git(Path(repo), deadline, "remote", "get-url", expected["remote"])).hexdigest() != expected["remote_url_sha256"]):
            raise ProofError("publication repository changed during verification")
    for path, identity in identities.items():
        _path(str(path))
        if _identity(path.lstat()) != identity:
            raise ProofError("publication file changed during verification")
    for item in files:
        if item["state"] == "deleted" and os.path.lexists(_path(item["path"])):
            raise ProofError("deleted publication path reappeared during observation")
    _remaining(deadline)
    return {"files": files, "repositories": repos}


def build(manifest, raw, results, *, seconds=10):
    """Called only by the existing flush owner inside its lifecycle/manifest lock."""
    deadline = time.monotonic() + seconds
    native = _json(raw).get("session_id")
    if not isinstance(native, str):
        raise ProofError("publication native identity is absent")
    manifest = _path(str(manifest))
    paths = _manifest(manifest, raw, native)
    if _read(manifest, MAX_MANIFEST, deadline)[0] != raw:
        raise ProofError("publication manifest changed during owner operation")
    snapshot = _snapshot(paths, deadline)
    for repo in snapshot["repositories"]:
        matching = [item for item in results if isinstance(item, dict) and item.get("repo") == repo]
        if not matching or any(item.get("action") not in PUBLISHED or item.get("alert") is not None for item in matching):
            raise ProofError("flush owner has not verified publication of every repository")
    if _read(manifest, MAX_MANIFEST, deadline)[0] != raw:
        raise ProofError("publication manifest changed before receipt")
    return {"schema": 1, "producer": OWNER, "session_id": native,
            "manifest": str(manifest), "manifest_sha256": hashlib.sha256(raw).hexdigest(),
            "manifest_base64": base64.b64encode(raw).decode(),
            "readiness": "REMOTE_READY", "verified_at_epoch": time.time(), **snapshot}


def observe(root, native, *, seconds=2, required_files=None, expected_receipt_sha256=None):
    """Bounded offline diagnostic. No receipt grants publication or checkpoint authority."""
    unknown = {"status": "UNKNOWN", "owner": OWNER, "live_remote_rechecked": False,
               "detail": "Publication is unverified. Absence of a current bound receipt does not mean unpublished; use the authorized exact-session flush owner."}
    try:
        deadline = time.monotonic() + seconds
        if not isinstance(native, str) or not native:
            return unknown
        root = _path(str(root))
        name = hashlib.sha256(native.encode()).hexdigest() + ".json"
        manifest = root / "pending" / name
        # A new attribution is a new obligation, even with identical bytes.
        if os.path.lexists(manifest):
            raise ProofError("current native attribution remains pending")
        receipt = root / "publication" / name
        raw, identity = _read(receipt, MAX_RECEIPT, deadline)
        metadata = receipt.lstat()
        if metadata.st_uid != os.geteuid() or metadata.st_nlink != 1 or metadata.st_mode & 0o022:
            raise ProofError("publication receipt is not private owner-controlled evidence")
        data = _json(raw)
        stamp = data.get("verified_at_epoch")
        if (type(stamp) not in {int, float} or not math.isfinite(stamp)
                or stamp <= 0 or stamp > time.time() + 1):
            raise ProofError("publication observation timestamp is invalid")
        if (type(data.get("schema")) is not int or data["schema"] != 1 or data.get("producer") != OWNER
                or data.get("session_id") != native or data.get("manifest") != str(manifest)
                or data.get("readiness") != "REMOTE_READY"):
            raise ProofError("publication receipt identity or owner is unverified")
        original = base64.b64decode(data.get("manifest_base64", ""), validate=True)
        paths = _manifest(manifest, original, native)
        if hashlib.sha256(original).hexdigest() != data.get("manifest_sha256"):
            raise ProofError("publication manifest digest is invalid")
        current = _snapshot(paths, deadline)
        if current["files"] != data.get("files") or current["repositories"] != data.get("repositories"):
            raise ProofError("publication receipt does not match current content")
        if expected_receipt_sha256 is not None and (
                not isinstance(expected_receipt_sha256, str)
                or hashlib.sha256(raw).hexdigest() != expected_receipt_sha256):
            raise ProofError("publication receipt changed from the selected receipt")
        if required_files is not None:
            if (not isinstance(required_files, dict) or not required_files
                    or len(required_files) > MAX_PATHS):
                raise ProofError("required publication files must be a bounded nonempty mapping")
            present = {item["path"]: item.get("sha256") for item in current["files"]
                       if item.get("state") == "present"}
            for path, digest in required_files.items():
                if (not isinstance(path, str) or str(_path(path)) != path
                        or not isinstance(digest, str) or len(digest) != 64
                        or present.get(path) != digest):
                    raise ProofError("required ingested bytes are not covered by publication")
        _path(str(receipt))
        _path(str(manifest))
        if _identity(receipt.lstat()) != identity or os.path.lexists(manifest):
            raise ProofError("publication attribution changed during observation")
        _remaining(deadline)
        return {"status": "VERIFIED_REMOTE_READY", "owner": OWNER,
                "live_remote_rechecked": False, "session_id": native,
                "manifest_sha256": data["manifest_sha256"], "receipt_sha256": hashlib.sha256(raw).hexdigest(),
                "verified_at_epoch": data.get("verified_at_epoch"),
                "detail": "The exact-session owner previously verified remote publication; current local bytes, commit and tracking refs still match. No network was used by this observer."}
    except (OSError, ValueError, TypeError, KeyError, RecursionError, subprocess.SubprocessError) as exc:
        return {**unknown, "reason": str(exc)}
