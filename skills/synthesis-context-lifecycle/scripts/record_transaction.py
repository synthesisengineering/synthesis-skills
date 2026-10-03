"""Cooperative project-record commit and recovery, owned by context_edit.

A set of ordinary paths cannot be renamed simultaneously. Managed readers hold
one project-directory lock; unfinished commits block readers and editors until
this owner reconciles under fresh native admission. External editors/readers
remain outside that cooperative visibility boundary. Journal data is evidence,
never authority. No rollback overwrites an intervening writer.
"""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from functools import wraps
import fcntl
import hashlib
import inspect
import json
import os
from pathlib import Path
import re
import stat
import sys
import time
import uuid

STORE = ".record-transactions"
MAX_FILES = 128
MAX_FILE_BYTES = 8 * 1024 * 1024
MAX_TOTAL_BYTES = 32 * 1024 * 1024
MAX_MANIFEST_BYTES = 1024 * 1024
MAX_HISTORY = 4096
_HELD = ContextVar("record_transaction_locks", default={})


class RecordTransactionError(RuntimeError):
    pass


def _digest(data):
    return hashlib.sha256(data).hexdigest()


def _json(data):
    return (
        json.dumps(
            data, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode()
        + b"\n"
    )


def _unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise RecordTransactionError("duplicate journal field")
        result[key] = value
    return result


def _path(path, root=None):
    path = Path(path).absolute()
    if ".." in path.parts or (root is not None and not path.is_relative_to(root)):
        raise RecordTransactionError("target escapes its exact project")
    for part in [path, *path.parents]:
        if part.is_symlink():
            raise RecordTransactionError(f"symlink path refused: {part}")
    return path


def _snapshot(path, *, _links=1):
    path = _path(path)
    fd = os.open(
        path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
    )
    try:
        before = os.fstat(fd)
        if (
            not stat.S_ISREG(before.st_mode)
            or before.st_nlink != _links
            or before.st_size > MAX_FILE_BYTES
        ):
            raise RecordTransactionError(
                "target must be a bounded singly-linked regular file"
            )
        chunks, length = [], 0
        while True:
            chunk = os.read(fd, min(65536, MAX_FILE_BYTES + 1 - length))
            if not chunk:
                break
            chunks.append(chunk)
            length += len(chunk)
            if length > MAX_FILE_BYTES:
                raise RecordTransactionError("file exceeds bounded read")
        data = b"".join(chunks)
        after = os.fstat(fd)
        fields = (
            "st_dev",
            "st_ino",
            "st_mode",
            "st_nlink",
            "st_size",
            "st_mtime_ns",
            "st_ctime_ns",
        )
        # Revalidate the actual pathname and every ancestor after reading.
        # An unchanged inode alone does not detect a new hardlink, chmod,
        # different device, or a symlink introduced during the descriptor read.
        final = _path(path).lstat()
        if any(getattr(before, k) != getattr(after, k) for k in fields) or any(
            getattr(after, k) != getattr(final, k) for k in fields
        ):
            raise RecordTransactionError("file identity changed during read")
        return data, {
            "dev": after.st_dev,
            "ino": after.st_ino,
            "mode": stat.S_IMODE(after.st_mode),
            "bytes": len(data),
            "sha256": _digest(data),
        }
    finally:
        os.close(fd)


def _read_json(path, limit=MAX_MANIFEST_BYTES):
    data, _ = _snapshot(path)
    if len(data) > limit:
        raise RecordTransactionError("journal exceeds bound")
    try:
        result = json.loads(data, object_pairs_hook=_unique)
    except (ValueError, RecursionError) as exc:
        raise RecordTransactionError("invalid transaction journal") from exc
    if not isinstance(result, dict):
        raise RecordTransactionError("journal must be an object")
    return result, data


def read_request(path):
    """Bound CLI JSON input with the same exact regular-file reader."""
    data, _ = _snapshot(path)
    try:
        return json.loads(data, object_pairs_hook=_unique)
    except (ValueError, RecursionError) as exc:
        raise RecordTransactionError("invalid bounded transaction request") from exc


def _sync_dir(path):
    fd = os.open(
        _path(path),
        os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0),
    )
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _new_file(path, data, mode=0o600):
    fd = os.open(
        _path(path),
        os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0),
        mode,
    )
    try:
        with os.fdopen(fd, "wb", closefd=False) as out:
            out.write(data)
            out.flush()
            os.fchmod(fd, mode)
            os.fsync(fd)
    finally:
        os.close(fd)


def _replace_json(path, data):
    temp = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
    _new_file(temp, _json(data))
    os.replace(temp, path)
    _sync_dir(path.parent)


