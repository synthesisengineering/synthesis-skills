"""Real managed connection owner with a synthetic, closed native transport."""

from copy import deepcopy
import json
from pathlib import Path
import pytest
import managed_native as native
import managed_permissions as policy
from test_managed_permissions import (
    managed,
    synthetic_connection,
    reply,
)

__all__ = ["managed", "synthetic_connection"]
from test_native_callback import SID, encode


@pytest.mark.parametrize(
    "fault",
    [
        None,
        "probe-failed",
        "probe-missing",
        "profile",
        "busy",
        "wrong-session",
        "claim",
        "truncated",
        "foreign-terminal",
        "duplicate-terminal",
        "interrupt",
    ],
)
def test_productive_turn_follows_current_probe_and_exact_owner(
    managed, synthetic_connection, monkeypatch, fault
):
    cfg, _, _, _ = managed
    cfg["required_capabilities"] = ["read"]
    parent = native.native_resume.MuseConnection

    class Connection(parent):
        def call(self, method, params):
            if method not in ("thread/read", "turn/start"):
                result = super().call(method, params)
                if method == "command/exec" and fault in (
                    "probe-failed",
                    "probe-missing",
                ):
                    result["exitCode"] = 2 if fault == "probe-failed" else 0
                    result["stdout"] = "{}"
                    lines = self.raw_stdout.splitlines()
                    lines[-1] = json.dumps(
                        {"id": self.next_id, "result": result}
                    ).encode()
                    self.raw_stdout = bytearray(b"\n".join(lines) + b"\n")
                if method == "config/read" and self.next_id > 5 and fault == "profile":
                    result["config"]["permissions"]["synthesis-control"]["network"][
                        "enabled"
                    ] = True
                    lines = self.raw_stdout.splitlines()
                    lines[-1] = json.dumps(
                        {"id": self.next_id, "result": result}
                    ).encode()
                    self.raw_stdout = bytearray(b"\n".join(lines) + b"\n")
                return result
            self.next_id += 1
            self.calls.append(method)
            self.send(
                {
                    "jsonrpc": "2.0",
                    "id": self.next_id,
                    "method": method,
                    "params": params,
                }
            )
            if method == "thread/read":
                value = {"thread": reply(cfg)["thread"]}
                value["thread"]["status"] = {
                    "type": "active" if fault == "busy" else "idle"
                }
                if fault == "wrong-session":
                    value["thread"]["id"] = "foreign"
            else:
                if fault == "interrupt":
                    raise KeyboardInterrupt()
                value = {"turn": {"id": "productive-turn"}}
                if fault != "truncated":
                    done = {
                        "method": "turn/completed",
                        "params": {
                            "threadId": SID,
                            "turn": {
                                "id": "foreign"
                                if fault == "foreign-terminal"
                                else "productive-turn",
                                "status": "completed",
                                "items": [],
                            },
                        },
                    }
                    self.raw_stdout.extend(
                        encode(
                            [
                                {
                                    "method": "turn/started",
                                    "params": {
                                        "threadId": SID,
                                        "turn": {
                                            "id": "productive-turn",
                                            "status": "inProgress",
                                            "items": [],
                                        },
                                    },
                                }
                            ]
                            + [done] * (2 if fault == "duplicate-terminal" else 1)
                        )
                    )
            self.raw_stdout.extend(encode([{"id": self.next_id, "result": value}]))
            return value

    monkeypatch.setattr(native.native_resume, "MuseConnection", Connection)
    checks = []

    def revalidate():
        checks.append(True)
        if (
            fault == "claim"
            and synthetic_connection
            and "command/exec" in synthetic_connection[0].calls
        ):
            raise ValueError("Synthetic current admission expired after probe")

    argv = policy.server_argv(cfg["executable_identity"]["path"], cfg["file_contract"])
    code, raw, err, failure, cleanup, sent = native.execute(
        argv,
        cfg,
        Path(cfg["file_contract"]["scratch_root"]),
        5,
        {},
        revalidate=revalidate,
    )
    calls = synthetic_connection[0].calls
    assert cleanup["cleanup_verified"] and synthetic_connection[0].closed
    if fault is None:
        assert code == 0, failure
        assert calls == [
            "initialize",
            "config/read",
            "thread/start",
            "config/read",
            "command/exec",
            "config/read",
            "thread/read",
            "turn/start",
        ]
        parsed = native.parse(raw, cfg, sent)
        verdict = native.boundary(cfg, [json.loads(line) for line in raw.splitlines()])
        assert parsed["protection"] == verdict and verdict["status"] == "ENFORCED"
        assert (
            verdict["protocol"] == native.STUDY_PROTOCOL
            and verdict["turn_id"] == "productive-turn"
        )
        assert verdict["thread_id"] == SID and len(checks) >= 5
    else:
        assert code == 2 and failure
        if fault in {
            "probe-failed",
            "probe-missing",
            "profile",
            "busy",
            "wrong-session",
            "claim",
        }:
            assert "turn/start" not in calls


