"""Finite process ownership for explicitly requested coordination effects.

This owns the child process group, not a sandbox. Existing OS permissions and
hooks still apply; deliberate session escape is outside process-group custody.
"""

import math
import os
from pathlib import Path
import selectors
import signal
import stat
import subprocess
import time


class EffectInterrupted(RuntimeError):
    """Cancellation must propagate rather than be consumed as selector EINTR."""


def run(command, *, cwd, timeout=60, output_bytes=1024 * 1024, pass_fds=()):
    if (
        not isinstance(command, list)
        or not command
        or any(not isinstance(x, str) or not x or "\0" in x for x in command)
    ):
        raise ValueError("an explicit nonempty command argv is required")
    if (
        isinstance(timeout, bool)
        or not isinstance(timeout, (int, float))
        or not math.isfinite(timeout)
        or not 0 < timeout <= 900
    ):
        raise ValueError("effect timeout must be finite and at most 900 seconds")
    if type(output_bytes) is not int or not 0 < output_bytes <= 1024 * 1024:
        raise ValueError("effect capture limit must be at most one MiB")
    # Only an explicit, bounded anonymous snapshot may cross process creation.
    # No descriptor is inherited by default; pipes/sockets/path-linked files
    # are not a byte-custody transport and remain refused.
    if not isinstance(pass_fds, tuple) or len(pass_fds) > 1:
        raise ValueError("at most one anonymous snapshot descriptor is allowed")
    for descriptor in pass_fds:
        if type(descriptor) is not int or descriptor < 3:
            raise ValueError("invalid anonymous snapshot descriptor")
        info = os.fstat(descriptor)
        if (
            not stat.S_ISREG(info.st_mode)
            or info.st_nlink != 0
            or info.st_uid != os.getuid()
            or info.st_size > 34 * 1024 * 1024
        ):
            raise ValueError("unsafe or oversized anonymous snapshot descriptor")
    started = time.monotonic()
    output = bytearray()
    process = None
    old = {}

    def interrupted(signum, _frame):
        raise EffectInterrupted(f"coordination effect interrupted by signal {signum}")

    try:
        for sig in (signal.SIGINT, signal.SIGTERM):
            old[sig] = signal.signal(sig, interrupted)
        process = subprocess.Popen(
            command,
            cwd=Path(cwd),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            start_new_session=True,
            pass_fds=pass_fds,
        )
        with selectors.DefaultSelector() as selected:
            selected.register(process.stdout, selectors.EVENT_READ)
            while selected.get_map():
                remaining = timeout - (time.monotonic() - started)
                if remaining <= 0:
                    raise TimeoutError("coordination effect exceeded its time ceiling")
                for key, _ in selected.select(min(0.1, remaining)):
                    block = os.read(
                        key.fileobj.fileno(), min(65536, output_bytes - len(output) + 1)
                    )
                    if not block:
                        selected.unregister(key.fileobj)
                    else:
                        output.extend(block)
                        if len(output) > output_bytes:
                            raise ValueError(
                                "coordination effect exceeded its output ceiling"
                            )
            code = process.wait(
                timeout=max(0.001, timeout - (time.monotonic() - started))
            )
        return subprocess.CompletedProcess(
            command, code, output.decode("utf-8", errors="replace"), ""
        )
    finally:
        # Another cancellation cannot interrupt bounded cleanup and strand a child.
        # Restore the caller's handlers even if cleanup itself reports a failure.
        try:
            for sig in old:
                signal.signal(sig, signal.SIG_IGN)
            if process is not None:
                # Never wait on an unbounded inherited pipe or leave a hook child
                # behind after timeout, interruption, or a successful parent exit.
                try:
                    os.killpg(process.pid, signal.SIGTERM)
                except ProcessLookupError:
                    pass
                try:
                    process.wait(timeout=0.5)
                except subprocess.TimeoutExpired:
                    pass
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                process.wait(timeout=2)
                if process.stdout is not None:
                    process.stdout.close()
        finally:
            for sig, handler in old.items():
                signal.signal(sig, handler)
