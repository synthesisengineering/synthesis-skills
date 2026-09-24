"""Production CLI consumers of state, workflow and native capability contracts."""
from __future__ import annotations

import importlib
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "synthesis-project-management/scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_run_admission import world  # noqa: F401
from test_run_state import contract

SCRIPT = Path(__file__).with_name("autopilot.py")


def cli(world, *args):
    actor = world["scratch"] / "actor.json"
    actor.write_text(json.dumps(world["actor"]))
    env = dict(os.environ, SYNTHESIS_AUTOPILOT_RUNTIME=str(world["runtime"]))
    return subprocess.run([sys.executable, str(SCRIPT), *args, "--actor", str(actor)],
                          text=True, capture_output=True, env=env)


def create(world):
    source = world["scratch"] / "contract.json"
    source.write_text(json.dumps(contract()))
    profile = world["scratch"] / "profile.json"
    profile.write_text(json.dumps({"schema": 1, "items": [{"id": "fixture", "criterion_ids": ["accept"]}]}))
    done = cli(world, "create", "--project", str(world["project"]), "--project-id", "alpha",
               "--plan", str(world["plan"]), "--contract", str(source), "--profile", str(profile),
               "--command-id", "cli-create")
    assert done.returncode == 0, done.stderr
    return json.loads(done.stdout)


def test_cli_creates_durable_state_and_status_explains_remaining(world):
    state = create(world)
    done = cli(world, "status", "--project", str(world["project"]), "--run-id", state["run_id"])
    assert done.returncode == 0, done.stderr
    result = json.loads(done.stdout)
    assert result["run_id"] == state["run_id"]
    assert "accept" in result["remaining_criteria"]
    assert result["status"] != "completed"


def test_cli_refuses_unknown_commands_and_forged_payload(world):
    state = create(world)
    data = world["scratch"] / "payload.json"
    data.write_text(json.dumps({"status": "completed", "verified": True}))
    done = cli(world, "command", "--project", str(world["project"]), "--run-id", state["run_id"],
               "--name", "close", "--payload", str(data), "--expected-revision", str(state["revision"]),
               "--command-id", "forge")
    assert done.returncode != 0


def test_cli_cancel_is_tombstoned_and_reports_unverified_cleanup(world):
    state = create(world)
    payload = world["scratch"] / "cancel.json"
    payload.write_text(json.dumps({"status": "cancelled", "reason": "Explicit user cancellation"}))
    done = cli(world, "command", "--project", str(world["project"]), "--run-id", state["run_id"],
               "--name", "close", "--payload", str(payload), "--expected-revision", str(state["revision"]),
               "--command-id", "cancel")
    assert done.returncode == 0, done.stderr
    assert json.loads(done.stdout)["status"] == "cancelled"


def test_hook_uses_scoped_owner_lookup_and_bounded_failure(world):
    state = create(world)
    module = importlib.import_module("autopilot")
    first = module.stop_result(world["actor"], runtime_root=world["runtime"])
    assert first["decision"] == "block"
    repeated = json.loads(json.dumps(world["actor"]))
    repeated["native_payload"]["stop_hook_active"] = True
    second = module.stop_result(repeated, runtime_root=world["runtime"])
    assert second["continue"] is False
    assert "UNRESOLVED" in second["systemMessage"]
    foreign = world["runtime"] / "owners/foreign.json"
    foreign.write_text("corrupt foreign data")
    assert module.stop_result(world["actor"], runtime_root=world["runtime"])["decision"] == "block"


def test_missing_native_identity_is_terminal_diagnostic_without_corrective_loop(world):
    module = importlib.import_module("autopilot")
    result = module.stop_result({"board": str(world["board"]), "native_payload": {}}, runtime_root=world["runtime"])
    assert result["continue"] is False
    assert result.get("decision") != "block"


def test_explain_surface_never_infers_scheduling_from_skill_portability(world):
    done = cli(world, "explain", "--surface", "cursor-ide")
    assert done.returncode == 0, done.stderr
    info = json.loads(done.stdout)
    assert info["level"] == "skill-only"
    assert info["unattended_admitted"] is False


def test_doctor_indexes_legacy_outside_stop_and_reports_unknown_records(world):
    legacy = world["runtime"] / "engagements"
    legacy.mkdir(parents=True)
    foreign = legacy / "unknown.json"
    foreign.write_text("malformed unassignable record")
    module = importlib.import_module("autopilot")
    before = module.stop_result(world["actor"], runtime_root=world["runtime"])
    assert before["continue"] is False
    assert "index-legacy" in before["systemMessage"]
    done = cli(world, "doctor", "--index-legacy")
    assert done.returncode == 0, done.stderr
    output = json.loads(done.stdout)
    assert output["legacy_inventory"]["scanned"] == 1
    assert len(output["legacy_inventory"]["unattributed"]) == 1
    assert output["status"] == "UNKNOWN"
    assert foreign.read_text() == "malformed unassignable record"
    after = module.stop_result(world["actor"], runtime_root=world["runtime"])
    assert after.get("decision") != "block"
    assert after.get("continue") is not False


def test_doctor_index_requires_native_actor_and_never_infers_native_acceptance(world):
    done = subprocess.run([sys.executable, str(SCRIPT), "doctor", "--index-legacy"],
                          capture_output=True, text=True)
    assert done.returncode != 0
    done = cli(world, "doctor")
    assert done.returncode == 0
    assert "UNKNOWN" in json.loads(done.stdout)["native_acceptance"]


def test_stop_retains_selected_corrupt_legacy_failure_after_indexing(world):
    from test_run_admission import NATIVE
    legacy = world["runtime"] / "engagements"
    legacy.mkdir(parents=True)
    own = legacy / "own.json"
    own.write_text('{"client_session_ref":"cc:' + NATIVE + '", broken')
    assert cli(world, "doctor", "--index-legacy").returncode == 0
    result = importlib.import_module("autopilot").stop_result(world["actor"], runtime_root=world["runtime"])
    assert result["continue"] is False
    assert "legacy" in result["systemMessage"].lower()
    assert "UNRESOLVED" in result["systemMessage"]


def test_first_task_doctor_explains_missing_home_without_creating_authority(world):
    before = world["board"].read_bytes()
    unregistered = world["repo"] / "projects/new-project"
    done = cli(world, "doctor", "--project", str(unregistered), "--project-id", "new-project")
    assert done.returncode == 0, done.stderr
    report = json.loads(done.stdout)
    assert report["durable_admission"]["status"] == "UNKNOWN"
    assert report["read_only_in_session"] is True
    assert report["unattended_admitted"] is False
    assert "project management" in report["next_step"].lower()
    assert not unregistered.exists()
    assert before == world["board"].read_bytes()


def test_first_task_doctor_validates_real_registered_ownership(world):
    done = cli(world, "doctor", "--project", str(world["project"]), "--project-id", "alpha")
    assert done.returncode == 0, done.stderr
    report = json.loads(done.stdout)
    assert report["durable_admission"]["status"] == "PASS"
    assert report["unattended_admitted"] is False
