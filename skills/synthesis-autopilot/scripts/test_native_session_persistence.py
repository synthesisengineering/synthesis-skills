"""Real worker/managed/receipt consumers; programmed native transport only."""

from pathlib import Path
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
import hashlib
import json
import pytest
import delegation_boundary as b
import managed_native as native
import native_protection as protection
from test_managed_permissions import (
    managed,
    register,
    reply,
    config_read,
    account_reply,
    Echo,
    successful_observation,
)
from test_native_callback import SID, hook, encode
from test_delegation_boundary import worker_world

__all__ = ["managed"]


@pytest.fixture
def chain(managed, monkeypatch):
    cfg, ctx, paths, spec = managed
    cfg["selected"] = {"model": "gpt-6-astra", "model_reasoning_effort": "xhigh"}
    state, ctx, runtime = worker_world((cfg["file_contract"], ctx, paths))
    state["owner"] = {k: ctx["binding"][k] for k in ("session_uuid", "native_ref")}
    state.update(contract_revision=1, profile_revision=1)
    flow = state["extensions"]["workflow"]
    flow["bindings"] = {
        k: state[k] for k in ("run_id", "contract_digest", "profile_digest")
    }
    flow["graph"] = {"nodes": {}}
    original = deepcopy(flow["children"].pop("worker"))
    root = Path(ctx["project"])
    inputs = root / "inputs"
    transcript = root / "native-session.jsonl"
    active_cfg = {}
    active_spec = {}
    specs = {}
    instances = []
    account = inputs / "account.json"
    now = datetime.now(timezone.utc)
    account.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "kind": "scoped-evaluation-account",
                "account_sha256": hashlib.sha256(b"approved").hexdigest(),
                "owner_native_ref": state["owner"]["native_ref"],
                "selection": {"model": "gpt-6-astra", "effort": "xhigh"},
                "issued_at": (now - timedelta(seconds=5)).isoformat(),
                "valid_until": (now + timedelta(seconds=90)).isoformat(),
            }
        )
    )
    account_ref = register(cfg["file_contract"], ctx, account, "account")
    source = inputs / "source.json"
    code = Path(b.__file__)
    rel = code.relative_to(code.parents[3]).as_posix()
    raw = code.read_bytes()
    sha = hashlib.sha256(raw).hexdigest()
    source_doc = {
        "status": "ROOT_ACCEPTED_FINAL_SOURCE",
        "accepted_commit": "a" * 40,
        "root": str(code.parents[3]),
        "files": [{"path": rel, "sha256": sha, "mode": 0o644}],
    }
    source.write_text(json.dumps(source_doc))
    source_ref = register(cfg["file_contract"], ctx, source, "source")
    entries = {
        rel: b"F\0"
        + rel.encode()
        + b"\0"
        + b"644\0"
        + str(len(raw)).encode()
        + b"\0"
        + bytes.fromhex(sha)
    }
    for p in Path(rel).parents:
        if str(p) != ".":
            entries[str(p)] = b"D\0" + str(p).encode() + b"\0"
    active = {
        "release_root": str(code.parents[3]),
        "commit": "a" * 40,
        "content_digest": hashlib.sha256(
            b"".join(entries[x] for x in sorted(entries))
        ).hexdigest(),
    }
    monkeypatch.setattr(
        b,
        "_session_runtime",
        lambda: SimpleNamespace(verified_release=lambda: active.copy()),
    )
    monkeypatch.setattr(b, "_authorize_worker", lambda *a: None)
    monkeypatch.setattr(
        b,
        "client_selection",
        lambda *a: (cfg["selected"], cfg["executable_identity"]["path"]),
    )
    monkeypatch.setattr(protection.socket, "create_connection", lambda *a, **k: Echo())

    class Connection:
        def __init__(self, *a, **kw):
            self.raw_stdout = bytearray()
            self.raw_stdin = bytearray()
            self.stderr = bytearray()
            self.next_id = 0
            self.calls = []
            self.closed = False
            instances.append(self)

        def send(self, row):
            self.raw_stdin.extend(encode([row]))
            if row.get("method") == "account/read":
                self.raw_stdout.extend(
                    encode([{"id": row["id"], "result": account_reply()}])
                )

        def call(self, method, params):
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
            response = reply(active_cfg)
            response["thread"].update(
                ephemeral=False, path=str(transcript), status={"type": "idle"}
            )
            if method == "initialize":
                value = {}
            elif method == "config/read":
                value = config_read(active_cfg)
            elif method == "thread/start":
                assert params["ephemeral"] is False
                transcript.write_text(
                    json.dumps({"type": "session_meta", "payload": {"id": SID}}) + "\n"
                )
                for status in ("running", "completed"):
                    self.raw_stdout.extend(
                        encode(
                            [
                                hook(
                                    status,
                                    context="SYNTHESIS_NATIVE_RECEIPT "
                                    + json.dumps(
                                        {"event_id": "synthetic", "sha256": "a" * 64}
                                    ),
                                )
                            ]
                        )
                    )
                value = response
            elif method == "thread/read":
                value = {"thread": response["thread"]}
            elif method == "thread/resume":
                assert params["threadId"] == SID
                value = response
            elif method == "command/exec":
                target = next(
                    x["path"]
                    for x in active_spec["filesystem"]["controls"]
                    if x["operation"] == "allowed-create"
                )
                Path(target).write_bytes(b"SYNTHESIS-STUDY-ALLOWED-WRITE\n")
                value = {
                    "exitCode": 0,
                    "stdout": json.dumps(successful_observation(active_spec)),
                    "stderr": "",
                }
            elif method == "turn/start":
                value = {"turn": {"id": "turn-" + str(len(instances))}}
                with transcript.open("ab") as f:
                    f.write(b'{"type":"event_msg","payload":{"type":"token_count"}}\n')
            else:
                raise AssertionError(method)
            self.raw_stdout.extend(encode([{"id": self.next_id, "result": value}]))
            if method == "turn/start":
                for status, event in [
                    ("inProgress", "turn/started"),
                    ("completed", "turn/completed"),
                ]:
                    self.raw_stdout.extend(
                        encode(
                            [
                                {
                                    "method": event,
                                    "params": {
                                        "threadId": SID,
                                        "turn": {
                                            "id": value["turn"]["id"],
                                            "status": status,
                                            "items": [],
                                        },
                                    },
                                }
                            ]
                        )
                    )
            return value

        def _read(self, *a):
            raise EOFError("Synthetic endpoint exhausted")

        def close(self):
            self.closed = True
            return {
                "group_absent": True,
                "leader_reaped": True,
                "terminated_pids": [],
                "unresolved_pids": [],
            }

    import native_callback

    original_callback = native_callback.MuseConnection
    original_connection = native.native_resume.MuseConnection
    patched_module = native.native_resume
    monkeypatch.setattr(patched_module, "MuseConnection", Connection)

    def add(ident, op, prior=None):
        c = deepcopy(cfg["file_contract"])
        profile = deepcopy(c["permissions"]["profile"])
        if op == "allocate":
            profile["probe"] = None
        if op == "resume":
            profile["probe"]["spec_artifact_id"] = ident + "-reference"
            sp = deepcopy(spec)
            sp["filesystem"]["profile_sha256"] = b.digest(profile)
            next(
                x
                for x in sp["filesystem"]["controls"]
                if x["operation"] == "allowed-create"
            )["path"] = str(root / "output" / ("created-" + ident))
            sf = inputs / (ident + "-spec.json")
            sf.write_text(json.dumps(sp))
            sr = register(c, ctx, sf, ident + "-spec")
            rf = inputs / (ident + "-reference.json")
            rf.write_text(json.dumps({"path": sr["path"], "sha256": sr["digest"]}))
            register(c, ctx, rf, ident + "-reference")
            specs[ident] = sp
        p = inputs / (ident + "-policy.json")
        p.write_text(json.dumps(profile))
        ref = register(c, ctx, p, ident + "-policy")
        c["permissions"] = {"source": ref, "profile": profile}
        request = {
            "schema_version": 1,
            "kind": "native-worker-session",
            "operation": op,
            "run_id": state["run_id"],
            "child_id": ident,
            "owner": state["owner"],
            "source": source_ref,
            "account_scope": account_ref,
            "predecessor_child_id": prior,
        }
        f = inputs / (ident + "-intent.json")
        f.write_text(json.dumps(request))
        c["native_session"] = register(c, ctx, f, ident + "-intent")
        child = {
            **deepcopy(original),
            "child_id": ident,
            "client": "codex",
            "file_contract": c,
            "required_capabilities": ["native-callback"]
            if op == "allocate"
            else ["read"],
            "reservation_id": ident + "-budget",
            "task_id": ident,
        }
        flow["children"][ident] = child
        flow["budget"]["reservations"][ident + "-budget"] = {
            **deepcopy(flow["budget"]["reservations"]["worker-budget"]),
            "id": ident + "-budget",
        }
        flow["graph"]["nodes"][ident] = {"id": ident, "status": "running"}
        return child

    def run(ident):
        child = flow["children"][ident]
        active_spec.clear()
        active_spec.update(specs.get(ident, spec))
        active_cfg.clear()
        active_cfg.update(
            cfg,
            file_contract=child["file_contract"],
            required_capabilities=child["required_capabilities"],
        )
        result = b.run_worker(
            state, ident, ctx, client="codex", runtime_root=runtime, timeout_seconds=20
        )
        assert result["terminal"] == "completed", json.loads(
            Path(result["receipt_path"]).read_text()
        )["failure"]
        assert b.verify_worker_observation(result, ctx)
        return result

    def record(ident, data):
        import workflow

        key = "receipt-" + ident
        bindings = {
            **{k: state[k] for k in ("run_id", "contract_digest", "profile_digest")},
            **{
                k: ctx["binding"].get(k)
                for k in (
                    "project_id",
                    "project_root",
                    "session_uuid",
                    "native_ref",
                    "claim_hash",
                    "repository",
                    "branch",
                )
            },
        }
        now = datetime.now(timezone.utc)
        observed = {
            "id": key,
            "kind": "native_worker",
            "bindings": bindings,
            "data": data,
            "observed_at": now.isoformat(),
            "expires_at": (now + timedelta(seconds=90)).isoformat(),
            "artifact_digests": {
                x["artifact_id"]: x["digest"]
                for x in flow["children"][ident]["file_contract"]["immutable_inputs"]
            },
        }
        observed["digest"] = b.digest(observed)
        state.setdefault("observations", {})[key] = deepcopy(observed)
        state.setdefault("evidence", {})[key] = {
            **{k: deepcopy(v) for k, v in observed.items() if k != "artifact_digests"},
            "artifact_id": "event:synthetic",
            "provenance": "engine-observation",
        }
        ctx.setdefault("evidence", {})[key] = deepcopy(state["evidence"][key])
        ctx["verify_receipt"] = (
            lambda identity, kind, bindings: kind == "native_worker"
            and identity in ctx["evidence"]
            and all(
                ctx["evidence"][identity]["bindings"].get(k) == v
                for k, v in bindings.items()
            )
            and b.verify_worker_observation(ctx["evidence"][identity]["data"], ctx)
        )
        ctx["now"] = datetime.now(timezone.utc).isoformat()
        new = workflow.worker_record(state, {"child_id": ident, "receipt_id": key}, ctx)
        state.clear()
        state.update(new)
        ctx["state"] = state
        flow.clear()
        flow.update(state["extensions"]["workflow"])
        state["extensions"]["workflow"] = flow
        return key

    yield SimpleNamespace(
        cfg=cfg,
        state=state,
        ctx=ctx,
        runtime=runtime,
        add=add,
        run=run,
        record=record,
        instances=instances,
        transcript=transcript,
        source=source,
        active=active,
    )

    # Other owner fixtures deliberately reload the module graph. Restore both
    # retained and currently published synthetic transport references.
    import sys

    native_callback.MuseConnection = original_callback
    patched_module.MuseConnection = original_connection
    if "native_resume" in sys.modules:
        sys.modules["native_resume"].MuseConnection = original_connection


