"""Synthetic current MSP fixtures; source qualification is not native acceptance."""

from copy import deepcopy
import hashlib
import time
from types import SimpleNamespace

import pytest

FINGERPRINT = "sha256:36466f634c8c78a812462ec941187fd4547b232ee06153e5feb2a1482f0d3d7f"


def initialized():
    return {
        "experimentalApi": False,
        "grantedCapabilities": ["userShell"],
        "museHome": "/synthetic/muse",
        "platformFamily": "unix",
        "platformOs": "linux",
        "schema": {"version": 1, "fingerprint": FINGERPRINT},
        "serverInfo": {"name": "muse", "version": "1.4.0"},
        "sessionDurability": "durable",
        "userAgent": "synthetic/muse-1.4.0",
    }


def resumed(identity, workspace):
    return {
        "session": {
            "sessionId": identity,
            "status": "idle",
            "activeTurnId": None,
            "forkedFrom": None,
            "workspaceRoot": workspace,
            "path": workspace + "/native.jsonl",
            "createdAt": "2026-01-01T00:00:00Z",
            "updatedAt": "2026-01-01T00:00:01Z",
            "modelId": None,
            "providerId": "synthetic",
            "turnCount": 0,
            "approvalMode": {
                "mode": "onRequest",
                "source": "startup",
                "lastCommandId": None,
            },
        },
        "pendingRequests": [],
        "viewCursor": "opaque-native-cursor",
        "history": {
            "mode": "none",
            "items": None,
            "snapshot": None,
            "noneReason": "excluded",
        },
    }


def grant():
    import native_resume as n
    from test_native_resume import explicit_posture

    result = {
        "client": "muse",
        "native_session_id": "01990000-0000-7000-8000-000000000022",
        "workspace": "/synthetic",
        "binary": {"path": "/synthetic/bin", "sha256": "a" * 64, "size": 4},
        "max_wall_seconds": 30,
        "max_output_bytes": 65536,
        "resume_command_id": n.command_id(),
        "turn_command_id": n.command_id(),
        "native_posture": explicit_posture(),
    }
    try:
        import native_muse_contract as contract

        result["native_protocol"] = contract.binding()
    except ImportError:
        pass  # The pre-repair causal fixture reaches the original production omission.
    return result


def run_launch(
    monkeypatch, initialize_reply, *, resume=None, ack_change=None, terminal_change=None
):
    import native_resume as n

    g = grant()
    calls = []

    class RPC:
        reconcile_queue = n.MuseConnection.reconcile_queue

        def __init__(self, *a, **kw):
            self.wire = hashlib.sha256()
            self.size = 0
            self.stderr = b""
            self.notifications = []
            self.process = SimpleNamespace(returncode=0)
            self.deadline = time.monotonic() + 30

        def initialize(self):
            calls.append("initialize")
            return deepcopy(initialize_reply)

        def call(self, method, payload):
            calls.append(method)
            if method == "session/resume":
                return (
                    deepcopy(resume)
                    if resume is not None
                    else resumed(g["native_session_id"], g["workspace"])
                )
            result = {
                "commandId": g["turn_command_id"],
                "status": "accepted",
                "disposition": "started",
                "startedNewTurn": True,
                "turnId": "actual-id",
            }
            if ack_change:
                result.update(ack_change)
            return result

        def terminal(self, session, turn, cancelled):
            result = {
                "sessionId": session,
                "turnId": turn,
                "terminal": "completed",
                "viewCursor": "opaque",
                "sourceRange": {
                    "stream": {"kind": "session", "id": session},
                    "first": {"id": "row", "sequence": 1},
                    "last": {"id": "row", "sequence": 1},
                },
            }
            if terminal_change:
                result.update(terminal_change)
            return result

        def _read(self):
            raise TimeoutError("synthetic missing queue evidence")

        def close(self):
            return {"group_absent": True, "leader_reaped": True, "fixture": "synthetic"}

    monkeypatch.setattr(n, "MuseConnection", RPC)
    monkeypatch.setattr(n, "binary_identity", lambda _: g["binary"])
    result = n.launch(
        g, "synthetic", send_admitted=lambda call: call(), cancelled=lambda: False
    )
    return result, calls


