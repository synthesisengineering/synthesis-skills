"""Fixtures for the pre-dispatch search-budget check.

Derived from the 2026-09-23 incident: six parallel research agents
silently exhausted one session-wide WebSearch budget because each
assumed its own.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).with_name("search_budget.py")
VAR = "SYNTHESIS_SEARCH_BUDGET_PER_AGENT"


def run(*args: str, cap: str | None = None):
    env = dict(os.environ)
    env.pop(VAR, None)
    if cap is not None:
        env[VAR] = cap
    return subprocess.run([sys.executable, str(SCRIPT), *args],
                          capture_output=True, text=True, env=env)


def test_unset_cap_fails_closed_with_remedy() -> None:
    done = run("check", "--agents", "6")
    assert done.returncode == 1
    assert VAR in done.stderr
    assert "export" in done.stderr


def test_malformed_cap_fails_closed() -> None:
    for bad in ("plenty", "0", "-4", "2.5"):
        done = run("check", "--agents", "6", cap=bad)
        assert done.returncode == 1, bad
        assert VAR in done.stderr


def test_set_cap_prints_the_split() -> None:
    done = run("check", "--agents", "6", cap="25")
    assert done.returncode == 0, done.stderr
    assert "6 agents x 25 searches = 150" in done.stdout


def test_json_reports_allowance() -> None:
    done = run("check", "--agents", "4", "--json", cap="25")
    assert done.returncode == 0, done.stderr
    payload = json.loads(done.stdout)
    assert payload == {"per_agent_cap": 25, "agents": 4, "allowance": 100, "admitted": False,
                       "scope": "arithmetic only; durable reservation required before dispatch"}


def test_non_positive_agents_rejected() -> None:
    done = run("check", "--agents", "0", cap="25")
    assert done.returncode == 2


import pytest
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "synthesis-project-management/scripts"))
from test_run_admission import world
from test_autopilot_cli import create
import autopilot
import search_budget


def test_search_adapter_reserves_and_reconciles_the_actual_shared_run(world):
    state = create(world)
    runtime = autopilot.engine()
    def command(name, payload, ident):
        nonlocal state
        state = runtime.apply_command(world["project"], state["run_id"], name, payload,
            expected_revision=state["revision"], command_id=ident, actor=world["actor"], runtime_root=world["runtime"])
    command("workflow.configure", {"dimensions": {"domains": ["research"], "uncertainty": "low",
        "effect": "none", "horizon": "turn", "parallelizable": True}}, "configure")
    command("workflow.budget", {"limits": {"searches": {"limit": 10, "enforcement": "hard"}},
        "deadline": "2099-01-01T00:00:00Z"}, "budget")
    kwargs = {"project": world["project"], "run_id": state["run_id"], "actor": world["actor"],
              "runtime_root": world["runtime"]}
    result = search_budget.reserve_searches(**kwargs, reservation_id="batch", agents=2, per_agent=4,
        expected_revision=state["revision"], command_id="search-reserve")
    assert result["admitted"] is True
    assert result["budget"]["available"] == 2
    with pytest.raises(ValueError):
        search_budget.reserve_searches(**kwargs, reservation_id="too-many", agents=2, per_agent=2,
            expected_revision=result["revision"], command_id="overrun")
    settled = search_budget.settle_searches(**kwargs, reservation_id="batch", actual=None,
        expected_revision=result["revision"], command_id="unknown")
    assert settled["budget"]["spent"] is None
    assert settled["budget"]["available"] == 2
    measured = search_budget.settle_searches(**kwargs, reservation_id="batch", actual=3,
        expected_revision=settled["revision"], command_id="measured")
    assert measured["budget"]["spent"] == 3
    assert measured["budget"]["available"] == 7


def test_search_cli_reaches_durable_reservation(world, monkeypatch, capsys):
    state = create(world)
    runtime = autopilot.engine()
    for name, payload in (("workflow.configure", {"dimensions": {"domains": ["research"],
            "uncertainty": "low", "effect": "none", "horizon": "turn", "parallelizable": True}}),
            ("workflow.budget", {"limits": {"searches": {"limit": 10, "enforcement": "hard"}},
                                "deadline": "2099-01-01T00:00:00Z"})):
        state = runtime.apply_command(world["project"], state["run_id"], name, payload,
            expected_revision=state["revision"], command_id=name, actor=world["actor"],
            runtime_root=world["runtime"])
    actor = world["project"] / "actor.json"
    actor.write_text(json.dumps(world["actor"]))
    monkeypatch.setenv("SYNTHESIS_AUTOPILOT_ROOT", str(world["runtime"]))
    assert search_budget.main(["reserve", "--project", str(world["project"]), "--actor", str(actor),
        "--run-id", state["run_id"], "--reservation-id", "cli-batch", "--command-id", "cli-reserve",
        "--expected-revision", str(state["revision"]), "--agents", "2", "--per-agent", "3"]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["budget"]["available"] == 4
    assert result["admitted"] is True


def test_search_cli_actor_errors_are_bounded(tmp_path, capsys):
    with pytest.raises(SystemExit) as error:
        search_budget.main(["reserve", "--project", str(tmp_path), "--actor", str(tmp_path / "missing"),
            "--run-id", "run", "--reservation-id", "r", "--command-id", "c",
            "--expected-revision", "0", "--agents", "1", "--per-agent", "1"])
    assert error.value.code == 2
    assert "search budget:" in capsys.readouterr().err
