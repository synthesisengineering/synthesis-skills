"""Bounded local first-run records owned by the onboarding engine.

No provider, telemetry, shell execution or project registration. Descriptor walks
refuse links and special files; a finite lock serializes cooperating consumers.
"""

from __future__ import annotations

from contextlib import contextmanager
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import time
import uuid

from system_contract import ContractError

MAX_RECORD_BYTES = 512 * 1024
MAX_ARTIFACT_BYTES = 1024 * 1024
MAX_RECORDS = 256
LOCK_SECONDS = 10
IDENTIFIER = re.compile(r"[a-f0-9]{32}")


def digest(value):
    return hashlib.sha256(
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode()
    ).hexdigest()


def identity(info):
    return [
        info.st_dev,
        info.st_ino,
        info.st_mode,
        info.st_uid,
        info.st_nlink,
        info.st_size,
        info.st_mtime_ns,
        info.st_ctime_ns,
    ]


def _path(path):
    path = Path(path)
    if (
        not path.is_absolute()
        or ".." in path.parts
        or path != Path(os.path.normpath(path))
    ):
        raise ContractError("first-run path must be absolute without traversal")
    return path


@contextmanager
def directory(path, *, create=False, guards=None):
    path = _path(path)
    fd = os.open("/", os.O_RDONLY | os.O_DIRECTORY)
    chain = []
    try:
        for name in path.parts[1:]:
            if create:
                try:
                    os.mkdir(name, 0o700, dir_fd=fd)
                    os.fsync(fd)
                except FileExistsError:
                    pass
            parent = fd
            info = os.stat(name, dir_fd=parent, follow_symlinks=False)
            if not stat.S_ISDIR(info.st_mode):
                raise ContractError("first-run path crosses a link or non-directory")
            fd = os.open(
                name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent
            )
            chain.append((parent, name, fd, identity(info)[:4]))
            if identity(info)[:4] != identity(os.fstat(fd))[:4]:
                raise ContractError("first-run directory changed during open")
        if os.fstat(fd).st_uid != os.getuid():
            raise ContractError("first-run directory has a foreign owner")

        def validate_ancestry():
            try:
                for parent, name, child, expected in chain:
                    if (
                        identity(os.stat(name, dir_fd=parent, follow_symlinks=False))[
                            :4
                        ]
                        != expected
                        or identity(os.fstat(child))[:4] != expected
                    ):
                        raise ContractError("first-run directory identity changed")
            except OSError as exc:
                raise ContractError(
                    "first-run directory ancestry is unavailable"
                ) from exc

        validate_ancestry()
        if guards is not None:
            guards.append(validate_ancestry)
        yield fd
        validate_ancestry()
    except ContractError:
        raise
    except (OSError, ValueError) as exc:
        raise ContractError("first-run directory is unavailable or changed") from exc
    finally:
        for parent, _, _, _ in chain:
            os.close(parent)
        os.close(fd)


def _read_at(fd, name, maximum):
    info = os.stat(name, dir_fd=fd, follow_symlinks=False)
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_size > maximum:
        raise ContractError("first-run input must be a bounded regular unlinked file")
    handle = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=fd)
    try:
        if identity(info) != identity(os.fstat(handle)):
            raise ContractError("first-run input changed before reading")
        chunks = []
        remaining = maximum + 1
        while remaining:
            chunk = os.read(handle, min(65536, remaining))
            if not chunk:
                break
            chunks.append(chunk)
            remaining -= len(chunk)
        data = b"".join(chunks)
        if (
            len(data) > maximum
            or identity(info) != identity(os.fstat(handle))
            or identity(info)
            != identity(os.stat(name, dir_fd=fd, follow_symlinks=False))
        ):
            raise ContractError(
                "first-run input changed while reading or exceeds limit"
            )
        return data, identity(info)
    finally:
        os.close(handle)


def read_file(path, maximum=MAX_RECORD_BYTES):
    path = _path(path)
    try:
        with directory(path.parent) as fd:
            return _read_at(fd, path.name, maximum)
    except OSError as exc:
        raise ContractError("first-run input is unavailable") from exc


def decode(data):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ContractError("first-run JSON has duplicate fields")
            result[key] = value
        return result

    try:
        return json.loads(
            data,
            object_pairs_hook=pairs,
            parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)),
        )
    except (ValueError, UnicodeError) as exc:
        raise ContractError("first-run JSON is invalid") from exc


def home_identity(state):
    with directory(state.home) as fd:
        info = os.fstat(fd)
        return {
            "path": str(state.home),
            "device": info.st_dev,
            "inode": info.st_ino,
            "uid": info.st_uid,
            "mode": stat.S_IMODE(info.st_mode),
        }