@pytest.mark.parametrize(
    "defect",
    [
        "empty",
        "schema",
        "fingerprint",
        "experimental",
        "ephemeral",
        "server",
        "version",
        "capabilities",
        "platform",
    ],
)
def test_actual_launch_refuses_unqualified_initialize_before_resume(
    monkeypatch, defect
):
    reply = initialized()
    if defect == "empty":
        reply = {}
    elif defect == "schema":
        reply["schema"]["version"] = True
    elif defect == "fingerprint":
        reply["schema"]["fingerprint"] = "sha256:" + "0" * 64
    elif defect == "experimental":
        reply["experimentalApi"] = True
    elif defect == "ephemeral":
        reply["sessionDurability"] = "ephemeral"
    elif defect == "server":
        reply["serverInfo"]["name"] = "foreign"
    elif defect == "version":
        reply["serverInfo"]["version"] = "1.5.0"
    elif defect == "capabilities":
        reply["grantedCapabilities"] = ["unknownFutureAction"]
    else:
        reply["platformOs"] = "futureOS"
    result, calls = run_launch(monkeypatch, reply)
    assert result["status"] == "unknown"
    assert calls == ["initialize"], (
        "invalid initialize must not resume or dispatch a native turn"
    )
    assert not result["task_accepted"]


def test_current_supported_handshake_is_only_transport_evidence(monkeypatch):
    result, calls = run_launch(monkeypatch, initialized())
    assert result["status"] == "native_terminal" and not result["task_accepted"]
    assert calls == ["initialize", "session/resume", "turn/start"]


def complete_resume(reply):
    """Add current metadata to old synthetic fixtures without repairing their defects."""
    reply = deepcopy(reply)
    session = reply.get("session")
    if isinstance(session, dict):
        for key, value in {
            "createdAt": "2026-01-01T00:00:00Z",
            "updatedAt": "2026-01-01T00:00:01Z",
            "modelId": None,
            "providerId": "synthetic",
            "turnCount": 0,
        }.items():
            session.setdefault(key, value)
    reply.setdefault(
        "history",
        {"mode": "none", "items": None, "snapshot": None, "noneReason": "excluded"},
    )
    reply.setdefault("viewCursor", "opaque-synthetic-cursor")
    return reply


def terminal(session, turn):
    return {
        "sessionId": session,
        "turnId": turn,
        "terminal": "completed",
        "viewCursor": "opaque",
        "sourceRange": {
            "stream": {"kind": "session", "id": session},
            "first": {"id": "row", "sequence": 1},
            "last": {"id": "row", "sequence": 1},
        },
    }


@pytest.mark.parametrize(
    "path,value",
    [
        (("experimentalApi",), 0),
        (("schema", "version"), 1.0),
        (("sessionDurability",), None),
        (("grantedCapabilities",), ["userShell", "userShell"]),
        (("grantedCapabilities",), [{}]),
        (("museHome",), "relative"),
        (("platformFamily",), "windows"),
        (("userAgent",), ""),
        (("serverInfo",), []),
        (("schema",), None),
    ],
)
def test_initialize_types_do_not_coerce_to_qualified_values(monkeypatch, path, value):
    reply = initialized()
    target = reply
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value
    result, calls = run_launch(monkeypatch, reply)
    assert result["status"] == "unknown" and calls == ["initialize"]