def test_productive_managed_plan_refuses_absent_probe(managed):
    cfg, _, _, _ = managed
    cfg["required_capabilities"] = ["read"]
    cfg["file_contract"]["permissions"]["profile"]["probe"] = None
    with pytest.raises(ValueError):
        native.requests(cfg)


def work_stream():
    from test_native_callback import hook

    start = {
        "method": "turn/started",
        "params": {
            "threadId": SID,
            "turn": {"id": "current-turn", "status": "inProgress", "items": []},
        },
    }
    item = {
        "id": "command-1",
        "type": "commandExecution",
        "command": "printf synthetic",
        "cwd": "/synthetic",
        "commandActions": [],
        "status": "inProgress",
    }
    values = [
        start,
        {
            "method": "item/started",
            "params": {
                "threadId": SID,
                "turnId": "current-turn",
                "item": item,
                "startedAtMs": 1,
            },
        },
        {
            "method": "item/commandExecution/outputDelta",
            "params": {
                "threadId": SID,
                "turnId": "current-turn",
                "itemId": "command-1",
                "delta": "synthetic output",
            },
        },
        {
            "method": "item/completed",
            "params": {
                "threadId": SID,
                "turnId": "current-turn",
                "item": {
                    **item,
                    "status": "completed",
                    "exitCode": 0,
                    "aggregatedOutput": "synthetic output",
                },
                "completedAtMs": 2,
            },
        },
    ]
    for status in ("running", "completed"):
        row = hook(status, context="Synthetic tool hook")
        row["params"]["turnId"] = "current-turn"
        row["params"]["run"].update(
            id="tool-hook", eventName="postToolUse", scope="turn"
        )
        values.append(row)
    values.append(
        {
            "method": "turn/completed",
            "params": {
                "threadId": SID,
                "turn": {"id": "current-turn", "status": "completed", "items": []},
            },
        }
    )
    return values


@pytest.mark.parametrize(
    "fault",
    [
        None,
        "missing-start",
        "missing-item-start",
        "duplicate-item",
        "missing-item-end",
        "foreign-thread",
        "foreign-turn",
        "wrong-type",
        "unknown-field",
        "unknown-method",
        "unpaired-hook",
        "failed-hook",
        "hook-identity",
        "partial-items",
        "late-item",
        "bool-integer",
    ],
)
def test_current_typed_native_turn_grammar_and_coverage(fault):
    from native_codex_turn import transcript
    from native_callback import CallbackIncomplete
    import native_codex

    rows = work_stream()
    if fault == "missing-start":
        rows.pop(0)
    if fault == "missing-item-start":
        rows.pop(1)
    if fault == "duplicate-item":
        rows.insert(2, deepcopy(rows[1]))
    if fault == "missing-item-end":
        rows.pop(3)
    if fault == "foreign-thread":
        rows[2]["params"]["threadId"] = "foreign"
    if fault == "foreign-turn":
        rows[2]["params"]["turnId"] = "foreign"
    if fault == "wrong-type":
        rows[1]["params"]["item"]["command"] = []
    if fault == "unknown-field":
        rows[2]["params"]["invented"] = True
    if fault == "unknown-method":
        rows[2]["method"] = "process/exited"
    if fault == "unpaired-hook":
        rows.pop(5)
    if fault == "failed-hook":
        rows[5]["params"]["run"]["status"] = "blocked"
    if fault == "hook-identity":
        rows[5]["params"]["run"]["sourcePath"] = "/foreign"
    if fault == "partial-items":
        rows[-1]["params"]["turn"]["itemsView"] = "notLoaded"
    if fault == "late-item":
        rows.append(deepcopy(rows[1]))
    if fault == "bool-integer":
        rows[1]["params"]["startedAtMs"] = True
    if fault:
        with pytest.raises((ValueError, CallbackIncomplete)):
            transcript(rows, SID, "current-turn")
    else:
        assert transcript(rows, SID, "current-turn")["status"] == "completed"
        binding = {
            "producer": {"client": "codex", "thread_id": SID, "root_session_id": SID},
            "mode": "native",
            "dialect": "codex.app_server_managed_turn",
        }
        facts = [f for row in rows for f in native_codex.decode_wire(row, binding)]
        assert [x["kind"] for x in facts].count("lifecycle.completed") == 1
        assert [x["kind"] for x in facts].count("runtime.hook") == 2
        assert all(x["data"].get("portable_completion") is False for x in facts)


