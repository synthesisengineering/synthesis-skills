"""Fixtures for the autopilot continuation stop-gate.

Derived from the real 2026-08-29 overnight failure: an engagement ran two
phases, the turn ended with no continuation mechanism, and the session sat
idle all night — a reboot passed unnoticed because nothing was executing.
"""
from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

MODULE_PATH = Path(__file__).with_name("autopilot_gate.py")
SPEC = importlib.util.spec_from_file_location("autopilot_gate", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


NATIVE_STOP_SESSION = "018f0000-0000-7000-8000-000000000001"


def native_stop_payload(repeat=False):
    return {"session_id": NATIVE_STOP_SESSION, "hook_event_name": "Stop",
            "stop_hook_active": repeat, "turn_id": "fixture-turn", "cwd": "/tmp/p"}


def native_engagement(tmp_path, **updates):
    root = tmp_path / "engagements"
    root.mkdir(parents=True, exist_ok=True)
    path = root / "owned.json"
    path.write_text(json.dumps({"status": "active", "session_id": NATIVE_STOP_SESSION,
        "client_session_ref": "codex:" + NATIVE_STOP_SESSION, "mission": "fixture obligation",
        "plan": "/tmp/p/plan.md", **updates}), encoding="utf-8")
    return path


@pytest.mark.parametrize("repeat", [False, True])
def test_native_stop_feedback_is_bounded_and_preserves_engagement(tmp_path, repeat):
    record = native_engagement(tmp_path)
    before = record.read_bytes()
    done = run_cli(tmp_path, "--gate", stdin=json.dumps(native_stop_payload(repeat)),
        env_extra={"SYNTHESIS_CLIENT_SESSION_REF": "codex:" + NATIVE_STOP_SESSION})
    assert done.returncode == 0
    output = json.loads(done.stdout)
    if repeat:
        assert output["continue"] is False
        assert output.get("decision") != "block"
        assert "fixture obligation" in output["stopReason"]
    else:
        assert output["decision"] == "block"
        assert "fixture obligation" in output["reason"]
    assert record.read_bytes() == before


@pytest.mark.parametrize("stdin", ["{broken", "[]", "{}",
    '{"hook_event_name":"Stop","stop_hook_active":false}'])
def test_native_stop_invalid_input_terminates_without_retry_or_false_success(tmp_path, stdin):
    record = native_engagement(tmp_path)
    before = record.read_bytes()
    done = run_cli(tmp_path, "--gate", stdin=stdin,
        env_extra={"SYNTHESIS_CLIENT_SESSION_REF": ""})
    assert done.returncode == 0
    output = json.loads(done.stdout)
    assert output["continue"] is False
    assert output.get("decision") != "block"
    assert record.read_bytes() == before


def test_native_stop_unreadable_registry_is_terminal_and_preserved(tmp_path):
    root = tmp_path / "engagements"
    root.mkdir()
    broken = root / "broken.json"
    broken.write_text("{broken", encoding="utf-8")
    done = run_cli(tmp_path, "--gate", stdin=json.dumps(native_stop_payload()),
        env_extra={"SYNTHESIS_CLIENT_SESSION_REF": "codex:" + NATIVE_STOP_SESSION})
    assert done.returncode == 0
    output = json.loads(done.stdout)
    assert output["continue"] is False
    assert "unreadable" in output["stopReason"]
    assert broken.read_text(encoding="utf-8") == "{broken"


@pytest.mark.parametrize("updates", [
    {"status": "closed", "closed_incomplete": "principal stopped this work"},
    {"blocker": {"reason": "awaiting principal decision", "alerted_at": "2026-09-23T00:00:00+00:00"}},
    {"continuation": {"kind": "native", "mechanism": "verified native continuation"}},
])
def test_native_repeated_stop_preserves_legitimate_wait_close_and_continuation(tmp_path, updates):
    record = native_engagement(tmp_path, **updates)
    before = record.read_bytes()
    done = run_cli(tmp_path, "--gate", stdin=json.dumps(native_stop_payload(True)),
        env_extra={"SYNTHESIS_CLIENT_SESSION_REF": "codex:" + NATIVE_STOP_SESSION})
    assert done.returncode == 0
    assert not done.stdout.strip() or json.loads(done.stdout).get("continue") is not False
    assert record.read_bytes() == before


def run_cli(tmp_path: Path, *args: str, stdin: str = "{}", env_extra=None):
    board = tmp_path / "board.md"
    if not board.exists():
        board.write_text(
            "# Board\n\nSchema: v4\n\n## Active sessions\n\n"
            "| session uuid | compact id | speakable id v1 | legacy id | agent | machine | client session ref | project | started | heartbeat | mode | workspace(s) / branch | goal | claimed areas (advisory lock) | context role | status |\n"
            "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|\n"
            "| session-a | s-aaaa-bbbb-cccc | words-1 | | agent | machine | tool:session-a | alpha | 2026-09-03T12:00:00-04:00 | 2026-09-03T12:00:00-04:00 | interactive | /tmp/p | fixture | /tmp/p/** | owner | active |\n"
            "\n## Messages\n",
            encoding="utf-8",
        )
    env = {
        **os.environ,
        "AUTOPILOT_GATE_STATE_DIR": str(tmp_path / "engagements"),
        "AUTOPILOT_GATE_SESSION_ID": "session-a",
        "AUTOPILOT_GATE_PROJECT_ID": "alpha",
        "AUTOPILOT_GATE_COORDINATION_BOARD": str(board),
        "SYNTHESIS_CLIENT_SESSION_REF": "tool:session-a",
        **(env_extra or {}),
    }
    return subprocess.run([sys.executable, str(MODULE_PATH), *args],
                          input=stdin, capture_output=True, text=True,
                          env=env)


def register(tmp_path: Path, plan: str = "/tmp/p/plan.md") -> None:
    done = run_cli(tmp_path, "register", "--plan", plan,
                   "--mission", "draft the backlog overnight")
    assert done.returncode == 0, done.stderr


def test_gate_passes_with_no_engagements(tmp_path: Path) -> None:
    assert run_cli(tmp_path, "--gate").returncode == 0


def test_gate_blocks_active_engagement_without_continuation(tmp_path) -> None:
    """The overnight failure, encoded: active + unfinished + nothing
    scheduled must refuse the stop."""
    register(tmp_path)
    done = run_cli(tmp_path, "--gate", stdin='{"session_id":"session-a"}')
    assert done.returncode == 2
    assert "silent-idle" in done.stderr
    assert "continuation" in done.stderr


def test_gate_passes_once_continuation_recorded(tmp_path: Path) -> None:
    register(tmp_path)
    done = run_cli(tmp_path, "continuation", "--plan", "/tmp/p/plan.md",
                   "--mechanism", "dynamic loop wakeup",
                   "--next-wake", "20 minutes, plan file is the re-entry seed",
                   "--survives", "turn end; not session kill (cron backstop set)")
    assert done.returncode == 0, done.stderr
    assert run_cli(tmp_path, "--gate").returncode == 0


def test_gate_passes_with_alerted_blocker(tmp_path: Path) -> None:
    register(tmp_path)
    assert run_cli(tmp_path, "blocker", "--plan", "/tmp/p/plan.md",
                   "--reason", "every path needs a principal-only answer",
                   "--alerted").returncode == 0
    assert run_cli(tmp_path, "--gate").returncode == 0


def test_blocker_requires_alert_attestation(tmp_path: Path) -> None:
    register(tmp_path)
    done = run_cli(tmp_path, "blocker", "--plan", "/tmp/p/plan.md",
                   "--reason", "stuck")
    assert done.returncode == 2
    assert "alert" in done.stderr


def test_gate_passes_after_honest_close(tmp_path: Path) -> None:
    register(tmp_path)
    assert run_cli(tmp_path, "close", "--plan", "/tmp/p/plan.md",
                   "--incomplete", "principal withdrew the goal").returncode == 0
    assert run_cli(tmp_path, "--gate").returncode == 0


def test_unreadable_record_fails_closed(tmp_path: Path) -> None:
    root = tmp_path / "engagements"
    root.mkdir(parents=True)
    (root / "broken.json").write_text("{not json", encoding="utf-8")
    done = run_cli(tmp_path, "--gate")
    assert done.returncode == 2
    assert "unreadable" in done.stderr


def test_registration_is_bound_to_session_project_claim_and_client_ref(tmp_path: Path) -> None:
    register(tmp_path)
    records = list((tmp_path / "engagements").glob("*.json"))
    assert len(records) == 1
    payload = json.loads(records[0].read_text(encoding="utf-8"))
    assert payload["session_id"] == "session-a"
    assert payload["project_id"] == "alpha"
    assert payload["client_session_ref"] == "tool:session-a"
    assert payload["claim_hash"]


def test_foreign_live_engagement_never_blocks_this_session(tmp_path: Path) -> None:
    register(tmp_path)
    done = run_cli(
        tmp_path,
        "--gate",
        stdin='{"session_id":"session-b"}',
        env_extra={"SYNTHESIS_CLIENT_SESSION_REF": "tool:session-b"},
    )
    assert done.returncode == 0


def test_registration_without_matching_claim_fails_closed(tmp_path: Path) -> None:
    done = run_cli(
        tmp_path,
        "register",
        "--plan",
        "/tmp/p/plan.md",
        "--mission",
        "finish",
        env_extra={"AUTOPILOT_GATE_SESSION_ID": "missing"},
    )
    assert done.returncode == 2
    assert "claim" in done.stderr.lower()


def test_bare_spin_cannot_be_recorded(tmp_path: Path) -> None:
    """Runaway control: a wake that advanced nothing must name an external
    wait; there is no way to log a bare spin."""
    register(tmp_path)
    done = run_cli(tmp_path, "cycle", "--plan", "/tmp/p/plan.md",
                   "--no-advance")
    assert done.returncode == 2
    assert "spinning" in done.stderr
    assert run_cli(tmp_path, "cycle", "--plan", "/tmp/p/plan.md",
                   "--no-advance", "--waiting-on",
                   "counterpart agent's review round").returncode == 0
    assert run_cli(tmp_path, "cycle", "--plan", "/tmp/p/plan.md",
                   "--advanced", "phase 2 drafted 4 articles").returncode == 0


def test_status_reports_state_without_mutating(tmp_path: Path) -> None:
    register(tmp_path)
    assert run_cli(tmp_path, "continuation", "--plan", "/tmp/p/plan.md",
                   "--mechanism", "dynamic loop wakeup",
                   "--next-wake", "20 minutes",
                   "--survives", "turn end").returncode == 0
    records = list((tmp_path / "engagements").glob("*.json"))
    assert len(records) == 1
    before = records[0].read_bytes()
    done = run_cli(tmp_path, "status", "--plan", "/tmp/p/plan.md")
    assert done.returncode == 0, done.stderr
    assert "draft the backlog overnight" in done.stdout
    assert "dynamic loop wakeup" in done.stdout
    as_json = run_cli(tmp_path, "status", "--plan", "/tmp/p/plan.md", "--json")
    assert as_json.returncode == 0, as_json.stderr
    payload = json.loads(as_json.stdout)
    assert payload["mission"] == "draft the backlog overnight"
    assert payload["continuation"]["mechanism"] == "dynamic loop wakeup"
    assert records[0].read_bytes() == before


def test_cron_continuation_passes_gate_within_grace(tmp_path: Path) -> None:
    register(tmp_path)
    done = run_cli(tmp_path, "continuation", "--plan", "/tmp/p/plan.md",
                   "--mechanism", "scheduled re-entry every 25 minutes",
                   "--next-wake", "next quarter hour",
                   "--survives", "turn end, session death, reboot",
                   "--cron-job", "job-123")
    assert done.returncode == 0, done.stderr
    assert run_cli(tmp_path, "--gate").returncode == 0


def test_cron_continuation_blocks_gate_when_unverified_and_aged(
        tmp_path: Path) -> None:
    register(tmp_path)
    assert run_cli(tmp_path, "continuation", "--plan", "/tmp/p/plan.md",
                   "--mechanism", "scheduled re-entry every 25 minutes",
                   "--next-wake", "next quarter hour",
                   "--survives", "turn end, session death, reboot",
                   "--cron-job", "job-123").returncode == 0
    records = list((tmp_path / "engagements").glob("*.json"))
    assert len(records) == 1
    payload = json.loads(records[0].read_text(encoding="utf-8"))
    assert payload["continuation"]["verified"] is False
    payload["engaged_at"] = "2026-01-01T00:00:00+00:00"
    records[0].write_text(json.dumps(payload), encoding="utf-8")
    blocked = run_cli(tmp_path, "--gate")
    assert blocked.returncode == 2
    assert "UNVERIFIED" in blocked.stderr
    assert "cron-fired" in blocked.stderr
    assert run_cli(tmp_path, "cron-fired",
                   "--plan", "/tmp/p/plan.md").returncode == 0
    assert run_cli(tmp_path, "--gate").returncode == 0


def test_cron_fired_without_cron_continuation_fails(tmp_path: Path) -> None:
    register(tmp_path)
    done = run_cli(tmp_path, "cron-fired", "--plan", "/tmp/p/plan.md")
    assert done.returncode == 2
    assert "cron-job" in done.stderr


def test_continuation_cron_job_must_name_the_schedule(
        tmp_path: Path) -> None:
    register(tmp_path)
    done = run_cli(tmp_path, "continuation", "--plan", "/tmp/p/plan.md",
                   "--mechanism", "scheduled re-entry",
                   "--next-wake", "soon", "--survives", "reboot",
                   "--cron-job", "  ")
    assert done.returncode == 2
    assert "on-disk" in done.stderr


def test_legacy_continuation_without_kind_still_passes(
        tmp_path: Path) -> None:
    register(tmp_path)
    assert run_cli(tmp_path, "continuation", "--plan", "/tmp/p/plan.md",
                   "--mechanism", "dynamic loop wakeup",
                   "--next-wake", "20 minutes",
                   "--survives", "turn end").returncode == 0
    records = list((tmp_path / "engagements").glob("*.json"))
    payload = json.loads(records[0].read_text(encoding="utf-8"))
    del payload["continuation"]["kind"]
    del payload["continuation"]["verified"]
    records[0].write_text(json.dumps(payload), encoding="utf-8")
    assert run_cli(tmp_path, "--gate").returncode == 0


def _write_real_plan(text: str) -> Path:
    plan = Path("/tmp/p/plan.md")
    plan.parent.mkdir(parents=True, exist_ok=True)
    plan.write_text(text, encoding="utf-8")
    return plan


def test_close_refuses_scratch_only_citations(tmp_path: Path) -> None:
    scratch = tmp_path / "evidence.md"
    scratch.write_text("unflushed findings", encoding="utf-8")
    plan = _write_real_plan(f"# Plan\n\nEvidence: {scratch}\n")
    try:
        register(tmp_path)
        done = run_cli(tmp_path, "close", "--plan", str(plan),
                       "--incomplete", "withdrawing")
        assert done.returncode == 2
        assert "scratch" in done.stderr
    finally:
        plan.unlink(missing_ok=True)


def test_close_accepts_durable_citations(tmp_path: Path) -> None:
    plan = _write_real_plan(f"# Plan\n\nGate: {MODULE_PATH}\n")
    try:
        register(tmp_path)
        done = run_cli(tmp_path, "close", "--plan", str(plan),
                       "--incomplete", "withdrawing")
        assert done.returncode == 0, done.stderr
    finally:
        plan.unlink(missing_ok=True)


def test_doctrine_carries_continuation_contract() -> None:
    skill = (MODULE_PATH.parents[1] / "SKILL.md").read_text(encoding="utf-8")
    assert "Continuation" in skill
    assert "Scheduled Property" in skill
    assert "verified continuation mechanism" in skill
    assert "autopilot_gate.py" in skill
    assert "probe" in skill  # capability verification before asserting absence
