"""Synthetic declared-machine review; real release/receipt owners, no live repair."""

from pathlib import Path
import importlib
import json
import pytest
from system_contract import SystemState
from test_runtime_payload import installation as _installation, snapshot, make_plan

import runtime_payload

installation = _installation


def api():
    return importlib.import_module("machine_review")


def declared():
    return {
        "schema": 1,
        "components": [
            {"id": "messages", "kind": "runtime", "component": "message-guard"}
        ],
        "registries": [],
    }


def test_review_is_mutation_negative_and_coverage_honest(installation):
    current, old, desc, home, state, receipts, protected = installation
    before = snapshot(home)
    result = api().review(SystemState(home), declared(), source_root=current)
    assert snapshot(home) == before
    assert result["coverage"] == "declared-only" and result["declared"] == 1
    assert result["results"][0]["status"] == "DRIFT" and not result["repair_authorized"]


def test_exact_receipt_owned_repair_roundtrip_and_noop(installation):
    current, old, desc, home, state, receipts, protected = installation
    runtime_payload.apply(make_plan(installation), receipts)
    target = home / ".synthesis/message-guard/message_guard.py"
    target.unlink()
    owner = SystemState(home)
    plan = api().repair_plan(owner, declared(), ["messages"], source_root=current)
    before = snapshot(home)
    assert (
        api().repair_apply(
            owner,
            declared(),
            plan,
            approval_digest=plan["digest"],
            source_root=current,
            dry_run=True,
        )["changed"]
        is False
    )
    assert snapshot(home) == before and not target.exists()
    result = api().repair_apply(
        owner, declared(), plan, approval_digest=plan["digest"], source_root=current
    )
    assert (
        result["status"] == "committed"
        and target.read_bytes()
        == (
            current / "skills/synthesis-message-guard/scripts/message_guard.py"
        ).read_bytes()
    )
    again = api().repair_plan(owner, declared(), ["messages"], source_root=current)
    assert (
        api().repair_apply(
            owner,
            declared(),
            again,
            approval_digest=again["digest"],
            source_root=current,
        )["changed"]
        is False
    )
    for rel, raw in protected.items():
        assert (home / rel).read_bytes() == raw


@pytest.mark.parametrize(
    "bad", ["approval", "foreign", "unowned", "inventory", "plan", "symlink"]
)
def test_repair_refusal_preserves_foreign_bytes(installation, bad):
    current, old, desc, home, state, receipts, _ = installation
    runtime_payload.apply(make_plan(installation), receipts)
    target = home / ".synthesis/message-guard/message_guard.py"
    target.unlink()
    owner = SystemState(home)
    request = declared()
    plan = api().repair_plan(owner, request, ["messages"], source_root=current)
    approval = plan["digest"]
    if bad == "approval":
        approval = "0" * 64
    elif bad == "foreign":
        target.write_text("foreign source")
    elif bad == "unowned":
        receipts.data["runtime_payloads"]["files"].pop(str(target))
        receipts.save()
    elif bad == "inventory":
        request["components"][0]["id"] = "other"
    elif bad == "plan":
        plan["targets"][0]["after_sha256"] = "0" * 64
    elif bad == "symlink":
        target.symlink_to(home / ".synthesis/message-guard/patterns.json")
    before = snapshot(home)
    with pytest.raises((ValueError, RuntimeError)):
        api().repair_apply(
            owner, request, plan, approval_digest=approval, source_root=current
        )
    assert snapshot(home) == before