@pytest.mark.parametrize(
    "path,value",
    [
        (("session", "sessionId"), "foreign"),
        (("session", "activeTurnId"), "busy"),
        (("session", "forkedFrom"), {"sessionId": "parent"}),
        (("session", "workspaceRoot"), "/foreign"),
        (("session", "status"), "running"),
        (("session", "path"), ""),
        (("pendingRequests",), [{"id": "human"}]),
        (("viewCursor",), ""),
        (("session", "approvalMode", "mode"), "autoApprove"),
        (("session", "approvalMode", "source"), "futureMode"),
        (("session", "turnCount"), True),
        (("session", "createdAt"), "yesterday"),
        (("session", "updatedAt"), "2025-01-01T00:00:00Z"),
        (("history", "mode"), "inline"),
        (("history", "items"), []),
        (("history", "noneReason"), "projectionUnavailable"),
        (("session", "attention"), ["futureHumanRequest"]),
    ],
)
def test_resume_refuses_unsupported_or_unavailable_current_state(
    monkeypatch, path, value
):
    g = grant()
    reply = resumed(g["native_session_id"], g["workspace"])
    target = reply
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value
    result, calls = run_launch(monkeypatch, initialized(), resume=reply)
    assert result["status"] == "unknown" and calls == ["initialize", "session/resume"]


@pytest.mark.parametrize(
    "field", ["history", "viewCursor", "pendingRequests", "session"]
)
def test_resume_required_envelope_not_guessed(monkeypatch, field):
    g = grant()
    reply = resumed(g["native_session_id"], g["workspace"])
    reply.pop(field)
    result, calls = run_launch(monkeypatch, initialized(), resume=reply)
    assert result["status"] == "unknown" and "turn/start" not in calls


@pytest.mark.parametrize(
    "change",
    [
        {"disposition": "queued", "startedNewTurn": False},
        {"disposition": "steered", "startedNewTurn": False},
        {"commandId": "foreign"},
        {"status": "futureResult"},
        {"startedNewTurn": 1},
        {"turnId": ""},
    ],
)
def test_non_started_command_ack_never_retries_or_reports_terminal(monkeypatch, change):
    result, calls = run_launch(monkeypatch, initialized(), ack_change=change)
    assert result["status"] == "unknown" and calls.count("turn/start") == 1
    assert result["cancellation_outcome"] == "UNKNOWN" and not result["task_accepted"]


@pytest.mark.parametrize(
    "change",
    [
        {"sessionId": "foreign"},
        {"turnId": "foreign"},
        {"sourceRange": {}},
        {"viewCursor": ""},
        {"terminal": "futureTerminal"},
        {"durationMs": True},
    ],
)
def test_actual_launch_validates_terminal_even_at_transport_seam(monkeypatch, change):
    result, calls = run_launch(monkeypatch, initialized(), terminal_change=change)
    assert result["status"] == "unknown" and calls.count("turn/start") == 1


@pytest.mark.parametrize(
    "mutation", ["missing", "fingerprint", "validator", "bool", "extra"]
)
def test_stale_owner_protocol_refused_before_binary_read_or_process(
    monkeypatch, mutation
):
    import native_resume as n

    g = grant()
    if mutation == "missing":
        g.pop("native_protocol")
    elif mutation == "fingerprint":
        g["native_protocol"]["fingerprint"] = "sha256:" + "0" * 64
    elif mutation == "validator":
        g["native_protocol"]["implementation"]["native_resume.py"] = "0" * 64
    elif mutation == "bool":
        g["native_protocol"]["schema_version"] = True
    else:
        g["native_protocol"]["extra"] = True
    monkeypatch.setattr(
        n, "binary_identity", lambda *_: pytest.fail("stale grant read binary")
    )
    monkeypatch.setattr(
        n, "MuseConnection", lambda *_: pytest.fail("stale grant spawned process")
    )
    with pytest.raises(ValueError, match="protocol qualification"):
        n.launch(
            g,
            "synthetic",
            send_admitted=lambda _: pytest.fail("turn admitted"),
            cancelled=lambda: False,
        )


