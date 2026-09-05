#!/usr/bin/env python3
"""Keep historical Codex plugin roots available after cache reconciliation.

Codex owns its cache directory and may replace the complete directory well
after an install command returns. Running tasks still execute hook commands
bound to the absolute version root from their SessionStart. The release
publisher therefore keeps an immutable, budgeted archive outside the client
cache, while this guardian restores historical roots whenever a later cache
generation removes them.

The newest archived version is deliberately excluded: it is the version the
client currently owns and may be installing. The guardian never deletes a
cache path and never writes through a differing existing root.
"""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import plistlib
import re
import shutil
import sqlite3
import stat
import subprocess
import sys
import tempfile
import time
from contextlib import closing, contextmanager
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Iterator


MARKETPLACE = "synthesis-engineering"
PLUGIN_NAME = "synthesis-skills"
LABEL = "org.synthesisengineering.synthesis-skills-cache-guardian"
VERSION_RE = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+$")
HOOK_PLUGIN_PATH_RE = re.compile(r"\$\{CLAUDE_PLUGIN_ROOT\}/([^\s\"']+)")
IGNORED_ROOTS = frozenset({".git", ".in_use", ".codex-marketplace-install.json"})
BYTECODE_CACHE_DIRECTORY = "__pycache__"
BYTECODE_SUFFIXES = frozenset({".pyc", ".pyo"})
BYTECODE_TEMP_RE = re.compile(r"^.+\.py[co]\.[0-9]+$")
DEFAULT_INTERVAL_SECONDS = 1.0
ERROR_RETRY_SECONDS = 10.0
LOCK_WAIT_TIMEOUT_SECONDS = 120.0
LOCK_WAIT_INTERVAL_SECONDS = 0.1
EX_TEMPFAIL = 75
STORE_NAME = "recovery.sqlite3"
ARCHIVE_BUDGET_BYTES = 512 * 1024 * 1024
SHA256_RE = re.compile(r"^[a-f0-9]{64}$")


class GuardianError(RuntimeError):
    """The guardian could not establish or preserve a safe cache state."""


class GuardianBusy(GuardianError):
    """Another cache transition currently owns the shared cache lock."""


def archive_root(home: Path) -> Path:
    return home / ".synthesis" / "plugin-cache-recovery" / MARKETPLACE / PLUGIN_NAME


def cache_parent(home: Path) -> Path:
    return home / ".codex" / "plugins" / "cache" / MARKETPLACE / PLUGIN_NAME


def runtime_path(home: Path) -> Path:
    return archive_root(home).parent / f".{PLUGIN_NAME}-cache-guardian.py"


def receipt_path(home: Path) -> Path:
    return archive_root(home).parent / "cache-guardian-last.json"


def lock_path(home: Path) -> Path:
    return archive_root(home).parent / f".{PLUGIN_NAME}.release.lock"


def _version_key(version: str) -> tuple[int, int, int]:
    return tuple(int(part) for part in version.split("."))  # type: ignore[return-value]


def _version_roots(parent: Path) -> dict[str, Path]:
    if not parent.is_dir() or parent.is_symlink():
        return {}
    return {
        child.name: child
        for child in sorted(parent.iterdir(), key=lambda item: item.name)
        if child.is_dir()
        and not child.is_symlink()
        and VERSION_RE.fullmatch(child.name) is not None
    }


def _is_ignorable_bytecode(path: Path, relative_path: Path) -> bool:
    """Ignore only regular Python bytecode in a real ``__pycache__`` directory.

    Hooks execute from immutable historical plugin roots. Python may create a
    sibling cache directory as a runtime side effect, but arbitrary files,
    nested directories, links, and special objects inside that directory must
    still change the integrity result or fail closed.
    """
    if (
        relative_path.name == BYTECODE_CACHE_DIRECTORY
        and relative_path.parts.count(BYTECODE_CACHE_DIRECTORY) == 1
    ):
        if path.is_symlink() or not path.is_dir():
            raise GuardianError(
                f"unsafe Python bytecode cache directory: {relative_path}"
            )
        return True
    if relative_path.parent.name == BYTECODE_CACHE_DIRECTORY and (
        relative_path.suffix in BYTECODE_SUFFIXES
        or BYTECODE_TEMP_RE.fullmatch(relative_path.name) is not None
    ) and relative_path.parts.count(BYTECODE_CACHE_DIRECTORY) == 1:
        try:
            mode = path.lstat().st_mode
        except FileNotFoundError:
            # CPython atomically replaces its numeric-suffixed temporary file;
            # disappearance between rglob and lstat is that expected boundary.
            return True
        if not stat.S_ISREG(mode):
            raise GuardianError(f"unsafe Python bytecode cache entry: {relative_path}")
        return True
    return False


