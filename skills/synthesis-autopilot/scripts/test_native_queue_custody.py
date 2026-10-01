"""Synthetic owner races: a queued continuation is an effect, never no-op."""

from copy import deepcopy
import hashlib
import json
import os
import subprocess
import sys
import time
from types import SimpleNamespace

import pytest

import native_resume as n
from test_native_protocol import grant, initialized, resumed, terminal


def unqueued(g, turn="new-queued"):
    return {
        "sessionId": g["native_session_id"],
        "turnId": turn,
        "commandId": g["turn_command_id"],
        "viewCursor": "queue-cursor",
        "sourceRange": terminal(g["native_session_id"], turn)["sourceRange"],
    }


def execute(
    monkeypatch,
    *,
    queue_case="removed",
    acknowledgement=None,
    event_change=None,
    post_send_failure=False,
    grant_override=None,
    dispatch=None,
):
    g = grant_override or grant()
    calls = []
    journal = []

    class RPC:
        reconcile_queue = getattr(n.MuseConnection, "reconcile_queue", None)

        def __init__(self, *args, **kwargs):
            self.wire = hashlib.sha256()
            self.size = 0
            self.stderr = b""
            self.process = SimpleNamespace(returncode=0)
            self.deadline = time.monotonic() + 30
            self.notifications = []

        def initialize(self):
            return initialized()

        def call(self, method, payload):
            calls.append((method, deepcopy(payload)))
            if method == "session/resume":
                return resumed(g["native_session_id"], g["workspace"])
            if method == "turn/start":
                if queue_case == "lost-start":
                    raise EOFError("synthetic missing start acknowledgement")
                reply = {
                    "commandId": g["turn_command_id"],
                    "status": "accepted",
                    "disposition": "queued",
                    "startedNewTurn": False,
                    "turnId": "new-queued",
                }
                reply.update(acknowledgement or {})
                return reply
            if method == "turn/unqueue":
                if queue_case in {
                    "already-launched",
                    "wrong-rejection",
                    "cancel-malformed",
                    "cancel-terminal-wrong",
                    "cancel-terminal-missing",
                    "cancel-failed",
                }:
                    raise n.RPCError(
                        {
                            "code": -32030,
                            "message": "synthetic",
                            "data": {
                                "kind": "commandRejected",
                                "commandId": (
                                    payload["commandId"]
                                    if queue_case != "wrong-rejection"
                                    else "foreign-command"
                                ),
                                "reason": "synthetic_rejection",
                            },
                        }
                    )
                if queue_case == "lost-unqueue":
                    raise EOFError("synthetic missing unqueue acknowledgement")
                event = unqueued(g)
                event.update(event_change or {})
                if queue_case != "ack-only":
                    self.notifications.append(
                        {"method": "turn/unqueued", "params": event}
                    )
                return {
                    "commandId": payload["commandId"],
                    "turnId": "new-queued",
                    "status": "wrong"
                    if queue_case == "malformed-unqueue"
                    else "accepted",
                }
            if method == "turn/cancel":
                assert payload["turnId"] == "new-queued", (
                    "never cancel foreground implicitly"
                )
                return {
                    "commandId": payload["commandId"],
                    "turnId": (
                        "foreign" if queue_case == "cancel-malformed" else "new-queued"
                    ),
                    "status": "accepted",
                }
            raise AssertionError(method)

        def terminal(self, session, turn, cancelled):
            assert turn == "new-queued"
            result = terminal(session, turn)
            result["terminal"] = "cancelled"
            if queue_case == "cancel-terminal-wrong":
                result["turnId"] = "foreign"
            elif queue_case == "cancel-terminal-missing":
                raise TimeoutError("synthetic no cancellation terminal")
            elif queue_case == "cancel-failed":
                result.update(
                    terminal="failed",
                    error={
                        "kind": "synthetic",
                        "message": "failed",
                        "retryable": False,
                    },
                )
            return result

        def _read(self):
            raise TimeoutError("synthetic bounded missing evidence")

        def close(self):
            return {"group_absent": True, "leader_reaped": True, "synthetic": True}

    monkeypatch.setattr(n, "MuseConnection", RPC)
    monkeypatch.setattr(n, "binary_identity", lambda _: g["binary"])

    def submit(send):
        ack = send()
        journal.append(deepcopy(ack))
        if post_send_failure:
            raise ValueError("synthetic issuer fence changed after send")
        return ack

    result = (
        dispatch()
        if dispatch
        else n.launch(g, "synthetic", send_admitted=submit, cancelled=lambda: False)
    )
    return result, calls, journal, g