def project_for(path):
    """Find the existing project boundary; ordinary isolated files use parent."""
    path = Path(path).absolute()
    start = path if path.is_dir() else path.parent
    for parent in [start, *start.parents]:
        if (
            parent.parent.name == "projects"
            or (parent / STORE).exists()
            or (parent / "CONTEXT.md").is_file()
        ):
            return parent
    return start


@contextmanager
def _lock(project, *, exclusive=False):
    project = _path(project)
    key = str(project)
    held = _HELD.get()
    if key in held:
        if exclusive and not held[key]:
            raise RecordTransactionError(
                "cannot upgrade a managed read into a transaction"
            )
        yield
        return
    fd = os.open(
        project,
        os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0),
    )
    token = None
    try:
        deadline = time.monotonic() + 5
        while True:
            try:
                fcntl.flock(
                    fd, (fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH) | fcntl.LOCK_NB
                )
                break
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    raise RecordTransactionError(
                        "project record transaction is busy; bounded lock expired"
                    )
                time.sleep(0.01)
        if (os.fstat(fd).st_dev, os.fstat(fd).st_ino) != (
            project.stat().st_dev,
            project.stat().st_ino,
        ):
            raise RecordTransactionError("project directory changed while locking")
        token = _HELD.set({**held, key: exclusive})
        yield
    finally:
        if token is not None:
            _HELD.reset(token)
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)


def _pending(project):
    store = _path(project / STORE, project)
    if not store.exists():
        return
    if not store.is_dir():
        raise RecordTransactionError("record transaction store is not a directory")
    if (store / "active").exists() or (store / "active").is_symlink():
        raise RecordTransactionError(
            "unfinished record transaction; context_edit recover-transaction is required"
        )
    if not (store / "history.json").is_file():
        raise RecordTransactionError(
            "transaction history is missing; recovery evidence must be reconciled"
        )
    if _history(store)["active"] is not None:
        raise RecordTransactionError(
            "active transaction journal is missing; preserve records and reconcile evidence"
        )


@contextmanager
def managed(project, *, exclusive=False):
    project = _path(project)
    with _lock(project, exclusive=exclusive):
        _pending(project)
        yield


def is_managed(project, *, exclusive=False):
    key = str(Path(project).absolute())
    held = _HELD.get()
    return key in held and (not exclusive or held[key])


def guarded(parameter="project", *, error=None, exclusive=False):
    """Hold a stable managed-read boundary across the real consumer call."""

    def decorate(function):
        signature = inspect.signature(function)

        @wraps(function)
        def wrapper(*args, **kwargs):
            bound = signature.bind(*args, **kwargs)
            path = Path(bound.arguments[parameter])
            try:
                with managed(
                    path if path.is_dir() else project_for(path), exclusive=exclusive
                ):
                    return function(*args, **kwargs)
            except RecordTransactionError as exc:
                if error is not None:
                    raise error(str(exc)) from exc
                raise

        return wrapper

    return decorate


def _history(store):
    data, _ = _read_json(store / "history.json")
    if (
        set(data) != {"schema", "completed", "active"}
        or type(data["schema"]) is not int
        or data["schema"] != 1
        or not isinstance(data["completed"], dict)
        or len(data["completed"]) > MAX_HISTORY
    ):
        raise RecordTransactionError("invalid transaction history")
    active = data["active"]
    if active is not None and (
        not isinstance(active, dict)
        or set(active) != {"id", "digest"}
        or not isinstance(active["id"], str)
        or not re.fullmatch("[a-f0-9]{32}", active["id"])
        or not isinstance(active["digest"], str)
        or not re.fullmatch("[a-f0-9]{64}", active["digest"])
    ):
        raise RecordTransactionError("invalid active transaction identity")
    for key, value in data["completed"].items():
        if (
            not re.fullmatch("[a-f0-9]{32}", key)
            or not isinstance(value, str)
            or not re.fullmatch("[a-f0-9]{64}", value)
        ):
            raise RecordTransactionError("invalid completed transaction identity")
    return data


def _authority(project, board, native_payload, paths, expected=None):
    if not isinstance(native_payload, dict):
        raise RecordTransactionError("native payload must be an object")
    pm_scripts = (
        Path(__file__).resolve().parents[2] / "synthesis-project-management" / "scripts"
    )
    if str(pm_scripts) not in sys.path:
        sys.path.insert(0, str(pm_scripts))
    try:
        import run_admission
    except ImportError as exc:
        raise RecordTransactionError(
            "PM admission runtime is required for multi-file records"
        ) from exc

    try:
        return dict(
            (run_admission.admit_registry_paths if project.parent / "index.yaml" in paths else run_admission.admit_paths)(
                Path(board),
                project.name,
                project,
                paths,
                native_payload,
                expected_claim_hash=expected,
            )
        )
    except (OSError, RuntimeError, ValueError) as exc:
        raise RecordTransactionError(
            f"fresh exact record authority refused: {exc}"
        ) from exc