@pytest.fixture
def completed_productive(managed, synthetic_connection, monkeypatch):
    cfg, _, _, _ = managed
    cfg["required_capabilities"] = ["read"]
    parent = native.native_resume.MuseConnection

    class Connection(parent):
        def call(self, method, params):
            if method not in ("thread/read", "turn/start"):
                return super().call(method, params)
            self.next_id += 1
            self.calls.append(method)
            self.send(
                {
                    "jsonrpc": "2.0",
                    "id": self.next_id,
                    "method": method,
                    "params": params,
                }
            )
            if method == "thread/read":
                value = {"thread": {**reply(cfg)["thread"], "status": {"type": "idle"}}}
            else:
                value = {"turn": {"id": "current-turn"}}
            self.raw_stdout.extend(encode([{"id": self.next_id, "result": value}]))
            if method == "turn/start":
                self.raw_stdout.extend(encode(work_stream()))
            return value

    monkeypatch.setattr(native.native_resume, "MuseConnection", Connection)
    argv = policy.server_argv(cfg["executable_identity"]["path"], cfg["file_contract"])
    code, raw, _, failure, cleanup, sent = native.execute(
        argv,
        cfg,
        Path(cfg["file_contract"]["scratch_root"]),
        5,
        {},
        revalidate=lambda: None,
    )
    assert code == 0 and failure is None and cleanup["cleanup_verified"], failure
    return cfg, raw, sent


@pytest.mark.parametrize(
    "fault",
    [
        None,
        "copied-connection",
        "request-digest",
        "profile-digest",
        "thread",
        "turn",
        "host-after",
        "probe-exit",
        "probe-body",
        "deleted-frame",
        "new-item",
        "reordered-readback",
        "wrong-request",
        "configuration-only",
    ],
)
def test_actual_owner_replay_rejects_forged_or_incomplete_protection(
    completed_productive, fault
):
    cfg, raw, sent = completed_productive
    cfg = deepcopy(cfg)
    rows = [json.loads(x) for x in raw.splitlines()]
    requests = [json.loads(x) for x in sent.splitlines()]
    obs = cfg["protection_observation"]
    if fault == "copied-connection":
        obs["transport"]["connection_id"] = "b" * 32
    if fault == "request-digest":
        obs["transport"]["probe_request_digest"] = "b" * 64
    if fault == "profile-digest":
        obs["profile_digest"] = "b" * 64
    if fault == "thread":
        obs["thread_id"] = "foreign"
    if fault == "turn":
        obs["transport"]["turn_id"] = "foreign"
    if fault == "host-after":
        obs["productive_after"] = {}
    if fault in ("probe-exit", "probe-body"):
        probe = next(x for x in rows if x.get("id") == 5)
        if fault == "probe-exit":
            probe["result"]["exitCode"] = 1
        else:
            probe["result"]["stdout"] = "{}"
    if fault == "deleted-frame":
        rows = [x for x in rows if x.get("method") != "item/completed"]
    if fault == "new-item":
        rows.insert(
            -1, deepcopy(next(x for x in rows if x.get("method") == "item/started"))
        )
    if fault == "reordered-readback":
        a = next(i for i, x in enumerate(rows) if x.get("id") == 6)
        rows[a], rows[a + 1] = rows[a + 1], rows[a]
    if fault == "wrong-request":
        requests[-1]["params"]["permissions"] = "foreign"
    if fault == "configuration-only":
        cfg.pop("protection_observation")
    if fault:
        with pytest.raises((ValueError, KeyError)):
            native.parse(encode(rows), cfg, encode(requests))
        if fault != "wrong-request":
            assert native.boundary(cfg, rows)["status"] == "UNKNOWN"
    else:
        result = native.parse(raw, cfg, sent)
        assert result["terminal"] == "completed"
        assert result["protection"] == native.boundary(cfg, rows)
        assert result["protection"]["status"] == "ENFORCED"


