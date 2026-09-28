"""Bounded observation of an admitted existing Hermes process, never its executor.

The PM worker owns selection, files and receipt issuance. The local channel
accepts only exact hook argv directly spawned by a pinned existing process. It does
not start a model, configure/trust hooks, signal that process or enforce its
permissions. Same-UID hostile host writers are outside the existing PM model.
"""

from __future__ import annotations
import hashlib
import base64
import json
import re
import os
from pathlib import Path
import shlex
import socket
import stat
import struct
import subprocess
import sys
import time

MAX_FRAME = 1024 * 1024
MAX_CAPTURE = 3 * MAX_FRAME
CAPABILITY = "native-context-observation"


def _owners():
    path = str(
        Path(__file__).resolve().parents[2] / "synthesis-agent-conformance/scripts"
    )
    if path not in sys.path:
        sys.path.insert(0, path)


def _json(raw):
    from native_adapter_sdk import strict_json

    return strict_json(raw)


def _remaining(deadline, limit=2):
    remaining = limit if deadline is None else min(limit, deadline - time.monotonic())
    if remaining <= 0:
        raise ValueError("native observation deadline exhausted")
    return remaining


def process_identity(pid, *, deadline=None):
    if type(pid) is not int or pid <= 1:
        raise ValueError("invalid native process identity")
    # Process identity is OS authority, not a command selected by caller PATH.
    # Resolve only the fixed system location (including merged-/usr Linux).
    inspector = Path("/bin/ps").resolve(strict=True)
    for member in (inspector, *inspector.parents):
        info = member.lstat()
        if info.st_uid != 0 or stat.S_IMODE(info.st_mode) & 0o022:
            raise ValueError("process inspector is not system-owned")
    if not stat.S_ISREG(inspector.lstat().st_mode) or not os.access(inspector, os.X_OK):
        raise ValueError("qualified system process inspector unavailable")
    value = subprocess.run(
        [str(inspector), "-ww", "-p", str(pid), "-o", "pid=,ppid=,uid=,lstart=,command="],
        capture_output=True,
        timeout=_remaining(deadline),
        check=True,
    )
    if len(value.stdout) > 32768 or value.stderr:
        raise ValueError("native process metadata exceeds its bound")
    fields = value.stdout.decode("utf-8").strip().split(None, 8)
    if len(fields) != 9 or int(fields[0]) != pid or int(fields[2]) != os.getuid():
        raise ValueError("native process is absent or foreign")
    return {
        "pid": pid,
        "ppid": int(fields[1]),
        "uid": int(fields[2]),
        "start": " ".join(fields[3:8]),
        "argv": shlex.split(fields[8]),
    }


def _peer(sock, *, deadline=None):
    if sys.platform == "darwin":
        pid = sock.getsockopt(0, 2)  # LOCAL_PEERPID, documented Unix peer PID.
    elif hasattr(socket, "SO_PEERCRED"):
        pid, uid, _ = struct.unpack(
            "3i", sock.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12)
        )
        if uid != os.getuid():
            raise ValueError("foreign channel owner")
    else:
        raise ValueError("authenticated local process transport unavailable")
    return process_identity(pid, deadline=deadline)


def _source_files(selection, *, deadline=None):
    _owners()
    from signed_receipt import read_regular

    expected = selection["source_files"]
    if not isinstance(expected, dict) or not 1 <= len(expected) <= 64:
        raise ValueError("native source inventory is missing or exceeds its bound")
    total = 0
    for filename, sha in expected.items():
        _remaining(deadline)
        raw = read_regular(Path(filename), limit=4 * 1024 * 1024)
        total += len(raw)
        if total > 16 * 1024 * 1024:
            raise ValueError("native selected source inventory exceeds aggregate bound")
        _remaining(deadline)
        if hashlib.sha256(raw).hexdigest() != sha:
            raise ValueError("native executable/source generation changed")


