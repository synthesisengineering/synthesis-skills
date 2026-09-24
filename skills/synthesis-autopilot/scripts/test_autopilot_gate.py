"""Production Stop gate acceptance after durable-run migration.

Old attestation-only success cases are replaced by receipt-backed state and
capability tests; native bounded-failure and preservation invariants remain.
"""
from __future__ import annotations
import json
import os
from pathlib import Path
import subprocess
import sys
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "synthesis-project-management/scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_run_admission import world, SEAT
from test_autopilot_cli import create

SCRIPT = Path(__file__).with_name("autopilot_gate.py")


def run(world, *args, payload=None):
    env = dict(os.environ, SYNTHESIS_AUTOPILOT_RUNTIME=str(world["runtime"]),
               SYNTHESIS_COORDINATION_BOARD=str(world["board"]),
               AUTOPILOT_GATE_STATE_DIR=str(world["runtime"] / "legacy"))
    data = world["actor"]["native_payload"] if payload is None else payload
    return subprocess.run([sys.executable, str(SCRIPT), *args], input=json.dumps(data),
                          capture_output=True, text=True, env=env)


def test_gate_passes_no_owned_runs(world):
    done = run(world, "--gate")
    assert done.returncode == 0
    assert not done.stdout.strip() or json.loads(done.stdout) == {}


@pytest.mark.parametrize("repeat", [False, True])
def test_native_feedback_is_bounded_and_preserves_durable_run(world, repeat):
    state = create(world)
    home = world["project"] / "resources/autopilot-runs" / state["run_id"]
    before = {str(p):p.read_bytes() for p in home.rglob("*") if p.is_file()}
    payload = dict(world["actor"]["native_payload"], stop_hook_active=repeat)
    done = run(world, "--gate", payload=payload)
    assert done.returncode == 0, done.stderr
    result = json.loads(done.stdout)
    assert (result.get("continue") is False) if repeat else (result["decision"] == "block")
    assert {str(p):p.read_bytes() for p in home.rglob("*") if p.is_file()} == before


@pytest.mark.parametrize("payload", [[], {}, {"hook_event_name":"Stop","stop_hook_active":False}])
def test_invalid_native_input_terminates_without_corrective_loop(world, payload):
    done = run(world, "--gate", payload=payload)
    assert done.returncode == 0
    result = json.loads(done.stdout)
    assert result["continue"] is False
    assert result.get("decision") != "block"


def test_malformed_owned_index_is_preserved_and_terminal(world):
    create(world)
    index = world["runtime"] / "owners" / (SEAT + ".json")
    index.write_text("{corrupt-owned")
    done = run(world, "--gate")
    assert json.loads(done.stdout)["continue"] is False
    assert index.read_text() == "{corrupt-owned"


def test_malformed_foreign_index_cannot_block_unrelated_session(world):
    directory = world["runtime"] / "owners"
    directory.mkdir(parents=True)
    foreign = directory / "foreign.json"
    foreign.write_text("{corrupt-foreign")
    done = run(world, "--gate")
    assert done.returncode == 0, done.stderr
    assert not done.stdout.strip() or json.loads(done.stdout) == {}
    assert foreign.read_text() == "{corrupt-foreign"


@pytest.mark.parametrize("command", ["register", "continuation", "cron-fired", "cycle", "blocker", "close"])
def test_attestation_only_legacy_mutations_require_explicit_conversion(world, command):
    done = run(world, command, "--plan", str(world["plan"]), "--mission", "fixture")
    assert done.returncode == 2
    assert "autopilot.py" in done.stderr
    assert "import" in done.stderr


def test_doctor_does_not_create_files_or_claim_native_acceptance(world):
    done = run(world, "--doctor")
    assert done.returncode == 0, done.stderr
    report = json.loads(done.stdout)
    assert report["native_acceptance"].startswith("UNKNOWN")
    assert not world["runtime"].exists()