def _target(project, name):
    """One explicit registry target; arbitrary parent traversal remains refused."""
    if name == "@registry":
        if project.parent.name != "projects":
            raise RecordTransactionError("registry target needs an exact project directory")
        return _path(project.parent / "index.yaml", project.parent)
    return _path(project / name, project)


def _target_name(project, path):
    return "@registry" if path == project.parent / "index.yaml" else str(path.relative_to(project))


def registry_authorship(project, *, session_uuid, repository, branch, board, staged, head, staged_mode, head_mode=None):
    """Verify staged registry bytes against this seat's retained exact intent.

    This evidence never grants claims; the caller separately admits the active
    seat, physical repository and staged paths through the ordinary gate.
    """
    project = _path(project)
    if project.parent != Path(repository) / "projects":
        raise RecordTransactionError("registry authorship needs the exact owning project")
    with _lock(project.parent), managed(project):
        current, current_meta = _snapshot(_target(project, "@registry"))
        if current != staged:
            raise RecordTransactionError("registry working bytes differ from staged intent")
        history = _history(project / STORE)
        matches, total = [], 0
        for ident, digest in history["completed"].items():
            path = project / STORE / "completed" / ident / "manifest.json"
            manifest, raw = _read_json(path)
            total += len(raw)
            if total > MAX_TOTAL_BYTES:
                raise RecordTransactionError("registry authorship history exceeds bounded read")
            if _digest(raw) != digest:
                raise RecordTransactionError("registry transaction history digest differs")
            files = manifest.get("files")
            if not isinstance(files, list) or not 1 <= len(files) <= MAX_FILES or any(not isinstance(item, dict) for item in files):
                raise RecordTransactionError("invalid registry history target list")
            for item in files:
                after = item.get("after")
                if not isinstance(after, dict):
                    raise RecordTransactionError("invalid registry history target identity")
                if item.get("path") != "@registry" or after.get("sha256") != _digest(staged):
                    continue
                _manifest(path.parent, project, completed=True)
                if current_meta != after or staged_mode != ("100755" if after["mode"] & 0o111 else "100644"):
                    raise RecordTransactionError("registry staged or working mode/identity differs from intent")
                authority = manifest.get("authority", {})
                before = item.get("before")
                preimage_matches = (before is None and head is None and head_mode is None) or (
                    isinstance(before, dict) and head is not None and before.get("sha256") == _digest(head)
                    and head_mode == ("100755" if before["mode"] & 0o111 else "100644"))
                if (preimage_matches
                    and authority.get("session_uuid") == session_uuid
                    and authority.get("repository") == str(repository)
                    and authority.get("branch") == branch
                    and authority.get("board") == str(Path(board).absolute())
                    and manifest.get("project") == str(project)):
                    matches.append(ident)
        if len(matches) != 1:
            raise RecordTransactionError("staged registry lacks one exact clean-preimage intent by this seat")
        return matches[0]


def registry_git_state(project):
    """Bounded positive Git queries: absent is an empty successful tree lookup."""
    import subprocess
    pm = Path(__file__).resolve().parents[2] / "synthesis-project-management/scripts"
    if str(pm) not in sys.path:
        sys.path.insert(0, str(pm))
    import native_git
    repo = project.parent.parent
    rows = []
    for query in (("ls-tree", "HEAD", "--", "projects/index.yaml"),
                  ("ls-files", "--stage", "--", "projects/index.yaml")):
        try:
            result = native_git.run(["git", *query], cwd=repo, timeout=10)
        except subprocess.SubprocessError as exc:
            raise RecordTransactionError("registry Git preimage exceeds bounded query") from exc
        if result.returncode:
            raise RecordTransactionError("registry Git membership query failed")
        lines = result.stdout.decode("utf-8", errors="strict").splitlines()
        if len(lines) > 1 or (lines and (lines[0].split("\t")[-1] != "projects/index.yaml"
                or lines[0].split()[0] not in ("100644", "100755"))):
            raise RecordTransactionError("registry Git membership or mode is ambiguous")
        if lines and query[0] == "ls-files" and lines[0].split()[2] != "0":
            raise RecordTransactionError("registry index is unmerged")
        rows.append(lines[0].split()[0] if lines else None)
    return tuple(rows)


