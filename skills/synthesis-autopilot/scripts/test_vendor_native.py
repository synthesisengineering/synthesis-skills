"""Synthetic emitted wire, real native-worker/PM/journal/custody consumers.

No native client or provider is invoked. An isolated local emitter substitutes
only the producer executable. Its actual OS sandbox remains enabled; acceptance
here qualifies source behavior, never a real client installation.
"""

from copy import deepcopy
from datetime import datetime, timezone, timedelta
import json
from pathlib import Path
import sys
import uuid
import pytest
import test_run_state as run_fixtures
import test_native_transport as wire

engine = run_fixtures.engine
world = run_fixtures.world
command = run_fixtures.command

CONF = Path(__file__).resolve().parents[2] / "synthesis-agent-conformance/scripts"
sys.path.insert(0, str(CONF))
import vendor_native as consumer  # noqa: E402
import vendor_bundle as bundle  # noqa: E402


def fixture_source(root):
    root.mkdir()
    for name in (".claude-plugin/plugin.json", ".codex-plugin/plugin.json"):
        path = root / name
        path.parent.mkdir(exist_ok=True)
        path.write_text(
            json.dumps(
                {
                    "name": "synthesis-skills",
                    "version": "1.2.3",
                    "description": "Synthetic source qualification",
                    "license": "Apache-2.0 AND CC0-1.0",
                }
            )
        )
    (root / "SKILL.md").write_text("Synthetic fixture source only\n")
    for name in (
        "LICENSE-APACHE",
        "LICENSE-CC0",
        "SUPPORT.md",
        "CONTRIBUTING.md",
        "GOVERNANCE.md",
    ):
        (root / name).write_text("Synthetic source fixture\n")
    skill = root / "skills/example/SKILL.md"
    skill.parent.mkdir(parents=True)
    skill.write_text(
        "---\nname: example\ndescription: Synthetic fixture\n---\n# Example\n"
    )

    return root


@pytest.fixture
def admitted_callback(world, monkeypatch, request):
    fault = getattr(request, "param", None)
    root = fixture_source(world["scratch"] / "synthetic-release")
    latest = world["scratch"] / "registry" / "session-start.json"
    latest.parent.mkdir()
    from live_receipt import receipt_event_path

    eid = str(uuid.uuid4())
    receipt = {
        "receipt_schema": 2,
        "client": "claude",
        "session_id": wire.SESSION,
        "receipt_event_id": eid,
        "hook_event_name": "SessionStart",
        "context_outcome": "INJECTED",
        "plugin_version": "1.2.3",
        "plugin_root": str(root),
        "execution_root": str(root),
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "provenance_env": "claude-transcript",
    }
    from live_receipt import callback_generation

    receipt["callback_generation"] = callback_generation(root, root)
    path = receipt_event_path(
        latest, client="claude", session_id=wire.SESSION, event_id=eid
    )
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(receipt))
    stdout = json.dumps(
        {
            "continue": True,
            "hookSpecificOutput": {
                "hookEventName": "SessionStart",
                "additionalContext": "Synthetic project context\n"
                + consumer.callback_witness(receipt, latest),
            },
        }
    )
    rows = wire.claude_rows()
    rows[0].update(
        cwd=str(world["project"] / "delegated/scratch"),
        permissionMode="default",
        tools=["Read", "Write", "Edit", "Bash"],
        model=None,
    )
    rows[-1].update(terminal_reason="completed")
    hooks = [
        {
            "type": "system",
            "subtype": kind,
            "session_id": wire.SESSION,
            "uuid": "synthetic-" + kind,
            "hook_id": "hook-one",
            "hook_name": "SessionStart:startup",
            "hook_event": "SessionStart",
            **(
                {"exit_code": 0, "outcome": "success", "stdout": stdout}
                if kind == "hook_response"
                else {}
            ),
        }
        for kind in ("hook_started", "hook_response")
    ]
    rows[1:1] = hooks
    if fault == "duplicate-callback":
        rows.insert(-1, deepcopy(hooks[1]))
    elif fault == "wrong-hook-event":
        hooks[1]["hook_event"] = "Stop"
    elif fault == "wrong-hook-id":
        hooks[1]["hook_id"] = "unpaired"
    elif fault == "error-outcome":
        hooks[1]["outcome"] = "error"
    elif fault == "bool-exit":
        hooks[1]["exit_code"] = False
    elif fault == "missing-witness":
        hooks[1]["stdout"] = "{}"
    elif fault == "boundary-unknown":
        rows[0]["permissionMode"] = "bypassPermissions"
    mode = "synthetic" if fault == "synthetic-source" else "native"
    monkeypatch.setattr(wire, "claude_rows", lambda: deepcopy(rows))
    import test_workflow
    import autopilot
    import workflow
    from test_run_state import create

    def native_fixture_owner(world):
        runtime = autopilot.engine()
        workflow.register_preparers(runtime.register_preparer)
        state = create(runtime, world)
        state = command(
            runtime,
            world,
            state,
            "native.enroll",
            {"source_handle": "root", "mode": mode},
        )
        state = command(
            runtime,
            world,
            state,
            "workflow.configure",
            {"dimensions": test_workflow.dimensions(parallelizable=False)},
        )
        state = command(
            runtime,
            world,
            state,
            "workflow.graph",
            {
                "nodes": [
                    {"id": "work", "deps": [], "criteria": ["accept"], "estimate": 1}
                ],
                "wip_limit": 1,
            },
        )
        return runtime, state

    monkeypatch.setattr(test_workflow, "_policy_owner", native_fixture_owner)
    runtime, state = wire.owned_worker(world, monkeypatch, "claude")
    child = state["extensions"]["workflow"]["children"]["worker-one"]
    assert child["worker_observation"]["boundary"]["status"] == (
        "UNKNOWN" if fault == "boundary-unknown" else "ENFORCED"
    )
    assert child["worker_observation"]["terminal"] == "completed"
    state = command(
        runtime,
        world,
        state,
        "native.enroll",
        {"source_handle": "worker:worker-one", "mode": mode},
    )
    state = command(
        runtime,
        world,
        state,
        "native.observe",
        {
            "source_handle": "worker:worker-one",
            "through_event": None,
            "task_id": "work",
            "attempt_id": None,
        },
    )
    ext = state["extensions"]["native_observations"]
    assert not ext["latest_batch"]["gaps"] and not ext["latest_batch"]["diagnostics"]
    events = [
        e["event_id"]
        for e in ext["latest_batch"]["events"]
        if e["kind"] in ("runtime.hook", "lifecycle.completed")
    ]
    if fault == "duplicate-callback":
        events = [events[0], events[1], events[-1]]
    assert len(events) == 3
    selection = {
        "project": str(world["project"]),
        "run_id": state["run_id"],
        "actor": world["actor"],
        "source_handle": "worker:worker-one",
        "source_generation": ext["sources"]["worker:worker-one"]["binding"][
            "generation"
        ],
        "event_ids": events,
        "registry_latest": str(latest),
    }
    entry = {"receipt": str(path), "plugin_root": str(root)}
    return {
        "root": root,
        "selection": selection,
        "entry": entry,
        "path": path,
        "runtime": runtime,
        "state": state,
        "world": world,
        "receipt": receipt,
        "inventory": bundle.source_inventory(root),
        "rows": rows,
    }


