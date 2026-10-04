#!/usr/bin/env python3
"""Bounded, exhaustive release groups, using ordinary pytest collection.

Every group collects the entire directory before selecting its exact partition.
No file allowlist: newly collected files enter core unless a domain rule owns them.
Reports bind full/selected node IDs, all three execution phases and source bytes.
"""

from __future__ import annotations

import argparse
import base64
import binascii
from contextlib import contextmanager
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
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
import threading
import time
from types import FunctionType
import zlib

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
_diagnostic_os_getcwd = os.getcwd
_diagnostic_os_fsync = os.fsync
_diagnostic_is_regular = stat.S_ISREG
_diagnostic_mode = stat.S_IMODE
_diagnostic_dumps = json.dumps
_diagnostic_loads = json.loads
_diagnostic_sha256 = hashlib.sha256
_diagnostic_open_file = open

GROUPS = ("state", "native", "evaluation", "core", "native-control", "timing")
AP = "skills/synthesis-autopilot/scripts"
OB = "skills/synthesis-onboarding/scripts"
ONBOARDING_RULES = {
    "onboarding-runtime": ("test_release_runtime", "test_runtime_integration", "test_runtime_doctors", "test_managed_runtime", "test_signed_receipt", "test_p13_", "test_local_messaging_runtime"),
    "onboarding-payload": ("test_runtime_payload", "test_b11_"),
    "onboarding-instructions": ("test_instruction_", "test_kb_"),
    "onboarding-enrollment": ("test_additive_", "test_team_", "test_fleet_", "test_organization", "test_upgrade_"),
    "onboarding-clients": ("test_native_", "test_long_transcript", "test_stop_", "test_plugin_", "test_reload_", "test_client_"),
}
ONBOARDING_GROUPS = (*ONBOARDING_RULES, "onboarding-core")
ALL_GROUPS = (*GROUPS, *ONBOARDING_GROUPS)
CHECK_SECONDS = 900
ACCEPTANCE_SECONDS = 6000  # finite whole-suite owner, not a per-group allowance
GROUP_SECONDS = 880  # collection, execution and reporting; 20s outer cleanup reserve
OUTPUT_BYTES = 8 * 1024 * 1024
# A receipt carries repeated collection/phase evidence from many bounded groups.
# Its lossless transport shares the ordinary output ceiling; decompression has
# its own finite ceiling and never changes test or process admission limits.
RECEIPT_BYTES = 32 * 1024 * 1024
RECEIPT_JSON_DEPTH = 64
RECEIPT_TRANSPORT = "acceptance-receipt-zlib-v1"
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


class _ReceiptJSONDepth:
    """Bound nesting before JSON decoding, independent of interpreter limits."""

    def __init__(self):
        self.depth = 0
        self.quoted = False
        self.escaped = False

    def check(self, text):
        for character in text:
            if self.quoted:
                if self.escaped:
                    self.escaped = False
                elif character == "\\":
                    self.escaped = True
                elif character == '"':
                    self.quoted = False
            elif character == '"':
                self.quoted = True
            elif character in "[{":
                self.depth += 1
                if self.depth > RECEIPT_JSON_DEPTH:
                    raise ValueError("acceptance receipt JSON depth exceeded")
            elif character in "]}":
                self.depth -= 1