def test_actual_three_connection_allocation_productive_cold_resume(chain):
    f = chain
    f.add("allocate", "allocate")
    first = f.run("allocate")
    f.record("allocate", first)
    assert (
        first["producer"] == "codex:" + SID and first["boundary"]["status"] == "UNKNOWN"
    )
    assert "turn/start" not in f.instances[0].calls
    import workflow

    allocated = workflow.child_return(
        f.state,
        {
            "child_id": "allocate",
            "disposition": "complete",
            "artifact_ids": [],
            "evidence_ids": ["receipt-allocate"],
            "reason": "Model-free allocation only, protection UNKNOWN",
        },
        f.ctx,
    )
    assert (
        allocated["extensions"]["workflow"]["children"]["allocate"][
            "worker_observation"
        ]["boundary"]["status"]
        == "UNKNOWN"
    )
    f.add("work", "resume", "allocate")
    work = f.run("work")
    f.record("work", work)
    assert (
        work["producer"] == first["producer"]
        and work["boundary"]["status"] == "ENFORCED"
    )
    assert f.instances[0].closed and f.instances[1].closed
    f.add("cold", "resume", "work")
    cold = f.run("cold")
    f.record("cold", cold)
    assert (
        cold["producer"] == work["producer"]
        and cold["boundary"]["status"] == "ENFORCED"
    )
    assert len(f.instances) == 3 and all(x.closed for x in f.instances)
    assert all(
        "thread/resume" in x.calls
        and x.calls.index("command/exec") < x.calls.index("turn/start")
        for x in f.instances[1:]
    )
    assert (
        cold["session_checkpoint"]["transcript"]["size"]
        > work["session_checkpoint"]["transcript"]["size"]
        > first["session_checkpoint"]["transcript"]["size"]
    )
    import workflow

    done = workflow.child_return(
        f.state,
        {
            "child_id": "cold",
            "disposition": "complete",
            "artifact_ids": [],
            "evidence_ids": ["receipt-cold"],
            "reason": "Synthetic real-owner three-connection proof only",
        },
        f.ctx,
    )
    assert (
        done["extensions"]["workflow"]["children"]["cold"]["disposition"] == "complete"
    )