def test_review_unknown_member_does_not_disappear(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    owner = SystemState(home)
    inv = {
        "schema": 1,
        "components": [
            {
                "id": "one",
                "kind": "file",
                "path": str(home / "missing"),
                "sha256": None,
            },
            {"id": "two", "kind": "unsupported", "path": str(home / "another")},
        ],
        "registries": [],
    }
    before = list(home.rglob("*"))
    result = api().review(owner, inv, source_root=Path(__file__).resolve().parents[3])
    assert (
        result["declared"] == 2
        and len(result["results"]) == 2
        and result["health"] == "UNKNOWN"
    )
    assert list(home.rglob("*")) == before


def test_existing_runtime_lock_has_finite_wait(tmp_path):
    import subprocess
    import sys
    import time
    from enrollment import engine_lock
    from system_contract import ContractError

    root = tmp_path / "locks"
    root.mkdir()
    lock = root / "engine.lock"
    lock.touch()
    code = "import fcntl,sys;f=open(sys.argv[1],'r+b');fcntl.flock(f,fcntl.LOCK_EX);print('ready',flush=True);sys.stdin.readline()"
    child = subprocess.Popen(
        [sys.executable, "-c", code, str(lock)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        text=True,
    )
    try:
        import select

        assert select.select([child.stdout], [], [], 5)[0]
        assert child.stdout.readline().strip() == "ready"
        start = time.monotonic()
        with pytest.raises(ContractError, match="bounded"):
            with engine_lock(root, timeout=0.05):
                pass
        assert time.monotonic() - start < 1
    finally:
        child.communicate("\n", timeout=5)
    assert child.returncode == 0


def test_saved_installation_planes_are_not_live_health(tmp_path):
    a = api()
    state = a.SystemState(tmp_path / "home")
    state.config_dir.mkdir(parents=True)
    state.state_dir.mkdir(parents=True)
    from system_contract import default_desired_state

    state.desired_path.write_text(
        json.dumps(default_desired_state("skills-only", ["codex"], "stable"))
    )
    state.observation_path.write_text(
        json.dumps({"schema_version": 3, "generation": 0, "transactions": []})
    )
    before = {p: p.read_bytes() for p in state.home.rglob("*") if p.is_file()}
    result = a.review(
        state,
        {
            "schema": 1,
            "components": [{"id": "installation", "kind": "installation"}],
            "registries": [],
        },
        source_root=tmp_path,
    )
    row = result["results"][0]
    assert row["status"] == "OBSERVED" and result["health"] == "UNKNOWN"
    assert row["live_claim"] == "UNVERIFIED_SAVED_EVIDENCE"
    assert before == {p: p.read_bytes() for p in state.home.rglob("*") if p.is_file()}


def test_registry_duplicates_are_refused():
    a = api()
    with pytest.raises((ValueError, RuntimeError)):
        a.project_ids(b"projects:\n - id: alpha\n   id: beta\n")


def test_runtime_repair_inputs_refuse_oversized_foreign_bytes(installation):
    current, old, desc, home, state, receipts, protected = installation
    runtime_payload.apply(make_plan(installation), receipts)
    target = home / ".synthesis/message-guard/message_guard.py"
    with target.open("wb") as stream:
        stream.truncate(9 * 1024 * 1024)
    a = api()
    owner = SystemState(home)
    report = a.review(
        owner,
        {
            "schema": 1,
            "components": [
                {"id": "guard", "kind": "runtime", "component": "message-guard"}
            ],
            "registries": [],
        },
        source_root=current,
    )
    assert report["results"][0]["status"] == "UNKNOWN"
    with pytest.raises((ValueError, RuntimeError)):
        a.repair_plan(
            owner,
            {
                "schema": 1,
                "components": [
                    {"id": "guard", "kind": "runtime", "component": "message-guard"}
                ],
                "registries": [],
            },
            ["guard"],
            source_root=current,
        )
    assert target.stat().st_size == 9 * 1024 * 1024


def test_runtime_owner_refuses_size_before_reading_payload(tmp_path, monkeypatch):
    path = tmp_path / "oversized"
    with path.open("wb") as stream:
        stream.truncate(9 * 1024 * 1024)
    original = Path.read_bytes

    def trap(self):
        if self == path:
            pytest.fail("owner attempted unbounded payload read")
        return original(self)

    monkeypatch.setattr(Path, "read_bytes", trap)
    with pytest.raises((ValueError, RuntimeError)):
        runtime_payload._fingerprint(path)


def test_runtime_owner_refuses_hardlink_alias(tmp_path):
    import os

    path = tmp_path / "original"
    path.write_bytes(b"fixture")
    alias = tmp_path / "alias"
    os.link(path, alias)
    with pytest.raises((ValueError, RuntimeError)):
        runtime_payload._fingerprint(alias)


def test_runtime_plan_expiry_during_lock_wait_prevents_new_effect(
    installation, monkeypatch
):
    from contextlib import contextmanager
    import machine_review as machine

    current, _, _, home, _, receipts, _ = installation
    runtime_payload.apply(make_plan(installation), receipts)
    target = home / ".synthesis/message-guard/message_guard.py"
    target.unlink()
    state = SystemState(home)
    inventory = {
        "schema": 1,
        "components": [
            {"id": "messages", "kind": "runtime", "component": "message-guard"}
        ],
        "registries": [],
    }
    plan = machine.repair_plan(
        state,
        inventory,
        ["messages"],
        source_root=current,
        now="2026-01-03T00:00:00+00:00",
    )
    clock = ["2026-01-03T00:59:59+00:00"]
    original_utc = machine.utc
    monkeypatch.setattr(
        machine, "utc", lambda value=None: original_utc(value or clock[0])
    )
    original_lock = machine.engine_lock

    @contextmanager
    def waited_lock(*args, **kwargs):
        with original_lock(*args, **kwargs):
            clock[0] = "2026-01-03T01:00:01+00:00"
            yield

    monkeypatch.setattr(machine, "engine_lock", waited_lock)
    before = snapshot(home)
    with pytest.raises((ValueError, RuntimeError), match="expir|fresh"):
        machine.repair_apply(
            state, inventory, plan, approval_digest=plan["digest"], source_root=current
        )
    assert not target.exists()
    assert snapshot(home) == before


def test_repair_expiry_during_final_input_derivation_prevents_effect(
    installation, monkeypatch
):
    import machine_review as machine

    current, _, _, home, _, receipts, _ = installation
    runtime_payload.apply(make_plan(installation), receipts)
    target = home / ".synthesis/message-guard/message_guard.py"
    target.unlink()
    state = SystemState(home)
    plan = machine.repair_plan(
        state,
        declared(),
        ["messages"],
        source_root=current,
        now="2026-01-03T00:00:00+00:00",
    )
    clock = ["2026-01-03T00:59:59+00:00"]
    original_utc = machine.utc
    monkeypatch.setattr(
        machine, "utc", lambda value=None: original_utc(value or clock[0])
    )
    original_inputs = machine._repair_inputs
    calls = []

    def delayed_inputs(*args, **kwargs):
        result = original_inputs(*args, **kwargs)
        calls.append(True)
        if len(calls) == 2:
            clock[0] = "2026-01-03T01:00:01+00:00"
        return result

    monkeypatch.setattr(machine, "_repair_inputs", delayed_inputs)
    before = snapshot(home)
    with pytest.raises((ValueError, RuntimeError), match="expir"):
        machine.repair_apply(
            state, declared(), plan, approval_digest=plan["digest"], source_root=current
        )
    assert len(calls) == 2 and snapshot(home) == before and not target.exists()