def validate_selection(value, *, deadline=None):
    required = {
        "schema",
        "client",
        "session_id",
        "profile_home",
        "profile",
        "cwd",
        "process",
        "hook_argv",
        "source_files",
        "producer_version",
        "state_home",
    }
    if (
        not isinstance(value, dict)
        or set(value) != required
        or type(value["schema"]) is not int
        or value["schema"] != 1
        or value["client"] != "hermes"
    ):
        raise ValueError("invalid owner-selected Hermes observation")
    for key in ("session_id", "profile", "producer_version"):
        if not isinstance(value[key], str) or not value[key] or len(value[key]) > 256:
            raise ValueError("invalid selected identity")
    _owners()
    from hermes_source import chain

    for key in ("profile_home", "cwd", "state_home"):
        chain(Path(value[key]))
    for key in ("process",):
        original = value[key]
        if process_identity(original.get("pid"), deadline=deadline) != original:
            raise ValueError("selected native process identity changed")
    # The input is admitted explicitly by PM, not discovered from caller hints.
    # A nonexistent/relative executable or script is not a source pin. Validate
    # membership before reading the complete inventory; read_regular then binds
    # actual bytes and rejects aliases, rather than using exists() as a filter.
    if not isinstance(value["source_files"], dict):
        raise ValueError("native source inventory is missing")
    for argv in (value["hook_argv"], value["process"]["argv"]):
        if (not isinstance(argv, list) or not argv or len(argv) > 32
                or any(not isinstance(x, str) or not x or len(x) > 4096
                       or "\x00" in x for x in argv)):
            raise ValueError("exact native process and hook argv required")
        # After Python's explicit -m/-c invocation mode, a relative .py
        # operand can be application data (for example a pytest selector).
        # Such operands are not direct script entrypoints. Absolute script
        # paths remain pinned, as does the interpreter in every mode.
        mode_index = next((i for i, arg in enumerate(argv) if arg in {"-m", "-c"}), len(argv))
        for index, arg in enumerate(argv):
            executable = index == 0
            script = arg.endswith(".py") and (arg.startswith("/") or index < mode_index)
            # X_OK on a directory means traversal, not executable code.
            # This supplementary check covers actual file arguments only;
            # argv[0] and direct scripts are mandatory even when nonexistent.
            extra_executable = (arg.startswith("/") and Path(arg).is_file()
                                and os.access(arg, os.X_OK))
            if executable or script or extra_executable:
                if not Path(arg).is_absolute() or arg not in value["source_files"]:
                    raise ValueError("selected executable or script is not source-pinned")
                if executable and not os.access(arg, os.X_OK):
                    raise ValueError("selected executable is unavailable")
    _source_files(value, deadline=deadline)
    return value


def authenticate(sock, selection, *, deadline=None):
    validate_selection(selection, deadline=deadline)
    peer = _peer(sock, deadline=deadline)
    if peer["argv"] != selection["hook_argv"]:
        raise ValueError("callback process does not execute the selected exact hook")
    target = selection["process"]
    # Pinned upstream agent/shell_hooks.py::_spawn uses a direct Popen with
    # shell=False. An arbitrary tool descendant can run the same executable,
    # so broader ancestry is not a native callback producer qualification.
    if peer["ppid"] != target["pid"]:
        raise ValueError("hook is not a direct child of the selected native producer")
    if process_identity(target["pid"], deadline=deadline) != target:
        raise ValueError("native producer identity changed")
    if process_identity(peer["pid"], deadline=deadline) != peer:
        raise ValueError("hook process changed during authentication")
    return peer


def _receive(sock, deadline, retained):
    raw, complete = bytearray(), False
    try:
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise ValueError("observation transport timed out")
            sock.settimeout(remaining)
            block = sock.recv(min(16384, MAX_FRAME + 1 - len(raw)))
            if not block:
                complete = True
                break
            raw.extend(block)
            if len(raw) > MAX_FRAME:
                raise ValueError("observation frame exceeds its byte bound")
        return _json(bytes(raw))
    finally:
        retained.append(
            {
                "raw_base64": base64.b64encode(raw).decode("ascii"),
                "complete": complete,
                "sha256": hashlib.sha256(raw).hexdigest(),
            }
        )