def consume(f):
    return consumer.current_callback(
        f["root"], "claude", f["entry"], "1.2.3", f["inventory"], f["selection"]
    )


def test_real_owner_callback_join_is_reachable(admitted_callback):
    f = admitted_callback
    result = consume(f)
    assert result["status"] == "PASS", result
    assert result["scope"] == "admitted-cli-session-start-context"
    assert (
        result["desktop_live_loading"] == "UNKNOWN" and result["all_hooks"] == "UNKNOWN"
    )
    assert result["action_authorized"] is False
    assert (
        bundle._native(
            "claude",
            f["entry"],
            "1.2.3",
            f["inventory"],
            root=f["root"],
            owner_context=f["selection"],
        )
        == "PASS"
    )


@pytest.mark.parametrize(
    "fault",
    [
        "receipt-bytes",
        "foreign-session",
        "source",
        "installed-root",
        "generation",
        "event-missing",
        "event-duplicate",
        "source-handle",
        "foreign-claim",
        "foreign-run",
        "raw-transport",
        "expired",
        "forged-context",
        "registry-path",
    ],
)
def test_real_owner_rejects_invalid_join(admitted_callback, monkeypatch, fault):
    f = admitted_callback
    assert consume(f)["status"] == "PASS"
    if fault in ("receipt-bytes", "foreign-session"):
        data = json.loads(f["path"].read_bytes())
        data["session_id"] = "foreign"
        f["path"].write_text(json.dumps(data))
    elif fault == "source":
        (f["root"] / "SKILL.md").write_text("changed")
    elif fault == "installed-root":
        f["entry"]["plugin_root"] = str(f["world"]["scratch"])
    elif fault == "generation":
        f["selection"]["source_generation"] = "wrong-generation"
    elif fault == "event-missing":
        f["selection"]["event_ids"][1] = "sha256:" + "0" * 64
    elif fault == "event-duplicate":
        f["selection"]["event_ids"][1] = f["selection"]["event_ids"][0]
    elif fault == "source-handle":
        f["selection"]["source_handle"] = "root"
    elif fault == "foreign-claim":
        from test_run_admission import write_board

        write_board(f["world"], claims=str(f["world"]["project"] / "elsewhere") + "/**")
    elif fault == "foreign-run":
        f["selection"]["run_id"] = str(uuid.uuid4())
    elif fault == "raw-transport":
        source = f["state"]["extensions"]["native_observations"]["sources"][
            "worker:worker-one"
        ]["binding"]["path"]
        p = Path(source)
        p.write_bytes(
            p.read_bytes()
            .replace(b"INJECTED", b"REFUSED")
            .replace(b"Synthetic project", b"Changed project")
        )
    elif fault == "expired":

        class Future(datetime):
            @classmethod
            def now(cls, tz=None):
                return datetime.now(tz) + timedelta(minutes=6)

        monkeypatch.setattr(consumer, "datetime", Future)
    elif fault == "forged-context":
        f["selection"]["status"] = "PASS"
    elif fault == "registry-path":
        f["selection"]["registry_latest"] = str(f["world"]["scratch"] / "wrong.json")
    assert consume(f)["status"] == "UNKNOWN"


