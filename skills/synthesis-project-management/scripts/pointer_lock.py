#!/usr/bin/env python3
"""Cross-process lock shared by active-project pointer writers and archivists."""

from __future__ import annotations

import os
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

try:
    import fcntl
except ImportError:  # pragma: no cover - Windows only
    fcntl = None

try:
    import msvcrt
except ImportError:  # pragma: no cover - POSIX only
    msvcrt = None


@contextmanager
def locked_pointer(pointer: Path) -> Iterator[None]:
    """Serialize pointer validation/replacement with ownership-check/archive."""
    parent = pointer.parent
    parent.mkdir(parents=True, exist_ok=True)
    if parent.is_symlink():
        raise ValueError(f"active-project parent must not be a symlink: {parent}")
    lock_path = parent / ".active-project.lock"
    if lock_path.is_symlink():
        raise ValueError(f"active-project lock must not be a symlink: {lock_path}")
    with lock_path.open("a+b") as lock:
        if fcntl is not None:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        elif msvcrt is not None:  # pragma: no cover - Windows only
            if lock.seek(0, os.SEEK_END) == 0:
                lock.write(b"\0")
                lock.flush()
            lock.seek(0)
            msvcrt.locking(lock.fileno(), msvcrt.LK_LOCK, 1)
        else:  # pragma: no cover - unsupported Python platform
            raise RuntimeError("active-project locking is unavailable on this platform")
        try:
            yield
        finally:
            if fcntl is not None:
                fcntl.flock(lock.fileno(), fcntl.LOCK_UN)
            elif msvcrt is not None:  # pragma: no cover - Windows only
                lock.seek(0)
                msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)