def _tree_digest(root: Path) -> str:
    if root.is_symlink() or not root.is_dir():
        raise GuardianError(f"unsafe or missing cache root: {root}")
    digest = hashlib.sha256()
    digest.update(b"ROOT\0" + str(stat.S_IMODE(root.stat().st_mode)).encode("ascii"))
    for path in sorted(root.rglob("*"), key=lambda item: str(item.relative_to(root))):
        relative_path = path.relative_to(root)
        if relative_path.parts and relative_path.parts[0] in IGNORED_ROOTS:
            continue
        if _is_ignorable_bytecode(path, relative_path):
            continue
        relative = str(relative_path).encode("utf-8")
        mode = str(stat.S_IMODE(path.lstat().st_mode)).encode("ascii")
        if path.is_symlink():
            digest.update(b"L\0" + relative + b"\0" + os.readlink(path).encode("utf-8"))
        elif path.is_dir():
            digest.update(b"D\0" + relative + b"\0" + mode)
        elif path.is_file():
            digest.update(b"F\0" + relative + b"\0" + mode + b"\0" + path.read_bytes())
        else:
            raise GuardianError(f"unsupported cache entry type: {relative_path}")
    return digest.hexdigest()


def _safe_archive_boundary(path: Path) -> None:
    if not path.is_absolute() or path in (Path("/"), Path.home(), Path.cwd()):
        raise GuardianError(f"unsafe archive boundary: {path}")
    for part in (path, *path.parents):
        if part.is_symlink():
            raise GuardianError(f"symlinked archive boundary: {part}")
    if (path / ".git").exists():
        raise GuardianError(f"repository cannot be an archive: {path}")


def _json_bytes(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _capture_tree(root: Path, version: str, objects: dict[str, bytes], *, validate: bool = True) -> dict:
    if not root.is_dir() or root.is_symlink():
        raise GuardianError(f"unsafe recovery input: {root}")
    entries = {}
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root)
        if relative.parts[0] in {".git", ".in_use"}:
            continue
        if _is_ignorable_bytecode(path, relative):
            continue
        info = path.lstat()
        mode = stat.S_IMODE(info.st_mode)
        if stat.S_ISLNK(info.st_mode):
            target = os.readlink(path)
            link = PurePosixPath(target)
            if not target or link.is_absolute() or ".." in link.parts:
                raise GuardianError(f"unsafe archive symlink: {relative}")
            entry = ["link", mode, target]
        elif stat.S_ISDIR(info.st_mode):
            entry = ["dir", mode]
        elif stat.S_ISREG(info.st_mode):
            descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
            with os.fdopen(descriptor, "rb") as handle:
                before = os.fstat(handle.fileno())
                data = handle.read()
                after = os.fstat(handle.fileno())
            if (before.st_ino, before.st_size, before.st_mtime_ns, before.st_mode) != (
                after.st_ino, after.st_size, after.st_mtime_ns, after.st_mode
            ) or before.st_ino != info.st_ino:
                raise GuardianError(f"recovery input changed while reading: {relative}")
            digest = hashlib.sha256(data).hexdigest()
            objects[digest] = data
            entry = ["file", mode, digest]
        else:
            raise GuardianError(f"unsupported archive entry type: {relative}")
        entries[relative.as_posix()] = entry
    manifest = {"version": version, "root_mode": stat.S_IMODE(root.stat().st_mode), "entries": entries}
    if validate:
        _validate_manifest(manifest, version, objects)
    return manifest


