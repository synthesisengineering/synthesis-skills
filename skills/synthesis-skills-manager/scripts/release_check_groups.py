#!/usr/bin/env python3
"""Bounded, exhaustive autopilot release groups, using ordinary pytest collection.

Every group collects the entire directory before selecting its exact partition.
No file allowlist: newly collected files enter core unless a domain rule owns them.
Reports bind full/selected node IDs, all three execution phases and source bytes.
"""

from __future__ import annotations

import argparse
from contextlib import contextmanager
import hashlib
import json
import math
import os
from pathlib import Path
import selectors
import signal
import stat
import subprocess
import sys
import tempfile
import time

# Product fixtures deliberately replace shared standard-library attributes. The
# execution observer captures its own primitives before fixtures run, so logging
# cannot consume simulated deadlines or mistake simulated metadata for custody.
# Real file mutation is still checked through these original OS primitives.
_diagnostic_monotonic = time.monotonic
_diagnostic_os_open = os.open
_diagnostic_os_close = os.close
_diagnostic_os_read = os.read
_diagnostic_os_write = os.write
_diagnostic_os_fstat = os.fstat
_diagnostic_os_stat = os.stat
_diagnostic_os_lstat = os.lstat
_diagnostic_os_getuid = os.getuid
_diagnostic_os_fsync = os.fsync
_diagnostic_is_regular = stat.S_ISREG
_diagnostic_mode = stat.S_IMODE
_diagnostic_dumps = json.dumps
_diagnostic_loads = json.loads
_diagnostic_sha256 = hashlib.sha256
_diagnostic_open_file = open

GROUPS = ("state", "native", "evaluation", "core", "native-control")
AP = "skills/synthesis-autopilot/scripts"
CHECK_SECONDS = 900
ACCEPTANCE_SECONDS = 6000  # finite whole-suite owner, not a per-group allowance
GROUP_SECONDS = 880  # collection, execution and reporting; 20s outer cleanup reserve
OUTPUT_BYTES = 8 * 1024 * 1024
REPORT_BYTES = 4 * 1024 * 1024
FAILURE_DETAIL_BYTES = 16 * 1024
FAILURE_DETAIL_TOTAL_BYTES = 256 * 1024
MAX_TESTS = 20000
MAX_SOURCE_BYTES = 128 * 1024 * 1024
STATE_PREFIXES = (
    "test_run_state",
    # Controller admission/readback owns the run-state transition facade.
    # Keep its complete family together in the state partition.
    "test_controller",
    "test_journal_",
    "test_required_citations",
    "test_search_budget",
    "test_recovery_capsule",
    "test_persistence_policy",
    "test_operator_status",
)
NATIVE_PREFIXES = (
    "test_native_",
    "test_codex_",
    "test_prepared_",
    "test_stop_",
    "test_legacy_",
    "test_observation_",
    "test_owner_resume",
)
EVALUATION_PREFIXES = (
    "test_evaluation",
    "test_consumer_",
    "test_evidence_bridge",
    "test_profile_evidence",
)
NATIVE_CONTROL_PREFIXES = (
    "test_native_cancellation",
    "test_native_admission",
    "test_native_session_owner_chain",
)


def group_for(nodeid: str) -> str:
    path = nodeid.split("::", 1)[0]
    if (
        not path.startswith(AP + "/")
        or not path.endswith(".py")
        or ".." in Path(path).parts
    ):
        raise ValueError("collection escaped the autopilot directory")
    name = Path(path).name
    choices = [
        name.startswith(prefixes)
        for prefixes in (STATE_PREFIXES, NATIVE_PREFIXES, EVALUATION_PREFIXES)
    ]
    if sum(choices) > 1:
        raise ValueError("overlapping group ownership")
    if choices[1] and name.startswith(NATIVE_CONTROL_PREFIXES):
        return "native-control"
    return GROUPS[choices.index(True)] if any(choices) else "core"


def partition(nodeids: list[str]) -> dict[str, list[str]]:
    if not nodeids or len(nodeids) > MAX_TESTS or len(set(nodeids)) != len(nodeids):
        raise ValueError("empty, duplicate or oversized collection")
    groups = {name: [] for name in GROUPS}
    for node in nodeids:
        groups[group_for(node)].append(node)
    if sorted(n for nodes in groups.values() for n in nodes) != sorted(nodeids):
        raise ValueError("non-exhaustive partition")
    return groups


