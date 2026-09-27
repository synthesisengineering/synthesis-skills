"""Canonical stdlib-only owner of bounded coordination/admission locks.

Authority remains with each caller. This file owns only the existing no-follow,
inode-checked flock protocol; admission re-exports its exception and function.
"""
from __future__ import annotations
from contextlib import contextmanager
import fcntl
import os
from pathlib import Path
import stat
import time


class AdmissionError(ValueError):
    pass



@contextmanager
def bounded_lock(path: Path, *, timeout: float = 5.0, create: bool = True):
    """Bound the existing flock protocol; optionally open without mutations.

    Noncreating admission is for an already-existing lock only. An absent,
    replaced or nonregular inode never becomes permission to create a new lock.
    The caller still performs current authority validation inside the lock.
    """
    if type(create) is not bool or type(timeout) not in (int, float) or not 0 < timeout < float("inf"):
        raise AdmissionError("lock mode and finite positive timeout are required")
    path = Path(path).absolute()
    def ancestors():
        if any(parent.is_symlink() for parent in path.parents):
            raise AdmissionError("unsafe lock ancestor")
    def regular_info():
        ancestors()
        try:
            info = path.lstat()
        except OSError as exc:
            raise AdmissionError("existing lock disappeared or is unavailable") from exc
        if not stat.S_ISREG(info.st_mode):
            raise AdmissionError("lock path must be a regular file")
        return info
    ancestors()
    before = None
    if create:
        path.parent.mkdir(parents=True, exist_ok=True)
        ancestors()
        try:
            before = path.lstat()
        except FileNotFoundError:
            pass
        if before is not None and not stat.S_ISREG(before.st_mode):
            raise AdmissionError("lock path must be a regular file")
    else:
        before = regular_info()
    flags = os.O_NONBLOCK | os.O_NOFOLLOW | (os.O_RDWR | os.O_CREAT if create else os.O_RDONLY)
    try:
        fd = os.open(path, flags, 0o600)
    except OSError as exc:
        raise AdmissionError("lock could not be opened safely") from exc
    acquired = False
    def unchanged():
        current = regular_info()
        actual = os.fstat(fd)
        if (not stat.S_ISREG(actual.st_mode) or (current.st_dev, current.st_ino) != (actual.st_dev, actual.st_ino)
                or (before is not None and (before.st_dev, before.st_ino) != (actual.st_dev, actual.st_ino))):
            raise AdmissionError("lock inode changed while acquiring it")
    try:
        unchanged()
        deadline = time.monotonic() + timeout
        while not acquired:
            unchanged()
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                acquired = True
                unchanged()
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    raise AdmissionError("timed out acquiring the authority/state lock")
                time.sleep(min(0.01, max(0, deadline - time.monotonic())))
        yield
    finally:
        if acquired:
            fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)