@pytest.mark.parametrize("fault", ["source", "claim", "account"])
def test_effect_guard_rechecks_at_actual_outbound_write(
    managed, synthetic_connection, monkeypatch, fault
):
    cfg, _, _, _ = managed
    cfg["required_capabilities"] = ["read"]
    parent = native.native_resume.MuseConnection
    written = []
    revoked = []

    class Connection(parent):
        def call(self, method, params):
            if method not in ("thread/read", "turn/start"):
                return super().call(method, params)
            self.next_id += 1
            self.calls.append(method)
            if method == "turn/start":
                if fault == "source":
                    Path(
                        cfg["file_contract"]["immutable_inputs"][0]["path"]
                    ).write_text("{}")
                else:
                    revoked.append(True)
            self.send(
                {
                    "jsonrpc": "2.0",
                    "id": self.next_id,
                    "method": method,
                    "params": params,
                }
            )
            if method == "turn/start":
                written.append(True)
                raise TimeoutError("Synthetic response unavailable")
            result = {"thread": {**reply(cfg)["thread"], "status": {"type": "idle"}}}
            self.raw_stdout.extend(encode([{"id": self.next_id, "result": result}]))
            return result

    monkeypatch.setattr(native.native_resume, "MuseConnection", Connection)

    def revalidate():
        if revoked:
            raise ValueError("Synthetic " + fault + " authority changed")

    argv = policy.server_argv(cfg["executable_identity"]["path"], cfg["file_contract"])
    code, _, _, failure, cleanup, _ = native.execute(
        argv,
        cfg,
        Path(cfg["file_contract"]["scratch_root"]),
        5,
        {},
        revalidate=revalidate,
    )
    assert code == 2 and failure and cleanup["cleanup_verified"]
    assert not written, (
        "Changed source/authority crossed the actual transport write boundary"
    )


@pytest.mark.parametrize("fault", ["terminal-error", "numeric-method", "object-method"])
def test_malformed_turn_observation_is_a_typed_refusal(fault):
    from native_codex_turn import transcript
    import native_codex

    rows = work_stream()
    if fault == "terminal-error":
        rows[-1]["params"]["turn"]["error"] = {
            "message": "Synthetic contradictory native error",
            "codexErrorInfo": None,
            "additionalDetails": None,
        }
    elif fault == "numeric-method":
        rows[2]["method"] = 42
    else:
        rows[2]["method"] = {"untrusted": "method"}
    with pytest.raises(ValueError):
        transcript(rows, SID, "current-turn")
    if fault != "terminal-error":
        binding = {
            "producer": {"client": "codex", "thread_id": SID, "root_session_id": SID},
            "mode": "native",
            "dialect": "codex.app_server_managed_turn",
        }
        with pytest.raises(ValueError):
            native_codex.decode_wire(rows[2], binding)


def test_current_codex_generation_includes_exact_typed_helper(monkeypatch):
    import hashlib
    import native_codex
    import native_codex_turn

    before = native_codex.adapter_digest()
    original = Path.read_bytes
    helper = Path(native_codex_turn.__file__)

    def changed(path):
        value = original(path)
        return value + b"\n# changed grammar generation\n" if path == helper else value

    monkeypatch.setattr(Path, "read_bytes", changed)
    assert native_codex.adapter_digest() != before
    assert (
        hashlib.sha256(original(helper)).hexdigest()
        != hashlib.sha256(changed(helper)).hexdigest()
    )


def test_managed_turn_source_pages_and_exact_current_bytes(
    completed_productive, tmp_path
):
    import native_observations as owner
    from test_native_observations import drain

    cfg, raw, sent = completed_productive
    path = tmp_path / "managed-turn.jsonl"
    path.write_bytes(raw)
    binding, cursor = owner.enroll_source(
        path,
        client="codex",
        expected_root_session_id=SID,
        expected_thread_id=SID,
        dialect="codex.app_server_managed_turn",
    )
    events, projection, batches = drain(binding, cursor, owner.Limits(page_bytes=256))
    assert len(batches) > 1 and not projection["gaps"] and not projection["diagnostics"]
    assert batches[-1]["cursor"]["trusted_through"] == len(raw)
    assert (
        owner.revalidate_observations(binding, events, required_interval=(0, len(raw)))[
            "status"
        ]
        == "current"
    )
    assert (
        sum(
            e["kind"] == "lifecycle.completed"
            and e["data"].get("turn_id") == "current-turn"
            for e in events
        )
        == 1
    )
    # First occurrence is the unselected RPC acknowledgement: the full managed
    # consumer, not selected-event revalidation, owns that cross-frame join.
    changed_reply = raw.replace(b"current-turn", b"changed-turn", 1)
    with pytest.raises(ValueError):
        native.parse(changed_reply, cfg, sent)
    terminal = next(e for e in events if e["kind"] == "lifecycle.completed")
    start = terminal["native"]["offset"]
    length = terminal["native"]["length"]
    selected = raw[start : start + length]
    altered = selected.replace(b"current-turn", b"changed-turn", 1)
    assert altered != selected and len(altered) == len(selected)
    path.write_bytes(raw[:start] + altered + raw[start + length :])
    assert owner.revalidate_observations(binding, events)["status"] == "invalid"