def encode_acceptance_receipt(payload: dict) -> str:
    """Losslessly frame one receipt without building its full JSON byte string.

    No fields are omitted. An oversized receipt refuses; it is never truncated
    or represented as success. The source/transaction consumer still decides
    whether the decoded evidence establishes authority.
    """
    if not isinstance(payload, dict):
        raise ValueError("acceptance receipt must be an object")
    compressor = zlib.compressobj()
    compressed = bytearray()
    digest = hashlib.sha256()
    size = 0
    nesting = _ReceiptJSONDepth()

    def retain(data):
        if len(compressed) + len(data) > (OUTPUT_BYTES // 4) * 3:
            raise ValueError("acceptance receipt transport exceeds byte ceiling")
        compressed.extend(data)

    try:
        encoder = json.JSONEncoder(
            sort_keys=True, separators=(",", ":"), allow_nan=False
        )
        for piece in encoder.iterencode(payload):
            # The encoder emits ASCII (including escapes); count before encoding.
            size += len(piece)
            if size > RECEIPT_BYTES:
                raise ValueError("acceptance receipt exceeds decoded byte ceiling")
            nesting.check(piece)
            for offset in range(0, len(piece), 65536):
                raw = piece[offset : offset + 65536].encode("ascii")
                digest.update(raw)
                retain(compressor.compress(raw))
        retain(compressor.flush())
    except (TypeError, RecursionError, zlib.error) as exc:
        raise ValueError("acceptance receipt serialization refused") from exc
    wire = json.dumps(
        {
            "receipt_transport": RECEIPT_TRANSPORT,
            "payload_bytes": size,
            "payload_sha256": digest.hexdigest(),
            "payload": base64.b64encode(compressed).decode("ascii"),
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    if len(wire) + 1 > OUTPUT_BYTES:  # Include the producer's terminal newline.
        raise ValueError("acceptance receipt transport exceeds byte ceiling")
    return wire


def parse_acceptance_json(raw, *, max_bytes=RECEIPT_BYTES):
    """Bound receipt/error JSON before allocating its structured representation."""
    if not isinstance(raw, (str, bytes)) or len(raw) > max_bytes:
        raise ValueError("acceptance receipt JSON byte ceiling exceeded")
    text = raw.decode("utf-8") if isinstance(raw, bytes) else raw
    if len(text.encode("utf-8")) > max_bytes:
        raise ValueError("acceptance receipt JSON byte ceiling exceeded")
    _ReceiptJSONDepth().check(text)

    def unique(rows):
        value = {}
        for key, item in rows:
            if key in value:
                raise ValueError("duplicate acceptance receipt JSON key")
            value[key] = item
        return value

    def invalid_constant(_value):
        raise ValueError("non-finite acceptance receipt JSON value")

    def finite_float(value):
        result = float(value)
        if not math.isfinite(result):
            raise ValueError("non-finite acceptance receipt JSON value")
        return result

    return json.loads(text, object_pairs_hook=unique,
                      parse_constant=invalid_constant, parse_float=finite_float)


def decode_acceptance_receipt(output: str | bytes) -> dict:
    """Read one bounded frame; reject ambiguous, corrupt or expanding evidence."""
    if not isinstance(output, (str, bytes)) or len(output) > OUTPUT_BYTES:
        raise ValueError("acceptance receipt transport exceeds byte ceiling")

    try:
        wire = output.encode("ascii") if isinstance(output, str) else output
        envelope = parse_acceptance_json(wire, max_bytes=OUTPUT_BYTES)
        if (
            not isinstance(envelope, dict)
            or set(envelope)
            != {"receipt_transport", "payload_bytes", "payload_sha256", "payload"}
            or envelope["receipt_transport"] != RECEIPT_TRANSPORT
            or type(envelope["payload_bytes"]) is not int
            or not 0 < envelope["payload_bytes"] <= RECEIPT_BYTES
            or not isinstance(envelope["payload_sha256"], str)
            or len(envelope["payload_sha256"]) != 64
            or any(c not in "0123456789abcdef" for c in envelope["payload_sha256"])
            or not isinstance(envelope["payload"], str)
        ):
            raise ValueError("acceptance receipt transport metadata refused")
        packed = base64.b64decode(envelope["payload"], validate=True)
        inflater = zlib.decompressobj()
        # The declared bound is checked before expansion. A lying length may
        # produce at most one extra byte; never use unbounded decompress/flush.
        raw = inflater.decompress(packed, envelope["payload_bytes"] + 1)
        if (
            len(raw) != envelope["payload_bytes"]
            or not inflater.eof
            or inflater.unused_data
            or inflater.unconsumed_tail
            or hashlib.sha256(raw).hexdigest() != envelope["payload_sha256"]
        ):
            raise ValueError("acceptance receipt transport integrity refused")
        payload = parse_acceptance_json(raw)
        if not isinstance(payload, dict):
            raise ValueError("acceptance receipt must be an object")
        return payload
    except (UnicodeError, binascii.Error, zlib.error, RecursionError) as exc:
        raise ValueError("acceptance receipt transport refused") from exc


def is_timing_sensitive_selector(selector: str) -> bool:
    """Identify actual wall-clock owner controls, including ancestor selectors.

    These tests invoke unchanged production deadlines. Isolation prevents other
    release fixtures from competing with them; it grants no extra time or work.
    Exact paths prevent unrelated similarly named tests from acquiring this lane.
    """
    path, separator, node = selector.partition("::")
    if path == AP + "/test_managed_native_owner.py":
        return True
    if path != AP + "/test_journal_storage.py":
        return False
    if not separator:
        return True
    return node.split("[", 1)[0] in (
        "test_native_history_crosses_snapshot_limit_and_recovers_exactly",
        "test_atomic_append_replay_projection_rebuild_and_operator",
    )


def group_for(nodeid: str) -> str:
    path = nodeid.split("::", 1)[0]
    if path.startswith(OB + "/"):
        if not path.endswith(".py") or ".." in Path(path).parts:
            raise ValueError("collection escaped the onboarding directory")
        choices = [group for group, prefixes in ONBOARDING_RULES.items()
                   if Path(path).name.startswith(prefixes)]
        if len(choices) > 1:
            raise ValueError("overlapping group ownership")
        return choices[0] if choices else "onboarding-core"
    if (
        not path.startswith(AP + "/")
        or not path.endswith(".py")
        or ".." in Path(path).parts
    ):
        raise ValueError("collection escaped the autopilot directory")
    if is_timing_sensitive_selector(nodeid):
        return "timing"
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


def partition(nodeids: list[str], *, group=None) -> dict[str, list[str]]:
    if not nodeids or len(nodeids) > MAX_TESTS or len(set(nodeids)) != len(nodeids):
        raise ValueError("empty, duplicate or oversized collection")
    onboarding = (group in ONBOARDING_GROUPS if group is not None
                  else nodeids[0].startswith(OB + "/"))
    groups = {name: [] for name in (ONBOARDING_GROUPS if onboarding else GROUPS)}
    for node in nodeids:
        owner = group_for(node)
        if owner not in groups:
            raise ValueError("mixed release collection domains")
        groups[owner].append(node)
    if sorted(n for nodes in groups.values() for n in nodes) != sorted(nodeids):
        raise ValueError("non-exhaustive partition")
    return groups


def source_digest(root: Path, *, portable=False) -> str:
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
            json.dumps([relative, 0 if portable else stat.S_IMODE(initial.st_mode), "directory"]).encode()
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
                            [path, (0o755 if mode & 0o111 else 0o644) if portable else stat.S_IMODE(mode), member.hexdigest()],
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
    cancel_event=None,
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
    initial_identity = None
    custody_records = {}

    def interrupted(signum, _frame):
        raise CheckInterrupted(f"check interrupted by signal {signum}")

    try:
        if threading.current_thread() is threading.main_thread():
            for sig in (signal.SIGTERM, signal.SIGINT):
                old[sig] = signal.signal(sig, interrupted)
        elif cancel_event is None:
            raise ValueError("parallel checks require an owning cancellation event")
        if cancel_event is not None and cancel_event.is_set():
            raise CheckInterrupted("check cancelled before launch")
        child_env = dict(os.environ if env is None else env)
        cache = fixture_root("synthesis-required-check-", child_env)
        custody_fd = os.open(cache, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        initial_identity = custody_identity(os.fstat(custody_fd))
        (cache / "tmp").mkdir(mode=0o700)
        executed = fixture_command(command, cache)
        child_env.pop("PYTEST_ADDOPTS", None)
        child_env.pop("PYTEST_PLUGINS", None)
        child_env.pop("SYNTHESIS_ACCEPTANCE_DIAGNOSTICS", None)
        child_env.pop("GITHUB_OUTPUT", None)
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
                if cancel_event is not None and cancel_event.is_set():
                    raise CheckInterrupted("check cancelled by parallel owner")
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
            # Closing output is not process termination. Continue observing the
            # shared cancellation event while a quiet child remains alive.
            while process.poll() is None:
                if cancel_event is not None and cancel_event.is_set():
                    raise CheckInterrupted("required check cancelled by parallel owner")
                remaining = timeout - (time.monotonic() - started)
                if remaining <= 0:
                    raise TimeoutError("required check exceeded its unchanged wall-time ceiling")
                try:
                    process.wait(timeout=min(.1, remaining))
                except subprocess.TimeoutExpired:
                    pass
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
                    custody_records[name] = {
                        "identity": list(_progress_stamp(os.fstat(stream.fileno()))),
                        "sha256": hashlib.sha256(content.encode()).hexdigest(),
                    }
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
            failure = "required-check custody could not be retained: " + str(error)
            text += (
                "\nFAIL required-check custody could not be retained: "
                + str(error)
                + "\n"
            )
    if custody_fd is not None:
        os.close(custody_fd)
    result = subprocess.CompletedProcess(executed, code, text, "")
    result.fixture_custody = str(cache) if cache is not None else None
    result.fixture_identity = initial_identity
    result.custody_records = custody_records
    result.failure = failure
    result.process_id = None if process is None else process.pid
    return result


def bounded_map(items, worker, *, workers=4, stop_when=None, on_result=None,
                exclusive_when=None):
    """Run at most four independent checks; drain owned children on every exit.

    The main thread owns signals. Each worker must pass the shared cancellation
    event to bounded_run, which retains output and reaps its own process group.
    Results keep input order; None explicitly identifies work never admitted.
    """
    if type(workers) is not int or not 1 <= workers <= 4:
        raise ValueError("check concurrency must be between one and four")
    if threading.current_thread() is not threading.main_thread():
        raise ValueError("parallel checks require a main-thread owner")
    items = list(items)
    exclusive = [bool(exclusive_when(item)) if exclusive_when else False for item in items]
    results = [None] * len(items)
    cancel = threading.Event()
    old = {}

    def interrupted(signum, _frame):
        cancel.set()
        raise CheckInterrupted(f"parallel checks interrupted by signal {signum}")

    try:
        for sig in (signal.SIGTERM, signal.SIGINT):
            old[sig] = signal.signal(sig, interrupted)
        with ThreadPoolExecutor(max_workers=workers) as pool:
            active = {}
            next_index = 0
            try:
                while active or next_index < len(items):
                    while not cancel.is_set() and len(active) < workers and next_index < len(items):
                        # A wall-clock-sensitive protocol fixture must not compete
                        # with an already admitted CPU-heavy check on this runner.
                        if active and (exclusive[next_index] or any(exclusive[i] for i in active.values())):
                            break
                        active[pool.submit(worker, items[next_index], cancel)] = next_index
                        next_index += 1
                        if exclusive[next_index - 1]:
                            break
                    if not active:
                        break
                    done, _ = wait(active, timeout=0.1, return_when=FIRST_COMPLETED)
                    for future in done:
                        index = active.pop(future)
                        value = future.result()
                        results[index] = value
                        if on_result is not None:
                            on_result(index, value)
                        if stop_when is not None and stop_when(value):
                            cancel.set()
            finally:
                cancel.set()
                # The executor waits for bounded_run cleanup and retained output.
                for sig in old:
                    signal.signal(sig, signal.SIG_IGN)
    finally:
        cancel.set()
        for sig, handler in old.items():
            signal.signal(sig, handler)
    return results


DIAGNOSTIC_RECORDS = 4096
DIAGNOSTIC_BYTES = 32 * 1024 * 1024
DIAGNOSTIC_SECONDS = 10


def check_diagnostic_capacity(plan: list[dict]) -> int:
    """Refuse an impossible complete capture before running acceptance tests.

    Two outer records and six per batch are retained, including missing-record
    metadata. Finalization also checks the ceiling, so leave one slot unused.
    The independent byte, time, identity and privacy limits still apply.
    """
    required = 2 + 6 * len(plan)
    if required >= DIAGNOSTIC_RECORDS:
        raise ValueError(
            f"diagnostic capacity: {required} planned records must be below {DIAGNOSTIC_RECORDS}"
        )
    return required


def custody_identity(info):
    return [info.st_dev, info.st_ino, info.st_mode, info.st_uid]


def diagnostic_record(path: Path, deadline: float, parent_identity: list) -> dict:
    """Pin bounded records through the already-owned group directory."""
    if time.monotonic() >= deadline or path.parent.resolve(strict=True) != path.parent:
        raise ValueError("diagnostic source pin deadline or alias")
    parent = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    fd = None
    try:
        if custody_identity(os.fstat(parent)) != parent_identity:
            raise ValueError("diagnostic source parent changed")
        try:
            fd = os.open(
                path.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent
            )
        except FileNotFoundError:
            return {"status": "MISSING"}
        before = os.fstat(fd)
        if (
            not stat.S_ISREG(before.st_mode)
            or before.st_nlink != 1
            or before.st_uid != os.getuid()
            or before.st_mode & 0o022
            or before.st_size > REPORT_BYTES
        ):
            raise ValueError("diagnostic source record refused")
        digest = hashlib.sha256()
        left = before.st_size
        while left:
            if time.monotonic() >= deadline:
                raise ValueError("diagnostic source pin deadline")
            data = os.read(fd, min(left, 65536))
            if not data:
                raise ValueError("diagnostic source truncated")
            digest.update(data)
            left -= len(data)
        identity = _progress_stamp(before)
        if (
            identity != _progress_stamp(os.fstat(fd))
            or identity
            != _progress_stamp(os.stat(path.name, dir_fd=parent, follow_symlinks=False))
            or custody_identity(path.parent.lstat()) != parent_identity
        ):
            raise ValueError("diagnostic source changed")
        return {"identity": list(identity), "sha256": digest.hexdigest()}
    finally:
        if fd is not None:
            os.close(fd)
        os.close(parent)


@contextmanager
def _diagnostic_directory_chain(path: Path, deadline: float):
    """Hold and recheck the no-alias chain through one observed closure."""
    if (
        not path.is_absolute()
        or path.resolve(strict=True) != path
        or len(path.parts) > 256
    ):
        raise ValueError("diagnostic directory ancestry refused")
    fds = []
    links = []

    def bound():
        if time.monotonic() >= deadline:
            raise ValueError("diagnostic directory ancestry deadline")

    def identity(info):
        return custody_identity(info) + [info.st_gid]

    def check():
        for parent, name, fd, expected in links:
            bound()
            current = os.stat(name, dir_fd=parent, follow_symlinks=False)
            if (
                not stat.S_ISDIR(current.st_mode)
                or identity(current) != expected
                or identity(os.fstat(fd)) != expected
            ):
                raise ValueError("diagnostic directory ancestry changed")

    try:
        parent = None
        for name in (path.anchor, *path.parts[1:]):
            bound()
            before = os.stat(name, dir_fd=parent, follow_symlinks=False)
            if not stat.S_ISDIR(before.st_mode):
                raise ValueError("diagnostic directory ancestry is not ordinary")
            fd = os.open(
                name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent
            )
            fds.append(fd)
            expected = identity(before)
            if identity(os.fstat(fd)) != expected:
                raise ValueError("diagnostic directory ancestry changed on open")
            links.append((parent, name, fd, expected))
            parent = fd
        check()
        yield parent, [row[3] for row in links], check
    finally:
        for fd in reversed(fds):
            os.close(fd)


def prepare_diagnostics_destination(path: Path, source: Path) -> dict:
    """An explicit new, private external destination; never adopt old output."""
    path = Path(path)
    if (
        not path.is_absolute()
        or path.parent.resolve(strict=True) != path.parent
        or path == source.resolve()
        or source.resolve() in path.parents
        or path.name in {"", ".", ".."}
    ):
        raise ValueError(
            "diagnostic destination must be new, canonical and outside source"
        )
    with _diagnostic_directory_chain(
        path.parent, time.monotonic() + DIAGNOSTIC_SECONDS
    ) as (parent, ancestors, check_ancestors):
        os.mkdir(path.name, 0o700, dir_fd=parent)
        fd = os.open(
            path.name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent
        )
        try:
            info = os.fstat(fd)
            if info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != 0o700:
                raise ValueError("diagnostic destination ownership refused")
            check_ancestors()
            if custody_identity(path.lstat()) != custody_identity(info):
                raise ValueError("diagnostic destination changed on creation")
            return {
                "path": str(path),
                "identity": custody_identity(info),
                "ancestors": ancestors + [custody_identity(info) + [info.st_gid]],
            }
        finally:
            os.close(fd)


def capture_acceptance_diagnostics(
    completed,
    source: Path,
    plan: list[dict],
    binding: dict,
    destination: dict | None = None,
    *,
    deadline: float | None = None,
) -> dict:
    """Copy only exact owned records locally; export only a closed public schema.

    No log, traceback, environment, parameter text or absolute path is exported.
    Diagnostic completeness is not acceptance or authority. A configured failure
    must block the consumer even if its test receipt otherwise looks successful.
    """
    until = min(
        time.monotonic() + DIAGNOSTIC_SECONDS,
        deadline if deadline is not None else float("inf"),
    )
    fds = []
    anchors = []
    closed_batches = []
    members = []
    total = 0
    root_fd = None
    raw_fd = None
    export_closed = False
    public = {
        "schema": "acceptance-diagnostics-v1",
        "authorizes_release": False,
        "status": "REFUSED",
        "binding_sha256": hashlib.sha256(
            json.dumps(binding, sort_keys=True).encode()
        ).hexdigest(),
        "planned_batches": len(plan),
        "not_admitted_batches": len(plan),
        "reason": "CUSTODY_OR_LIMIT_REFUSED",
        "batches": [],
        "records": [],
        "withheld": [
            "raw-output",
            "exception-text",
            "absolute-paths",
            "parameter-values",
            "environment",
            "fixture-trees",
        ],
    }

    def bound():
        if (
            time.monotonic() >= until
            or len(members) >= DIAGNOSTIC_RECORDS
            or total > DIAGNOSTIC_BYTES
        ):
            raise ValueError("diagnostic budget refused")

    def stamp(info):
        return _progress_stamp(info)

    def directory(parent, name, expected=None):
        bound()
        info = os.stat(name, dir_fd=parent, follow_symlinks=False)
        if (
            not stat.S_ISDIR(info.st_mode)
            or info.st_uid != os.getuid()
            or info.st_mode & 0o022
        ):
            raise ValueError("diagnostic directory refused")
        fd = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent)
        fds.append(fd)
        if custody_identity(info) != custody_identity(os.fstat(fd)) or (
            expected is not None and custody_identity(info) != expected
        ):
            raise ValueError("diagnostic directory identity changed")
        anchors.append((parent, name, fd, custody_identity(info)))
        return fd

    def check_anchors(selected):
        for parent, name, fd, identity in selected:
            bound()
            info = os.stat(name, dir_fd=parent, follow_symlinks=False)
            if fd is None:
                if stamp(info) != identity:
                    raise ValueError("diagnostic member changed at closure")
            elif (
                custody_identity(info) != identity
                or custody_identity(os.fstat(fd)) != identity
            ):
                raise ValueError("diagnostic directory changed at closure")
        # Close the parent fence after all member checks as well: replacement
        # during a record stat must not make an old open directory authoritative.
        for parent, name, fd, identity in selected:
            if fd is not None:
                bound()
                if (custody_identity(os.stat(name, dir_fd=parent, follow_symlinks=False))
                        != identity or custody_identity(os.fstat(fd)) != identity):
                    raise ValueError("diagnostic directory changed at closure")

    @contextmanager
    def batch_directories(parent, group_name, group_identity,
                          process_name, process_identity, *, remember):
        # Keep only one batch's descriptors live. Saved names and identities
        # are evidence to revalidate, never authority to skip a fresh open.
        first_fd, first_anchor = len(fds), len(anchors)
        try:
            group = directory(parent, group_name, group_identity)
            process = directory(group, process_name, process_identity)
            yield group, process
            check_anchors(anchors[first_anchor:])
            if remember:
                records = []
                for record_parent, name, fd, identity in anchors[first_anchor:]:
                    if fd is None:
                        if record_parent not in (group, process):
                            raise ValueError("diagnostic record parent escaped batch")
                        records.append((record_parent == process, name, identity))
                closed_batches.append((group_name, group_identity, process_name,
                                       process_identity, records))
        finally:
            for fd in reversed(fds[first_fd:]):
                os.close(fd)
            del fds[first_fd:]
            del anchors[first_anchor:]

    def save(parent, name, data):
        bound()
        fd = os.open(
            name,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
            0o600,
            dir_fd=parent,
        )
        try:
            view = memoryview(data)
            while view:
                bound()
                wrote = os.write(fd, view)
                if wrote <= 0:
                    raise OSError("incomplete diagnostic write")
                view = view[wrote:]
            os.fsync(fd)
            finished = stamp(os.fstat(fd))
            if finished != stamp(os.stat(name, dir_fd=parent, follow_symlinks=False)):
                raise ValueError("diagnostic output replaced during write")
            return finished
        finally:
            os.close(fd)

    def read(
        parent, name, label, cap, *, optional=False, expected_hash=None, expected=None
    ):
        nonlocal total
        bound()
        try:
            fd = os.open(
                name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent
            )
        except FileNotFoundError:
            if not optional or expected != {"status": "MISSING"}:
                raise
            members.append({"id": label, "status": "MISSING"})
            return None
        try:
            before = os.fstat(fd)
            if (
                not stat.S_ISREG(before.st_mode)
                or before.st_nlink != 1
                or before.st_uid != os.getuid()
                or before.st_mode & 0o022
                or before.st_size > cap
                or total + before.st_size > DIAGNOSTIC_BYTES
            ):
                raise ValueError("diagnostic record refused")
            raw = bytearray()
            while len(raw) < before.st_size:
                bound()
                part = os.read(fd, min(65536, before.st_size - len(raw)))
                if not part:
                    raise ValueError("diagnostic record truncated")
                raw.extend(part)
            if stamp(before) != stamp(os.fstat(fd)) or stamp(before) != stamp(
                os.stat(name, dir_fd=parent, follow_symlinks=False)
            ):
                raise ValueError("diagnostic record changed")
            if expected is not None and list(stamp(before)) != expected.get("identity"):
                raise ValueError("diagnostic record identity differs from receipt")
            data = bytes(raw)
            digest = hashlib.sha256(data).hexdigest()
            if expected is not None and digest != expected.get("sha256"):
                raise ValueError("diagnostic record bytes differ from receipt")
            if expected_hash is not None and digest != expected_hash:
                raise ValueError("diagnostic captured output changed")
            total += len(data)
            slot = f"{len(members):04d}.bin"
            save(raw_fd, slot, data)
            members.append(
                {
                    "id": label,
                    "status": "RETAINED",
                    "size": len(data),
                    "sha256": digest,
                    "raw_member": slot,
                }
            )
            anchors.append((parent, name, None, stamp(before)))
            return data
        finally:
            os.close(fd)

    def parse(data):
        bound()

        def pairs(rows):
            result = {}
            for key, value in rows:
                if key in result:
                    raise ValueError("duplicate diagnostic JSON key")
                result[key] = value
            return result

        return json.loads(data, object_pairs_hook=pairs)

    def phases(records, selectors):
        clean = []
        for row in records:
            bound()
            if not isinstance(row, dict) or row.get("kind") not in {"phase", "subtest"}:
                continue
            node = row.get("nodeid")
            if not isinstance(node, str) or len(node) > 8192:
                raise ValueError("invalid diagnostic test identity")
            owners = [
                s
                for s in selectors
                if node == s or node.startswith(s + "[") or node.startswith(s + "::")
            ]
            duration = row.get("duration")
            if (
                not owners
                or row.get("when") not in {"setup", "call", "teardown"}
                or row.get("outcome") not in {"passed", "failed", "skipped"}
                or type(duration) not in (int, float)
                or not math.isfinite(duration)
                or duration < 0
            ):
                raise ValueError("invalid diagnostic phase")
            clean.append(
                {
                    "selectors": [s.split("[", 1)[0] for s in owners],
                    "node_sha256": hashlib.sha256(node.encode()).hexdigest(),
                    "kind": row["kind"],
                    "when": row["when"],
                    "outcome": row["outcome"],
                    "seconds": duration,
                }
            )
            site = row.get("failure_site")
            if site is not None:
                source = node.split("::", 1)[0]
                if (
                    row["outcome"] != "failed"
                    or not isinstance(site, dict)
                    or set(site) != {"source_sha256", "line"}
                    or site["source_sha256"] != hashlib.sha256(source.encode()).hexdigest()
                    or type(site["line"]) is not int
                    or not 1 <= site["line"] <= 1000000
                ):
                    raise ValueError("invalid diagnostic failure site")
                clean[-1]["failure_line"] = site["line"]
            if len(clean) > MAX_TESTS * 4:
                raise ValueError("diagnostic phase ceiling")
        return clean

    try:
        # Only public source selectors are eligible. Parameter values remain hashes.
        for batch in plan:
            for selected in batch["selectors"]:
                path, separator, test = selected.partition("::")
                if (
                    not separator
                    or not path.endswith(".py")
                    or Path(path).is_absolute()
                    or any(part in {"", ".", ".."} for part in path.split("/"))
                    or any(not (c.isalnum() or c in "_./-") for c in path)
                    or not test
                    or any(
                        not (c.isalnum() or c in "_:") for c in test.split("[", 1)[0]
                    )
                ):
                    raise ValueError("non-public diagnostic selector")
        root = Path(completed.fixture_custody)
        if root.resolve(strict=True) != root:
            raise ValueError("diagnostic process custody alias")
        root_fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        fds.append(root_fd)
        root_info = os.fstat(root_fd)
        if (
            custody_identity(root_info) != completed.fixture_identity
            or root_info.st_uid != os.getuid()
            or root_info.st_mode & 0o022
        ):
            raise ValueError("diagnostic process custody changed")
        os.mkdir("diagnostics", 0o700, dir_fd=root_fd)
        local = directory(root_fd, "diagnostics")
        os.mkdir("raw", 0o700, dir_fd=local)
        raw_fd = directory(local, "raw")
        raw = read(
            root_fd,
            "output.log",
            "runner-output",
            OUTPUT_BYTES + 4096,
            expected_hash=hashlib.sha256(completed.stdout.encode()).hexdigest(),
            expected=completed.custody_records["output.log"],
        )
        read(
            root_fd,
            "result.json",
            "runner-result",
            REPORT_BYTES,
            expected=completed.custody_records["result.json"],
        )
        try:
            receipt = decode_acceptance_receipt(raw)
        except (ValueError, UnicodeError):
            receipt = None
        public["status"] = "INCOMPLETE"
        public["reason"] = "RUNNER_RECEIPT_UNAVAILABLE"
        if isinstance(receipt, dict):
            batches = receipt.get("execution", {}).get("batches", [])
            if not isinstance(batches, list) or len(batches) > len(plan):
                raise ValueError("diagnostic batch membership changed")
            temp = directory(root_fd, "tmp")
            public["not_admitted_batches"] = len(plan) - len(batches)
            complete = len(batches) == len(plan)
            for index, batch in enumerate(batches):
                bound()
                expected = plan[index]
                if (
                    not isinstance(batch, dict)
                    or batch.get("id") != expected["id"]
                    or batch.get("selectors") != expected["selectors"]
                ):
                    raise ValueError("diagnostic batch membership changed")
                group_path = Path(batch.get("fixture_custody", ""))
                process_path = Path(batch.get("process_custody", ""))
                if (
                    group_path.parent != root / "tmp"
                    or not group_path.name.startswith("synthesis-release-check-")
                    or process_path.parent != group_path
                    or not process_path.name.startswith("synthesis-required-check-")
                ):
                    raise ValueError("diagnostic member escaped process custody")
                with batch_directories(
                    temp, group_path.name, batch.get("custody_identity", []),
                    process_path.name, batch.get("process_identity", []),
                    remember=True,
                ) as (group, process):
                    pins = batch["diagnostic_records"]
                    selection = parse(
                        read(
                            group,
                            "selection.json",
                            f"batch-{index}-selection",
                            REPORT_BYTES,
                            expected=pins["selection.json"],
                        )
                    )
                    if selection != expected["selectors"]:
                        raise ValueError("diagnostic selector custody differs")
                    read(
                        group,
                        "pytest.ini",
                        f"batch-{index}-config",
                        4096,
                        expected=pins["pytest.ini"],
                    )
                    inventory = read(
                        group,
                        "inventory.json",
                        f"batch-{index}-inventory",
                        REPORT_BYTES,
                        optional=True,
                        expected=pins["inventory.json"],
                    )
                    progress = read(
                        group,
                        "inventory.progress.jsonl",
                        f"batch-{index}-progress",
                        REPORT_BYTES,
                        optional=True,
                        expected=pins["inventory.progress.jsonl"],
                    )
                    read(
                        process,
                        "output.log",
                        f"batch-{index}-output",
                        OUTPUT_BYTES + 4096,
                        expected_hash=batch["output_sha256"],
                        expected=batch["process_records"]["output.log"],
                    )
                    read(
                        process,
                        "result.json",
                        f"batch-{index}-result",
                        REPORT_BYTES,
                        expected=batch["process_records"]["result.json"],
                    )
                    rows = []
                    truncated = False
                    if progress is not None:
                        truncated = bool(progress and not progress.endswith(b"\n"))
                        lines = progress.splitlines()
                        if truncated:
                            lines = lines[:-1]
                        rows = [parse(line) for line in lines]
                        if (
                            not rows
                            or len(rows) > MAX_TESTS * 4 + 4
                            or any(
                                not isinstance(r, dict)
                                or type(r.get("sequence")) is not int
                                or r["sequence"] != i
                                for i, r in enumerate(rows)
                            )
                            or rows[0].get("kind") != "start"
                        ):
                            raise ValueError("diagnostic progress sequence refused")
                    complete = (
                        complete
                        and inventory is not None
                        and progress is not None
                        and not truncated
                    )
                    public["batches"].append(
                        {
                            "id": f"batch-{index}",
                            "selectors": [
                                s.split("[", 1)[0] for s in expected["selectors"]
                            ],
                            "inventory": "PRESENT" if inventory is not None else "MISSING",
                            "progress": "MISSING"
                            if progress is None
                            else "TRUNCATED"
                            if truncated
                            else "PRESENT",
                            "process": "OWNER_FAILURE"
                            if batch.get("process_failure")
                            else "EXIT_ZERO"
                            if batch.get("returncode") == 0
                            else "EXIT_NONZERO",
                            "phases": phases(rows, expected["selectors"]),
                        }
                    )
            public["status"] = "RETAINED" if complete else "INCOMPLETE"
            public["reason"] = (
                "CLOSED_DIAGNOSTICS" if complete else "PARTIAL_OR_NOT_ADMITTED"
            )
        for group_name, group_identity, process_name, process_identity, records in closed_batches:
            with batch_directories(
                temp, group_name, group_identity, process_name, process_identity,
                remember=False,
            ) as (group, process):
                # Every retained record is checked again against its original
                # content/metadata stamp after all other batches were copied.
                for in_process, name, identity in records:
                    anchors.append((process if in_process else group, name,
                                    None, identity))
        check_anchors(anchors)
        if custody_identity(root.lstat()) != completed.fixture_identity:
            raise ValueError("diagnostic root changed at closure")
        save(
            local,
            "index.json",
            json.dumps(
                {"schema": 1, "members": members, "authorizes_release": False},
                sort_keys=True,
            ).encode(),
        )
    except (OSError, ValueError, TypeError, KeyError, AttributeError, UnicodeError):
        public["status"] = "REFUSED"
        public["reason"] = "CUSTODY_OR_LIMIT_REFUSED"
        public["batches"] = []
    finally:
        for fd in reversed(fds):
            os.close(fd)
    public["records"] = [
        {k: v for k, v in row.items() if k != "raw_member"} for row in members
    ]
    if destination is not None:
        path = Path(destination["path"])
        try:
            bound()
            with _diagnostic_directory_chain(path, until) as (
                fd,
                ancestors,
                check_ancestors,
            ):
                if ancestors != destination["ancestors"]:
                    raise ValueError("diagnostic destination ancestry changed")
                if custody_identity(os.fstat(fd)) != destination["identity"]:
                    raise ValueError("diagnostic destination changed")
                with os.scandir(fd) as entries:
                    if next(entries, None) is not None:
                        raise ValueError("diagnostic destination has unindexed members")
                data = json.dumps(public, sort_keys=True).encode()
                if total + len(data) > DIAGNOSTIC_BYTES:
                    raise ValueError("diagnostic export too large")
                diagnostic_identity = save(fd, "diagnostics.json", data)
                manifest = {
                    "schema": 1,
                    "authorizes_release": False,
                    "status": public["status"],
                    "members": [
                        {
                            "path": "diagnostics.json",
                            "size": len(data),
                            "sha256": hashlib.sha256(data).hexdigest(),
                        }
                    ],
                }
                manifest_identity = save(
                    fd, "manifest.json", json.dumps(manifest, sort_keys=True).encode()
                )
                os.fsync(fd)
                names = set()
                with os.scandir(fd) as entries:
                    for entry in entries:
                        bound()
                        names.add(entry.name)
                        if len(names) > 2:
                            raise ValueError(
                                "diagnostic destination membership changed"
                            )
                if names != {"diagnostics.json", "manifest.json"}:
                    raise ValueError("diagnostic destination membership changed")
                for name, identity in (
                    ("diagnostics.json", diagnostic_identity),
                    ("manifest.json", manifest_identity),
                ):
                    if (
                        stamp(os.stat(name, dir_fd=fd, follow_symlinks=False))
                        != identity
                    ):
                        raise ValueError(
                            "diagnostic exported member changed at closure"
                        )
                if custody_identity(path.lstat()) != destination["identity"]:
                    raise ValueError("diagnostic destination changed at closure")
                check_ancestors()
                export_closed = True
        except (OSError, ValueError, KeyError):
            public["status"] = "REFUSED"
    return {
        "status": public["status"],
        "authorizes_release": False,
        "export_closed": export_closed,
        "record_count": len(members),
        "raw_bytes": total,
    }


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
        self.source_root = Path(_diagnostic_os_getcwd())
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

    def _failure_site(self, report):
        """Retain only a line in the selected source file; never exception data.

        This is diagnostic metadata, not outcome, custody or release authority.
        A helper failure may identify its nearest selected-source caller, not
        the innermost throw. Foreign paths and oversized tracebacks stay unknown.
        """
        node = getattr(report, "nodeid", None)
        if not isinstance(node, str) or len(node) > 8192:
            return None
        source = node.split("::", 1)[0]
        if not source.endswith(".py") or Path(source).is_absolute() or any(
            p in {"", ".", ".."} for p in source.split("/")
        ):
            return None
        representation = getattr(report, "longrepr", None)
        paths = {source, str(self.source_root / source)}

        def selected_site(location):
            line = getattr(location, "lineno", None)
            path = getattr(location, "path", None)
            if type(line) is not int or not 1 <= line <= 1000000:
                return None
            if not isinstance(path, str) or path not in paths:
                return None
            return {"source_sha256": _diagnostic_sha256(source.encode()).hexdigest(), "line": line}

        site = selected_site(getattr(representation, "reprcrash", None))
        if site is not None:
            return site
        entries = getattr(getattr(representation, "reprtraceback", None), "reprentries", None)
        if type(entries) not in (list, tuple) or len(entries) > 128:
            return None
        for entry in reversed(entries):
            site = selected_site(getattr(entry, "reprfileloc", None))
            if site is not None:
                return site
        return None

    def _failure_detail(self, report):
        """Render bounded pytest diagnostics without collecting arbitrary locals.

        The ordinary report remains the authority for outcome and lifecycle.
        A prefix, missing representation or renderer error is explicitly labeled;
        none supplies acceptance evidence. Stop rendering at the byte boundary.
        """
        limit = min(
            FAILURE_DETAIL_BYTES, FAILURE_DETAIL_TOTAL_BYTES - self.failure_detail_bytes
        )
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
                raw = text[: remaining + 1].encode("utf-8")
                prefix = (
                    raw[:remaining].decode("utf-8", errors="ignore").encode("utf-8")
                )
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
        detail = {
            "status": status,
            "text": raw.decode("utf-8"),
            "bytes": len(raw),
            "sha256": _diagnostic_sha256(raw).hexdigest(),
        }
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
            groups = partition(self.full, group=self.group)
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
            self._progress(
                "collection-failure",
                nodeid=report.nodeid,
                outcome=report.outcome,
                failure=self._failure_detail(report),
            )

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
                **(
                    {"failure": self._failure_detail(report), "failure_site": self._failure_site(report)}
                    if report.outcome == "failed"
                    else {}
                ),
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
        if (report.outcome == "skipped" and type(longrepr) is tuple
                and len(longrepr) == 3 and isinstance(longrepr[2], str)):
            phases[report.when]["skip_reason"] = longrepr[2][:1024]
        self._progress(
            "phase",
            nodeid=report.nodeid,
            when=report.when,
            outcome=report.outcome,
            duration=report.duration,
            **(
                {"failure": self._failure_detail(report), "failure_site": self._failure_site(report)}
                if report.outcome == "failed"
                else {}
            ),
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
            # Ordinary source onboarding has two optional dependency controls.
            # Admit only their existing call-time skips, never arbitrary skips,
            # xfails, missing phases or failures. Acceptance selectors retain
            # their independent polarity contract above.
            reason = phases.get("call", {}).get("skip_reason")
            optional_reason = {
                OB + "/test_instruction_adversarial.py::test_actual_private_adapter_and_public_engine_converge_without_mutating_sources": "Skipped: optional private adapter is not installed",
                **{OB + "/test_distribution.py::test_real_package_manager_install_is_usable_without_install_scripts[" + manager + "]": "Skipped: package-manager consumer acceptance requires npm and " + manager for manager in ("npm", "bun")},
            }.get(node)
            if (self.group in ONBOARDING_GROUPS and optional_reason is not None
                    and reason == optional_reason
                    and set(phases) == {"setup", "call", "teardown"}
                    and phases["call"]["outcome"] == "skipped"
                    and phases["setup"]["outcome"] == phases["teardown"]["outcome"] == "passed"
                    and not any(p.get("wasxfail") for p in phases.values())):
                continue
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


def _registered_inventory(group, report, selection=None):
    """Bind this observer to the resident owner at registration, before fixtures.

    Tests may fault-inject the public module, including limits, while their call
    reports are emitted before monkeypatch teardown. Keep those deliberate
    injections effective on explicitly constructed test instances, but not on
    the independent observer. Reuse the same code objects, with a private global
    binding; do not reload a mutable source path or implement a second runner.
    Captured OS primitives still inspect real custody on every report. This is
    fixture isolation, not a security boundary against arbitrary in-process code.
    """
    namespace = dict(globals())

    def bind(function):
        bound = FunctionType(
            function.__code__,
            namespace,
            function.__name__,
            function.__defaults__,
            function.__closure__,
        )
        bound.__kwdefaults__ = function.__kwdefaults__
        return bound

    for name in ("_progress_stamp", "is_timing_sensitive_selector", "group_for", "partition", "expand_selectors"):
        namespace[name] = bind(namespace[name])
    methods = {
        name: bind(value) if isinstance(value, FunctionType) else value
        for name, value in InventoryPlugin.__dict__.items()
        if name not in {"__dict__", "__weakref__"}
    }
    observer = type("RegisteredInventoryPlugin", (), methods)
    return observer(group, report, selection)


def pytest_configure(config):
    selection_path = os.environ.get("SYNTHESIS_ACCEPTANCE_SELECTION")
    if selection_path:
        selectors = read_inventory(Path(selection_path))
        if not isinstance(selectors, list):
            raise ValueError("acceptance selection is not a list")
        config.pluginmanager.register(
            _registered_inventory(
                "acceptance",
                Path(os.environ["SYNTHESIS_RELEASE_TEST_REPORT"]),
                selectors,
            ),
            "release-inventory",
        )
        return
    group = os.environ.get("SYNTHESIS_RELEASE_TEST_GROUP")
    if group:
        if group not in ALL_GROUPS:
            raise ValueError("unknown release test group")
        config.pluginmanager.register(
            _registered_inventory(
                group, Path(os.environ["SYNTHESIS_RELEASE_TEST_REPORT"])
            ),
            "release-inventory",
        )


def run_group(root: Path, group: str) -> tuple[int, dict]:
    if group not in ALL_GROUPS:
        raise ValueError("unknown release test group")
    directory = OB if group in ONBOARDING_GROUPS else AP
    deadline = time.monotonic() + CHECK_SECONDS - 5
    before = source_digest(root)
    with retained_group_fixture() as temp:
        report = temp / "inventory.json"
        config = temp / "pytest.ini"
        config.write_text("[pytest]\n")
        env = dict(os.environ)
        # External pytest flags/plugins cannot deselect, repeat or short-circuit a gate.
        env.pop("PYTEST_ADDOPTS", None)
        env.pop("PYTEST_PLUGINS", None)
        # This explicit group owns a complete partition, never its caller's slice.
        env.pop("SYNTHESIS_ACCEPTANCE_SELECTION", None)
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
                "-c",
                str(config),
                "--confcutdir",
                str(root),
                directory,
                # An outer acceptance config can be above a nested fixture.
                # Bind node IDs to this explicitly admitted source root.
                "--rootdir",
                str(root),
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
            groups = partition(payload["inventory"], group=group)
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
                payload["partial_execution"] = read_progress(
                    report.with_suffix(".progress.jsonl")
                )
            except (OSError, ValueError, KeyError, TypeError) as error:
                payload["partial_execution"] = {
                    "status": "UNAVAILABLE",
                    "authorizes_success": False,
                    "error": str(error),
                }
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
    parser.add_argument("--group", choices=ALL_GROUPS, required=True)
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