def _validate_manifest(manifest: dict, version: str, objects: dict[str, bytes]) -> None:
    if not isinstance(manifest, dict) or set(manifest) != {"version", "root_mode", "entries"}:
        raise GuardianError("invalid recovery manifest fields")
    if VERSION_RE.fullmatch(version) is None or manifest["version"] != version:
        raise GuardianError("invalid recovery version identity")
    if type(manifest["root_mode"]) is not int or not 0 <= manifest["root_mode"] <= 0o777:
        raise GuardianError("invalid recovery root mode")
    entries = manifest["entries"]
    if not isinstance(entries, dict) or not entries:
        raise GuardianError("empty or invalid recovery manifest")
    for name, entry in entries.items():
        if not isinstance(name, str):
            raise GuardianError("invalid recovery manifest path type")
        relative = PurePosixPath(name)
        if not name or relative.is_absolute() or relative.as_posix() != name or ".." in relative.parts or "\\" in name or "\0" in name:
            raise GuardianError(f"unsafe recovery manifest path: {name!r}")
        for parent in relative.parents:
            if parent == PurePosixPath("."):
                break
            parent_entry = entries.get(parent.as_posix())
            if not isinstance(parent_entry, list) or len(parent_entry) != 2 or parent_entry[0] != "dir":
                raise GuardianError(f"non-directory recovery manifest parent: {name}")
        if not isinstance(entry, list) or len(entry) not in (2, 3):
            raise GuardianError(f"invalid recovery manifest entry: {name}")
        kind, mode = entry[:2]
        if type(mode) is not int or not 0 <= mode <= 0o777:
            raise GuardianError(f"invalid recovery entry mode: {name}")
        if kind == "file" and len(entry) == 3:
            if not isinstance(entry[2], str) or not SHA256_RE.fullmatch(entry[2]) or entry[2] not in objects:
                raise GuardianError(f"missing or invalid recovery object: {name}")
        elif kind == "link" and len(entry) == 3:
            target = entry[2]
            if not isinstance(target, str) or not target or "\0" in target or "\\" in target or PurePosixPath(target).is_absolute() or ".." in PurePosixPath(target).parts:
                raise GuardianError(f"unsafe recovery link: {name}")
        elif kind != "dir" or len(entry) != 2:
            raise GuardianError(f"unsupported recovery manifest entry: {name}")


def _source_entries(manifest: dict) -> dict:
    return {"root_mode": manifest["root_mode"], "entries": {name: entry for name, entry in manifest["entries"].items() if name.split("/")[0] not in IGNORED_ROOTS}}


