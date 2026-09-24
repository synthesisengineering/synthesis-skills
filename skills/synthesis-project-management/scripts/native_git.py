"""Bounded, uncached native Git identity queries.

Darwin's atomic CLOEXEC_DEFAULT spawn flag avoids Python's fork path while
closing every unrelated descriptor, including descriptors opened concurrently.
The fallback uses ordinary subprocess descriptor isolation. Neither path runs
a shell, changes Git identity semantics, or retains an authority observation.
"""
from __future__ import annotations

import errno
import locale
import math
import os
import selectors
import shutil
import signal
import subprocess
import sys
import time

_CLOEXEC_DEFAULT = 0x4000  # Darwin sys/spawn.h, not portable POSIX flags.
_SETSIGDEF = 0x0004
_API = None
_QUERIES = frozenset({
    ("config", "--null", "--show-origin", "--list"),
    ("rev-parse", "--path-format=absolute", "--git-common-dir", "--show-toplevel"),
    ("worktree", "list", "--porcelain", "-z"),
    ("rev-parse", "--show-toplevel", "--symbolic-full-name", "HEAD"),
    ("rev-parse", "--show-toplevel"),
    ("branch", "--show-current"),
})


class OutputLimitExceeded(subprocess.SubprocessError):
    """A native query exceeded the combined stdout/stderr capture budget."""


class _Unavailable(Exception):
    pass


def _get_darwin_api():
    global _API
    if sys.platform != "darwin":
        return None
    if _API is not None:
        return _API
    try:
        import ctypes as c
        library = c.CDLL(None, use_errno=True)
    except (ImportError, OSError):
        return None
    pointer = c.POINTER(c.c_void_p)
    signatures = {
        "posix_spawnattr_init": [pointer],
        "posix_spawnattr_destroy": [pointer],
        "posix_spawnattr_setflags": [pointer, c.c_short],
        "posix_spawnattr_setsigdefault": [pointer, c.POINTER(c.c_uint32)],
        "posix_spawn_file_actions_init": [pointer],
        "posix_spawn_file_actions_destroy": [pointer],
        "posix_spawn_file_actions_adddup2": [pointer, c.c_int, c.c_int],
        "posix_spawn_file_actions_addclose": [pointer, c.c_int],
        "posix_spawn_file_actions_addchdir_np": [pointer, c.c_char_p],
        "posix_spawn": [c.POINTER(c.c_int), c.c_char_p, pointer, pointer,
                        c.POINTER(c.c_char_p), c.POINTER(c.c_char_p)],
        "sigemptyset": [c.POINTER(c.c_uint32)],
        "sigaddset": [c.POINTER(c.c_uint32), c.c_int],
    }
    try:
        for name, arguments in signatures.items():
            function = getattr(library, name)
            function.argtypes = arguments
            function.restype = c.c_int
    except AttributeError:
        return None  # No weaker spawn flags or racy descriptor enumeration.
    _API = (c, library)
    return _API


def _check(code):
    if code:
        raise OSError(code, os.strerror(code))


