"""Finite process ownership for explicitly requested coordination effects.

This owns the child process group, not a sandbox. Existing OS permissions and
hooks still apply; deliberate session escape is outside process-group custody.
"""

import json
import hashlib
import marshal
import math
import os
from pathlib import Path
import selectors
import signal
import stat
import subprocess
import time
import sys
import tempfile
import threading


class EffectInterrupted(RuntimeError):
    """Cancellation must propagate rather than be consumed as selector EINTR."""


def _validate(command, timeout, output_bytes, pass_fds):
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


def run(command, *, cwd, timeout=60, output_bytes=1024 * 1024, pass_fds=()):
    _validate(command, timeout, output_bytes, pass_fds)
    if threading.current_thread() is not threading.main_thread():
        return _thread_run(
            command,
            cwd=cwd,
            timeout=timeout,
            output_bytes=output_bytes,
            pass_fds=pass_fds,
        )
    return _run(
        command, cwd=cwd, timeout=timeout, output_bytes=output_bytes, pass_fds=pass_fds
    )


def _run(
    command, *, cwd, timeout, output_bytes, pass_fds, lifeline=None, announce=None
):
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
        if announce is not None:
            announce(process.pid)
        with selectors.DefaultSelector() as selected:
            selected.register(process.stdout, selectors.EVENT_READ)
            if lifeline is not None:
                selected.register(lifeline, selectors.EVENT_READ)
            output_open = True
            while output_open or process.poll() is None:
                remaining = timeout - (time.monotonic() - started)
                if remaining <= 0:
                    raise TimeoutError("coordination effect exceeded its time ceiling")
                for key, _ in selected.select(min(0.1, remaining)):
                    if lifeline is not None and key.fd == lifeline:
                        os.read(lifeline, 1)
                        raise EffectInterrupted("coordination caller lifeline ended")
                    block = os.read(
                        key.fileobj.fileno(), min(65536, output_bytes - len(output) + 1)
                    )
                    if not block:
                        selected.unregister(key.fileobj)
                        output_open = False
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


# Worker-thread calls must not touch process-global signal handlers. The same
# owner runs in its own main thread and observes parent-death EOF, so this is
# not a signal-skip path. This private transport is neither a shell nor a grant.
_PROTOCOL_BYTES = 8 * 1024 * 1024
_CONFIG_BYTES = 1024 * 1024


def _thread_run(command, *, cwd, timeout, output_bytes, pass_fds):
    deadline = time.monotonic() + timeout
    config = {
        "command": command,
        "cwd": str(Path(cwd).absolute()),
        "deadline": deadline,
        "output_bytes": output_bytes,
        "pass_fds": list(pass_fds),
    }
    raw = json.dumps(config, allow_nan=False).encode()
    if len(raw) > _CONFIG_BYTES:
        raise ValueError("coordination thread request exceeds byte ceiling")
    process = None
    capture = bytearray()
    child_pid = None
    try:
        with tempfile.TemporaryFile() as snapshot, tempfile.TemporaryFile() as source:
            source.write(_OWNER_CODE)
            source.flush()
            source.seek(0)
            snapshot.write(raw)
            snapshot.flush()
            snapshot.seek(0)
            process = subprocess.Popen(
                [
                    sys.executable,
                    "-I",
                    "-B",
                    "-c",
                    _SOURCE_BOOTSTRAP,
                    "--thread-owner",
                    str(snapshot.fileno()),
                    str(source.fileno()),
                    hashlib.sha256(_OWNER_CODE).hexdigest(),
                ],
                cwd=cwd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                start_new_session=True,
                pass_fds=(snapshot.fileno(), source.fileno(), *pass_fds),
                bufsize=0,
            )
        with selectors.DefaultSelector() as selected:
            selected.register(process.stdout, selectors.EVENT_READ)
            while selected.get_map():
                if time.monotonic() >= deadline + 4:
                    raise TimeoutError(
                        "coordination supervisor exceeded finite cleanup ceiling"
                    )
                for key, _ in selected.select(0.1):
                    block = os.read(
                        key.fd, min(65536, _PROTOCOL_BYTES - len(capture) + 1)
                    )
                    if not block:
                        selected.unregister(key.fileobj)
                    else:
                        capture.extend(block)
                        if len(capture) > _PROTOCOL_BYTES:
                            raise ValueError(
                                "coordination supervisor exceeded output ceiling"
                            )
                        if child_pid is None and b"\n" in capture:
                            first = json.loads(capture.split(b"\n", 1)[0])
                            if (
                                set(first) == {"child_pid"}
                                and type(first["child_pid"]) is int
                                and first["child_pid"] > 1
                            ):
                                child_pid = first["child_pid"]
                            elif set(first) != {"error", "message"}:
                                raise ValueError("invalid coordination child identity")
        process.wait(timeout=max(0.01, deadline + 4 - time.monotonic()))
        lines = capture.splitlines()
        result = json.loads(lines[-1]) if lines else None
        if process.returncode != 0 or not isinstance(result, dict):
            raise RuntimeError(
                "coordination supervisor did not return a terminal result"
            )
        if "error" in result:
            if set(result) != {"error", "message"} or not isinstance(
                result["message"], str
            ):
                raise ValueError("malformed coordination failure result")
            kind = {
                "TimeoutError": TimeoutError,
                "ValueError": ValueError,
                "EffectInterrupted": EffectInterrupted,
                "OSError": OSError,
            }.get(result["error"], RuntimeError)
            raise kind(result["message"])
        if (
            set(result) != {"returncode", "stdout"}
            or type(result["returncode"]) is not int
            or not isinstance(result["stdout"], str)
        ):
            raise ValueError("malformed coordination terminal result")
        if child_pid is None or len(lines) != 2:
            raise ValueError("coordination result has no exact child custody")
        return subprocess.CompletedProcess(
            command, result["returncode"], result["stdout"], ""
        )
    finally:
        if process is not None:
            # EOF asks the supervisor to clean its child group even if this
            # caller was interrupted. Caller process death closes the same FD.
            process.stdin.close()
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                process.terminate()
                try:
                    process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    # Only this call's announced child and owned supervisor.
                    if child_pid is not None:
                        try:
                            os.killpg(child_pid, signal.SIGKILL)
                        except ProcessLookupError:
                            pass
                    process.kill()
                    process.wait(timeout=2)
            process.stdout.close()