class RecoveryStore:
    """Immutable, independently verified SQLite content-addressed archive.

    Publishers build a separate candidate and replace the closed database only
    after validation and budget checks. Readers never open a writable database.
    The store travels inside this standalone guardian, including after restart.
    """

    def __init__(self) -> None:
        self.versions: dict[str, dict] = {}
        self.objects: dict[str, bytes] = {}
        self.stored_bytes = 0

    @classmethod
    def read(cls, archive: Path, *, budget: int = ARCHIVE_BUDGET_BYTES) -> RecoveryStore:
        _safe_archive_boundary(archive)
        if archive.exists():
            for child in archive.iterdir():
                if child.name == STORE_NAME:
                    continue
                version = child.name.removeprefix(".retired-")
                if not VERSION_RE.fullmatch(version) or child.is_symlink() or not child.is_dir():
                    raise GuardianError(f"unexpected or unsafe archive entry: {child}")
        return cls.read_file(archive / STORE_NAME, budget=budget)

    @classmethod
    def read_file(cls, path: Path, *, budget: int = ARCHIVE_BUDGET_BYTES) -> RecoveryStore:
        result = cls()
        if not path.exists() and not path.is_symlink():
            return result
        info = path.lstat()
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
            raise GuardianError(f"unsafe recovery database: {path}")
        if info.st_size > budget:
            raise GuardianError("recovery archive exceeds the 512 MiB hard budget")
        try:
            with closing(sqlite3.connect(path.as_uri() + "?mode=ro&immutable=1", uri=True)) as db:
                db.execute("PRAGMA trusted_schema=OFF")
                if db.execute("PRAGMA user_version").fetchone()[0] != 1 or db.execute("PRAGMA integrity_check").fetchall() != [("ok",)]:
                    raise GuardianError("recovery database integrity or schema failure")
                for digest, payload in db.execute("SELECT digest, payload FROM objects"):
                    if not isinstance(payload, bytes) or hashlib.sha256(payload).hexdigest() != digest:
                        raise GuardianError("recovery object digest mismatch")
                    result.objects[digest] = payload
                for version, raw, digest in db.execute("SELECT version, manifest, digest FROM versions"):
                    if not isinstance(raw, str) or hashlib.sha256(raw.encode()).hexdigest() != digest:
                        raise GuardianError("recovery manifest digest mismatch")
                    manifest = json.loads(raw)
                    _validate_manifest(manifest, version, result.objects)
                    result.versions[version] = manifest
                referenced = {entry[2] for manifest in result.versions.values() for entry in manifest["entries"].values() if entry[0] == "file"}
                if referenced != set(result.objects):
                    raise GuardianError("recovery object membership differs from version manifests")
                pages = db.execute("PRAGMA page_count").fetchone()[0] * db.execute("PRAGMA page_size").fetchone()[0]
                if pages != info.st_size or pages > budget:
                    raise GuardianError("recovery database pages violate hard budget or file size")
        except (sqlite3.Error, ValueError, TypeError) as exc:
            raise GuardianError(f"unreadable recovery database: {exc}") from exc
        if not result.versions:
            raise GuardianError("recovery database has no versions")
        result.stored_bytes = info.st_size
        return result

    def materialize(self, version: str, target: Path) -> None:
        manifest = self.versions[version]
        _validate_manifest(manifest, version, self.objects)
        target.mkdir(parents=True, exist_ok=False)
        # Create with writable staging modes; final directory modes come last.
        for name, entry in sorted(manifest["entries"].items()):
            path = target / name
            if entry[0] == "dir":
                path.mkdir()
            elif entry[0] == "file":
                data = self.objects[entry[2]]
                if hashlib.sha256(data).hexdigest() != entry[2]:
                    raise GuardianError("recovery object changed before materialization")
                with path.open("xb") as handle:
                    handle.write(data)
                path.chmod(entry[1])
            else:
                path.symlink_to(entry[2])
        for name, entry in sorted(manifest["entries"].items(), reverse=True):
            if entry[0] == "dir":
                (target / name).chmod(entry[1])
        target.chmod(manifest["root_mode"])
        observed = _capture_tree(target, version, {})
        if observed != manifest:
            raise GuardianError(f"materialized recovery differs from manifest: {version}")


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _retire_legacy(archive: Path, store: RecoveryStore) -> None:
    """Resume a verified move-before-delete, even after partial tree removal."""
    for child in sorted(archive.iterdir()):
        version = child.name.removeprefix(".retired-")
        if not VERSION_RE.fullmatch(version):
            continue
        if child.is_symlink() or not child.is_dir() or version not in store.versions:
            raise GuardianError(f"unsafe legacy retirement: {child}")
        observed = _capture_tree(child, version, {}, validate=False)
        expected = store.versions[version]
        retiring = child.name.startswith(".retired-")
        if observed["root_mode"] != expected["root_mode"] or (not retiring and observed != expected) or any(expected["entries"].get(key) != entry for key, entry in observed["entries"].items()):
            raise GuardianError(f"legacy retirement differs from committed recovery: {child}")
        target = archive / f".retired-{version}"
        if not retiring:
            if target.exists() or target.is_symlink():
                raise GuardianError(f"legacy retirement destination already exists: {target}")
            os.rename(child, target)
            _fsync_directory(archive)
        if target.parent != archive or target.is_symlink() or archive in (Path.home(), Path.cwd(), Path("/")):
            raise GuardianError(f"unsafe retirement cleanup: {target}")
        shutil.rmtree(target)
        _fsync_directory(archive)