def source_digest(root: Path) -> str:
    """Hash a descriptor-anchored tree; missing, replaced or unreadable input refuses.

    Names are opened relative to verified directory descriptors. Every entry is
    revalidated against its descriptor after use, including directory identity.
    Generated caches are excluded; checks isolate bytecode caches per process.
    """
    digest = hashlib.sha256()
    total = 0
    count = 0
    deadline = time.monotonic() + 30
    ignored = {".git", "__pycache__", ".pytest_cache"}

    def identity(info):
        return (
            info.st_dev,
            info.st_ino,
            info.st_mode,
            info.st_size,
            info.st_mtime_ns,
            info.st_ctime_ns,
            info.st_nlink,
        )

    def bounded():
        if count > 20000 or time.monotonic() > deadline:
            raise ValueError("source inventory exceeds count or time ceiling")

    def visit(fd, relative, depth):
        nonlocal total, count
        if depth > 64:
            raise ValueError("source inventory exceeds directory depth ceiling")
        initial = os.fstat(fd)
        if not stat.S_ISDIR(initial.st_mode):
            raise ValueError("source directory is not a directory")
        names = []
        # scandir errors propagate; unreadable directories are never omitted.
        with os.scandir(fd) as entries:
            for entry in entries:
                if entry.name in ignored:
                    continue
                count += 1
                bounded()
                names.append(entry.name)
        digest.update(
            json.dumps([relative, stat.S_IMODE(initial.st_mode), "directory"]).encode()
        )
        for name in sorted(names):
            bounded()
            before = os.stat(name, dir_fd=fd, follow_symlinks=False)
            mode = before.st_mode
            if not (stat.S_ISDIR(mode) or stat.S_ISREG(mode)):
                raise ValueError("source member is not a regular file or directory")
            flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK
            if stat.S_ISDIR(mode):
                flags |= os.O_DIRECTORY
            child = os.open(name, flags, dir_fd=fd)
            try:
                if identity(before) != identity(os.fstat(child)):
                    raise ValueError("source pathname changed before opening")
                path = relative + "/" + name if relative else name
                if stat.S_ISDIR(mode):
                    visit(child, path, depth + 1)
                else:
                    total += before.st_size
                    if total > MAX_SOURCE_BYTES:
                        raise ValueError("source inventory exceeds byte ceiling")
                    member = hashlib.sha256()
                    remaining = before.st_size
                    while remaining:
                        bounded()
                        chunk = os.read(child, min(65536, remaining))
                        if not chunk:
                            raise ValueError("source member changed while reading")
                        member.update(chunk)
                        remaining -= len(chunk)
                    digest.update(
                        json.dumps(
                            [path, stat.S_IMODE(mode), member.hexdigest()],
                            separators=(",", ":"),
                        ).encode()
                    )
                if identity(before) != identity(os.fstat(child)):
                    raise ValueError("source descriptor changed while reading")
                if identity(before) != identity(
                    os.stat(name, dir_fd=fd, follow_symlinks=False)
                ):
                    raise ValueError("source pathname changed while reading")
            finally:
                os.close(child)
        if identity(initial) != identity(os.fstat(fd)):
            raise ValueError("source directory changed while reading")

    root_fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        before = os.fstat(root_fd)
        visit(root_fd, "", 0)
        if identity(before) != identity(os.stat(root, follow_symlinks=False)):
            raise ValueError("source root pathname changed while reading")
    finally:
        os.close(root_fd)
    return digest.hexdigest()


class CheckInterrupted(RuntimeError):
    """Do not use InterruptedError: selectors intentionally consumes EINTR."""


def fixture_root(prefix: str, environment: dict[str, str] | None = None) -> Path:
    """Create fresh, canonical, private check custody; never delete it implicitly.

    Only the scratch base is canonicalized (including macOS system aliases).
    This does not canonicalize any production input or relax its no-follow rules.
    The caller's temporary-root selection is preserved, with a distinct child
    for every owner, so pytest never reuses a shared numbered retention root.
    """
    env = os.environ if environment is None else environment
    base = Path(env.get("TMPDIR") or tempfile.gettempdir()).resolve(strict=True)
    if not base.is_dir():
        raise ValueError("release fixture base is not a directory")
    root = Path(tempfile.mkdtemp(prefix=prefix, dir=base))
    if root.resolve() != root or root.stat().st_uid != os.getuid():
        raise ValueError("release fixture custody identity is invalid")
    return root


@contextmanager
def retained_group_fixture():
    root = fixture_root("synthesis-release-check-")
    # No TemporaryDirectory finalizer: failure/interruption are evidence too.
    yield root


def fixture_command(command: list[str], root: Path) -> list[str]:
    """Bind ordinary pytest to this invocation without changing test selection."""
    if not (len(command) >= 3 and command[1:3] == ["-m", "pytest"]):
        return list(command)
    result = []
    index = 0
    while index < len(command):
        word = command[index]
        if word == "--basetemp":
            if index + 1 == len(command):
                raise ValueError("pytest basetemp is missing its value")
            index += 2
        elif word.startswith("--basetemp="):
            index += 1
        else:
            result.append(word)
            index += 1
    # Only the fresh path below can be pytest's destructive initialization target.
    return result + ["--basetemp", str(root / "pytest")]