def _registry_clean(project, data, mode):
    # First-write custody binds bytes AND executable mode, never a shell window.
    import subprocess
    expected_mode = "100755" if mode & 0o111 else "100644"
    if registry_git_state(project) != (expected_mode, expected_mode):
        raise RecordTransactionError("registry preimage mode differs from HEAD or index; preserve foreign work")
    import native_git
    for spec in ("HEAD:projects/index.yaml", ":projects/index.yaml"):
        try:
            result = native_git.run(["git", "show", spec], cwd=project.parent.parent, timeout=10)
        except subprocess.SubprocessError as exc:
            raise RecordTransactionError("registry Git preimage exceeds bounded query") from exc
        if result.returncode or result.stdout != data:
            raise RecordTransactionError("registry preimage is not clean in HEAD and index; preserve foreign work")


def _matches(path, expected):
    try:
        _, actual = _snapshot(path)
    except FileNotFoundError:
        return expected is None
    return expected is not None and actual == expected


def _settle_creation(path, item):
    """Recover only the two exact names of our interrupted no-clobber link.

    No general hardlink permission: both journal-derived names must designate
    the staged inode, and its link count must be exactly two. A third link,
    changed bytes/mode, or replaced name remains an unresolved foreign effect.
    """
    if item["before"] is not None:
        return
    stage = Path(item["stage"])
    if not path.exists() or not stage.exists():
        return
    for candidate in (path, stage):
        _, actual = _snapshot(candidate, _links=2)
        if actual != item["after"]:
            raise RecordTransactionError(
                "ambiguous interrupted creation; preserve both names"
            )
    stage.unlink()
    _sync_dir(stage.parent)
    _sync_dir(path.parent)
    if not _matches(path, item["after"]):
        raise RecordTransactionError("created target changed during recovery")


def _manifest(active, project, *, completed=False):
    manifest, raw = _read_json(active / "manifest.json")
    if (
        set(manifest)
        != (
            {"schema", "id", "project", "project_identity", "authority", "files"}
            | ({"sources"} if manifest.get("schema") == 2 else set())
        )
        or type(manifest["schema"]) is not int
        or manifest["schema"] not in (1, 2)
    ):
        raise RecordTransactionError("invalid transaction manifest fields")
    if manifest["project"] != str(project) or not re.fullmatch(
        "[a-f0-9]{32}", str(manifest["id"])
    ):
        raise RecordTransactionError("transaction belongs to another project")
    st = project.stat()
    if manifest["project_identity"] != [st.st_dev, st.st_ino]:
        raise RecordTransactionError("original project directory was replaced")
    authority = manifest["authority"]
    required = (
        "claim_hash",
        "native_ref",
        "session_uuid",
        "project_id",
        "repository",
        "branch",
        "board",
    )
    if not isinstance(authority, dict) or any(
        not isinstance(authority.get(k), str) or not authority[k] for k in required
    ):
        raise RecordTransactionError("invalid original native authority binding")
    files = manifest["files"]
    if not isinstance(files, list) or not 1 <= len(files) <= MAX_FILES:
        raise RecordTransactionError("invalid transaction target count")
    paths, identities, total = set(), set(), 0
    for index, item in enumerate(files):
        if not isinstance(item, dict) or set(item) != {
            "path",
            "before",
            "after",
            "stage",
            "note",
            "lines",
        }:
            raise RecordTransactionError("invalid target record")
        if not isinstance(item["path"], str):
            raise RecordTransactionError("target path must be a string")
        path = _target(project, item["path"])
        if (
            item["path"] != _target_name(project, path)
            or STORE in Path(item["path"]).parts
        ):
            raise RecordTransactionError("invalid target relative path")
        expected_stage = (project / STORE / "active" if completed else active) / (str(index) + ".staged")
        if item["stage"] != str(expected_stage):
            raise RecordTransactionError("invalid staged target path")
        if str(path) in paths:
            raise RecordTransactionError("duplicate target path")
        paths.add(str(path))
        for phase in ["before", "after"]:
            value = item[phase]
            if phase == "before" and value is None and manifest["schema"] == 2:
                continue
            if not isinstance(value, dict) or set(value) != {
                "dev",
                "ino",
                "mode",
                "bytes",
                "sha256",
            }:
                raise RecordTransactionError("invalid target identity")
            if (
                any(
                    type(value[k]) is not int or value[k] < 0
                    for k in ["dev", "ino", "mode", "bytes"]
                )
                or value["bytes"] > MAX_FILE_BYTES
                or value["mode"] > 0o7777
                or not isinstance(value["sha256"], str)
                or not re.fullmatch("[a-f0-9]{64}", value["sha256"])
            ):
                raise RecordTransactionError("invalid target identity value")
        if item["before"] is not None:
            identity = (item["before"]["dev"], item["before"]["ino"])
            if (
                identity in identities
                or item["before"]["mode"] != item["after"]["mode"]
            ):
                raise RecordTransactionError("aliased target or changed final mode")
            identities.add(identity)
        elif item["after"]["mode"] not in (0o600, 0o644):
            raise RecordTransactionError(
                "new project records require a nonexecutable private or readable mode"
            )
        total += item["after"]["bytes"]
    if total > MAX_TOTAL_BYTES:
        raise RecordTransactionError("transaction exceeds aggregate byte bound")
    _check_custody(project, active, manifest)
    return manifest, _digest(raw)


