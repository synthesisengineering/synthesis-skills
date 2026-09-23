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
    assert payload == {"per_agent_cap": 25, "agents": 4, "allowance": 100}


def test_non_positive_agents_rejected() -> None:
    done = run("check", "--agents", "0", cap="25")
    assert done.returncode == 2