def persist_archive(archive: Path, roots: dict[str, Path], *, budget: int = ARCHIVE_BUDGET_BYTES) -> RecoveryStore:
    """Admit complete versions under the publisher's shared transition lock.

    Transient candidate and migration copies coexist until verification; only
    committed recovery storage is admitted against the unchanged hard limit.
    No version or unique payload is evicted to satisfy the limit.
    """
    _safe_archive_boundary(archive)
    archive.mkdir(parents=True, exist_ok=True)
    store = RecoveryStore.read(archive)
    legacy = _version_roots(archive)
    for version, root in [*legacy.items(), *roots.items()]:
        manifest = _capture_tree(root, version, store.objects)
        previous = store.versions.get(version)
        if previous is not None:
            if _source_entries(previous) != _source_entries(manifest):
                raise GuardianError(f"immutable historical version differs: {version}")
            # Retain original installation metadata, never replace history.
        else:
            store.versions[version] = manifest
    if not store.versions:
        raise GuardianError("no recovery versions to persist")
    descriptor, temporary_name = tempfile.mkstemp(prefix=".recovery-candidate-", dir=archive.parent)
    os.close(descriptor)
    candidate = Path(temporary_name)
    try:
        with closing(sqlite3.connect(candidate)) as db:
            db.execute("PRAGMA journal_mode=DELETE")
            db.execute("PRAGMA synchronous=FULL")
            db.execute("PRAGMA user_version=1")
            db.execute("CREATE TABLE objects (digest TEXT PRIMARY KEY, payload BLOB NOT NULL)")
            db.execute("CREATE TABLE versions (version TEXT PRIMARY KEY, manifest TEXT NOT NULL, digest TEXT NOT NULL)")
            referenced = {entry[2] for manifest in store.versions.values() for entry in manifest["entries"].values() if entry[0] == "file"}
            db.executemany("INSERT INTO objects VALUES (?, ?)", ((digest, store.objects[digest]) for digest in sorted(referenced)))
            for version, manifest in sorted(store.versions.items()):
                raw = _json_bytes(manifest)
                db.execute("INSERT INTO versions VALUES (?, ?, ?)", (version, raw.decode(), hashlib.sha256(raw).hexdigest()))
            db.commit()
        verified = RecoveryStore.read_file(candidate, budget=budget)
        if verified.versions != store.versions or set(verified.objects) != referenced:
            raise GuardianError("candidate recovery store differs after commit")
        _safe_archive_boundary(archive)
        destination = archive / STORE_NAME
        if destination.is_symlink() or (destination.exists() and (not destination.is_file() or destination.stat().st_nlink != 1)):
            raise GuardianError("unsafe recovery database promotion target")
        os.replace(candidate, destination)
        _fsync_directory(archive)
        committed = RecoveryStore.read(archive, budget=budget)
        _retire_legacy(archive, committed)
        return committed
    finally:
        candidate.unlink(missing_ok=True)