@pytest.mark.parametrize("client", ["codex", "muse", "hermes"])
def test_other_client_does_not_inherit_claude_success(admitted_callback, client):
    f = admitted_callback
    assert (
        consumer.current_callback(
            f["root"], client, f["entry"], "1.2.3", f["inventory"], f["selection"]
        )["status"]
        == "UNKNOWN"
    )


def test_no_owner_context_cannot_promote_local_receipt(admitted_callback):
    f = admitted_callback
    assert bundle._native("claude", f["entry"], "1.2.3", f["inventory"]) == "UNKNOWN"


@pytest.mark.parametrize(
    "fault", ["extra", "duplicate", "not-final", "refused", "event", "boolean-exit"]
)
def test_callback_result_constraints(fault):
    witness = consumer.PREFIX + json.dumps(
        {"event_id": str(uuid.uuid4()), "sha256": "a" * 64}
    )
    value = {
        "continue": True,
        "hookSpecificOutput": {
            "hookEventName": "SessionStart",
            "additionalContext": witness,
        },
    }
    if fault == "extra":
        value["approved"] = True
    elif fault == "duplicate":
        value["hookSpecificOutput"]["additionalContext"] = witness + "\n" + witness
    elif fault == "not-final":
        value["hookSpecificOutput"]["additionalContext"] = witness + "\nmore"
    elif fault == "refused":
        value["continue"] = False
    elif fault == "event":
        value["hookSpecificOutput"]["hookEventName"] = "Stop"
    elif fault == "boolean-exit":
        value["continue"] = 1
    with pytest.raises(ValueError):
        consumer._witness(json.dumps(value))


@pytest.mark.parametrize(
    "admitted_callback",
    [
        "duplicate-callback",
        "wrong-hook-event",
        "wrong-hook-id",
        "error-outcome",
        "bool-exit",
        "missing-witness",
        "boundary-unknown",
        "synthetic-source",
    ],
    indirect=True,
)
def test_real_owner_requires_complete_matching_native_callback(admitted_callback):
    assert consume(admitted_callback)["status"] == "UNKNOWN"


def test_receipt_hardlink_and_ancestor_alias_refuse(admitted_callback):
    import os

    f = admitted_callback
    assert consume(f)["status"] == "PASS"
    os.link(f["path"], f["path"].with_suffix(".linked"))
    assert consume(f)["status"] == "UNKNOWN"


def test_consumer_rechecks_claim_after_installation_read(
    admitted_callback, monkeypatch
):
    import system_contract
    from test_run_admission import write_board

    f = admitted_callback
    real = system_contract.verify_native_release_inventory
    count = []

    def changed(*args, **kwargs):
        value = real(*args, **kwargs)
        if not count:
            count.append(True)
            write_board(
                f["world"], claims=str(f["world"]["project"] / "different") + "/**"
            )
        return value

    monkeypatch.setattr(system_contract, "verify_native_release_inventory", changed)
    assert consume(f)["status"] == "UNKNOWN"


def test_receipt_pins_the_observed_generation_not_only_version(admitted_callback):
    f = admitted_callback
    assert consume(f)["status"] == "PASS"
    (f["root"] / "SKILL.md").write_text("Different reviewed bytes, same version\n")
    f["inventory"] = bundle.source_inventory(f["root"])
    result = consume(f)
    assert result["status"] == "UNKNOWN"
    assert "generation" in result["reason"]


def test_actual_vendor_prepare_consumes_owner_callback(admitted_callback):
    f = admitted_callback
    request = {
        "schema": 1,
        "vendor": "anthropic",
        "draft": "Synthetic unsent review draft.",
        "native": {"claude": f["entry"]},
        "official_sources": [],
    }
    result = bundle.prepare(
        f["root"], request, native_context={"claude": f["selection"]}
    )
    assert result["gates"]["native.claude"] == "PASS"
    assert result["gates"]["native.codex"] == "UNKNOWN"
    assert result["technical_review_ready"] is False
    assert (
        result["submission_authorized"] is False
        and result["contact_authorized"] is False
    )
    assert str(f["world"]["project"]) not in json.dumps(result)


def test_freshness_cannot_expire_during_installation_read(
    admitted_callback, monkeypatch
):
    f = admitted_callback
    assert consume(f)["status"] == "PASS"
    import system_contract

    real = system_contract.verify_native_release_inventory

    class Future(datetime):
        @classmethod
        def now(cls, tz=None):
            return datetime.now(tz) + timedelta(minutes=6)

    def expire(*args, **kwargs):
        result = real(*args, **kwargs)
        monkeypatch.setattr(consumer, "datetime", Future)
        return result

    monkeypatch.setattr(system_contract, "verify_native_release_inventory", expire)
    assert consume(f)["status"] == "UNKNOWN"
