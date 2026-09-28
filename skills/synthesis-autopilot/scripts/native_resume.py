"""Bounded exact-session native transport. Protocol outcomes are not task grades.

Muse's exact-session submit may race an idle snapshot and queue a new turn.
That exact effect is withdrawn with authoritative native evidence or retained
as unresolved custody. Resume does not establish a connection-exclusive lease.
Other transports remain unavailable until their admission semantics qualify.
The explicit owner request determines fixed host-construction arguments.
Sandbox enabled and workspace trust disabled rely on documented native defaults;
argument construction alone does not attest effective inherited-policy enforcement.
Saved session metadata does not establish the previous host's sandbox posture.
No trust, provider, model or approval reconfiguration is performed.
"""

from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import selectors
import signal
import subprocess
import time
import uuid
import re
import shutil
import errno
import sys

import native_muse_contract

_OBSERVATION_KEY = object()


class TransportObservation(dict):
    def __init__(self, value, *, key):
        if key is not _OBSERVATION_KEY:
            raise ValueError(
                "transport observations come from the owned native operation"
            )
        super().__init__(value)
        self._key = key


def _observation(value):
    return TransportObservation(value, key=_OBSERVATION_KEY)


def is_observation(value):
    return isinstance(value, TransportObservation) and value._key is _OBSERVATION_KEY


def command_id():
    value = (
        (int(time.time() * 1000) << 80)
        | (7 << 76)
        | (int.from_bytes(os.urandom(2), "big") & 0xFFF) << 64
    )
    value |= (2 << 62) | (int.from_bytes(os.urandom(8), "big") & ((1 << 62) - 1))
    return str(uuid.UUID(int=value))


def transport_for(client):
    if client != "muse":
        raise ValueError(
            "native atomic exact-session ownership is not qualified for " + str(client)
        )
    return "muse-msp-exact-turn-custody"


def posture_arguments(posture):
    """Closed requested policy, never arbitrary flags or inferred old defaults.

    Muse's serve posture is fixed for the host lifetime. MSP cannot restore it
    from a saved session. A native owner must explicitly request this supported
    restricted profile, preserving any stricter known shell/write restrictions.
    """
    fields = {
        "schema_version",
        "profile",
        "sandbox_enabled",
        "network",
        "shell_enabled",
        "write_enabled",
        "workspace_trust",
        "approval_mode",
    }
    if (
        not isinstance(posture, dict)
        or set(posture) != fields
        or type(posture["schema_version"]) is not int
        or posture["schema_version"] != 1
        or posture["profile"] != "muse-restricted-v1"
        or any(
            type(posture[name]) is not bool
            for name in (
                "sandbox_enabled",
                "shell_enabled",
                "write_enabled",
                "workspace_trust",
            )
        )
        or posture["sandbox_enabled"] is not True
        or posture["network"] != "restricted"
        or posture["workspace_trust"] is not False
        or posture["approval_mode"] != "onRequest"
    ):
        raise ValueError(
            "native posture is missing, malformed or unsupported; original host policy is not inferred"
        )
    result = ["--sandbox-network", "restricted"]
    if not posture["write_enabled"]:
        result.append("--disable-write")
    if not posture["shell_enabled"]:
        result.append("--disable-shell")
    return tuple(result)


def installed_binary(client):
    transport_for(client)
    launcher = shutil.which("muse")
    if not launcher:
        raise ValueError("installed Muse executable is unavailable")
    path = Path(launcher).resolve()
    with path.open("rb") as stream:
        prefix = stream.read(2)
    if prefix == b"#!":
        version = (path.parent / ".muse-version").read_text().strip()
        if not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+-R[0-9]+(?:\.[0-9]+)?", version):
            raise ValueError("installed Muse binary version selector is invalid")
        path = path.parent / ("muse-bin-" + version)
    return binary_identity(path)