def test_handshake_refusal_precedes_initialized_notification(monkeypatch):
    import native_resume as n

    rpc = n.MuseConnection.__new__(n.MuseConnection)
    sent = []
    calls = []

    def call(method, params):
        calls.append((method, deepcopy(params)))
        return {}

    rpc.call = call
    rpc.send = sent.append
    with pytest.raises(ValueError):
        rpc.initialize()
    assert not sent and calls == [
        (
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
    ]


def test_stale_contract_handoff_refused_before_passive_identity_or_journal(monkeypatch):
    import prepared_native_launch as owner
    import native_muse_contract as contract

    g = grant()
    g["native_protocol"]["server_version"] = "older"
    monkeypatch.setattr(
        owner, "_clock", lambda: pytest.fail("stale contract reached later admission")
    )
    with pytest.raises(ValueError, match="protocol qualification"):
        owner.current_fence("/synthetic", {}, g)
    monkeypatch.setattr(owner.run_state, "load_run", lambda *a: {})
    monkeypatch.setattr(owner, "_grant", lambda *a: g)
    monkeypatch.setattr(
        owner, "_step", lambda *a, **k: pytest.fail("stale contract consumed permit")
    )
    with pytest.raises(ValueError, match="protocol qualification"):
        owner.execute("/synthetic", "run", "permit", "token")
    assert contract.binding()["server_version"] == "1.4.0"


@pytest.mark.parametrize(
    "change",
    [
        {"terminal": "failed"},
        {
            "terminal": "completed",
            "error": {"kind": "failure", "message": "x", "retryable": False},
        },
        {"terminal": "failed", "error": {}},
        {
            "terminal": "failed",
            "error": {"kind": "failure", "message": "x", "retryable": 0},
        },
    ],
)
def test_current_terminal_failure_shape_is_not_guessed(monkeypatch, change):
    result, _ = run_launch(monkeypatch, initialized(), terminal_change=change)
    assert result["status"] == "unknown"


def test_well_formed_native_failure_remains_a_failure_observation(monkeypatch):
    result, _ = run_launch(
        monkeypatch,
        initialized(),
        terminal_change={
            "terminal": "failed",
            "error": {
                "kind": "environment",
                "message": "synthetic failure",
                "retryable": False,
            },
        },
    )
    assert (
        result["status"] == "native_terminal"
        and result["terminal"]["terminal"] == "failed"
    )
    assert not result["task_accepted"]


def test_current_contract_matches_pinned_exported_surface():
    import json
    from pathlib import Path
    import native_muse_contract as c

    witness = json.loads(
        (Path(__file__).parents[1] / "references/muse-launch-protocol.json").read_text()
    )
    assert witness["manifest"] == {
        "experimental": False,
        "fingerprint": c.FINGERPRINT,
        "schemaVersion": 1,
    }
    defs = witness["definitions"]
    assert set(defs["InitializeResult"]["required"]) <= initialized().keys()
    assert set(defs["CapabilityName"]["enum"]) == c.CAPABILITIES
    sample = resumed("synthetic", "/synthetic")
    assert set(defs["SessionResumeResult"]["required"]) <= sample.keys()
    assert set(defs["Session"]["required"]) <= sample["session"].keys()
    assert defs["IfBusy"]["enum"] == ["queue", "steer", "replace"]
    assert set(defs["TurnStartParams"]["required"]) == {
        "commandId",
        "input",
        "sessionId",
    }
    assert set(defs["TurnStartResult"]["required"]) == {
        "commandId",
        "disposition",
        "startedNewTurn",
        "status",
        "turnId",
    }
    assert set(defs["TurnCompletedParams"]["required"]) == {
        "sessionId",
        "sourceRange",
        "terminal",
        "turnId",
        "viewCursor",
    }
    assert "source" in defs["ReasoningEffortState"]["required"]


def test_historical_passive_fingerprint_does_not_authorize_new_launch(monkeypatch):
    import native_muse

    reply = initialized()
    reply["schema"]["fingerprint"] = native_muse.STABLE_FINGERPRINT
    result, calls = run_launch(monkeypatch, reply)
    assert result["status"] == "unknown" and calls == ["initialize"]


@pytest.mark.parametrize("defect", ["fingerprint", "missing", "ephemeral", "duplicate"])
def test_bad_real_stdio_handshake_cannot_resume(monkeypatch, tmp_path, defect):
    import json
    import os
    import subprocess
    import sys
    import native_resume as n

    g = grant()
    g["workspace"] = str(tmp_path)
    wire = tmp_path / "wire.jsonl"
    payload = initialized()
    if defect == "fingerprint":
        payload["schema"]["fingerprint"] = "sha256:" + "0" * 64
    elif defect == "missing":
        payload.pop("schema")
    elif defect == "ephemeral":
        payload["sessionDurability"] = "ephemeral"
    code = """import sys,json
path,reply,defect=sys.argv[1:]
for line in sys.stdin:
 request=json.loads(line)
 with open(path,'a') as f:f.write(json.dumps(request)+'\\n')
 response=json.dumps({'jsonrpc':'2.0','id':request['id'],'result':json.loads(reply)})
 if defect=='duplicate':response=response[:-1]+',"result":{}}'
 print(response,flush=True)
"""
    processes = []
    actual = subprocess.Popen

    def spawn(args, **kwargs):
        p = actual(
            [
                sys.executable,
                "-I",
                "-B",
                "-u",
                "-c",
                code,
                str(wire),
                json.dumps(payload),
                defect,
            ],
            **kwargs,
        )
        processes.append(p)
        return p

    monkeypatch.setattr(n.subprocess, "Popen", spawn)
    monkeypatch.setattr(n, "binary_identity", lambda _: g["binary"])
    result = n.launch(
        g,
        "synthetic",
        send_admitted=lambda _: pytest.fail("bad initialize dispatched"),
        cancelled=lambda: False,
    )
    assert result["status"] == "unknown" and not result["task_accepted"]
    assert [json.loads(line)["method"] for line in wire.read_text().splitlines()] == [
        "initialize"
    ]
    assert len(processes) == 1 and processes[0].returncode is not None
    with pytest.raises(ProcessLookupError):
        os.killpg(processes[0].pid, 0)
    print(
        json.dumps(
            {
                "fixture": "bad-current-handshake",
                "mode": defect,
                "pid": processes[0].pid,
                "returncode": processes[0].returncode,
                "group_absent": True,
            }
        )
    )


def test_interpretation_pin_cannot_hash_a_replaced_path(monkeypatch, tmp_path):
    import native_muse_contract as c
    import os

    target = tmp_path / "native_muse_contract.py"
    target.write_text("original")
    replacement = tmp_path / "replacement.py"
    replacement.write_text("changed!")
    monkeypatch.setattr(c, "__file__", str(target))
    original = os.read
    changed = []

    def read(fd, size):
        result = original(fd, size)
        if result and not changed:
            replacement.replace(target)
            changed.append(True)
        return result

    monkeypatch.setattr(c.os, "read", read)
    with pytest.raises(ValueError, match="changed while binding"):
        c._code_digest("native_muse_contract.py")
    assert changed and target.read_text() == "changed!"


@pytest.mark.parametrize("kind", ["symlink", "fifo", "oversized"])
def test_interpretation_pin_refuses_nonregular_or_unbounded_source(
    monkeypatch, tmp_path, kind
):
    import native_muse_contract as c
    import os

    target = tmp_path / "native_muse_contract.py"
    foreign = tmp_path / "foreign.py"
    foreign.write_text("private sentinel")
    if kind == "symlink":
        target.symlink_to(foreign)
    elif kind == "fifo":
        os.mkfifo(target)
    else:
        target.write_bytes(b"x" * (128 * 1024 + 1))
    monkeypatch.setattr(c, "__file__", str(target))
    with pytest.raises((ValueError, OSError)):
        c._code_digest("native_muse_contract.py")
    assert foreign.read_text() == "private sentinel"