def _thread_owner(fd):
    """Read one anonymous request; stdin is a parent-only EOF lifeline."""
    try:
        info = os.fstat(fd)
        if (
            not stat.S_ISREG(info.st_mode)
            or info.st_nlink != 0
            or info.st_uid != os.getuid()
            or info.st_size > _CONFIG_BYTES
        ):
            raise ValueError("invalid coordination supervisor snapshot")
        data = os.read(fd, _CONFIG_BYTES + 1)
        if len(data) != info.st_size:
            raise ValueError("incomplete coordination supervisor snapshot")
        config = json.loads(data)
        if not isinstance(config, dict) or set(config) != {
            "command",
            "cwd",
            "deadline",
            "output_bytes",
            "pass_fds",
        }:
            raise ValueError("invalid coordination supervisor request")
        if type(config["deadline"]) not in (int, float) or not math.isfinite(
            config["deadline"]
        ):
            raise ValueError("invalid coordination supervisor deadline")
        timeout = config["deadline"] - time.monotonic()
        if timeout <= 0:
            raise TimeoutError("coordination effect exceeded its time ceiling")
        pass_fds = tuple(config["pass_fds"])
        _validate(config["command"], timeout, config["output_bytes"], pass_fds)

        def announce(pid):
            print(json.dumps({"child_pid": pid}), flush=True)

        result = _run(
            config["command"],
            cwd=config["cwd"],
            timeout=timeout,
            output_bytes=config["output_bytes"],
            pass_fds=pass_fds,
            lifeline=0,
            announce=announce,
        )
        print(
            json.dumps({"returncode": result.returncode, "stdout": result.stdout}),
            flush=True,
        )
    except (Exception, KeyboardInterrupt) as exc:
        try:
            print(
                json.dumps({"error": type(exc).__name__, "message": str(exc)[:4096]}),
                flush=True,
            )
        except BrokenPipeError:
            pass  # Parent death was already observed and child cleanup ran.
    finally:
        os.close(fd)


# Dispatch exact already executing module code, never reopen mutable __file__.
# This anonymous descriptor contains only this trusted resident code object;
# caller commands remain validated data and cannot supply serialized code.
_SOURCE_BOOTSTRAP = """import hashlib, marshal, os, stat, sys
expected = sys.argv.pop()
fd = int(sys.argv.pop())
try:
    info = os.fstat(fd)
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 0 or info.st_uid != os.getuid() or not 0 < info.st_size <= 1048576:
        raise ValueError('invalid owner code snapshot')
    raw = os.read(fd, 1048577)
    if len(raw) != info.st_size or hashlib.sha256(raw).hexdigest() != expected:
        raise ValueError('owner code snapshot changed')
finally:
    os.close(fd)
exec(marshal.loads(raw), {'__name__': '__main__', '__file__': '<coordination-owner-snapshot>'})
"""
_OWNER_CODE = marshal.dumps(sys._getframe().f_code)
if len(_OWNER_CODE) > _CONFIG_BYTES:
    raise ValueError("coordination owner code exceeds the bounded transport")


if __name__ == "__main__":
    if len(sys.argv) != 3 or sys.argv[1] != "--thread-owner":
        raise SystemExit("only the private coordination thread owner is supported")
    _thread_owner(int(sys.argv[2]))
