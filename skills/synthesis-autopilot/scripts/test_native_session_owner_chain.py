"""Real PM/journal/dispatch/return/integration; only native observations synthetic."""

from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
import hashlib
import json
import pytest
from test_run_state import world, command, create
from test_workflow import dimensions, _owner_register
from test_managed_permissions import (
    managed,
    reply,
    config_read,
    account_reply,
    Echo,
    successful_observation,
)
from test_native_callback import SID, hook, encode
from test_evidence_bridge import append_claude_tool

__all__ = ["world"]


@pytest.fixture
def complete_chain(world, monkeypatch, request):
    import autopilot
    import workflow
    import delegation_boundary as boundary
    import managed_native as native
    import native_callback
    import native_protection as protection

    runtime = autopilot.engine()
    workflow.register_preparers(runtime.register_preparer)
    state = create(runtime, world)
    for kind, payload in [
        ("native.enroll", {"source_handle": "root", "mode": "native"}),
        ("workflow.configure", {"dimensions": dimensions(parallelizable=False)}),
        (
            "workflow.graph",
            {
                "nodes": [
                    {
                        "id": "allocate",
                        "deps": [],
                        "criteria": ["accept"],
                        "estimate": 1,
                    },
                    {
                        "id": "work",
                        "deps": ["allocate"],
                        "criteria": ["accept"],
                        "estimate": 1,
                    },
                    {
                        "id": "cold",
                        "deps": ["work"],
                        "criteria": ["accept"],
                        "estimate": 1,
                    },
                    {
                        "id": "replay",
                        "deps": ["work"],
                        "criteria": ["accept"],
                        "estimate": 1,
                    },
                ],
                "wip_limit": 1,
            },
        ),
        (
            "workflow.budget",
            {
                "limits": {"wall_millis": {"limit": 240000, "enforcement": "hard"}},
                "deadline": (
                    datetime.now(timezone.utc) + timedelta(minutes=5)
                ).isoformat(),
            },
        ),
    ]:
        state = command(runtime, world, state, kind, payload)
    for ident in ["allocate", "work", "cold", "replay"]:
        for suffix, category, amount in [
            ("work", "work", 20000),
            ("integrate", "integration", 10000),
            ("verify", "verification", 10000),
            ("recover", "recovery", 10000),
        ]:
            state = command(
                runtime,
                world,
                state,
                "workflow.reserve",
                {
                    "reservation_id": ident + "-" + suffix,
                    "amounts": {"wall_millis": amount},
                    "category": category,
                },
            )
    delegated = world["project"] / "delegated"
    delegated.mkdir()
    configuration, _, _, original_spec = managed.__wrapped__(delegated)
    selection = getattr(request, "param", {}).get(
        "selected", {"model": "gpt-6-astra", "model_reasoning_effort": "xhigh"}
    )
    configuration["selected"] = selection
    declared = getattr(request, "param", {}).get(
        "declared",
        {"model": selection["model"], "effort": selection["model_reasoning_effort"]},
    )
    base = configuration["file_contract"]
    inputs = Path(base["immutable_inputs"][0]["path"]).parent
    transcript = delegated / "native-session.jsonl"
    cfg = {}
    spec = {}
    instances = []

    def registered(path, ident, value=None, role="input"):
        nonlocal state
        if value is not None:
            path.write_text(json.dumps(value))
        state = command(
            runtime,
            world,
            state,
            "artifact.register",
            {
                "id": ident,
                "path": str(path),
                "role": role,
                "required": False,
                "retention": "durable",
            },
        )
        return {
            "artifact_id": ident,
            "path": str(path),
            "digest": hashlib.sha256(path.read_bytes()).hexdigest(),
        }

    for row in base["immutable_inputs"]:
        registered(Path(row["path"]), row["artifact_id"])
    now = datetime.now(timezone.utc)
    account = registered(
        inputs / "account.json",
        "account",
        {
            "schema_version": 1,
            "kind": "scoped-evaluation-account",
            "account_sha256": hashlib.sha256(b"approved").hexdigest(),
            "owner_native_ref": state["owner"]["native_ref"],
            "selection": declared,
            "issued_at": (now - timedelta(seconds=5)).isoformat(),
            "valid_until": (now + timedelta(minutes=4)).isoformat(),
        },
    )
    code = Path(boundary.__file__)
    root = code.parents[3]
    rel = code.relative_to(root).as_posix()
    raw = code.read_bytes()
    sha = hashlib.sha256(raw).hexdigest()
    source = registered(
        inputs / "source.json",
        "source",
        {
            "status": "ROOT_ACCEPTED_FINAL_SOURCE",
            "accepted_commit": "a" * 40,
            "root": str(root),
            "files": [{"path": rel, "sha256": sha, "mode": 0o644}],
        },
    )
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
    activated = {
        "release_root": str(root),
        "commit": "a" * 40,
        "content_digest": hashlib.sha256(
            b"".join(entries[k] for k in sorted(entries))
        ).hexdigest(),
    }
    monkeypatch.setattr(
        boundary,
        "_session_runtime",
        lambda: SimpleNamespace(verified_release=lambda: deepcopy(activated)),
    )
    monkeypatch.setattr(
        boundary,
        "client_selection",
        lambda *a: (
            deepcopy(configuration["selected"]),
            configuration["executable_identity"]["path"],
        ),
    )
    monkeypatch.setattr(protection.socket, "create_connection", lambda *a, **kw: Echo())

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
            response = reply(cfg)
            response["thread"].update(
                ephemeral=False, path=str(transcript), status={"type": "idle"}
            )
            if method == "initialize":
                value = {}
            elif method == "config/read":
                value = config_read(cfg)
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
                    for x in spec["filesystem"]["controls"]
                    if x["operation"] == "allowed-create"
                )
                Path(target).write_bytes(b"SYNTHESIS-STUDY-ALLOWED-WRITE\n")
                value = {
                    "exitCode": 0,
                    "stdout": json.dumps(successful_observation(spec)),
                    "stderr": "",
                }
            elif method == "turn/start":
                value = {"turn": {"id": "turn-" + str(len(instances))}}
                with transcript.open("ab") as stream:
                    stream.write(
                        b'{"type":"event_msg","payload":{"type":"token_count"}}\n'
                    )
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

    original_connection = native.native_resume.MuseConnection
    original_callback = native_callback.MuseConnection
    monkeypatch.setattr(native.native_resume, "MuseConnection", Connection)
    specs = {}

    def dispatch(ident, operation, prior=None):
        nonlocal state
        contract = deepcopy(base)
        contract["immutable_inputs"] += [account, source]
        profile = deepcopy(contract["permissions"]["profile"])
        if operation == "allocate":
            profile["probe"] = None
        else:
            profile["probe"]["spec_artifact_id"] = ident + "-reference"
            item = deepcopy(original_spec)
            item["filesystem"]["profile_sha256"] = boundary.digest(profile)
            next(
                x
                for x in item["filesystem"]["controls"]
                if x["operation"] == "allowed-create"
            )["path"] = str(Path(contract["output_roots"][0]) / ("created-" + ident))
            sp = registered(inputs / (ident + "-spec.json"), ident + "-spec", item)
            ref = registered(
                inputs / (ident + "-reference.json"),
                ident + "-reference",
                {"path": sp["path"], "sha256": sp["digest"]},
            )
            contract["immutable_inputs"] += [sp, ref]
            specs[ident] = item
        p = registered(inputs / (ident + "-policy.json"), ident + "-policy", profile)
        contract["immutable_inputs"].append(p)
        contract["permissions"] = {"source": p, "profile": profile}
        intent = registered(
            inputs / (ident + "-intent.json"),
            ident + "-intent",
            {
                "schema_version": 1,
                "kind": "native-worker-session",
                "operation": operation,
                "run_id": state["run_id"],
                "child_id": ident,
                "owner": {k: state["owner"][k] for k in ("session_uuid", "native_ref")},
                "source": source,
                "account_scope": account,
                "predecessor_child_id": prior,
            },
        )
        contract["immutable_inputs"].append(intent)
        contract["native_session"] = intent
        state = command(
            runtime,
            world,
            state,
            "workflow.dispatch",
            {
                "child_id": ident,
                "task_id": ident,
                "deliverables": ["Verify one synthetic persistent owner stage"],
                "paths": [str(delegated)],
                "criteria": ["accept"],
                "reservation_id": ident + "-work",
                "integration_reservation_id": ident + "-integrate",
                "verification_reservation_id": ident + "-verify",
                "recovery_reservation_id": ident + "-recover",
                "integration_owner": state["owner"]["session_uuid"],
                "return_contract": ["artifact_ids", "evidence_ids", "disposition"],
                "cancellation": "Retain cancelled or uncertain native evidence",
                "mode": "native-cli",
                "client": "codex",
                "required_capabilities": ["native-callback"]
                if operation == "allocate"
                else ["read"],
                "file_contract": contract,
                "admission_id": "parent",
                "admission_requests": [
                    {"id": "parent", "actor": world["actor"], "paths": [str(delegated)]}
                ],
            },
        )
        return deepcopy(state)

    def observe(ident):
        nonlocal state
        child = state["extensions"]["workflow"]["children"][ident]
        cfg.clear()
        cfg.update(
            configuration,
            file_contract=child["file_contract"],
            required_capabilities=child["required_capabilities"],
        )
        spec.clear()
        spec.update(specs.get(ident, original_spec))
        state = _owner_register(
            runtime,
            world,
            state,
            "check-" + ident,
            {
                "schema_version": 1,
                "kind": "native_worker",
                "arguments": {"child_id": ident, "timeout_seconds": 20},
            },
        )
        state = runtime.observe(
            world["project"],
            state["run_id"],
            "native_worker",
            {"check_id": "check-" + ident},
            expected_revision=state["revision"],
            command_id="observed-" + ident,
            actor=world["actor"],
            runtime_root=world["runtime"],
        )
        assert runtime.load_run(world["project"], state["run_id"]) == state
        state = command(
            runtime,
            world,
            state,
            "workflow.worker_record",
            {"child_id": ident, "receipt_id": "observed-" + ident},
        )
        data = state["extensions"]["workflow"]["children"][ident]["worker_observation"]
        assert data["terminal"] == "completed", data
        return deepcopy(data)

    def finish(ident):
        nonlocal state
        state = command(
            runtime,
            world,
            state,
            "workflow.return",
            {
                "child_id": ident,
                "disposition": "complete",
                "artifact_ids": [],
                "evidence_ids": ["observed-" + ident],
                "reason": "Synthetic source control, not native acceptance",
            },
        )
        child = state["extensions"]["workflow"]["children"][ident]
        data = child["worker_observation"]
        audit = {
            "child_id": ident,
            "task_id": ident,
            "accepted": True,
            "criteria": ["accept"],
            "artifact_ids": [],
            "artifact_digests": {},
            "reviewer": "claude-agent:review-" + ident,
            "producer": data["producer"],
            "integration_owner": state["owner"]["session_uuid"],
            "actual": {"wall_millis": data["elapsed_millis"]},
        }
        bindings = {
            k: state[k] for k in ("run_id", "contract_digest", "profile_digest")
        }
        request = {
            "schema_version": 1,
            "kind": "child_integration",
            "bindings": bindings,
            "artifact_digests": {"source": source["digest"]},
            "producer": data["producer"],
        }
        response = {
            "schema_version": 1,
            "kind": "child_integration",
            "bindings": bindings,
            "data": audit,
        }
        append_claude_tool(
            world,
            "Agent",
            {"prompt": json.dumps({"autopilot_review": request})},
            {"autopilot_review": response},
            "review-" + ident,
        )
        stamp = datetime.now(timezone.utc)
        receipt = {
            "kind": "child_integration",
            "observed_at": stamp.isoformat(),
            "expires_at": (stamp + timedelta(minutes=2)).isoformat(),
            "bindings": {
                **runtime.inspect_context(
                    state, world["actor"], project=world["project"]
                )["binding"],
                **bindings,
            },
            "data": {
                **audit,
                "source": {"kind": "native-agent", "call_id": "review-" + ident},
            },
        }
        registered(
            inputs / ("review-" + ident + ".json"),
            "review-" + ident,
            receipt,
            role="evidence",
        )
        state = command(
            runtime,
            world,
            state,
            "evidence.record",
            {
                "id": "review-" + ident,
                "kind": "child_integration",
                "artifact_id": "review-" + ident,
            },
        )
        state = command(
            runtime,
            world,
            state,
            "workflow.integrate",
            {"child_id": ident, "receipt_id": "review-" + ident},
        )
        assert (
            state["extensions"]["workflow"]["children"][ident]["audit_status"]
            == "accepted"
        )
        assert (
            state["extensions"]["workflow"]["graph"]["nodes"][ident]["status"] == "done"
        )
        return deepcopy(state)

    def cancel(ident):
        nonlocal state
        state = command(
            runtime,
            world,
            state,
            "workflow.cancel_child",
            {"child_id": ident, "reason": "Synthetic cancellation must remain binding"},
        )

    yield SimpleNamespace(
        dispatch=dispatch,
        observe=observe,
        finish=finish,
        cancel=cancel,
        instances=instances,
        transcript=transcript,
        state=lambda: deepcopy(state),
        runtime=runtime,
        world=world,
    )
    native.native_resume.MuseConnection = original_connection
    native_callback.MuseConnection = original_callback