def send(path, payload, result, active, *, seconds=2):
    """Existing approved hook emits evidence; no receipt/authority is issued here."""
    _owners()
    from hermes_source import chain

    path = Path(path)
    chain(path.parent)
    info = path.lstat()
    if (
        not stat.S_ISSOCK(info.st_mode)
        or info.st_uid != os.getuid()
        or stat.S_IMODE(info.st_mode) != 0o600
    ):
        raise ValueError("observation channel is not private and owned")
    raw = json.dumps(
        {
            "payload": payload,
            "result": result,
            "release": {
                key: active[key]
                for key in ("release_root", "content_digest", "version")
            },
        },
        sort_keys=True,
        allow_nan=False,
    ).encode()
    if len(raw) > MAX_FRAME:
        raise ValueError("hook observation exceeds its bound")
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as connection:
        connection.settimeout(seconds)
        connection.connect(str(path))
        if (path.lstat().st_dev, path.lstat().st_ino) != (info.st_dev, info.st_ino):
            raise ValueError("channel identity changed")
        connection.sendall(raw)
        connection.shutdown(socket.SHUT_WR)
        if connection.recv(16) != b"retained\n":
            raise ValueError("owner did not retain the complete hook observation")


def validate_pair(rows, selection):
    if len(rows) != 2:
        raise ValueError("complete context/consumer pair required")
    first, second = [r["payload"] for r in rows]
    for index, row in enumerate(rows):
        if (
            set(row) != {"payload", "result", "release", "peer", "sequence"}
            or type(row["sequence"]) is not int
            or row["sequence"] != index
        ):
            raise ValueError("observation sequence or fields changed")
        payload = row["payload"]
        if any(
            payload.get(k) != selection[k] for k in ("session_id", "profile", "cwd")
        ):
            raise ValueError("native callback identity differs")
        if not isinstance(payload.get("extra"), dict):
            raise ValueError("native callback metadata missing")
    if (
        first["hook_event_name"] != "pre_llm_call"
        or second["hook_event_name"] != "pre_api_request"
    ):
        raise ValueError("native callback stages are not the actual consumer pair")
    a, b = first["extra"], second["extra"]
    if (
        not isinstance(a.get("turn_id"), str)
        or not a["turn_id"]
        or b.get("turn_id") != a["turn_id"]
        or not isinstance(b.get("api_request_id"), str)
        or not b["api_request_id"]
    ):
        raise ValueError("native turn/request join differs")
    if rows[0]["release"] != rows[1]["release"]:
        raise ValueError("hook source changed between producer and consumer")
    context = rows[0]["result"].get("context")
    if not isinstance(context, str) or not context or len(context.encode()) > 6000:
        raise ValueError("context cannot fit the native untruncated consumer contract")
    from vendor_native import _context_witness, PREFIX

    witness = _context_witness(context)
    import uuid

    if (
        not isinstance(witness.get("event_id"), str)
        or str(uuid.UUID(witness["event_id"])) != witness["event_id"]
    ):
        raise ValueError("invalid registry event identity")
    request = b.get("request")
    if (
        not isinstance(request, dict)
        or request.get("method") != "POST"
        or not isinstance(request.get("body"), dict)
    ):
        raise ValueError("actual assembled native request is missing")
    body = request["body"]
    fields = [name for name in ("messages", "input") if name in body]
    if len(fields) != 1:
        raise ValueError("native request has no unique actual message field")
    messages = body[fields[0]]
    if not isinstance(messages, list) or not messages or len(messages) > 200:
        raise ValueError("native message inventory unavailable or partial")
    # The vendor sanitizer marks incomplete structures at any nesting level.
    # Examine the bounded whole request, including non-text blocks, so a second
    # marker cannot disappear merely because its content shape is unsupported.
    pending, nodes, markers = [(body, 0)], 0, 0
    while pending:
        item, depth = pending.pop()
        nodes += 1
        if nodes > 10000 or depth > 12:
            raise ValueError("native request inspection bound exceeded")
        if isinstance(item, dict):
            if any(key in item for key in ("_truncated", "_truncated_items")):
                raise ValueError("native request contains truncated inventory")
            pending.extend((value, depth + 1) for value in item.values())
        elif isinstance(item, list):
            pending.extend((value, depth + 1) for value in item)
        elif isinstance(item, str):
            if re.search(r"\.\.\.\[truncated \d+ chars\]$", item) or re.fullmatch(
                r"<\w+ depth limit>", item
            ):
                raise ValueError("native request contains truncated content")
            markers += item.count(PREFIX)
    matched = 0
    for message in messages:
        if not isinstance(message, dict):
            raise ValueError("native message inventory is incomplete")
        content = message.get("content")
        texts = [content] if isinstance(content, str) else []
        if isinstance(content, list):
            texts = [
                part["text"]
                for part in content
                if isinstance(part, dict)
                and part.get("type") in {"text", "input_text"}
                and isinstance(part.get("text"), str)
            ]
        if message.get("role") == "user":
            matched += sum(text.endswith(context) for text in texts)
    if matched != 1 or markers != 1:
        raise ValueError(
            "native consumer did not carry the exact unique emitted context"
        )
    return witness


