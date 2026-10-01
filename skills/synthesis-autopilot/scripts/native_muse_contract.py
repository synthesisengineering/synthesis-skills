"""Qualified Muse 1.4 stable launch subset; no execution or permission authority.

Grounding: the 1.4.0-R4161.1 offline stable MSP export and retained initialize
response. Historical passive-wire decoding has its own explicitly pinned owner.
Unknown versions, capabilities and durability states are not launch-qualified.
"""

from __future__ import annotations

from datetime import datetime
import hashlib
import json
import os
import re
from pathlib import Path
import stat

FINGERPRINT = "sha256:36466f634c8c78a812462ec941187fd4547b232ee06153e5feb2a1482f0d3d7f"
SERVER_VERSION = "1.4.0"
CAPABILITIES = frozenset({"userShell", "sessionMcp", "sessionListStream"})


def _code_digest(name):
    path = Path(__file__).absolute().with_name(name)
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        before = os.fstat(fd)
        if not stat.S_ISREG(before.st_mode) or before.st_size > 128 * 1024:
            raise ValueError(
                "native protocol implementation is unavailable or oversized"
            )
        data = b""
        while len(data) <= 128 * 1024:
            part = os.read(fd, 16384)
            if not part:
                break
            data += part
        after = os.fstat(fd)
        named = path.lstat()

        def signature(s):
            return (
                s.st_dev,
                s.st_ino,
                s.st_size,
                s.st_mode,
                s.st_mtime_ns,
                s.st_ctime_ns,
            )

        if (
            signature(before) != signature(after)
            or signature(after) != signature(named)
            or len(data) != before.st_size
        ):
            raise ValueError("native protocol implementation changed while binding")
        return hashlib.sha256(data).hexdigest()
    finally:
        os.close(fd)


def binding():
    """Owner-derived immutable interpretation pin, separate from the binary pin."""
    return {
        "schema_version": 1,
        "contract": "muse-current-launch-v1",
        "fingerprint": FINGERPRINT,
        "server_version": SERVER_VERSION,
        "experimental_api": False,
        "session_durability": "durable",
        "implementation": {
            name: _code_digest(name)
            for name in (
                "native_muse_contract.py",
                "native_resume.py",
                "prepared_native_launch.py",
            )
        },
    }


def validate_binding(value):
    # JSON comparison keeps bool/int and extra-field differences meaningful.
    if not isinstance(value, dict) or json.dumps(
        value, sort_keys=True, allow_nan=False
    ) != json.dumps(binding(), sort_keys=True):
        raise ValueError(
            "native protocol qualification changed or is missing; prepare a new owner grant"
        )


def _object(value, required, label):
    if not isinstance(value, dict) or not required <= value.keys():
        raise ValueError(label + " lacks its typed required fields")
    return value


def _text(value, label, *, absolute=False):
    if not isinstance(value, str) or not 0 < len(value) <= 4096 or "\x00" in value:
        raise ValueError("invalid " + label)
    if absolute and not value.startswith("/"):
        raise ValueError(label + " must be absolute on the qualified POSIX host")
    return value


def validate_initialize(reply):
    _object(
        reply,
        {
            "experimentalApi",
            "grantedCapabilities",
            "museHome",
            "platformFamily",
            "platformOs",
            "schema",
            "serverInfo",
            "sessionDurability",
            "userAgent",
        },
        "native initialize",
    )
    schema = _object(reply["schema"], {"version", "fingerprint"}, "native schema")
    server = _object(reply["serverInfo"], {"name", "version"}, "native server")
    if (
        type(schema["version"]) is not int
        or schema["version"] != 1
        or schema["fingerprint"] != FINGERPRINT
        or server["name"] != "muse"
        or server["version"] != SERVER_VERSION
        or reply["experimentalApi"] is not False
        or reply["sessionDurability"] != "durable"
        or reply["platformFamily"] != "unix"
        or reply["platformOs"] not in ("macos", "linux")
    ):
        raise ValueError(
            "native initialize does not match the qualified stable durable POSIX contract"
        )
    capabilities = reply["grantedCapabilities"]
    if (
        not isinstance(capabilities, list)
        or len(capabilities) > len(CAPABILITIES)
        or any(not isinstance(x, str) or x not in CAPABILITIES for x in capabilities)
        or len(set(capabilities)) != len(capabilities)
    ):
        raise ValueError("native initialize contains unqualified capability grants")
    _text(reply["museHome"], "Muse home", absolute=True)
    _text(reply["userAgent"], "native user agent")
    # A policy-implicit userShell grant is documented, not a request to use it.
    return {
        "schema": dict(schema),
        "serverInfo": dict(server),
        "experimentalApi": False,
        "sessionDurability": "durable",
        "platformFamily": reply["platformFamily"],
        "platformOs": reply["platformOs"],
        "grantedCapabilities": list(capabilities),
    }


def validate_resume_shape(reply):
    """Current response for our exact excludeItems=true, no-config request."""
    _object(
        reply, {"session", "history", "pendingRequests", "viewCursor"}, "native resume"
    )
    _text(reply["viewCursor"], "native resume view cursor")
    history = _object(
        reply["history"], {"mode", "items", "snapshot", "noneReason"}, "native history"
    )
    if (
        history["mode"] != "none"
        or history["noneReason"] != "excluded"
        or history["items"] is not None
        or history["snapshot"] is not None
    ):
        raise ValueError("native resume history does not match explicit exclusion")
    session = _object(
        reply["session"],
        {
            "activeTurnId",
            "createdAt",
            "forkedFrom",
            "modelId",
            "path",
            "providerId",
            "sessionId",
            "status",
            "turnCount",
            "updatedAt",
            "workspaceRoot",
        },
        "native session",
    )
    for name in ("sessionId", "status"):
        _text(session[name], "native " + name)
    _text(session["path"], "native durable session path", absolute=True)
    _text(session["workspaceRoot"], "native workspace", absolute=True)
    for name in ("modelId", "providerId"):
        if session[name] is not None:
            _text(session[name], "native " + name)
    if type(session["turnCount"]) is not int or session["turnCount"] < 0:
        raise ValueError("native session has invalid completed turn count")
    dates = []
    for name in ("createdAt", "updatedAt"):
        value = _text(session[name], "native " + name)
        if not re.fullmatch(
            r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})", value
        ):
            raise ValueError("native session timestamp is not RFC3339")
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as error:
            raise ValueError("native session has malformed timestamp") from error
        if parsed.tzinfo is None:
            raise ValueError("native session timestamp lacks timezone")
        dates.append(parsed)
    if dates[1] < dates[0]:
        raise ValueError("native session timestamps are reversed")
    if "attention" in session and session["attention"] != []:
        raise ValueError("native session has unresolved or unqualified attention")
    mode = _object(
        session.get("approvalMode"),
        {"mode", "source", "lastCommandId"},
        "native approval mode",
    )
    if mode["source"] not in ("startup", "replay", "approvalReconfigure"):
        raise ValueError("native approval source is unqualified")
    return session


def validate_terminal_shape(data):
    if data["terminal"] == "failed":
        error = _object(
            data.get("error"), {"kind", "message", "retryable"}, "native turn failure"
        )
        _text(error["kind"], "native failure kind")
        _text(error["message"], "native failure message")
        if type(error["retryable"]) is not bool:
            raise ValueError("native failure retryability is not boolean")
    elif "error" in data:
        raise ValueError("native nonfailed terminal carries contradictory failure data")