def _check_custody(project, active, manifest):
    """Authenticate preserved source copies and their still-current inputs."""
    sources = manifest.get("sources", [])
    if not isinstance(sources, list) or len(sources) > 512:
        raise RecordTransactionError("source custody count exceeds bound")
    seen = set()
    total = sum(item["after"]["bytes"] for item in manifest.get("files", []))
    for index, item in enumerate(sources):
        if not isinstance(item, dict) or set(item) != {"path", "before", "archive"}:
            raise RecordTransactionError("invalid source custody record")
        relative = item["path"]
        if not isinstance(relative, str):
            raise RecordTransactionError("source path must be text")
        source = _path(project / relative, project)
        if (
            str(source.relative_to(project)) != relative
            or STORE in source.relative_to(project).parts
            or relative in seen
            or item["archive"] != str(index) + ".source"
        ):
            raise RecordTransactionError("source custody path is ambiguous")
        before = item["before"]
        if (
            not isinstance(before, dict)
            or set(before) != {"dev", "ino", "mode", "bytes", "sha256"}
            or any(
                type(before[k]) is not int or before[k] < 0
                for k in ("dev", "ino", "mode", "bytes")
            )
            or before["bytes"] > MAX_FILE_BYTES
            or before["mode"] > 0o7777
            or not isinstance(before["sha256"], str)
            or not re.fullmatch("[a-f0-9]{64}", before["sha256"])
        ):
            raise RecordTransactionError("invalid source custody identity")
        if relative in {entry["path"] for entry in manifest.get("files", [])}:
            raise RecordTransactionError("source custody overlaps effect target")
        seen.add(relative)
        data, original = _snapshot(source)
        archived, meta = _snapshot(active / "sources" / item["archive"])
        if original != item["before"] or data != archived or meta["mode"] != 0o600:
            raise RecordTransactionError("source or preserved custody changed")
        total += len(data)
        if total > MAX_TOTAL_BYTES:
            raise RecordTransactionError("source custody exceeds aggregate capacity")


def _project_identity(project, manifest):
    info = _path(project).stat()
    if [info.st_dev, info.st_ino] != manifest["project_identity"]:
        raise RecordTransactionError(
            "original project directory changed during transaction"
        )


def _finish(project, active, manifest, digest, history):
    _project_identity(project, manifest)
    _check_custody(project, active, manifest)
    for item in manifest["files"]:
        if not _matches(_target(project, item["path"]), item["after"]):
            raise RecordTransactionError(
                "final transaction readback differs; retained for reconciliation"
            )
    history["completed"][manifest["id"]] = digest
    history["active"] = None
    _replace_json(active.parent / "history.json", history)
    completed = active.parent / "completed"
    if not completed.exists():
        completed.mkdir(mode=0o700)
        _sync_dir(active.parent)
    _path(completed, project)
    destination = completed / manifest["id"]
    if destination.exists():
        raise RecordTransactionError("completed transaction already exists; no replay")
    os.rename(active, destination)
    _sync_dir(completed)
    _sync_dir(active.parent)
    return {
        "transaction": manifest["id"],
        "status": "committed",
        "files": len(manifest["files"]),
        "journal": str(destination),
    }