class _NativeProcess:
    def __init__(self, pid, stdout, stderr):
        self.pid, self.stdout, self.stderr = pid, stdout, stderr
        self.returncode = None

    def poll(self):
        if self.returncode is None:
            child, status = os.waitpid(self.pid, os.WNOHANG)
            if child:
                self.returncode = os.waitstatus_to_exitcode(status)
        return self.returncode

    def kill(self):
        if self.poll() is None:
            try:
                os.kill(self.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass

    def wait(self, timeout=None):
        if timeout is None:
            if self.returncode is None:
                _, status = os.waitpid(self.pid, 0)
                self.returncode = os.waitstatus_to_exitcode(status)
            return self.returncode
        deadline = time.monotonic() + timeout
        while self.poll() is None:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise subprocess.TimeoutExpired("native Git", timeout)
            time.sleep(min(remaining, 0.0005))
        return self.returncode


def _start_native(argv, *, env, cwd, api):
    import fcntl
    c, library = api
    # exec's relative PATH entries are interpreted after the requested chdir.
    # Resolve the executable under that same directory, without changing the
    # parent process cwd or substituting a different configured Git binary.
    directory = os.path.abspath(cwd) if cwd is not None else os.getcwd()
    search = os.pathsep.join(entry if os.path.isabs(entry) else os.path.join(directory, entry)
                            for entry in env.get("PATH", os.defpath).split(os.pathsep))
    executable = shutil.which(argv[0], path=search)
    if executable is None:
        raise FileNotFoundError(errno.ENOENT, "native executable is unavailable", argv[0])
    executable = os.path.abspath(executable)
    arguments = (c.c_char_p * (len(argv) + 1))(*(os.fsencode(value) for value in argv), None)
    entries = [os.fsencode(key + "=" + value) for key, value in env.items()]
    environment = (c.c_char_p * (len(entries) + 1))(*entries, None)
    actions, attributes, pid = c.c_void_p(), c.c_void_p(), c.c_int()
    actions_ready = attributes_ready = started = False
    owned = set()
    streams = []

    def own(fd):
        # Parent stdin/out/err may be closed. Keep every source descriptor
        # above2 so dup2 actions cannot overwrite a later action's source.
        owned.add(fd)
        if fd <= 2:
            moved = fcntl.fcntl(fd, fcntl.F_DUPFD_CLOEXEC, 3)
            owned.add(moved)
            close(fd)
            fd = moved
        return fd

    def close(fd):
        owned.remove(fd)
        os.close(fd)

    def pipe():
        pair = os.pipe()
        # Relocating the first low descriptor may fail. Both descriptors must
        # already be owned so cleanup cannot leak the second pipe endpoint.
        owned.update(pair)
        return tuple(own(fd) for fd in pair)

    try:
        _check(library.posix_spawn_file_actions_init(c.byref(actions)))
        actions_ready = True
        _check(library.posix_spawnattr_init(c.byref(attributes)))
        attributes_ready = True
        code = library.posix_spawnattr_setflags(c.byref(attributes), _CLOEXEC_DEFAULT | _SETSIGDEF)
        if code in {errno.EINVAL, errno.ENOSYS, errno.ENOTSUP}:
            raise _Unavailable("atomic descriptor closure is unavailable")
        _check(code)
        defaults = c.c_uint32()
        _check(library.sigemptyset(c.byref(defaults)))
        for name in ("SIGPIPE", "SIGXFZ", "SIGXFSZ"):
            if hasattr(signal, name):
                _check(library.sigaddset(c.byref(defaults), getattr(signal, name)))
        _check(library.posix_spawnattr_setsigdefault(c.byref(attributes), c.byref(defaults)))
        if cwd is not None:
            _check(library.posix_spawn_file_actions_addchdir_np(c.byref(actions), os.fsencode(cwd)))
        stdin = own(os.open(os.devnull, os.O_RDONLY))
        stdout_read, stdout_write = pipe()
        stderr_read, stderr_write = pipe()
        for source, target in ((stdin, 0), (stdout_write, 1), (stderr_write, 2)):
            _check(library.posix_spawn_file_actions_adddup2(c.byref(actions), source, target))
        for fd in owned:
            _check(library.posix_spawn_file_actions_addclose(c.byref(actions), fd))
        _check(library.posix_spawn(c.byref(pid), os.fsencode(executable), c.byref(actions),
                                  c.byref(attributes), arguments, environment))
        started = True
        for fd in (stdin, stdout_write, stderr_write):
            close(fd)
        for fd in (stdout_read, stderr_read):
            streams.append(os.fdopen(fd, "rb", buffering=0))
            owned.remove(fd)
        process = _NativeProcess(pid.value, *streams)
        started = False  # The collector now owns the child and its streams.
        return process
    finally:
        if started:
            try:
                os.kill(pid.value, signal.SIGKILL)
            except ProcessLookupError:
                pass
            os.waitpid(pid.value, 0)
            for stream in streams:
                stream.close()
        for fd in owned:
            os.close(fd)
        if actions_ready:
            library.posix_spawn_file_actions_destroy(c.byref(actions))
        if attributes_ready:
            library.posix_spawnattr_destroy(c.byref(attributes))


def _start_process(argv, *, env, cwd):
    api = _get_darwin_api()
    if api is not None:
        try:
            return _start_native(argv, env=env, cwd=cwd, api=api)
        except _Unavailable:
            pass
    return subprocess.Popen(argv, env=env, cwd=cwd, stdin=subprocess.DEVNULL,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, close_fds=True)


def _spawn(argv, *, env=None, cwd=None, timeout=10, max_output_bytes=4 * 1024 * 1024):
    if not isinstance(argv, (list, tuple)) or not argv or any(not isinstance(value, str) or "\0" in value for value in argv):
        raise ValueError("native query requires literal NUL-free argv")
    if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or not math.isfinite(timeout) or timeout <= 0:
        raise ValueError("native query requires a finite positive timeout")
    if type(max_output_bytes) is not int or max_output_bytes <= 0:
        raise ValueError("native query requires a positive output budget")
    environment = dict(os.environ if env is None else env)
    if any(not isinstance(key, str) or not isinstance(value, str) or not key or "=" in key or "\0" in key + value for key, value in environment.items()):
        raise ValueError("invalid native query environment")
    directory = os.fspath(cwd) if cwd is not None else None
    if directory is not None and (not isinstance(directory, str) or "\0" in directory):
        raise ValueError("invalid native query working directory")
    deadline = time.monotonic() + timeout
    process = _start_process(list(argv), env=environment, cwd=directory)
    chunks = {"stdout": [], "stderr": []}
    size = 0
    try:
        with selectors.DefaultSelector() as selector:
            for name in chunks:
                stream = getattr(process, name)
                os.set_blocking(stream.fileno(), False)
                selector.register(stream, selectors.EVENT_READ, name)
            while selector.get_map():
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise subprocess.TimeoutExpired(argv, timeout)
                for key, _ in selector.select(remaining):
                    try:
                        data = os.read(key.fd, 65536)
                    except (BlockingIOError, InterruptedError):
                        continue
                    if not data:
                        selector.unregister(key.fileobj)
                        key.fileobj.close()
                    else:
                        size += len(data)
                        if size > max_output_bytes:
                            raise OutputLimitExceeded("native query exceeded the combined output budget")
                        chunks[key.data].append(data)
            process.wait(timeout=max(0, deadline - time.monotonic()))
        return subprocess.CompletedProcess(argv, process.returncode, b"".join(chunks["stdout"]), b"".join(chunks["stderr"]))
    except BaseException:
        process.kill()
        process.wait()
        raise
    finally:
        process.stdout.close()
        process.stderr.close()


def run(argv, *, env=None, cwd=None, capture_output=True, text=False, timeout=10, check=False):
    """Run only the fixed, read-only identity queries owned by coordination."""
    if not isinstance(argv, (list, tuple)) or not argv or argv[0] != "git" or not capture_output:
        raise ValueError("unregistered native Git query")
    query = list(argv[1:])
    if query and query[0] == "--no-optional-locks":
        query.pop(0)
    if len(query) >= 2 and query[0] == "-C":
        query = query[2:]
    if tuple(query) not in _QUERIES:
        raise ValueError("unregistered native Git query")
    result = _spawn(argv, env=env, cwd=cwd, timeout=timeout)
    if text:
        encoding = locale.getpreferredencoding(False)
        result.stdout = result.stdout.decode(encoding).replace("\r\n", "\n").replace("\r", "\n")
        result.stderr = result.stderr.decode(encoding).replace("\r\n", "\n").replace("\r", "\n")
    if check:
        result.check_returncode()
    return result