def test_complete_registered_allocation_productive_and_cold_owner_chain(complete_chain):
    f = complete_chain
    f.dispatch("allocate", "allocate")
    a = f.observe("allocate")
    allocated = f.finish("allocate")
    assert (
        a["boundary"]["status"] == "UNKNOWN"
        and "turn/start" not in f.instances[0].calls
    )
    assert (
        allocated["extensions"]["workflow"]["children"]["allocate"]["write_enforcement"]
        == "UNKNOWN"
    )
    f.dispatch("work", "resume", "allocate")
    b = f.observe("work")
    f.finish("work")
    assert b["boundary"]["status"] == "ENFORCED"
    assert f.instances[0].closed and f.instances[1].closed
    f.dispatch("cold", "resume", "work")
    c = f.observe("cold")
    final = f.finish("cold")
    assert a["producer"] == b["producer"] == c["producer"] == "codex:" + SID
    assert all(x.closed for x in f.instances) and len(f.instances) == 3
    assert all(
        x.calls.index("command/exec") < x.calls.index("turn/start")
        for x in f.instances[1:]
    )
    assert (
        c["session_checkpoint"]["transcript"]["size"]
        > b["session_checkpoint"]["transcript"]["size"]
        > a["session_checkpoint"]["transcript"]["size"]
    )
    for key in ("allocate", "work", "cold"):
        child = final["extensions"]["workflow"]["children"][key]
        assert (
            child["disposition"] == "complete" and child["audit_status"] == "accepted"
        )
        assert (
            final["observations"]["observed-" + key]["data"]["producer"]
            == a["producer"]
        )
        assert child["worker_observation"]["usage"] == {
            "tokens": None,
            "usd_micros": None,
        }
    assert f.runtime.load_run(f.world["project"], final["run_id"]) == final


