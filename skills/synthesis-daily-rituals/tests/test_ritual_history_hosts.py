"""Ritual history kept for each host (plan item 13.5, part 5; 5.20.0), the record's side.

The audit of 2026-11-11 (gap 6): a ritual's record lived only in this Mac's `<synthesis home>/rituals/history.jsonl`.
The first build committed each record into the plans repository, and its review showed why that cannot stand: two
Macs that each record before pulling diverge, and a commit lands on whatever state the checkout is in (F4, F9, F12).
So `record` commits nothing. The hourly `synthesis sessions sync` carries each workspace's records to its sessions
repo, which it already pulls, commits and pushes; the record says where its history goes.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import date
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
TODAY = date.today().isoformat()


@pytest.fixture(autouse=True)
def no_machine_git_or_synthesis_state(tmp_path, monkeypatch):
    """The commits these tests make run no hook of this Mac's and write no synthesis state of its own."""
    config = tmp_path / "gitconfig"
    config.write_text("[user]\n\temail = test@example.com\n\tname = test\n", encoding="utf-8")
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(config))
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    monkeypatch.setenv("SYNTHESIS_HOME", str(tmp_path / "synthesis-home"))


def git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, check=True).stdout.strip()


def run(state: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(SCRIPTS / "ritual_state.py"), "--state-dir", str(state), *args],
                          capture_output=True, text=True, check=False, env={**os.environ, "RITUAL_STATE_DIR": str(state)})


def test_a_record_commits_nothing_and_says_where_its_history_goes(tmp_path: Path) -> None:
    repo = tmp_path / "ai-knowledge-alpha"
    (repo / "daily-plans").mkdir(parents=True)
    git(tmp_path, "init", "-q", str(repo))
    (repo / "daily-plans" / f"{TODAY}.md").write_text(f"# Plan for {TODAY}\n", encoding="utf-8")
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "start")
    state = tmp_path / "state"
    state.mkdir()
    (state / "config.json").write_text(json.dumps({"workspaces": {"alpha": {"plans_dirs": [str(repo / "daily-plans")]}}}),
                                       encoding="utf-8")
    home = tmp_path / "synthesis-home"
    home.mkdir()
    (home / "config.json").write_text(json.dumps({"sessions_repos": {"alpha": str(tmp_path / "sessions-alpha")}}),
                                      encoding="utf-8")
    before = (git(repo, "log", "--format=%H"), git(repo, "status", "--porcelain"))
    done = run(state, "record", "--direction", "day-end", "--workspace", "alpha", "--date", TODAY)
    assert done.returncode == 0, done.stderr
    assert (git(repo, "log", "--format=%H"), git(repo, "status", "--porcelain")) == before  # nothing written, nothing committed
    assert f"ritual history: `synthesis sessions sync` carries it to {tmp_path / 'sessions-alpha'}" in done.stdout
    (home / "config.json").write_text("{}", encoding="utf-8")
    done = run(state, "record", "--direction", "day-start", "--workspace", "alpha", "--date", TODAY)
    assert done.returncode == 0 and "ritual history: kept on this Mac only" in done.stdout, done.stdout
