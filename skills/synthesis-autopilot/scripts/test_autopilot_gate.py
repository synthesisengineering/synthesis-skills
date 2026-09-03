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

MODULE_PATH = Path(__file__).with_name("autopilot_gate.py")
SPEC = importlib.util.spec_from_file_location("autopilot_gate", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def run_cli(tmp_path: Path, *args: str, stdin: str = "{}", env_extra=None):
    board = tmp_path / "board.md"
    if not board.exists():
        board.write_text(
            "| Session UUID | Compact ID | Speakable ID | Client session ref | Project | Workspace(s) / branch | Claimed areas (advisory lock) | Context role | Started | Heartbeat | Status |\n"
            "|---|---|---|---|---|---|---|---|---|---|---|\n"
            "| session-a | s-aaaa-bbbb-cccc | words-1 | tool:session-a | alpha | /tmp/p | /tmp/p/** | owner | 2026-09-03T12:00:00-04:00 | 2026-09-03T12:00:00-04:00 | active |\n",
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


def test_doctrine_carries_continuation_contract() -> None:
    skill = (MODULE_PATH.parents[1] / "SKILL.md").read_text(encoding="utf-8")
    assert "Continuation" in skill
    assert "Scheduled Property" in skill
    assert "verified continuation mechanism" in skill
    assert "autopilot_gate.py" in skill
    assert "probe" in skill  # capability verification before asserting absence