def _commit(project, active, manifest, digest, history, board, payload):
    _project_identity(project, manifest)
    _check_custody(project, active, manifest)
    paths = [_target(project, item["path"]) for item in manifest["files"]]
    expected = manifest["authority"]["claim_hash"]
    proof = _authority(project, board, payload, [*paths, project / STORE], expected)
    if any(
        proof.get(k) != manifest["authority"].get(k)
        for k in [
            "native_ref",
            "session_uuid",
            "project_id",
            "repository",
            "branch",
            "board",
        ]
    ):
        raise RecordTransactionError("transaction identity/checkout changed")
    # Validate every member before resuming any effect. Mixed old/new is an
    # expected interrupted commit, but a third state or inode is foreign work.
    declared = history["active"]
    if declared is not None and declared != {"id": manifest["id"], "digest": digest}:
        raise RecordTransactionError(
            "journal does not match the admitted active transaction"
        )
    pending = []
    # Reconcile exact stage links only after admission and journal binding.
    for item, path in zip(manifest["files"], paths):
        _settle_creation(path, item)
    for item, path in zip(manifest["files"], paths):
        if _matches(path, item["after"]):
            continue
        if not _matches(path, item["before"]) or not _matches(
            Path(item["stage"]), item["after"]
        ):
            raise RecordTransactionError(
                "ambiguous target or staging effect; preserving all bytes"
            )
        pending.append((item, path))
    if manifest["id"] in history["completed"]:
        if history["completed"][manifest["id"]] != digest or pending:
            raise RecordTransactionError("completed transaction replay refused")
        return _finish(project, active, manifest, digest, history)
    if history["active"] is None:
        history["active"] = {"id": manifest["id"], "digest": digest}
        _replace_json(active.parent / "history.json", history)
    for item, path in pending:
        _project_identity(project, manifest)
        _check_custody(project, active, manifest)
        _authority(project, board, payload, [*paths, project / STORE], expected)
        if not _matches(path, item["before"]) or not _matches(
            Path(item["stage"]), item["after"]
        ):
            raise RecordTransactionError(
                "source changed before replacement; recovery required"
            )
        if item["before"] is None:
            # Atomic absence check: unlike replace(), link never overwrites a
            # concurrently-created target. Recovery owns only these two names.
            os.link(item["stage"], path, follow_symlinks=False)
            _sync_dir(path.parent)
            _settle_creation(path, item)
        else:
            os.replace(item["stage"], path)
            _sync_dir(path.parent)
    _authority(project, board, payload, [*paths, project / STORE], expected)
    return _finish(project, active, manifest, digest, history)


def recover(project, *, board, native_payload):
    """Reconcile the original committed intent; never replay an arbitrary file."""
    project = _path(project)
    with _lock(project.parent if project.parent.name == "projects" else project, exclusive=True), _lock(project, exclusive=True):
        store = _path(project / STORE, project)
        active = _path(store / "active", project)
        if not active.is_dir():
            raise RecordTransactionError("no active transaction to recover")
        history = _history(store)
        manifest, digest = _manifest(active, project)
        commit, _ = _read_json(active / "commit.json")
        if commit != {"manifest_sha256": digest}:
            raise RecordTransactionError(
                "missing or corrupt durable commit decision; no effect replay"
            )
        return _commit(
            project, active, manifest, digest, history, board, native_payload
        )