class Store:
    def __init__(self, state):
        self.path = state.state_dir / "first-run"
        self.fd = None
        self.lock_identity = None
        self.ancestry_guard = None

    @contextmanager
    def locked(self):
        guards = []
        with directory(self.path, create=True, guards=guards) as fd:
            lock = os.open(
                "owner.lock",
                os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW | os.O_NONBLOCK,
                0o600,
                dir_fd=fd,
            )
            try:
                info = os.fstat(lock)
                if (
                    not stat.S_ISREG(info.st_mode)
                    or info.st_nlink != 1
                    or info.st_uid != os.getuid()
                ):
                    raise ContractError("first-run lock is not exclusively owned")
                deadline = time.monotonic() + LOCK_SECONDS
                while True:
                    try:
                        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                        break
                    except BlockingIOError:
                        if time.monotonic() >= deadline:
                            raise ContractError(
                                "first-run owner is busy; no effect admitted"
                            )
                        time.sleep(0.02)
                if (
                    identity(os.stat("owner.lock", dir_fd=fd, follow_symlinks=False))[
                        :5
                    ]
                    != identity(info)[:5]
                ):
                    raise ContractError("first-run lock identity changed")
                self.fd = fd
                self.lock_identity = identity(info)[:5]
                self.ancestry_guard = guards[0]
                yield self
            finally:
                self.fd = None
                self.lock_identity = None
                self.ancestry_guard = None
                os.close(lock)

    def name(self, kind, record_id):
        if (
            kind not in {"journey", "study"}
            or not isinstance(record_id, str)
            or not IDENTIFIER.fullmatch(record_id)
        ):
            raise ContractError("first-run record identifier is invalid")
        if self.fd is None:
            raise ContractError("first-run record requires its owner lock")
        self.ancestry_guard()
        try:
            held = identity(
                os.stat("owner.lock", dir_fd=self.fd, follow_symlinks=False)
            )[:5]
        except OSError as exc:
            raise ContractError("first-run lock pathname is unavailable") from exc
        if held != self.lock_identity:
            raise ContractError("first-run lock pathname changed; no effect admitted")
        return kind + "-" + record_id + ".json"

    def read(self, kind, record_id):
        name = self.name(kind, record_id)
        try:
            data, _ = _read_at(self.fd, name, MAX_RECORD_BYTES)
        except FileNotFoundError:
            raise ContractError("first-run record does not exist") from None
        value = decode(data)
        if (
            not isinstance(value, dict)
            or set(value) != {"body", "sha256"}
            or not isinstance(value["body"], dict)
            or value["sha256"] != digest(value["body"])
        ):
            raise ContractError("first-run record integrity failed")
        body = value["body"]
        if (
            type(body.get("schema_version")) is not int
            or body["schema_version"] != 1
            or body.get("id") != record_id
            or body.get("kind") != kind
        ):
            raise ContractError("first-run record identity failed")
        return body

    def write(self, body, *, expected=None):
        name = self.name(body["kind"], body["id"])
        try:
            before, inode = _read_at(self.fd, name, MAX_RECORD_BYTES)
        except FileNotFoundError:
            before = inode = None
        if expected is None:
            if before is not None:
                raise ContractError("first-run record already exists")
            with os.scandir(self.fd) as entries:
                count = 0
                for entry in entries:
                    count += 1
                    if count >= MAX_RECORDS + 1:
                        raise ContractError(
                            "first-run record capacity reached; review retention"
                        )
        elif before is None or decode(before).get("sha256") != digest(expected):
            raise ContractError("first-run record changed before write")
        data = (
            json.dumps(
                {"body": body, "sha256": digest(body)},
                sort_keys=True,
                ensure_ascii=False,
                allow_nan=False,
            )
            + "\n"
        ).encode()
        if len(data) > MAX_RECORD_BYTES:
            raise ContractError("first-run record exceeds byte limit")
        temporary = "." + name + ".prepared-" + uuid.uuid4().hex
        handle = os.open(
            temporary,
            os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW,
            0o600,
            dir_fd=self.fd,
        )
        try:
            view = memoryview(data)
            while view:
                written = os.write(handle, view)
                if written <= 0:
                    raise ContractError("first-run record write did not advance")
                view = view[written:]
            os.fsync(handle)
        finally:
            os.close(handle)
        # Recheck the exact pathname before replacing only this owner's record.
        try:
            current = identity(os.stat(name, dir_fd=self.fd, follow_symlinks=False))
        except FileNotFoundError:
            current = None
        if current != inode:
            raise ContractError(
                "first-run record changed during preparation; prepared bytes retained"
            )
        self.name(body["kind"], body["id"])
        os.replace(temporary, name, src_dir_fd=self.fd, dst_dir_fd=self.fd)
        os.fsync(self.fd)

    def prepared(self, kind, record_id):
        """Inspect only exact record-owned crash preparations before erasure."""
        prefix = "." + self.name(kind, record_id) + ".prepared-"
        result = []
        ordinary_count = 0
        with os.scandir(self.fd) as entries:
            for entry in entries:
                if not entry.name.startswith(prefix):
                    ordinary_count += 1
                    # Count every other entry, including foreign names. Exact
                    # owned preparations have their separate existing ceiling,
                    # so a full directory can still recover a prepared write.
                    if ordinary_count > MAX_RECORDS + 1:
                        raise ContractError("first-run directory capacity exceeded")
                    continue
                if len(result) >= MAX_RECORDS:
                    raise ContractError("first-run preparation capacity exceeded")
                data, inode = _read_at(self.fd, entry.name, MAX_RECORD_BYTES)
                value = decode(data)
                body = value.get("body") if isinstance(value, dict) else None
                if (
                    not isinstance(body, dict)
                    or value.get("sha256") != digest(body)
                    or body.get("id") != record_id
                    or body.get("kind") != kind
                ):
                    raise ContractError(
                        "first-run preparation is foreign or corrupt; no erasure"
                    )
                result.append((entry.name, inode))
        return result

    def erase_prepared(self, prepared):
        for name, inode in prepared:
            match = re.fullmatch(
                r"\.(journey|study)-([a-f0-9]{32})\.json\.prepared-[a-f0-9]{32}", name
            )
            if not match:
                raise ContractError("preparation name is not an exact owned record")
            self.name(match.group(1), match.group(2))
            if identity(os.stat(name, dir_fd=self.fd, follow_symlinks=False)) != inode:
                raise ContractError("prepared record changed before authorized erasure")
            os.unlink(name, dir_fd=self.fd)
            os.fsync(self.fd)

    def exists(self, kind, record_id):
        name = self.name(kind, record_id)
        try:
            os.stat(name, dir_fd=self.fd, follow_symlinks=False)
            return True
        except FileNotFoundError:
            return False