def test_idle_to_queue_race_requires_exact_authoritative_withdrawal(monkeypatch):
    result, calls, journal, g = execute(monkeypatch)
    assert [method for method, _ in calls] == [
        "session/resume",
        "turn/start",
        "turn/unqueue",
    ]
    assert journal[0]["disposition"] == "queued"
    evidence = result["queue_reconciliation"]
    assert evidence["status"] == "removed"
    assert evidence["event"] == unqueued(g)
    assert result["admission"]["turnId"] == "new-queued"
    assert result["task_accepted"] is False


def test_post_send_fence_failure_still_withdraws_exact_owned_queue(monkeypatch):
    result, calls, _, _ = execute(monkeypatch, post_send_failure=True)
    assert calls[-1][0] == "turn/unqueue"
    assert result["status"] == "unknown"
    assert result["queue_reconciliation"]["status"] == "removed"


@pytest.mark.parametrize(
    "case", ["ack-only", "lost-unqueue", "malformed-unqueue", "wrong-rejection"]
)
def test_missing_or_ambiguous_removal_preserves_unresolved_custody(monkeypatch, case):
    result, calls, _, _ = execute(monkeypatch, queue_case=case)
    assert result["queue_reconciliation"]["status"] == "unresolved"
    assert result["admission"]["turnId"] == "new-queued"
    assert result["cancellation_outcome"] == "UNKNOWN"
    assert [method for method, _ in calls].count("turn/start") == 1
    assert not any(method == "turn/cancel" for method, _ in calls)


@pytest.mark.parametrize(
    "change",
    [
        {"sessionId": "foreign"},
        {"turnId": "foreign"},
        {"commandId": "foreign"},
        {"sourceRange": {}},
        {
            "sourceRange": {
                "stream": {"kind": "run", "id": "new-queued"},
                "first": {"id": "r", "sequence": 1},
                "last": {"id": "r", "sequence": 1},
            }
        },
        {"viewCursor": ""},
    ],
)
def test_foreign_or_malformed_removal_never_settles_custody(monkeypatch, change):
    result, _, _, _ = execute(monkeypatch, event_change=change)
    assert result["queue_reconciliation"]["status"] == "unresolved"
    assert result["task_accepted"] is False


def test_explicit_rejection_only_cancels_our_exact_new_turn(monkeypatch):
    result, calls, _, _ = execute(monkeypatch, queue_case="already-launched")
    assert [method for method, _ in calls][-2:] == ["turn/unqueue", "turn/cancel"]
    assert result["queue_reconciliation"]["status"] == "cancelled"
    assert result["queue_reconciliation"]["terminal"]["terminal"] == "cancelled"
    assert all(
        payload.get("turnId") == "new-queued"
        for method, payload in calls
        if method in {"turn/cancel", "turn/unqueue"}
    )


@pytest.mark.parametrize(
    "change",
    [
        {"commandId": "foreign"},
        {"disposition": "steered"},
        {"startedNewTurn": True},
        {"turnId": ""},
        {"status": "noop"},
    ],
)
def test_unowned_acknowledgement_never_withdraws_another_turn(monkeypatch, change):
    result, calls, _, _ = execute(monkeypatch, acknowledgement=change)
    assert result["status"] == "unknown"
    assert not any(method in {"turn/unqueue", "turn/cancel"} for method, _ in calls)
    assert result["submission"]["state"] == "unresolved"


def test_lost_acknowledgement_retains_exact_command_without_retry(monkeypatch):
    result, calls, _, g = execute(monkeypatch, queue_case="lost-start")
    assert result["submission"]["command_id"] == g["turn_command_id"]
    assert result["submission"]["session_id"] == g["native_session_id"]
    assert result["submission"]["state"] == "unresolved"
    assert [method for method, _ in calls].count("turn/start") == 1


@pytest.mark.parametrize(
    "case", ["cancel-malformed", "cancel-terminal-wrong", "cancel-terminal-missing"]
)
def test_cancel_ack_or_wrong_terminal_never_proves_cancellation(monkeypatch, case):
    result, calls, _, _ = execute(monkeypatch, queue_case=case)
    assert result["queue_reconciliation"]["status"] == "unresolved"
    assert result["cancellation_outcome"] == "UNKNOWN"
    assert [method for method, _ in calls].count("turn/cancel") == 1