def binary_identity(path):
    """Bounded current executable bytes with retained no-follow ancestry."""
    import stat

    path = Path(path).expanduser().absolute()
    if len(path.parts) > 256 or ".." in path.parts:
        raise ValueError("native executable pathname exceeds its bound")
    descriptors = []
    fd = None
    deadline = time.monotonic() + 10

    def signature(value):
        return (
            value.st_dev,
            value.st_ino,
            value.st_mode,
            value.st_nlink,
            value.st_size,
            value.st_mtime_ns,
            value.st_ctime_ns,
        )

    try:
        parent = os.open("/", os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        descriptors.append((Path("/"), parent, os.fstat(parent)))
        current = Path("/")
        for part in path.parent.parts[1:]:
            current = current / part
            parent = os.open(
                part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent
            )
            descriptors.append((current, parent, os.fstat(parent)))
        fd = os.open(
            path.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent
        )
        before = os.fstat(fd)
        if (
            not stat.S_ISREG(before.st_mode)
            or not before.st_mode & 0o111
            or before.st_nlink != 1
            or not 4 <= before.st_size <= 1024**3
        ):
            raise ValueError("native executable must be one bounded regular executable")
        first = os.read(fd, 4)
        if first not in (
            b"\x7fELF",
            b"\xcf\xfa\xed\xfe",
            b"\xfe\xed\xfa\xcf",
            b"\xca\xfe\xba\xbe",
            b"\xbe\xba\xfe\xca",
        ):
            raise ValueError(
                "native transport binds the installed binary, not a mutable launcher script"
            )
        digest = hashlib.sha256(first)
        size = len(first)
        while True:
            if time.monotonic() > deadline:
                raise ValueError("native executable digest wall bound reached")
            chunk = os.read(fd, min(1024 * 1024, before.st_size - size + 1))
            if not chunk:
                break
            size += len(chunk)
            if size > before.st_size:
                raise ValueError("native executable grew during read")
            digest.update(chunk)
        if (
            size != before.st_size
            or signature(before) != signature(os.fstat(fd))
            or signature(before) != signature(path.lstat())
        ):
            raise ValueError("native executable changed during read")
        for target, descriptor, initial in descriptors:
            for value in (os.fstat(descriptor), target.lstat()):
                if (value.st_dev, value.st_ino, value.st_mode) != (
                    initial.st_dev,
                    initial.st_ino,
                    initial.st_mode,
                ):
                    raise ValueError("native executable ancestry changed")
        return {"path": str(path), "sha256": digest.hexdigest(), "size": size}
    except OSError as exc:
        raise ValueError("native executable custody refused: " + str(exc)) from exc
    finally:
        if fd is not None:
            os.close(fd)
        for _, descriptor, _ in reversed(descriptors):
            os.close(descriptor)


def validate_resumed(grant, reply):
    native_muse_contract.validate_resume_shape(reply)
    if not isinstance(reply, dict) or not isinstance(reply.get("session"), dict):
        raise ValueError("native resume response has no typed session object")
    session = reply["session"]
    if (
        session.get("sessionId") != grant["native_session_id"]
        or session.get("status") != "idle"
        or "activeTurnId" not in session
        or session["activeTurnId"] is not None
        or "forkedFrom" not in session
        or session["forkedFrom"] is not None
        or session.get("workspaceRoot") != grant["workspace"]
        or not isinstance(session.get("path"), str)
        or not session["path"]
        or reply.get("pendingRequests") != []
    ):
        raise ValueError(
            "native resume did not acquire the exact idle session without pending human requests"
        )
    mode = session.get("approvalMode")
    if (
        not isinstance(mode, dict)
        or mode.get("mode") != "onRequest"
        or not isinstance(mode.get("source"), str)
        or not mode["source"]
        or "lastCommandId" not in mode
        or not (
            mode["lastCommandId"] is None
            or isinstance(mode["lastCommandId"], str)
            and 0 < len(mode["lastCommandId"]) <= 512
        )
    ):
        raise ValueError(
            "native resumed approval mode is not verified onRequest; no new turn is admitted"
        )
    return session


def validate_terminal(data, session, turn):
    """Accept only supported exact-session durable terminal provenance."""
    if (
        not isinstance(data, dict)
        or data.get("sessionId") != session
        or data.get("turnId") != turn
        or not isinstance(data.get("terminal"), str)
        or data["terminal"] not in {"completed", "failed", "cancelled"}
        or not isinstance(data.get("viewCursor"), str)
        or not 0 < len(data["viewCursor"]) <= 4096
    ):
        raise ValueError("native terminal has invalid identity, disposition or cursor")
    _validate_source_range(data, session, turn)
    for name in ("durationMs", "timeToFirstTokenMs"):
        if name in data and (type(data[name]) is not int or data[name] < 0):
            raise ValueError("native terminal contains invalid measured duration")
    native_muse_contract.validate_terminal_shape(data)
    return data


def _validate_source_range(data, session, turn):
    source = data.get("sourceRange")
    if not isinstance(source, dict) or set(source) != {"stream", "first", "last"}:
        raise ValueError("native terminal lacks a typed durable source range")
    if source["stream"] not in (
        {"kind": "session", "id": session},
        {"kind": "run", "id": turn},
    ):
        raise ValueError(
            "native terminal source belongs to another or unsupported stream"
        )
    for name in ("first", "last"):
        row = source[name]
        if (
            not isinstance(row, dict)
            or set(row) != {"id", "sequence"}
            or not isinstance(row["id"], str)
            or not 0 < len(row["id"]) <= 512
            or type(row["sequence"]) is not int
            or row["sequence"] < 0
        ):
            raise ValueError("native terminal source position is malformed")
    first, last = source["first"], source["last"]
    if (
        last["sequence"] < first["sequence"]
        or first["sequence"] == last["sequence"]
        and first["id"] != last["id"]
    ):
        raise ValueError("native terminal source range is reversed or contradictory")


def validate_unqueued(data, session, start):
    """Only a durable session event can prove our queued submit never launched."""
    if (
        not isinstance(data, dict)
        or data.get("sessionId") != session
        or data.get("turnId") != start["turnId"]
        or data.get("commandId") != start["commandId"]
        or not isinstance(data.get("viewCursor"), str)
        or not 0 < len(data["viewCursor"]) <= 4096
    ):
        raise ValueError("native unqueue event has invalid exact ownership or cursor")
    _validate_source_range(data, session, start["turnId"])
    if data["sourceRange"]["stream"] != {"kind": "session", "id": session}:
        raise ValueError("native unqueue requires session-stream provenance")
    return {
        key: data[key]
        for key in ("sessionId", "turnId", "commandId", "viewCursor", "sourceRange")
    }


def _decode_frame(raw):
    def pairs(values):
        result = {}
        for key, value in values:
            if key in result:
                raise ValueError("native protocol contains duplicate fields")
            result[key] = value
        return result

    return json.loads(
        raw,
        object_pairs_hook=pairs,
        parse_constant=lambda value: (_ for _ in ()).throw(
            ValueError("native protocol contains nonfinite JSON")
        ),
    )


class RPCError(ValueError):
    def __init__(self, error):
        self.error = error
        super().__init__(
            "native RPC refused: " + json.dumps(error, sort_keys=True)[:4096]
        )


def _child_wait_probe():
    """Select a non-reaping POSIX child-ownership check before spawning.

    Darwin exposes waitid in libc but not CPython's os module. We need only its
    return/errno contract; the deliberately oversized aligned siginfo buffer is
    never interpreted. WNOWAIT keeps the exited child PID reserved through all
    group signals. Missing support refuses construction before any child exists.
    """
    flags = os.WEXITED | os.WNOHANG | os.WNOWAIT
    if hasattr(os, "waitid"):

        def wait(pid):
            os.waitid(os.P_PID, pid, flags)
    elif sys.platform == "darwin":
        import ctypes

        class SigInfo(ctypes.Union):
            _fields_ = [
                ("alignment", ctypes.c_longdouble),
                ("storage", ctypes.c_ubyte * 1024),
            ]

        try:
            function = ctypes.CDLL(None, use_errno=True).waitid
        except AttributeError as error:
            raise OSError("non-reaping child ownership check unavailable") from error
        function.argtypes = [ctypes.c_int, ctypes.c_uint, ctypes.c_void_p, ctypes.c_int]
        function.restype = ctypes.c_int

        def wait(pid):
            value = SigInfo()
            if function(os.P_PID, pid, ctypes.byref(value), flags) != 0:
                number = ctypes.get_errno()
                raise OSError(number, os.strerror(number))
    else:
        raise OSError("non-reaping child ownership check unavailable")

    def probe(pid):
        for _ in range(4):
            try:
                wait(pid)
                return True
            except OSError as error:
                if error.errno == errno.ECHILD:
                    return False
                if error.errno != errno.EINTR:
                    raise
        raise OSError("non-reaping child ownership check repeatedly interrupted")

    return probe


def _validate_reply_admission(sent, received):
    """Reject replies for requests that have not crossed this owned transport.

    Notifications and server requests have their own protocol handling. A reply
    is admitted once, by its exact typed request ID. Validate before each send
    and after each read, so buffered future replies cannot authenticate a later
    effect. Only complete received frames are inspected; partial frames remain
    with the finite reader until decoded.
    """
    issued = set()
    for line in bytes(sent).splitlines():
        if not line:
            continue
        row = _decode_frame(line)
        if "method" in row and "id" in row:
            identity = row["id"]
            if type(identity) not in (int, str):
                raise ValueError("native request identity is malformed")
            key = (type(identity), identity)
            if key in issued:
                raise ValueError("native request identity is duplicated")
            issued.add(key)
    seen = set()
    complete = bytes(received).rpartition(b"\n")[0]
    for line in complete.splitlines():
        if not line:
            continue
        row = _decode_frame(line)
        if "method" in row or "id" not in row:
            continue
        identity = row["id"]
        if type(identity) not in (int, str):
            raise ValueError("native reply identity is malformed")
        key = (type(identity), identity)
        if key not in issued or key in seen:
            raise ValueError("native reply is unsolicited, preplayed or duplicated")
        if ("result" in row) == ("error" in row):
            raise ValueError("native reply must contain exactly one result or error")
        seen.add(key)


def _finish_received_frame(connection):
    # A fragmented future reply must not gain authority merely because its
    # suffix arrives after the next send. Finish the existing frame under the
    # connection's unchanged wall/byte bound; asynchronous notifications remain
    # legal. This performs no native action or automatic retry.
    while connection.raw_stdout and not connection.raw_stdout.endswith(b"\n"):
        connection._read()
        _validate_reply_admission(connection.raw_stdin, connection.raw_stdout)
    _validate_reply_admission(connection.raw_stdin, connection.raw_stdout)


class MuseConnection:
    """One bounded stdio connection; its own process group is the only signal target."""

    def __init__(
        self,
        binary,
        workspace,
        *,
        timeout=120,
        max_bytes=1024 * 1024,
        extra_args=(),
        command=None,
        environment=None,
        require_jsonrpc=True,
    ):
        self.deadline = time.monotonic() + timeout
        self.max_bytes = max_bytes
        self.size = 0
        self.buffer = b""
        self.raw_stdout = bytearray()
        self.require_jsonrpc = require_jsonrpc
        self.frames = []
        self.notifications = []
        self.stderr = bytearray()
        self.wire = hashlib.sha256()
        self.next_id = 0
        self.outgoing = bytearray()
        self.sent_bytes = 0
        self.raw_stdin = bytearray()
        environment = dict(os.environ if environment is None else environment)
        if command is None:
            environment.setdefault("MUSE_NO_AUTO_UPDATE", "1")
        # A native child establishes its own identity. A parent's hook/seat
        # hints are not transferable and must not poison that authentication.
        for name in (
            "CODEX_THREAD_ID",
            "CLAUDE_CODE_SESSION_ID",
            "CLAUDE_CODE_HOST_SESSION_ID",
            "CLAUDE_PID",
            "CLAUDECODE",
            "MUSE_SESSION_ID",
            "SYNTHESIS_CLIENT_SESSION_REF",
            "SYNTHESIS_COORDINATION_SESSION",
        ):
            environment.pop(name, None)
        self._child_waitable = _child_wait_probe()
        self.process = subprocess.Popen(
            [str(binary), "serve", *extra_args] if command is None else list(command),
            cwd=workspace,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=environment,
            start_new_session=True,
            bufsize=0,
        )
        self.selector = None
        self.cleanup = None
        try:
            os.set_blocking(self.process.stdin.fileno(), False)
            self.selector = selectors.DefaultSelector()
            self.selector.register(self.process.stdout, selectors.EVENT_READ, "stdout")
            self.selector.register(self.process.stderr, selectors.EVENT_READ, "stderr")
        except BaseException as error:
            try:
                self.close()
            except (OSError, ValueError, subprocess.SubprocessError) as cleanup_error:
                error.add_note(
                    "Native construction cleanup unresolved: " + str(cleanup_error)
                )
            raise

    def send(self, value):
        if "method" in value and "id" in value:
            _finish_received_frame(self)
        _validate_reply_admission(self.raw_stdin, self.raw_stdout)
        raw = (json.dumps(value, separators=(",", ":")) + "\n").encode()
        if (
            len(raw) > 256 * 1024
            or self.sent_bytes + len(self.outgoing) + len(raw) > self.max_bytes
        ):
            raise ValueError("native transport input bound reached")
        self.raw_stdin.extend(raw)
        self.outgoing.extend(raw)
        self._flush_outgoing()

    def _flush_outgoing(self):
        # Never block the reader on an approval reply. An uncooperative host
        # may fill its stdin while still filling stdout; both directions share
        # the same bounded event loop, and no buffered close can flush forever.
        while self.outgoing:
            if time.monotonic() >= self.deadline:
                raise TimeoutError("native transport wall bound reached")
            try:
                written = os.write(self.process.stdin.fileno(), self.outgoing)
            except BlockingIOError:
                break
            if written <= 0:
                raise EOFError("native transport input closed")
            self.sent_bytes += written
            del self.outgoing[:written]
        registered = self.process.stdin in [
            key.fileobj for key in self.selector.get_map().values()
        ]
        if self.outgoing and not registered:
            self.selector.register(self.process.stdin, selectors.EVENT_WRITE, "stdin")
        elif not self.outgoing and registered:
            self.selector.unregister(self.process.stdin)

    def _read(self, seconds=0.2):
        if time.monotonic() >= self.deadline:
            raise TimeoutError("native transport wall bound reached")
        for key, _ in self.selector.select(
            min(seconds, max(0, self.deadline - time.monotonic()))
        ):
            if key.data == "stdin":
                self._flush_outgoing()
                continue
            raw = os.read(key.fileobj.fileno(), 65536)
            if not raw:
                self.selector.unregister(key.fileobj)
                continue
            self.size += len(raw)
            if self.size > self.max_bytes:
                raise ValueError("native transport output bound reached")
            self.wire.update(key.data.encode() + b"\0" + raw)
            if key.data == "stderr":
                self.stderr.extend(raw)
                continue
            self.raw_stdout.extend(raw)
            self.buffer += raw
            if len(self.buffer) > 256 * 1024:
                raise ValueError("native transport frame bound reached")
            while b"\n" in self.buffer:
                line, self.buffer = self.buffer.split(b"\n", 1)
                if not line:
                    continue
                frame = _decode_frame(line)
                if not isinstance(frame, dict):
                    raise ValueError("native protocol frame is not an object")
                if (self.require_jsonrpc and frame.get("jsonrpc") != "2.0") or (
                    not self.require_jsonrpc
                    and frame.get("jsonrpc") not in (None, "2.0")
                ):
                    raise ValueError("native protocol version mismatch")
                if frame.get("id") is not None:
                    if type(frame["id"]) not in (int, str):
                        raise ValueError(
                            "native protocol request identity is malformed"
                        )
                    if "method" in frame:
                        # Unknown server request receives no fabricated human approval.
                        self.send(
                            {
                                "jsonrpc": "2.0",
                                "id": frame["id"],
                                "error": {
                                    "code": -32601,
                                    "message": "Unattended client cannot supply this action",
                                },
                            }
                        )
                    else:
                        self.frames.append(frame)
                else:
                    self.notifications.append(frame)
            if len(self.frames) + len(self.notifications) > 4096:
                raise ValueError("native frame count bound reached")
        _validate_reply_admission(self.raw_stdin, self.raw_stdout)
        # Do not poll/wait here: an unreaped leader pins the group identity until
        # close has finished every signal. EOF is sufficient to reject a reply.
        if not any(
            key.data in {"stdout", "stderr"} for key in self.selector.get_map().values()
        ):
            raise EOFError(
                "native transport closed before a verified terminal response"
            )

    def call(self, method, params):
        _finish_received_frame(self)
        _validate_reply_admission(self.raw_stdin, self.raw_stdout)
        self.next_id += 1
        identity = self.next_id
        self.send(
            {"jsonrpc": "2.0", "id": identity, "method": method, "params": params}
        )
        while True:
            for index, frame in enumerate(self.frames):
                if type(frame.get("id")) is int and frame["id"] == identity:
                    self.frames.pop(index)
                    if "error" in frame:
                        raise RPCError(frame["error"])
                    if not isinstance(frame.get("result"), dict):
                        raise ValueError("native result is not an object")
                    return frame["result"]
            self._read()
            _validate_reply_admission(self.raw_stdin, self.raw_stdout)

    def initialize(self):
        reply = self.call(
            "initialize",
            {
                "clientInfo": {"name": "synthesis_supervision", "version": "1"},
                "capabilities": {
                    "experimentalApi": False,
                    "requestedCapabilities": [],
                    "userInputDialogs": False,
                },
            },
        )
        native_muse_contract.validate_initialize(reply)
        self.send({"jsonrpc": "2.0", "method": "initialized"})
        return reply

    def terminal(self, session, turn, cancelled):
        cancelled_once = False
        while True:
            while self.notifications:
                frame = self.notifications.pop(0)
                data = frame.get("params", {})
                if not isinstance(data, dict):
                    raise ValueError("native notification parameters are not an object")
                if (
                    frame.get("method") == "turn/completed"
                    and data.get("sessionId") == session
                    and data.get("turnId") == turn
                ):
                    return validate_terminal(data, session, turn)
            if cancelled() and not cancelled_once:
                self.call(
                    "turn/cancel",
                    {"commandId": command_id(), "sessionId": session, "turnId": turn},
                )
                cancelled_once = True
            self._read()

    def reconcile_queue(self, session, start):
        """Withdraw only a well-formed acknowledgement's newly queued turn.

        One unqueue and, only after an exact command rejection, one exact-turn
        cancel share the remaining wall budget and a ten-second cleanup bound.
        Never target an omitted/current foreground turn or retry a lost command.
        """
        result = {
            "status": "unresolved",
            "session_id": session,
            "start_command_id": start["commandId"],
            "turn_id": start["turnId"],
            "unqueue_command_id": command_id(),
            "cancellation_outcome": "UNKNOWN",
        }
        original_deadline = self.deadline
        self.deadline = min(original_deadline, time.monotonic() + 10)
        try:
            try:
                reply = self.call(
                    "turn/unqueue",
                    {
                        "commandId": result["unqueue_command_id"],
                        "sessionId": session,
                        "turnId": start["turnId"],
                    },
                )
            except RPCError as error:
                data = error.error.get("data", {})
                if (
                    error.error.get("code") != -32030
                    or not isinstance(data, dict)
                    or data.get("kind") != "commandRejected"
                    or data.get("commandId") != result["unqueue_command_id"]
                ):
                    raise
                # The reason vocabulary is open. A rejection does not prove
                # launch, but an exact cancellation can affect only our known
                # newly minted queued turn, never a preexisting foreground turn.
                result["unqueue_rejected"] = True
                result["cancel_command_id"] = command_id()
                reply = self.call(
                    "turn/cancel",
                    {
                        "commandId": result["cancel_command_id"],
                        "sessionId": session,
                        "turnId": start["turnId"],
                    },
                )
                if (
                    reply.get("commandId") != result["cancel_command_id"]
                    or reply.get("status") != "accepted"
                    or reply.get("turnId") != start["turnId"]
                ):
                    raise ValueError(
                        "exact queued-turn cancellation acknowledgement is uncertain"
                    )
                observed = self.terminal(session, start["turnId"], lambda: False)
                validate_terminal(observed, session, start["turnId"])
                result.update(terminal=observed, status="terminal")
                if observed["terminal"] == "cancelled":
                    result.update(
                        status="cancelled",
                        cancellation_outcome="VERIFIED_NATIVE_TERMINAL",
                    )
                return result
            if (
                reply.get("commandId") != result["unqueue_command_id"]
                or reply.get("status") != "accepted"
                or reply.get("turnId") != start["turnId"]
            ):
                raise ValueError("exact unqueue acknowledgement is uncertain")
            result["unqueue_admitted"] = True
            while True:
                while self.notifications:
                    frame = self.notifications.pop(0)
                    data = frame.get("params", {})
                    if not isinstance(data, dict):
                        raise ValueError(
                            "native queue notification parameters are invalid"
                        )
                    if (
                        frame.get("method") == "turn/unqueued"
                        and data.get("sessionId") == session
                        and data.get("turnId") == start["turnId"]
                    ):
                        event = validate_unqueued(data, session, start)
                        result.update(status="removed", event=event)
                        return result
                self._read()
        except (ValueError, OSError, EOFError, TimeoutError) as error:
            result["diagnostic"] = str(error)[:4096]
            return result
        finally:
            self.deadline = original_deadline

    def close(self):
        """Close the exact owned group before reaping its identity anchor.

        The child starts a new session. Until wait/poll reaps its leader, that
        PID cannot be reused as a foreign process-group ID. No reader reaps it.
        This covers members still in this group, not escaped sessions, and does
        not attest provider cancellation. External reaping invalidates the anchor.
        """
        if self.cleanup is not None:
            if not self.cleanup["group_absent"]:
                raise ValueError(
                    "native cleanup remains unresolved; no repeated signals"
                )
            return dict(self.cleanup)
        self.cleanup = {
            "group_absent": False,
            "leader_reaped": False,
            "scope": "owned process group only; escaped sessions are not covered",
            "signals": [],
            "signal_errors": [],
            "error": None,
        }
        interrupted = []
        cleanup_deadline = time.monotonic() + 4.2

        def finish(operation):
            # Preserve a user interrupt, but finish this owned cleanup first.
            # Repeated interrupts are finite and remain an unresolved error.
            for _ in range(4):
                try:
                    return operation()
                except (KeyboardInterrupt, SystemExit) as error:
                    interrupted.append(error)
            raise ValueError("native cleanup repeatedly interrupted")

        def group_exists():
            try:
                os.killpg(self.process.pid, 0)
                return True
            except ProcessLookupError:
                return False

        try:
            try:
                self.process.stdin.close()
            except (OSError, ValueError):
                pass
            if self.process.returncode is not None:
                if group_exists():
                    raise ValueError(
                        "native group anchor was reaped externally; group ownership is unproven"
                    )
            else:
                # waitid confirms this PID is still our waitable child, even
                # when getpgid/getsid cannot inspect an exited leader on Darwin.
                anchored = self._child_waitable(self.process.pid)
                if not anchored and group_exists():
                    raise ValueError(
                        "native group anchor is unavailable; group ownership is unproven"
                    )
                if anchored:
                    try:
                        os.killpg(self.process.pid, signal.SIGTERM)
                        self.cleanup["signals"].append("TERM")
                    except ProcessLookupError:
                        pass
                    except OSError as error:
                        self.cleanup["signal_errors"].append(
                            {"signal": "TERM", "errno": error.errno}
                        )
                    # Give the native host a finite opportunity to finish. The
                    # leader is deliberately not reaped during this grace time.
                    finish(lambda: time.sleep(0.1))
                    if not self._child_waitable(self.process.pid):
                        if group_exists():
                            raise ValueError(
                                "native group anchor changed before escalation; ownership is unproven"
                            )
                    else:
                        try:
                            os.killpg(self.process.pid, signal.SIGKILL)
                            self.cleanup["signals"].append("KILL")
                        except ProcessLookupError:
                            pass
                        except OSError as error:
                            self.cleanup["signal_errors"].append(
                                {"signal": "KILL", "errno": error.errno}
                            )
                finish(
                    lambda: self.process.wait(
                        timeout=max(0.001, min(2, cleanup_deadline - time.monotonic()))
                    )
                )
            self.cleanup["leader_reaped"] = self.process.returncode is not None
            deadline = min(cleanup_deadline, time.monotonic() + 2)
            while True:
                try:
                    if not group_exists():
                        self.cleanup["group_absent"] = True
                        break
                except PermissionError:
                    # A dying orphan can be temporarily uninspectable. This
                    # is not absence; wait finitely without further signals.
                    pass
                if time.monotonic() >= deadline:
                    break
                finish(lambda: time.sleep(0.01))
            if not self.cleanup["group_absent"]:
                raise ValueError("native owned group cleanup remains unresolved")
        except BaseException as error:
            self.cleanup["error"] = str(error)[:4096]
            raise
        finally:
            if self.selector is not None:
                self.selector.close()
            for stream in (
                self.process.stdin,
                self.process.stdout,
                self.process.stderr,
            ):
                try:
                    stream.close()
                except (OSError, ValueError):
                    pass
        if interrupted:
            self.cleanup["interrupted"] = type(interrupted[0]).__name__
            raise interrupted[0]
        return dict(self.cleanup)


def launch(grant, prompt, *, send_admitted, cancelled):
    transport_for(grant["client"])
    native_muse_contract.validate_binding(grant.get("native_protocol"))
    arguments = posture_arguments(grant.get("native_posture"))
    if binary_identity(grant["binary"]["path"]) != grant["binary"]:
        raise ValueError("native executable changed after owner preparation")
    rpc = MuseConnection(
        grant["binary"]["path"],
        grant["workspace"],
        timeout=grant["max_wall_seconds"],
        max_bytes=grant["max_output_bytes"],
        extra_args=arguments,
    )
    outcome = {
        "status": "unknown",
        "task_accepted": False,
        "native_session_id": grant["native_session_id"],
        "requested_native_posture": dict(grant["native_posture"]),
    }
    try:
        outcome["protocol"] = native_muse_contract.validate_initialize(rpc.initialize())
        resumed = rpc.call(
            "session/resume",
            {
                "commandId": grant["resume_command_id"],
                "sessionId": grant["native_session_id"],
                "excludeItems": True,
            },
        )
        session = validate_resumed(grant, resumed)
        outcome["native_source_path"] = session["path"]
        outcome["resumed_approval_mode"] = dict(session["approvalMode"])
        if cancelled():
            raise ValueError("prepared launch was cancelled before native turn")

        def send():
            original_deadline = rpc.deadline
            rpc.deadline = min(original_deadline, time.monotonic() + 10)
            outcome["submission"] = {
                "state": "unresolved",
                "session_id": grant["native_session_id"],
                "command_id": grant["turn_command_id"],
            }
            try:
                result = rpc.call(
                    "turn/start",
                    {
                        "commandId": grant["turn_command_id"],
                        "sessionId": grant["native_session_id"],
                        "ifBusy": "queue",
                        "input": [{"type": "text", "text": prompt}],
                    },
                )
            finally:
                rpc.deadline = original_deadline
            if (
                result.get("commandId") != grant["turn_command_id"]
                or result.get("status") != "accepted"
                or result.get("disposition") not in {"started", "queued"}
                or result.get("startedNewTurn")
                is not (result.get("disposition") == "started")
                or not isinstance(result.get("turnId"), str)
                or not 0 < len(result["turnId"]) <= 512
            ):
                raise ValueError("native turn admission is uncertain; do not retry")
            ack = {
                key: result[key]
                for key in (
                    "commandId",
                    "status",
                    "disposition",
                    "startedNewTurn",
                    "turnId",
                )
            }
            outcome.update(admission=ack, turn_id=ack["turnId"])
            outcome["submission"]["state"] = "acknowledged"
            return ack

        ack = send_admitted(send)
        outcome["turn_id"] = ack["turnId"]
        outcome["admission"] = ack
        if ack["disposition"] == "queued":
            raise ValueError(
                "native submit raced idle admission and queued; exact withdrawal required"
            )
        terminal = rpc.terminal(grant["native_session_id"], ack["turnId"], cancelled)
        validate_terminal(terminal, grant["native_session_id"], ack["turnId"])
        outcome.update(status="native_terminal", terminal=terminal)
    except (ValueError, OSError, EOFError, TimeoutError) as exc:
        outcome.update(status="unknown", diagnostic=str(exc)[:4096])
        if isinstance(exc, RPCError):
            outcome["rpc_error"] = exc.error
        # Owned subprocess termination below is not evidence of native/provider cancellation.
        outcome["cancellation_outcome"] = "UNKNOWN"
    finally:
        try:
            ack = outcome.get("admission")
            if isinstance(ack, dict) and ack.get("disposition") == "queued":
                # Retain custody even if the journal's post-send fence refused.
                # Only the exact validated newly queued turn is eligible.
                outcome["queue_reconciliation"] = rpc.reconcile_queue(
                    grant["native_session_id"], ack
                )
                if outcome["queue_reconciliation"]["status"] == "cancelled":
                    outcome["cancellation_outcome"] = "VERIFIED_NATIVE_TERMINAL"
        finally:
            try:
                outcome["process_cleanup"] = rpc.close()
            except (OSError, ValueError, subprocess.SubprocessError) as error:
                outcome.update(
                    status="unknown",
                    cancellation_outcome="UNKNOWN",
                    cleanup_error=str(error)[:4096],
                    process_cleanup=getattr(rpc, "cleanup", None),
                )
            outcome.update(
                wire_sha256=rpc.wire.hexdigest(),
                output_bytes=rpc.size,
                stderr_sha256=hashlib.sha256(rpc.stderr).hexdigest(),
                process_exit=rpc.process.returncode,
            )
    return _observation(outcome)