def apply(
    project,
    requests,
    *,
    board,
    native_payload,
    dry_run=False,
    intent_id=None,
    source_custody=None,
    expected_claim_hash=None,
):
    """Preflight all files, publish durable intent, then recoverably commit."""
    import context_edit

    project = _path(project)
    if intent_id is not None and (
        not isinstance(intent_id, str) or not re.fullmatch("[a-f0-9]{32}", intent_id)
    ):
        raise RecordTransactionError("invalid caller intent identity")
    if not isinstance(requests, list) or not 1 <= len(requests) <= MAX_FILES:
        raise RecordTransactionError("files must be a nonempty bounded array")
    with _lock(project.parent if any(isinstance(q, dict) and q.get("file") == "@registry" for q in requests) else project, exclusive=True), _lock(project, exclusive=True):
        _pending(project)
        prepared = []
        seen = set()
        inodes = set()
        total = 0
        for request in requests:
            if (
                not isinstance(request, dict)
                or set(request)
                - {
                    "file",
                    "edits",
                    "max_lines",
                    "allow_header_lag",
                    "allow_stale_body",
                    "state_reviewed",
                    "expected_sha256",
                    "create",
                }
                or "file" not in request
                or (("edits" in request) == ("create" in request))
            ):
                raise RecordTransactionError("invalid transaction request")
            if (
                not isinstance(request["file"], str)
                or Path(request["file"]).is_absolute()
            ):
                raise RecordTransactionError("target must be a project-relative file")
            path = _target(project, request["file"])
            if STORE in Path(request["file"]).parts or str(path) in seen:
                raise RecordTransactionError("duplicate/reserved transaction target")
            seen.add(str(path))
            if "create" in request:
                if request["file"] == "@registry" and (len(requests) != 1 or registry_git_state(project) != (None, None)):
                    raise RecordTransactionError("registry bootstrap requires one absent HEAD/index target")
                if set(request) != {"file", "create"}:
                    raise RecordTransactionError("creation cannot carry edit overrides")
                create = request["create"]
                if (
                    not isinstance(create, dict)
                    or set(create) != {"text", "mode"}
                    or not isinstance(create["text"], str)
                    or type(create["mode"]) is not int
                    or create["mode"] not in (0o600, 0o644)
                ):
                    raise RecordTransactionError(
                        "bounded text and nonexecutable record mode required"
                    )
                if not _matches(path, None) or not _path(path.parent).is_dir():
                    raise RecordTransactionError(
                        "new record target must be absent with an existing parent"
                    )
                before = None
                output = create["text"].encode("utf-8")
                if request["file"] == "@registry":
                    context_edit._registry_nodes(create["text"])
                    if project.name not in context_edit._registry_nodes(create["text"])[1]:
                        raise RecordTransactionError("bootstrap must register the already authenticated owning project")
                note = "explicit additive record creation"
                lines = context_edit._check_budget(create["text"], None, path)
            else:
                data, before = _snapshot(path)
                if request["file"] == "@registry":
                    if "expected_sha256" not in request:
                        raise RecordTransactionError("registry requires an exact reviewed preimage")
                    _registry_clean(project, data, before["mode"])
                expected_sha256 = request.get("expected_sha256")
                if "expected_sha256" in request and (
                    not isinstance(expected_sha256, str)
                    or not re.fullmatch("[0-9a-f]{64}", expected_sha256)
                    or before["sha256"] != expected_sha256
                ):
                    raise RecordTransactionError(
                        "reviewed source hash changed before transaction preflight"
                    )
                identity = (before["dev"], before["ino"])
                if identity in inodes:
                    raise RecordTransactionError("aliased targets")
                inodes.add(identity)
                original = data.decode("utf-8")
                edited = original
                edits = request["edits"]
                if not isinstance(edits, list) or not 1 <= len(edits) <= 1000:
                    raise RecordTransactionError(
                        "edits must be a bounded nonempty list"
                    )
                for edit in edits:
                    edited = context_edit._edit_in_memory(edited, edit)
                if edited == original:
                    raise RecordTransactionError("file edit leaves bytes unchanged")
                limit = request.get("max_lines")
                if limit is not None and (type(limit) is not int or limit < 0):
                    raise RecordTransactionError("invalid line budget")
                flags = [
                    request.get(k, False)
                    for k in ["allow_header_lag", "allow_stale_body", "state_reviewed"]
                ]
                if any(type(flag) is not bool for flag in flags):
                    raise RecordTransactionError("override flags must be boolean")
                lines = context_edit._check_budget(edited, limit, path)
                note = context_edit._coherence_gate(path, original, edited, *flags)
                output = edited.encode("utf-8")
            if request["file"] == "@registry":
                context_edit._registry_nodes(output.decode("utf-8"))
                pm = Path(__file__).resolve().parents[2] / "synthesis-project-management/scripts"
                if str(pm) not in sys.path:
                    sys.path.insert(0, str(pm))
                from project_recipient import registry_entries
                registry_entries(output.decode("utf-8"))
            total += len(output)
            if len(output) > MAX_FILE_BYTES or total > MAX_TOTAL_BYTES:
                raise RecordTransactionError("transaction byte bound exceeded")
            prepared.append(
                (
                    path,
                    before,
                    output,
                    note,
                    lines,
                    request.get("create", {}).get("mode"),
                )
            )
        source_custody = [] if source_custody is None else source_custody
        if not isinstance(source_custody, list) or len(source_custody) > 512:
            raise RecordTransactionError("bounded preserved source list required")
        sources, source_names = [], set()
        for item in source_custody:
            if (
                not isinstance(item, dict)
                or set(item) != {"file", "expected"}
                or not isinstance(item["file"], str)
            ):
                raise RecordTransactionError(
                    "exact source custody declaration required"
                )
            source = _path(project / item["file"], project)
            if (
                str(source.relative_to(project)) != item["file"]
                or STORE in source.relative_to(project).parts
                or str(source) in seen
                or str(source) in source_names
            ):
                raise RecordTransactionError(
                    "source custody overlaps an effect or repeated input"
                )
            data, meta = _snapshot(source)
            if meta != item["expected"]:
                raise RecordTransactionError("source custody changed since preview")
            total += len(data)
            if total > MAX_TOTAL_BYTES:
                raise RecordTransactionError(
                    "combined output and custody exceeds byte budget"
                )
            sources.append((source, meta, data))
            source_names.add(str(source))
        paths = [item[0] for item in prepared]
        ident = intent_id or uuid.uuid4().hex
        store = _path(project / STORE, project)
        # An interrupted preparation has no published effect intent. Preserve it
        # and admit a distinct preparation for the same caller intent; never
        # overwrite or infer authority from the earlier staged bytes.
        attempt = uuid.uuid4().hex
        initial = project / (STORE + ".init-" + ident + "-" + attempt)
        preparation = "preparing-" + ident + "-" + attempt
        for parent, prefix in ((project, STORE + ".init-"), (store, "preparing-")):
            if not parent.exists():
                continue
            count = 0
            for member in parent.iterdir():
                if member.name.startswith(prefix):
                    count += 1
                    if count >= 64:
                        raise RecordTransactionError(
                            "retained preparation capacity reached; preserve and reconcile custody"
                        )
        metadata = [
            store,
            store / "history.json",
            store / preparation,
            store / "active",
            store / "completed" / ident,
        ]
        if not store.exists():
            metadata.extend([initial, initial / "history.json"])
        proof = _authority(
            project, board, native_payload, [*paths, *metadata], expected_claim_hash
        )
        for path, before, *_ in prepared:
            if not _matches(path, before):
                raise RecordTransactionError("source changed during preflight")
        if dry_run:
            return {"status": "dry-run", "files": len(prepared), "changed": False}
        store = _path(project / STORE, project)
        if not store.exists():
            initial.mkdir(mode=0o700)
            _new_file(
                initial / "history.json",
                _json({"schema": 1, "completed": {}, "active": None}),
            )
            _sync_dir(initial)
            os.rename(initial, store)
            _sync_dir(project)
        history = _history(store)
        if ident in history["completed"]:
            raise RecordTransactionError(
                "caller intent already committed; verify its original receipt"
            )
        if len(history["completed"]) >= MAX_HISTORY:
            raise RecordTransactionError(
                "transaction history capacity reached; preserve and rotate through owner"
            )
        staging = store / preparation
        staging.mkdir(mode=0o700)
        files = []
        for index, (path, before, data, note, lines, create_mode) in enumerate(
            prepared
        ):
            stage = staging / (str(index) + ".staged")
            _new_file(
                stage, data, before["mode"] if before is not None else create_mode
            )
            _, after = _snapshot(stage)
            if (
                before["dev"] if before is not None else path.parent.stat().st_dev
            ) != after["dev"]:
                raise RecordTransactionError("transaction requires one filesystem")
            files.append(
                {
                    "path": _target_name(project, path),
                    "before": before,
                    "after": after,
                    "stage": str(store / "active" / stage.name),
                    "note": note,
                    "lines": lines,
                }
            )
        source_records = []
        if sources:
            (staging / "sources").mkdir(mode=0o700)
            for index, (source, before, data) in enumerate(sources):
                archive = str(index) + ".source"
                _new_file(staging / "sources" / archive, data, 0o600)
                if _snapshot(staging / "sources" / archive)[0] != data or not _matches(
                    source, before
                ):
                    raise RecordTransactionError(
                        "source custody write or original readback differs"
                    )
                source_records.append(
                    {
                        "path": str(source.relative_to(project)),
                        "before": before,
                        "archive": archive,
                    }
                )
            _sync_dir(staging / "sources")
        info = project.stat()
        manifest = {
            "schema": 2
            if sources or any(item["before"] is None for item in files)
            else 1,
            "id": ident,
            "project": str(project),
            "project_identity": [info.st_dev, info.st_ino],
            "authority": proof,
            "files": files,
        }
        if manifest["schema"] == 2:
            manifest["sources"] = source_records
        raw = _json(manifest)
        if len(raw) > MAX_MANIFEST_BYTES:
            raise RecordTransactionError("manifest exceeds bounded capacity")
        _new_file(staging / "manifest.json", raw)
        digest = _digest(raw)
        _new_file(staging / "commit.json", _json({"manifest_sha256": digest}))
        _sync_dir(staging)
        # Every snapshot/claim is checked after staging and before the first
        # target mutation. Staging artifacts remain owned evidence on failure.
        _authority(
            project,
            board,
            native_payload,
            [*paths, project / STORE],
            proof["claim_hash"],
        )
        for path, before, *_ in prepared:
            if not _matches(path, before):
                raise RecordTransactionError("source changed before commit decision")
        active = store / "active"
        os.rename(staging, active)
        _sync_dir(store)
        return _commit(
            project, active, manifest, digest, history, board, native_payload
        )