def test_valid_failed_terminal_stays_failed_not_cancelled(monkeypatch):
    result, _, _, _ = execute(monkeypatch, queue_case="cancel-failed")
    assert result["queue_reconciliation"]["status"] == "terminal"
    assert result["queue_reconciliation"]["terminal"]["terminal"] == "failed"
    assert result["cancellation_outcome"] == "UNKNOWN"


def test_interrupted_queue_reconciliation_still_closes_process(monkeypatch):
    closed = []
    original = n.MuseConnection.reconcile_queue

    def interruption(*_args):
        raise KeyboardInterrupt("synthetic queue cleanup interruption")

    # execute's synthetic RPC consumes the current owned method; instrument
    # launch's final process close without adding a native executable.
    monkeypatch.setattr(n.MuseConnection, "reconcile_queue", interruption)

    def trace(frame, event, arg):
        if (
            event == "call"
            and frame.f_code.co_name == "close"
            and frame.f_code.co_filename == __file__
        ):
            closed.append(True)
        return trace

    sys.settrace(trace)
    try:
        with pytest.raises(KeyboardInterrupt):
            execute(monkeypatch)
    finally:
        sys.settrace(None)
        monkeypatch.setattr(n.MuseConnection, "reconcile_queue", original)
    assert closed == [True]


@pytest.mark.parametrize(
    "case,expected",
    [("removed", "removed"), ("foreign", "unresolved"), ("missing", "unresolved")],
)
def test_real_synthetic_stdio_preserves_exact_queued_custody(
    monkeypatch, tmp_path, case, expected
):
    """Exercise owned descriptors and notification ordering, never Muse."""
    g = grant()
    g["workspace"] = str(tmp_path)
    g["max_wall_seconds"] = 1
    config = tmp_path / "wire-input.json"
    trace = tmp_path / "wire-requests.jsonl"
    event = unqueued(g)
    if case == "foreign":
        event["commandId"] = "foreign-command"
    config.write_text(
        json.dumps(
            {
                "initialize": initialized(),
                "resume": resumed(g["native_session_id"], str(tmp_path)),
                "event": event,
                "case": case,
            }
        )
    )
    program = tmp_path / "synthetic_wire.py"
    program.write_text("""import json,sys,time
from pathlib import Path
config=json.loads(Path(sys.argv[1]).read_text())
def send(data): print(json.dumps(data),flush=True)
for line in sys.stdin:
 frame=json.loads(line);method=frame.get("method");params=frame.get("params",{})
 with open(sys.argv[2],"a") as log:log.write(json.dumps(frame)+"\\n")
 if method=="initialized":continue
 if method=="initialize":reply=config["initialize"]
 elif method=="session/resume":reply=config["resume"]
 elif method=="turn/start":reply={"commandId":params["commandId"],"status":"accepted","disposition":"queued","startedNewTurn":False,"turnId":"new-queued"}
 elif method=="turn/unqueue":reply={"commandId":params["commandId"],"status":"accepted","turnId":"new-queued"}
 else:raise RuntimeError("unexpected native operation")
 send({"jsonrpc":"2.0","id":frame["id"],"result":reply})
 if method=="turn/unqueue":
  if config["case"]!="missing":send({"jsonrpc":"2.0","method":"turn/unqueued","params":config["event"]})
  time.sleep(2)
""")
    original = subprocess.Popen
    made = []

    def spawn(_argv, **kwargs):
        p = original(
            [sys.executable, "-I", "-B", str(program), str(config), str(trace)],
            **kwargs,
        )
        made.append(p)
        return p

    monkeypatch.setattr(n.subprocess, "Popen", spawn)
    monkeypatch.setattr(n, "binary_identity", lambda _: g["binary"])
    result = n.launch(
        g, "synthetic", send_admitted=lambda call: call(), cancelled=lambda: False
    )
    assert result["queue_reconciliation"]["status"] == expected
    assert result["status"] == "unknown" and not result["task_accepted"]
    requests = [json.loads(line) for line in trace.read_text().splitlines()]
    assert [frame["method"] for frame in requests] == [
        "initialize",
        "initialized",
        "session/resume",
        "turn/start",
        "turn/unqueue",
    ]
    assert requests[-1]["params"]["turnId"] == "new-queued"
    assert len(made) == 1 and made[0].returncode is not None
    with pytest.raises(ProcessLookupError):
        os.killpg(made[0].pid, 0)
    print(
        json.dumps(
            {
                "case": "queued-stdio-" + case,
                "pid": made[0].pid,
                "returncode": made[0].returncode,
                "group_absent": True,
            }
        )
    )