def capture(path, selection, seconds, *, raw_frames=None):
    """Own only this finite listener; never signal/start the selected process."""
    if type(seconds) not in (int, float) or not 0 < seconds <= 3600:
        raise ValueError("finite observation deadline required")
    deadline = time.monotonic() + seconds
    validate_selection(selection, deadline=deadline)
    path = Path(path)
    _owners()
    from hermes_source import chain

    chain(path.parent)
    parent = path.parent.stat()
    if parent.st_uid != os.getuid() or parent.st_mode & 0o022:
        raise ValueError("observation channel parent is not privately owned")
    if path.exists() or path.is_symlink() or len(os.fsencode(path)) > 100:
        raise ValueError("fresh bounded local channel path required")
    rows, failure = [], None
    raw_frames = [] if raw_frames is None else raw_frames
    if raw_frames:
        raise ValueError("fresh raw transport custody required")
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as server:
        server.bind(str(path))
        os.chmod(path, 0o600, follow_symlinks=False)
        bound = path.lstat()
        server.listen(1)
        try:
            for sequence in range(2):
                server.settimeout(max(0.001, deadline - time.monotonic()))
                with server.accept()[0] as connection:
                    peer = authenticate(connection, selection, deadline=deadline)
                    row = _receive(connection, deadline, raw_frames)
                    if set(row) != {"payload", "result", "release"}:
                        raise ValueError("unexpected callback envelope")
                    authenticate(connection, selection, deadline=deadline)
                    row.update(peer=peer, sequence=sequence)
                    rows.append(row)
                    if len(json.dumps(rows).encode()) > MAX_CAPTURE:
                        raise ValueError(
                            "observation capture exceeds its aggregate bound"
                        )
                    connection.sendall(b"retained\n")
            validate_selection(selection, deadline=deadline)
            validate_pair(rows, selection)
        except (
            OSError,
            ValueError,
            KeyError,
            TypeError,
            subprocess.SubprocessError,
            KeyboardInterrupt,
        ) as exc:
            failure = type(exc).__name__ + ": " + str(exc)[:500]
        finally:
            # Descriptor is closed independently. Only our same inode is removed.
            try:
                now = path.lstat()
                if (now.st_dev, now.st_ino) == (bound.st_dev, bound.st_ino):
                    path.unlink()
                else:
                    failure = "observation channel replaced; foreign path retained"
            except FileNotFoundError:
                failure = "observation channel disappeared during capture"
    return rows, failure