def bounded_run(
    command: list[str],
    cwd: Path,
    timeout: float = CHECK_SECONDS,
    env: dict[str, str] | None = None,
    *,
    suite: bool = False,
) -> subprocess.CompletedProcess:
    """Own one process group; limit wall time/output and reap on every exit path.

    This runner is for trusted repository checks, not hostile code confinement.
    Consumers retain their own OS sandbox. A descendant deliberately escaping
    its session is outside this process-group contract, never claimed reaped.
    """
    if (
        type(suite) is not bool
        or os.name != "posix"
        or timeout <= 0
        or timeout > (ACCEPTANCE_SECONDS if suite else CHECK_SECONDS)
    ):
        raise ValueError("bounded release checks require POSIX and a valid deadline")
    started = time.monotonic()
    output = bytearray()
    process = None
    failure = None
    old = {}
    cache = None
    executed = list(command)
    custody_fd = None

    def interrupted(signum, _frame):
        raise CheckInterrupted(f"check interrupted by signal {signum}")

    try:
        for sig in (signal.SIGTERM, signal.SIGINT):
            old[sig] = signal.signal(sig, interrupted)
        child_env = dict(os.environ if env is None else env)
        cache = fixture_root("synthesis-required-check-", child_env)
        custody_fd = os.open(cache, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        (cache / "tmp").mkdir(mode=0o700)
        executed = fixture_command(command, cache)
        child_env.pop("PYTEST_ADDOPTS", None)
        child_env.pop("PYTEST_PLUGINS", None)
        child_env.update(
            {
                "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1",
                "PYTHONDONTWRITEBYTECODE": "1",
                "PYTHONPYCACHEPREFIX": str(cache / "pycache"),
                "TMPDIR": str(cache / "tmp"),
                "TMP": str(cache / "tmp"),
                "TEMP": str(cache / "tmp"),
            }
        )
        process = subprocess.Popen(
            executed,
            cwd=cwd,
            env=child_env,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
        with selectors.DefaultSelector() as selector:
            selector.register(process.stdout, selectors.EVENT_READ)
            while selector.get_map():
                remaining = timeout - (time.monotonic() - started)
                if remaining <= 0:
                    raise TimeoutError(
                        "required check exceeded its unchanged wall-time ceiling"
                    )
                for key, _ in selector.select(min(0.1, remaining)):
                    data = os.read(
                        key.fileobj.fileno(), min(65536, OUTPUT_BYTES - len(output) + 1)
                    )
                    if not data:
                        selector.unregister(key.fileobj)
                    else:
                        output.extend(data)
                        if len(output) > OUTPUT_BYTES:
                            raise ValueError(
                                "required check output exceeded byte ceiling"
                            )
            process.wait(timeout=max(0.001, timeout - (time.monotonic() - started)))
    except (
        OSError,
        ValueError,
        TimeoutError,
        subprocess.TimeoutExpired,
        KeyboardInterrupt,
        CheckInterrupted,
    ) as error:
        failure = str(error) or type(error).__name__
    finally:
        for sig in old:
            signal.signal(sig, signal.SIG_IGN)
        if process is not None:
            # A successful parent is also responsible for descendants holding no pipe.
            try:
                os.killpg(process.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
            except OSError as error:
                failure = f"owned process-group cleanup failed: {error}"
            try:
                process.wait(timeout=5 if suite else 1)
            except subprocess.TimeoutExpired:
                pass
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            except OSError as error:
                failure = f"owned process-group cleanup failed: {error}"
            try:
                process.wait(timeout=2)
            except (OSError, subprocess.TimeoutExpired) as error:
                failure = f"owned child reap failed: {error}"
            if process.stdout:
                process.stdout.close()
        for sig, handler in old.items():
            signal.signal(sig, handler)
    text = bytes(output[:OUTPUT_BYTES]).decode("utf-8", errors="replace")
    if failure:
        text += "\nFAIL " + failure + "\n"
    code = 1 if failure or process is None else process.returncode
    if cache is not None and custody_fd is not None:
        try:
            before = os.fstat(custody_fd)
            present = cache.lstat()
            if (
                cache.resolve() != cache
                or (before.st_dev, before.st_ino, before.st_mode, before.st_uid)
                != (present.st_dev, present.st_ino, present.st_mode, present.st_uid)
                or present.st_mode & 0o022
            ):
                raise OSError("required-check custody pathname changed")
            receipt = {
                "requested_command": command,
                "executed_command": executed,
                "cwd": str(cwd),
                "returncode": code,
                "failure": failure,
                "process_id": None if process is None else process.pid,
                "seconds": time.monotonic() - started,
                "fixture_custody": str(cache),
                "retention": "retained; explicit owner reconciliation required",
                "process_scope": "owned process group; escaped sessions are not covered",
            }
            for name, content in (
                ("output.log", text),
                ("result.json", json.dumps(receipt, sort_keys=True)),
            ):
                fd = os.open(
                    name,
                    os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                    0o600,
                    dir_fd=custody_fd,
                )
                with os.fdopen(fd, "w", encoding="utf-8") as stream:
                    stream.write(content)
                    stream.flush()
                    os.fsync(stream.fileno())
            os.fsync(custody_fd)
            present = cache.lstat()
            if (
                cache.resolve() != cache
                or (before.st_dev, before.st_ino, before.st_mode, before.st_uid)
                != (present.st_dev, present.st_ino, present.st_mode, present.st_uid)
                or present.st_mode & 0o022
            ):
                raise OSError("required-check custody pathname changed during receipt")
        except OSError as error:
            code = 1
            text += (
                "\nFAIL required-check custody could not be retained: "
                + str(error)
                + "\n"
            )
    if custody_fd is not None:
        os.close(custody_fd)
    result = subprocess.CompletedProcess(executed, code, text, "")
    result.fixture_custody = str(cache) if cache is not None else None
    result.failure = failure
    result.process_id = None if process is None else process.pid
    return result


def _progress_stamp(info):
    # A diagnostic reader may update atime; that is not content mutation.
    return (
        info.st_dev,
        info.st_ino,
        info.st_mode,
        info.st_uid,
        info.st_gid,
        info.st_nlink,
        info.st_size,
        info.st_mtime_ns,
        info.st_ctime_ns,
    )


def read_progress(path: Path) -> dict:
    """Bounded diagnostic evidence only; never substitutes for final inventory."""
    fd = _diagnostic_os_open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        before = _diagnostic_os_fstat(fd)
        if (
            not _diagnostic_is_regular(before.st_mode)
            or before.st_nlink != 1
            or before.st_uid != _diagnostic_os_getuid()
            or _diagnostic_mode(before.st_mode) != 0o600
            or before.st_size > REPORT_BYTES
        ):
            raise ValueError("invalid or oversized progress custody")
        raw = bytearray()
        while len(raw) < before.st_size:
            block = _diagnostic_os_read(fd, min(65536, before.st_size - len(raw)))
            if not block:
                raise ValueError("progress changed while reading")
            raw.extend(block)
        if _progress_stamp(_diagnostic_os_fstat(fd)) != _progress_stamp(
            before
        ) or _progress_stamp(_diagnostic_os_lstat(path)) != _progress_stamp(before):
            raise ValueError("progress changed while reading")
    finally:
        _diagnostic_os_close(fd)
    trailing = bool(raw and not raw.endswith(b"\n"))
    lines = bytes(raw).splitlines()
    if trailing:
        lines = lines[:-1]
    events = [_diagnostic_loads(line) for line in lines]
    if (
        not events
        or len(events) > MAX_TESTS * 4 + 4
        or any(
            not isinstance(row, dict) or row.get("sequence") != index
            for index, row in enumerate(events)
        )
        or events[0].get("kind") != "start"
    ):
        raise ValueError("invalid progress sequence")
    phases = {
        key: sum(
            row.get("duration", 0)
            for row in events
            if row.get("kind") == "phase" and row.get("when") == key
        )
        for key in ("setup", "call", "teardown")
    }
    finished = events[-1].get("kind") == "sessionfinish" and not trailing
    return {
        "status": "DIAGNOSTIC_ONLY" if finished else "INCOMPLETE",
        "authorizes_success": False,
        "trailing_incomplete": trailing,
        "events": events,
        "bytes": len(raw),
        "sha256": _diagnostic_sha256(raw).hexdigest(),
        "timing": {"phase_seconds": phases},
    }


class InventoryPlugin:
    def __init__(self, group: str, report: Path, selection: list[str] | None = None):
        self.group = group
        self.selection = selection
        self.report = report
        self.full = []
        self.collected_ids = set()
        self.selected = []
        self.phases = {}
        self.errors = []
        self.counts = {}
        self.subtests = {}
        self.subtest_count = 0
        self.started = _diagnostic_monotonic()
        self.collection_seconds = None
        self.progress = report.with_suffix(".progress.jsonl")
        self.progress_identity = None
        self.progress_parent = None
        self.progress_sequence = 0
        self.reporting_seconds = 0.0
        self.failure_detail_bytes = 0

    def _failure_detail(self, report):
        """Render bounded pytest diagnostics without collecting arbitrary locals.

        The ordinary report remains the authority for outcome and lifecycle.
        A prefix, missing representation or renderer error is explicitly labeled;
        none supplies acceptance evidence. Stop rendering at the byte boundary.
        """
        limit = min(FAILURE_DETAIL_BYTES,
                    FAILURE_DETAIL_TOTAL_BYTES - self.failure_detail_bytes)
        if limit <= 0:
            return {"status": "omitted", "reason": "diagnostic_budget_exhausted"}
        representation = getattr(report, "longrepr", None)
        if representation is None:
            return {"status": "unavailable", "reason": "missing_representation"}
        chunks = []
        captured = 0

        class PrefixComplete(Exception):
            pass

        class Sink:
            def write(self, text):
                nonlocal captured
                remaining = limit - captured
                raw = text[:remaining + 1].encode("utf-8")
                prefix = raw[:remaining].decode("utf-8", errors="ignore").encode("utf-8")
                chunks.append(prefix)
                captured += len(prefix)
                if len(raw) > remaining:
                    raise PrefixComplete

            def flush(self):
                pass

        status = "complete"
        reason = None
        error_type = None
        try:
            if isinstance(representation, str):
                Sink().write(representation)
            elif callable(getattr(representation, "toterminal", None)):
                from _pytest._io import TerminalWriter

                writer = TerminalWriter(file=Sink())
                writer.hasmarkup = False
                representation.toterminal(writer)
            else:
                status, reason = "unavailable", "unsupported_representation"
        except PrefixComplete:
            status = "truncated"
        except Exception as error:
            status, reason = "unavailable", "renderer_error"
            error_type = type(error).__name__
        raw = b"".join(chunks)
        self.failure_detail_bytes += len(raw)
        detail = {"status": status, "text": raw.decode("utf-8"),
                  "bytes": len(raw), "sha256": _diagnostic_sha256(raw).hexdigest()}
        if reason is not None:
            detail["reason"] = reason
        if error_type is not None:
            detail["error_type"] = error_type
        return detail

    def _progress(self, kind, **data):
        """Append each observed phase once, with constant per-phase work.

        Writes survive a killed pytest process; power-loss durability is not
        claimed. Final inventory and unchanged source remain acceptance gates.
        """
        started = _diagnostic_monotonic()
        records = []
        if self.progress_identity is None:
            records.append({"kind": "start", "group": self.group, "schema_version": 1})
        records.append({"kind": kind, **data})
        raw = b""
        for record in records:
            record["sequence"] = self.progress_sequence
            self.progress_sequence += 1
            raw += (
                _diagnostic_dumps(
                    record, sort_keys=True, separators=(",", ":")
                ).encode()
                + b"\n"
            )
        if self.progress_sequence > MAX_TESTS * 4 + 4:
            raise ValueError("progress event ceiling exceeded")
        parent = _diagnostic_os_open(
            self.report.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
        )
        fd = None
        try:
            info = _diagnostic_os_fstat(parent)
            parent_identity = (info.st_dev, info.st_ino, info.st_mode, info.st_uid)
            if (
                self.progress_parent is not None
                and self.progress_parent != parent_identity
            ):
                raise ValueError("progress parent changed")
            self.progress_parent = parent_identity
            flags = os.O_WRONLY | os.O_APPEND | os.O_NOFOLLOW | os.O_NONBLOCK
            if self.progress_identity is None:
                flags |= os.O_CREAT | os.O_EXCL
            fd = _diagnostic_os_open(self.progress.name, flags, 0o600, dir_fd=parent)
            before = _diagnostic_os_fstat(fd)
            if (
                not _diagnostic_is_regular(before.st_mode)
                or before.st_nlink != 1
                or before.st_uid != _diagnostic_os_getuid()
                or _diagnostic_mode(before.st_mode) != 0o600
                or self.progress_identity is not None
                and _progress_stamp(before) != self.progress_identity
            ):
                raise ValueError("progress custody changed")
            if before.st_size + len(raw) > REPORT_BYTES:
                raise ValueError("progress byte ceiling exceeded")
            if _diagnostic_os_write(fd, raw) != len(raw):
                raise OSError("incomplete progress write")
            after = _diagnostic_os_fstat(fd)
            if (
                _progress_stamp(
                    _diagnostic_os_stat(
                        self.progress.name, dir_fd=parent, follow_symlinks=False
                    )
                )
                != _progress_stamp(after)
                or _diagnostic_os_lstat(self.report.parent)[:3]
                != _diagnostic_os_fstat(parent)[:3]
            ):
                raise ValueError("progress pathname changed")
            self.progress_identity = _progress_stamp(after)
        finally:
            if fd is not None:
                _diagnostic_os_close(fd)
            _diagnostic_os_close(parent)
            self.reporting_seconds += _diagnostic_monotonic() - started

    def pytest_itemcollected(self, item):
        # Collection modifiers run after this event. Expanding a declared class
        # or function from their reduced list would silently certify omissions.
        node = item.nodeid
        if node in self.collected_ids or len(self.full) >= MAX_TESTS:
            raise ValueError("duplicate or oversized original collection")
        self.collected_ids.add(node)
        self.full.append(node)

    def pytest_collection_modifyitems(self, session, config, items):
        if self.selection is None:
            groups = partition(self.full)
            self.counts = {name: len(nodes) for name, nodes in groups.items()}
            self.selected = groups[self.group]
        else:
            expansions = expand_selectors(self.full, self.selection)
            wanted = {node for nodes in expansions.values() for node in nodes}
            self.selected = [node for node in self.full if node in wanted]
            self.counts = {self.group: len(self.selected)}
        if not self.selected:
            raise ValueError("required group collected no tests")
        wanted = set(self.selected)
        deselected = [item for item in items if item.nodeid not in wanted]
        items[:] = [item for item in items if item.nodeid in wanted]
        config.hook.pytest_deselected(items=deselected)
        self.collection_seconds = _diagnostic_monotonic() - self.started
        self._progress(
            "collection",
            inventory=self.full,
            selected=self.selected,
            group_counts=self.counts,
            seconds=self.collection_seconds,
        )

    def pytest_collection_finish(self, session):
        # Also catch modifiers that run after our own selection. Reordering is
        # harmless; missing, injected or duplicated required items are not.
        actual = [item.nodeid for item in session.items]
        if len(actual) != len(self.selected) or set(actual) != set(self.selected):
            self.errors.append("collection modifiers changed required inventory")
            raise ValueError("collection modifiers changed required inventory")

    def pytest_collectreport(self, report):
        if report.failed:
            self.errors.append("collection failed")
            self._progress("collection-failure", nodeid=report.nodeid,
                           outcome=report.outcome, failure=self._failure_detail(report))

    def pytest_runtest_logreport(self, report):
        # Pytest 9 emits real subtest call reports before the parent's call
        # report. They are additional evidence, not repeated parent phases.
        try:
            from _pytest.subtests import SubtestReport
        except ImportError:
            SubtestReport = ()  # Older pytest emits only the parent reports.
        if isinstance(report, SubtestReport):
            self.subtest_count += 1
            if self.subtest_count > MAX_TESTS:
                if self.subtest_count == MAX_TESTS + 1:
                    self.errors.append("subtest inventory exceeds count ceiling")
                return
            phases = self.phases.get(report.nodeid, {})
            if (
                report.nodeid not in self.selected
                or report.when != "call"
                or phases.get("setup", {}).get("outcome") != "passed"
                or "call" in phases
                or "teardown" in phases
            ):
                self.errors.append("subtest outside selected parent call interval")
            rows = self.subtests.setdefault(report.nodeid, [])
            rows.append(
                {
                    "ordinal": len(rows) + 1,
                    "outcome": report.outcome,
                    "duration": report.duration,
                }
            )
            self._progress(
                "subtest",
                nodeid=report.nodeid,
                ordinal=len(rows),
                when=report.when,
                outcome=report.outcome,
                duration=report.duration,
                **({"failure": self._failure_detail(report)} if report.outcome == "failed" else {}),
            )
            if report.outcome != "passed" and self.selection is None:
                self.errors.append(
                    "required subtest failed or skipped: " + report.nodeid
                )
            return
        phases = self.phases.setdefault(report.nodeid, {})
        if report.when in phases:
            self.errors.append("duplicate execution phase")
        # An inventory is execution evidence only when parent phases arrive in
        # lifecycle order. Failed/skipped setup legitimately proceeds directly
        # to teardown; sessionfinish still decides the one applicable host skip.
        prior = set(phases)
        ordered = (
            (report.when == "setup" and not prior)
            or (
                report.when == "call"
                and prior == {"setup"}
                and phases["setup"]["outcome"] == "passed"
            )
            or (
                report.when == "teardown"
                and (
                    prior == {"setup", "call"}
                    or (prior == {"setup"} and phases["setup"]["outcome"] != "passed")
                )
            )
        )
        if not ordered:
            self.errors.append("execution phase outside parent lifecycle order")
        wasxfail = getattr(report, "wasxfail", None)
        # Pytest's strict XPASS producer marks a failed call with this string
        # instead of setting wasxfail. It is never an actual failed assertion
        # and therefore cannot satisfy an acceptance expected-fail case.
        longrepr = getattr(report, "longrepr", None)
        if (
            wasxfail is None
            and isinstance(longrepr, str)
            and longrepr.startswith("[XPASS(strict)] ")
        ):
            wasxfail = longrepr
        phases[report.when] = {
            "outcome": report.outcome,
            "duration": report.duration,
            "wasxfail": wasxfail,
        }
        self._progress(
            "phase",
            nodeid=report.nodeid,
            when=report.when,
            outcome=report.outcome,
            duration=report.duration,
            **({"failure": self._failure_detail(report)} if report.outcome == "failed" else {}),
        )

    def pytest_sessionfinish(self, session, exitstatus):
        if set(self.phases) != set(self.selected):
            self.errors.append("execution did not cover exact selected inventory")
        for node, phases in self.phases.items():
            if self.selection is not None:
                continue  # Caller checks exact polarity; lifecycle errors still refuse.
            # The one host-specific Darwin control is inapplicable on other OSes.
            host_skip = (
                sys.platform != "darwin"
                and node
                == AP
                + "/test_evaluation_artifacts.py::test_mac_worker_cannot_fork_or_spawn_a_process_outside_the_deadline"
            )
            if (
                host_skip
                and set(phases) == {"setup", "teardown"}
                and phases["setup"]["outcome"] == "skipped"
                and phases["teardown"]["outcome"] == "passed"
            ):
                continue
            if set(phases) != {"setup", "call", "teardown"} or any(
                p["outcome"] != "passed" for p in phases.values()
            ):
                self.errors.append("required execution failed or skipped: " + node)
        self._progress("sessionfinish", exitstatus=int(exitstatus), errors=self.errors)
        timing = {
            "collection_seconds": self.collection_seconds,
            "elapsed_seconds": _diagnostic_monotonic() - self.started,
            "reporting_seconds": self.reporting_seconds,
            "phase_seconds": {
                key: sum(
                    row.get(key, {}).get("duration", 0) for row in self.phases.values()
                )
                for key in ("setup", "call", "teardown")
            },
        }
        payload = {
            "timing": timing,
            "group": self.group,
            "inventory": self.full,
            "selected": self.selected,
            "group_counts": self.counts,
            "phases": self.phases,
            "errors": self.errors,
            "subtests": self.subtests,
            "exitstatus": int(exitstatus),
        }
        raw = _diagnostic_dumps(payload, sort_keys=True).encode()
        if len(raw) > REPORT_BYTES:
            self.errors.append("inventory report exceeds byte ceiling")
        else:
            with _diagnostic_open_file(self.report, "xb") as stream:
                stream.write(raw)
                stream.flush()
                _diagnostic_os_fsync(stream.fileno())
        if self.errors:
            session.exitstatus = 1


def expand_selectors(
    inventory: list[str], selectors: list[str]
) -> dict[str, list[str]]:
    """Each declared function selector owns itself or its parameter expansions."""
    if (
        not isinstance(inventory, list)
        or not inventory
        or len(inventory) > MAX_TESTS
        or any(not isinstance(n, str) or not n for n in inventory)
        or len(set(inventory)) != len(inventory)
        or not isinstance(selectors, list)
        or not selectors
        or len(selectors) > MAX_TESTS
        or any(not isinstance(s, str) or "::" not in s for s in selectors)
        or len(set(selectors)) != len(selectors)
    ):
        raise ValueError("invalid or duplicate selection inventory")
    result = {
        s: [
            n
            for n in inventory
            if n == s or n.startswith(s + "[") or n.startswith(s + "::")
        ]
        for s in selectors
    }
    if any(not nodes for nodes in result.values()):
        raise ValueError("declared selector has no collected tests")
    return result


def read_inventory(path: Path):
    """Use the diagnostic owner's descriptor/stability rules for final JSON too."""
    if path.parent.resolve(strict=True) != path.parent:
        raise ValueError("inventory parent is an alias")
    parent = _diagnostic_os_lstat(path.parent)
    fd = _diagnostic_os_open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        before = _diagnostic_os_fstat(fd)
        if (
            not _diagnostic_is_regular(before.st_mode)
            or before.st_nlink != 1
            or before.st_uid != _diagnostic_os_getuid()
            or before.st_mode & 0o022
            or before.st_size > REPORT_BYTES
        ):
            raise ValueError("invalid final inventory custody")
        raw = bytearray()
        while len(raw) < before.st_size:
            block = _diagnostic_os_read(fd, min(65536, before.st_size - len(raw)))
            if not block:
                raise ValueError("incomplete final inventory")
            raw.extend(block)
        if (
            _progress_stamp(before) != _progress_stamp(_diagnostic_os_fstat(fd))
            or _progress_stamp(before) != _progress_stamp(_diagnostic_os_lstat(path))
            or parent[:3] != _diagnostic_os_lstat(path.parent)[:3]
        ):
            raise ValueError("inventory changed during read")

        def unique(pairs):
            result = {}
            for key, value in pairs:
                if key in result:
                    raise ValueError("duplicate inventory JSON key")
                result[key] = value
            return result

        return _diagnostic_loads(raw, object_pairs_hook=unique)
    finally:
        _diagnostic_os_close(fd)


def selection_results(payload: dict, selectors: list[str]) -> tuple[dict, dict]:
    """Independently consume complete phase evidence; exit 0 alone proves nothing."""
    if not isinstance(payload, dict) or payload.get("group") != "acceptance":
        raise ValueError("wrong acceptance inventory")
    expanded = expand_selectors(payload.get("inventory"), selectors)
    wanted = {n for nodes in expanded.values() for n in nodes}
    selected = payload.get("selected")
    if (
        not isinstance(selected, list)
        or len(selected) != len(wanted)
        or set(selected) != wanted
        or payload.get("errors") != []
        or not isinstance(payload.get("phases"), dict)
        or set(payload["phases"]) != wanted
        or type(payload.get("exitstatus")) is not int
        or payload["exitstatus"] not in (0, 1)
    ):
        raise ValueError("incomplete acceptance execution inventory")
    statuses = {}
    for node in selected:
        phases = payload["phases"][node]
        if (
            not isinstance(phases, dict)
            or set(phases) != {"setup", "call", "teardown"}
            or any(
                not isinstance(p, dict)
                or "wasxfail" not in p
                or p["wasxfail"] is not None
                or type(p.get("duration")) not in (int, float)
                or not math.isfinite(p["duration"])
                or p["duration"] < 0
                or p.get("outcome") not in ("passed", "failed")
                for p in phases.values()
            )
            or any(phases[k]["outcome"] != "passed" for k in ("setup", "teardown"))
        ):
            raise ValueError(
                "skipped, xfail or unsuccessful fixture lifecycle: " + node
            )
        statuses[node] = phases["call"]["outcome"]
    subtests = payload.get("subtests", {})
    if not isinstance(subtests, dict) or set(subtests) - wanted:
        raise ValueError("unexpected subtest inventory")
    subtest_count = 0
    for node, rows in subtests.items():
        if not isinstance(rows, list):
            raise ValueError("invalid subtest evidence")
        subtest_count += len(rows)
        if subtest_count > MAX_TESTS:
            raise ValueError("subtest inventory exceeds count ceiling")
        for index, row in enumerate(rows):
            if (
                not isinstance(row, dict)
                or type(row.get("ordinal")) is not int
                or row.get("ordinal") != index + 1
                or row.get("outcome") not in ("passed", "failed")
                or type(row.get("duration")) not in (int, float)
                or not math.isfinite(row["duration"])
                or row["duration"] < 0
            ):
                raise ValueError("invalid or skipped subtest")
            if row["outcome"] == "failed":
                statuses[node] = "failed"
    expected_exit = 1 if "failed" in statuses.values() else 0
    if payload["exitstatus"] != expected_exit:
        raise ValueError("process exit disagrees with actual test outcomes")
    return expanded, statuses


def pytest_configure(config):
    selection_path = os.environ.get("SYNTHESIS_ACCEPTANCE_SELECTION")
    if selection_path:
        selectors = read_inventory(Path(selection_path))
        if not isinstance(selectors, list):
            raise ValueError("acceptance selection is not a list")
        config.pluginmanager.register(
            InventoryPlugin(
                "acceptance",
                Path(os.environ["SYNTHESIS_RELEASE_TEST_REPORT"]),
                selectors,
            ),
            "release-inventory",
        )
        return
    group = os.environ.get("SYNTHESIS_RELEASE_TEST_GROUP")
    if group:
        if group not in GROUPS:
            raise ValueError("unknown release test group")
        config.pluginmanager.register(
            InventoryPlugin(group, Path(os.environ["SYNTHESIS_RELEASE_TEST_REPORT"])),
            "release-inventory",
        )


def run_group(root: Path, group: str) -> tuple[int, dict]:
    deadline = time.monotonic() + CHECK_SECONDS - 5
    before = source_digest(root)
    with retained_group_fixture() as temp:
        report = temp / "inventory.json"
        env = dict(os.environ)
        # External pytest flags/plugins cannot deselect, repeat or short-circuit a gate.
        env.pop("PYTEST_ADDOPTS", None)
        env.pop("PYTEST_PLUGINS", None)
        env.update(
            {
                "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1",
                "PYTHONDONTWRITEBYTECODE": "1",
                "SYNTHESIS_RELEASE_TEST_GROUP": group,
                "SYNTHESIS_RELEASE_TEST_REPORT": str(report),
                "PYTHONPATH": str(Path(__file__).resolve().parent),
                "TMPDIR": str(temp),
            }
        )
        started = time.monotonic()
        completed = bounded_run(
            [
                sys.executable,
                "-m",
                "pytest",
                AP,
                "-q",
                "-o",
                "addopts=",
                "-p",
                "no:cacheprovider",
                "-p",
                "release_check_groups",
                "--basetemp",
                str(temp / "pytest"),
                "--durations=20",
            ],
            root,
            min(GROUP_SECONDS, deadline - time.monotonic() - 33),
            env,
        )
        print(completed.stdout, end="")
        if not report.is_file() or report.stat().st_size > REPORT_BYTES:
            try:
                diagnostic = read_progress(report.with_suffix(".progress.jsonl"))
            except (OSError, ValueError, KeyError, TypeError) as error:
                diagnostic = {
                    "status": "UNAVAILABLE",
                    "authorizes_success": False,
                    "error": str(error),
                }
            return 1, {
                "partial_execution": diagnostic,
                "group": group,
                "fixture_custody": str(temp),
                "error": "missing or oversized execution inventory",
            }
        payload = json.loads(report.read_text())
        payload["fixture_custody"] = str(temp)
        # Independently validate plugin output rather than trusting its return code alone.
        try:
            groups = partition(payload["inventory"])
        except (ValueError, KeyError, TypeError) as error:
            payload["error"] = str(error)
            groups = None
        if (
            groups is None
            or payload["selected"] != groups[group]
            or payload["errors"]
            or payload["exitstatus"] != 0
        ):
            try:
                payload["partial_execution"] = read_progress(report.with_suffix(".progress.jsonl"))
            except (OSError, ValueError, KeyError, TypeError) as error:
                payload["partial_execution"] = {"status": "UNAVAILABLE", "authorizes_success": False,
                                                "error": str(error)}
            return 1, payload
        if before != source_digest(root):
            return 1, {
                "group": group,
                "fixture_custody": str(temp),
                "error": "source changed during required checks",
            }
        payload.update({"source_sha256": before, "seconds": time.monotonic() - started})
        return completed.returncode, payload


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--group", choices=GROUPS, required=True)
    args = parser.parse_args(argv)
    try:
        code, payload = run_group(Path(__file__).resolve().parents[3], args.group)
        if code:
            # Keep the actionable reason ahead of the complete inventory; some
            # log clients omit the large single-line JSON report.
            reasons = payload.get("errors") or [
                payload.get("error", "required check failed")
            ]
            print(
                "FAIL release group "
                + args.group
                + ": "
                + "; ".join(dict.fromkeys(reasons))[:2048]
            )
        print(json.dumps(payload, sort_keys=True))
        return code
    except (OSError, ValueError, KeyError) as error:
        print("FAIL release group: " + str(error))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