@pytest.mark.parametrize("fault", ["cancelled", "consumed"])
def test_real_owner_refuses_cancelled_or_consumed_predecessor(complete_chain, fault):
    f = complete_chain
    f.dispatch("allocate", "allocate")
    f.observe("allocate")
    if fault == "cancelled":
        f.cancel("allocate")
        f.finish("allocate")
        assert f.state()["extensions"]["workflow"]["children"]["allocate"][
            "cancellation_requested"
        ]
        f.dispatch("work", "resume", "allocate")
        with pytest.raises(
            (ValueError, RuntimeError), match="Cancelled or incomplete predecessor"
        ):
            f.observe("work")
        assert len(f.instances) == 1
    else:
        f.finish("allocate")
        f.dispatch("work", "resume", "allocate")
        f.observe("work")
        f.finish("work")
        f.dispatch("cold", "resume", "allocate")
        count = len(f.instances)
        with pytest.raises((ValueError, RuntimeError)):
            f.observe("cold")
        assert len(f.instances) == count


@pytest.mark.parametrize(
    "complete_chain",
    [{"selected": {"model": "synthetic-model", "model_reasoning_effort": "high"}}],
    indirect=True,
)
def test_explicit_matching_alternative_selection_uses_current_owner(complete_chain):
    f = complete_chain
    f.dispatch("allocate", "allocate")
    f.observe("allocate")
    f.finish("allocate")
    f.dispatch("work", "resume", "allocate")
    result = f.observe("work")
    f.finish("work")
    assert json.loads(Path(result["receipt_path"]).read_text())["configuration"][
        "selected"
    ] == {"model": "synthetic-model", "model_reasoning_effort": "high"}