def _validate_root(root: Path, version: str) -> None:
    if not root.is_dir() or root.is_symlink():
        raise GuardianError(f"archive root is absent, not a directory, or a symlink: {root}")
    for path in root.rglob("*"):
        if not path.is_symlink():
            continue
        link = PurePosixPath(os.readlink(path))
        if link.is_absolute() or ".." in link.parts:
            raise GuardianError(
                f"unsafe archive symlink: {path.relative_to(root)} -> {link}"
            )
    versions: set[str] = set()
    for manifest in (".claude-plugin/plugin.json", ".codex-plugin/plugin.json"):
        candidate = root / manifest
        if not candidate.is_file():
            continue
        try:
            payload = json.loads(candidate.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise GuardianError(f"unreadable archive manifest {candidate}: {exc}") from exc
        value = payload.get("version")
        if isinstance(value, str):
            versions.add(value)
    if version not in versions:
        raise GuardianError(f"no archive manifest reports {version}: {root}")
    hooks = root / "hooks" / "hooks.json"
    try:
        hook_text = hooks.read_text(encoding="utf-8")
        json.loads(hook_text)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise GuardianError(f"unreadable archive hook definition {hooks}: {exc}") from exc
    targets = sorted(set(HOOK_PLUGIN_PATH_RE.findall(hook_text)))
    if not targets:
        raise GuardianError(f"archive hook definition has no plugin-root target: {hooks}")
    missing = [target for target in targets if not (root / target).is_file()]
    if missing:
        raise GuardianError(f"archive root {version} misses hook target(s): {', '.join(missing[:3])}")
    if not any(root.glob("skills/*/SKILL.md")):
        raise GuardianError(f"archive root has no skill entry point: {root}")


def _refuse_symlinked_boundary(home: Path, path: Path) -> None:
    if not home.is_absolute() or not path.is_absolute():
        raise GuardianError("home and cache boundaries must be absolute")
    try:
        relative = path.relative_to(home)
    except ValueError as exc:
        raise GuardianError(f"path escapes home boundary: {path}") from exc
    cursor = home
    if cursor.is_symlink():
        raise GuardianError(f"home boundary is a symlink: {cursor}")
    for part in relative.parts:
        cursor = cursor / part
        if cursor.is_symlink():
            raise GuardianError(f"refusing symlinked cache boundary: {cursor}")


def _atomic_write(path: Path, payload: bytes, mode: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_symlink():
        raise GuardianError(f"refusing to replace symlinked file: {path}")
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        temporary.chmod(mode)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


@contextmanager
def _cache_lock(home: Path, *, blocking: bool) -> Iterator[None]:
    path = lock_path(home)
    _refuse_symlinked_boundary(home, path)
    path.parent.mkdir(parents=True, exist_ok=True)
    flags = os.O_RDWR | os.O_CREAT
    if hasattr(os, "O_CLOEXEC"):
        flags |= os.O_CLOEXEC
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    descriptor = os.open(path, flags, 0o600)
    handle = os.fdopen(descriptor, "a+")
    deadline = time.monotonic() + LOCK_WAIT_TIMEOUT_SECONDS if blocking else None
    acquired = False
    try:
        while True:
            try:
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                acquired = True
                break
            except BlockingIOError as exc:
                if deadline is None:
                    raise GuardianBusy("another cache transition owns the cache lock") from exc
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise GuardianBusy(
                        "another cache transition held the cache lock for more than "
                        f"{LOCK_WAIT_TIMEOUT_SECONDS:g} seconds"
                    ) from exc
                time.sleep(min(LOCK_WAIT_INTERVAL_SECONDS, remaining))
        yield
    finally:
        try:
            if acquired:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        finally:
            handle.close()


def _remove_staging(path: Path, parent: Path) -> None:
    if not path.exists():
        return
    if path.parent != parent or not path.name.startswith(".guardian-") or path.is_symlink():
        raise GuardianError(f"refusing unsafe staging cleanup target: {path}")
    shutil.rmtree(path)


def _restore_missing(source: Path, destination: Path, parent: Path) -> bool:
    staging = parent / f".guardian-{destination.name}-{os.getpid()}-{time.time_ns()}"
    try:
        shutil.copytree(source, staging, symlinks=True)
        if _tree_digest(source) != _tree_digest(staging):
            raise GuardianError(f"staged recovery differs from archive: {source.name}")
        if destination.exists() or destination.is_symlink():
            if destination.is_symlink() or not destination.is_dir():
                raise GuardianError(f"cache root appeared with an unsafe type: {destination}")
            if _tree_digest(source) != _tree_digest(destination):
                raise GuardianError(f"cache root appeared with differing content: {destination}")
            return False
        os.rename(staging, destination)
        if _tree_digest(source) != _tree_digest(destination):
            raise GuardianError(f"restored cache root differs from archive: {destination}")
        return True
    finally:
        _remove_staging(staging, parent)


def _restore_stored(store: RecoveryStore, version: str, destination: Path, parent: Path) -> bool:
    staging = parent / f".guardian-{version}-{os.getpid()}-{time.time_ns()}"
    try:
        store.materialize(version, staging)
        _validate_root(staging, version)
        if destination.exists() or destination.is_symlink():
            if destination.is_symlink() or not destination.is_dir() or _tree_digest(staging) != _tree_digest(destination):
                raise GuardianError(f"cache root appeared with differing content: {destination}")
            return False
        os.rename(staging, destination)
        _fsync_directory(parent)
        return True
    finally:
        _remove_staging(staging, parent)


def restore_once(home: Path | None = None, *, blocking: bool = False) -> dict[str, object]:
    home = (home or Path.home()).absolute()
    archive = archive_root(home)
    cache = cache_parent(home)
    _refuse_symlinked_boundary(home, archive)
    _refuse_symlinked_boundary(home, cache)
    if not archive.is_dir():
        raise GuardianError(f"recovery archive is unavailable: {archive}")
    restored: list[str] = []
    verified: list[str] = []
    with _cache_lock(home, blocking=blocking):
        store = RecoveryStore.read(archive)
        archived = _version_roots(archive)
        ordered = sorted(set(archived) | set(store.versions), key=_version_key)
        if not ordered:
            raise GuardianError(f"recovery archive has no version roots: {archive}")
        current = ordered[-1]
        protected = ordered[:-1]
        cache.mkdir(parents=True, exist_ok=True)
        if cache.is_symlink():
            raise GuardianError(f"cache parent is a symlink: {cache}")
        # A task is most likely to be pinned to the version immediately before
        # the current release. Restore from newest to oldest so that root is
        # available first even when a large archive takes time to rehydrate.
        for version in reversed(protected):
            destination = cache / version
            if destination.is_symlink() or (destination.exists() and not destination.is_dir()):
                raise GuardianError(f"historical cache root has an unsafe type: {destination}")
            if version in store.versions:
                if not destination.exists():
                    if _restore_stored(store, version, destination, cache):
                        restored.append(version)
                else:
                    observed = _capture_tree(destination, version, {})
                    if _source_entries(observed) != _source_entries(store.versions[version]):
                        raise GuardianError(f"historical cache root differs from archive: {destination}")
                    _validate_root(destination, version)
                verified.append(version)
                continue
            source = archived[version]
            _validate_root(source, version)
            if not destination.exists():
                if _restore_missing(source, destination, cache):
                    restored.append(version)
            elif _tree_digest(source) != _tree_digest(destination):
                raise GuardianError(f"historical cache root differs from archive: {destination}")
            verified.append(version)
    record: dict[str, object] = {
        "schema": 1,
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "archive": str(archive),
        "cache": str(cache),
        "current_excluded": current,
        "protected_versions": protected,
        "verified": len(verified),
        "restored": restored,
    }
    _atomic_write(receipt_path(home), (json.dumps(record, indent=2, sort_keys=True) + "\n").encode(), 0o600)
    return record


def _cache_signature(home: Path) -> tuple[object, ...]:
    parent = cache_parent(home)
    if not parent.is_dir() or parent.is_symlink():
        return ("absent",)
    stat = parent.stat()
    return (stat.st_ino, stat.st_mtime_ns, tuple(sorted(_version_roots(parent))))


def watch(home: Path | None = None, interval: float = DEFAULT_INTERVAL_SECONDS) -> None:
    home = (home or Path.home()).absolute()
    previous: tuple[object, ...] | None = None
    while True:
        signature = _cache_signature(home)
        if signature != previous:
            try:
                restore_once(home)
                previous = _cache_signature(home)
            except GuardianBusy:
                previous = None
            except GuardianError as exc:
                print(f"cache guardian retrying after error: {exc}", file=sys.stderr, flush=True)
                previous = None
                time.sleep(ERROR_RETRY_SECONDS)
                continue
        time.sleep(interval)


def _launchd_payload(home: Path, runtime: Path) -> bytes:
    logs = archive_root(home).parent / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    return plistlib.dumps(
        {
            "Label": LABEL,
            "ProgramArguments": [sys.executable, str(runtime), "--watch"],
            "RunAtLoad": True,
            "KeepAlive": True,
            "ThrottleInterval": 10,
            "ProcessType": "Background",
            "StandardOutPath": str(logs / "cache-guardian.out.log"),
            "StandardErrorPath": str(logs / "cache-guardian.err.log"),
        },
        sort_keys=False,
    )


def _systemd_quote(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _systemd_payload(runtime: Path) -> bytes:
    command = " ".join(_systemd_quote(value) for value in (sys.executable, str(runtime), "--watch"))
    return (
        "[Unit]\nDescription=Synthesis Skills historical Codex cache guardian\n\n"
        "[Service]\nType=simple\n"
        f"ExecStart={command}\n"
        "Restart=always\nRestartSec=10\n\n"
        "[Install]\nWantedBy=default.target\n"
    ).encode()


def _completed_detail(completed: subprocess.CompletedProcess[str]) -> str:
    return (completed.stderr or completed.stdout or "").strip()


def install_supervisor(
    home: Path,
    runtime: Path,
    *,
    platform: str | None = None,
    runner=subprocess.run,
) -> str:
    platform = platform or sys.platform
    if platform == "darwin":
        launchctl = shutil.which("launchctl")
        if launchctl is None:
            raise GuardianError("launchctl is required for the macOS cache guardian")
        plist = home / "Library" / "LaunchAgents" / f"{LABEL}.plist"
        _refuse_symlinked_boundary(home, plist)
        _atomic_write(plist, _launchd_payload(home, runtime), 0o644)
        domain = f"gui/{os.getuid()}"
        runner([launchctl, "bootout", domain, str(plist)], capture_output=True, text=True, check=False)
        boot = runner([launchctl, "bootstrap", domain, str(plist)], capture_output=True, text=True, check=False)
        if boot.returncode:
            raise GuardianError(f"launchctl bootstrap failed: {_completed_detail(boot)}")
        kick = runner([launchctl, "kickstart", "-k", f"{domain}/{LABEL}"], capture_output=True, text=True, check=False)
        if kick.returncode:
            raise GuardianError(f"launchctl kickstart failed: {_completed_detail(kick)}")
        probe = runner([launchctl, "print", f"{domain}/{LABEL}"], capture_output=True, text=True, check=False)
        if probe.returncode:
            raise GuardianError(f"launchctl could not verify the guardian: {_completed_detail(probe)}")
        return str(plist)
    if platform.startswith("linux"):
        systemctl = shutil.which("systemctl")
        if systemctl is None:
            raise GuardianError("systemctl is required for the Linux cache guardian")
        unit = home / ".config" / "systemd" / "user" / f"{LABEL}.service"
        _refuse_symlinked_boundary(home, unit)
        _atomic_write(unit, _systemd_payload(runtime), 0o644)
        for command in (
            [systemctl, "--user", "daemon-reload"],
            [systemctl, "--user", "enable", "--now", unit.name],
            [systemctl, "--user", "restart", unit.name],
            [systemctl, "--user", "is-active", unit.name],
        ):
            completed = runner(command, capture_output=True, text=True, check=False)
            if completed.returncode:
                raise GuardianError(f"systemd guardian command failed: {_completed_detail(completed)}")
        return str(unit)
    raise GuardianError(f"no supported user supervisor on platform {platform}")


def prepare_runtime(home: Path | None = None) -> dict[str, object]:
    home = (home or Path.home()).absolute()
    runtime = runtime_path(home)
    _refuse_symlinked_boundary(home, runtime)
    source = Path(__file__).resolve()
    _atomic_write(runtime, source.read_bytes(), 0o755)
    if runtime.read_bytes() != source.read_bytes():
        raise GuardianError(f"installed guardian differs from source: {runtime}")
    supervisor = install_supervisor(home, runtime)
    return {"runtime": str(runtime), "supervisor": supervisor}


def install(home: Path | None = None) -> dict[str, object]:
    home = (home or Path.home()).absolute()
    deployed = prepare_runtime(home)
    record = restore_once(home, blocking=True)
    record.update(deployed)
    return record


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--once", action="store_true", help="restore and verify historical roots once")
    modes.add_argument("--watch", action="store_true", help="continuously guard later cache generations")
    modes.add_argument("--install", action="store_true", help="install and start the durable user supervisor")
    modes.add_argument("--prepare", action="store_true", help="verify the archive-aware supervisor before archive migration")
    modes.add_argument(
        "--doctor",
        action="store_true",
        help="wait for the cache transition lock, restore once, and verify the durable runtime exists",
    )
    parser.add_argument("--interval", type=float, default=DEFAULT_INTERVAL_SECONDS)
    args = parser.parse_args(argv)
    try:
        if args.watch:
            watch(interval=max(args.interval, 0.1))
            return 0
        if args.prepare:
            record = prepare_runtime()
        elif args.install:
            record = install()
        else:
            # A synchronous doctor is a completion gate for onboarding. It
            # waits through ordinary watcher work instead of turning normal
            # lock contention into a false update failure. ``--once`` and the
            # watcher remain nonblocking so background work never queues.
            record = restore_once(blocking=args.doctor)
            if args.doctor:
                runtime = runtime_path(Path.home())
                if not runtime.is_file() or runtime.is_symlink():
                    raise GuardianError(f"durable guardian runtime is unavailable: {runtime}")
        print(json.dumps(record, sort_keys=True))
        return 0
    except GuardianBusy as exc:
        print(f"cache guardian busy: {exc}", file=sys.stderr)
        return EX_TEMPFAIL
    except (GuardianError, OSError, subprocess.SubprocessError) as exc:
        print(f"cache guardian failed: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