@pytest.mark.parametrize(
    "fault",
    [
        "unrecorded",
        "foreign-session",
        "changed-prefix",
        "failed",
        "unknown-protection",
        "used-predecessor",
        "wrong-owner",
        "wrong-run",
        "changed-source",
        "foreign-account",
        "expired",
        "unregistered-intent",
        "cancelled",
        "incomplete",
    ],
)
def test_no_foreign_replay_or_stale_session_authority(chain, fault):
    f = chain
    f.add("allocate", "allocate")
    data = f.run("allocate")
    f.record("allocate", data)
    prior = "allocate"
    if fault == "unknown-protection":
        f.add("work", "resume", "allocate")
        data = f.run("work")
        f.record("work", data)
        prior = "work"
    child = f.add("resume", "resume", prior)
    if fault == "unrecorded":
        f.state["extensions"]["workflow"]["children"][prior].pop("worker_receipt_id")
    elif fault == "foreign-session":
        f.ctx["evidence"]["receipt-" + prior]["data"]["session_checkpoint"][
            "session_id"
        ] = "foreign"
    elif fault == "changed-prefix":
        f.transcript.write_text('{"type":"session_meta","payload":{"id":"foreign"}}\n')
    elif fault in ("failed", "unknown-protection"):
        row = f.ctx["evidence"]["receipt-" + prior]["data"]
        row["terminal"] = "failed" if fault == "failed" else row["terminal"]
        row["boundary"]["status"] = "UNKNOWN"
    elif fault == "used-predecessor":
        f.add("used", "resume", prior)
        (f.runtime / "used").mkdir()
    elif fault == "cancelled":
        f.state["extensions"]["workflow"]["children"][prior][
            "cancellation_requested"
        ] = True
    elif fault == "incomplete":
        f.state["extensions"]["workflow"]["children"][prior]["disposition"] = (
            "incomplete"
        )
    elif fault == "wrong-owner":
        f.state["owner"]["native_ref"] = "codex:foreign"
    elif fault == "wrong-run":
        f.state["run_id"] = "foreign"
    elif fault == "changed-source":
        f.source.write_text("{}")
    elif fault in ("foreign-account", "expired"):
        a = next(
            x
            for x in child["file_contract"]["immutable_inputs"]
            if x["artifact_id"] == "account"
        )
        p = Path(a["path"])
        p.write_text("{}")
    else:
        child["file_contract"]["immutable_inputs"].remove(
            child["file_contract"]["native_session"]
        )
    count = len(f.instances)
    with pytest.raises((ValueError, KeyError, TypeError)):
        b.run_worker(
            f.state,
            "resume",
            f.ctx,
            client="codex",
            runtime_root=f.runtime,
            timeout_seconds=20,
        )
    assert len(f.instances) == count


def test_ordinary_worker_has_no_persistent_intent(chain):
    f = chain
    child = f.add("ordinary", "allocate")
    child["file_contract"].pop("native_session")
    assert b.native_session_binding(f.state, child, f.ctx) is None
    requests = native.requests(
        {
            **f.cfg,
            "file_contract": child["file_contract"],
            "required_capabilities": ["native-callback"],
        }
    )
    assert (
        next(row for row in requests if row.get("method") == "thread/start")["params"][
            "ephemeral"
        ]
        is True
    )


def test_allocated_reader_ignores_only_access_time(chain, monkeypatch):
    f = chain
    f.add("allocate", "allocate")
    data = f.run("allocate")
    import os

    original = os.fstat
    count = 0

    def read(fd):
        nonlocal count
        value = original(fd)
        if value.st_ino == f.transcript.stat().st_ino:
            count += 1

            class Changed:
                def __getattr__(self, name):
                    return (
                        value.st_atime + count
                        if name == "st_atime"
                        else getattr(value, name)
                    )

            return Changed()
        return value

    monkeypatch.setattr(os, "fstat", read)
    assert b.verify_worker_observation(data, f.ctx)