@pytest.mark.parametrize(
    "complete_chain",
    [
        {"declared": {"model": "different-model", "effort": "xhigh"}},
        {"declared": {"model": "gpt-6-astra", "effort": "high"}},
    ],
    indirect=True,
)
def test_declared_selection_mismatch_refuses_before_native_connection(complete_chain):
    f = complete_chain
    f.dispatch("allocate", "allocate")
    with pytest.raises((ValueError, RuntimeError), match="selection"):
        f.observe("allocate")
    assert not f.instances


@pytest.mark.parametrize(
    "fault",
    [
        "child-producer",
        "copied-receipt",
        "forged-receipt",
        "stale-source",
        "stale-claim",
        "parent-narration",
    ],
)
def test_independent_integration_requires_current_worker_and_native_review(
    complete_chain, fault
):
    import native_review

    f = complete_chain
    f.dispatch("allocate", "allocate")
    f.observe("allocate")
    state = f.finish("allocate")

    def current():
        return {
            **f.runtime.inspect_context(
                state, f.world["actor"], project=f.world["project"]
            ),
            "state": deepcopy(state),
            "actor": deepcopy(f.world["actor"]),
            "project": f.world["project"],
        }

    context = current()
    review = deepcopy(state["evidence"]["review-allocate"])
    assert native_review.verify_source(review, context)
    child = context["state"]["extensions"]["workflow"]["children"]["allocate"]
    if fault == "child-producer":
        child["producer"] = "codex:foreign"
    elif fault == "copied-receipt":
        context["evidence"]["copy"] = deepcopy(context["evidence"]["observed-allocate"])
        child["worker_receipt_id"] = "copy"
    elif fault == "forged-receipt":
        context["evidence"]["observed-allocate"]["data"]["producer"] = "codex:foreign"
    elif fault == "stale-source":
        source = f.world["project"] / state["artifacts"]["source"]["path"]
        source.with_suffix(".original").write_bytes(source.read_bytes())
        value = json.loads(source.read_text())
        value["accepted_commit"] = "b" * 40
        source.write_text(json.dumps(value))
        context = current()
    elif fault == "stale-claim":
        context["binding"]["claim_hash"] = "f" * 64
    else:
        transcript = f.world["transcript"]
        transcript.with_suffix(".original").write_bytes(transcript.read_bytes())
        transcript.write_text(
            transcript.read_text().replace('"name": "Agent"', '"name": "Bash"')
        )
    assert not native_review.verify_source(review, context)
    assert f.runtime.load_run(f.world["project"], state["run_id"]) == state
