"""Ritual history kept for each host in the workspace's own repository (plan item 13.5, part 5; 5.20.0).

The audit of 2026-11-11 (gap 6): a ritual's record lived only in this Mac's `<synthesis home>/rituals/history.jsonl`,
so another Mac's streak, last close and reviews could not read what this one did. `record` now also appends the same
line to `<the workspace's repo>/.agents/ritual-history/<host>.jsonl` and commits that file alone, and every view
reads the local log and each host's file, every record once.
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
PLUGIN = Path(__file__).resolve().parents[3]
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


def repo_with_plans(tmp_path: Path) -> Path:
    repo = tmp_path / "ai-knowledge-alpha"
    (repo / "daily-plans").mkdir(parents=True)
    git(tmp_path, "init", "-q", str(repo))
    (repo / "daily-plans" / f"{TODAY}.md").write_text(f"# Plan for {TODAY}\n", encoding="utf-8")
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "start")
    return repo


def configure(state: Path, workspace: dict) -> None:
    state.mkdir(parents=True, exist_ok=True)
    (state / "config.json").write_text(json.dumps({"workspaces": {"alpha": workspace}}), encoding="utf-8")


def run(state: Path, host: str, *args: str) -> subprocess.CompletedProcess:
    env = {**os.environ, "SYNTHESIS_HOST": host, "RITUAL_STATE_DIR": str(state)}
    return subprocess.run([sys.executable, str(SCRIPTS / "ritual_state.py"), "--state-dir", str(state), *args],
                          capture_output=True, text=True, check=False, env=env)


def read(state: Path, host: str) -> list:
    """The records every view reads, as `rituals.read()` gives them on this host."""
    code = "import json, sys; sys.path.insert(0, sys.argv[1]); from synthesis import rituals; print(json.dumps(rituals.read()))"
    env = {**os.environ, "SYNTHESIS_HOST": host, "RITUAL_STATE_DIR": str(state)}
    done = subprocess.run([sys.executable, "-c", code, str(PLUGIN)], capture_output=True, text=True, check=True, env=env)
    return json.loads(done.stdout)


def test_a_record_is_kept_for_its_host_in_the_workspaces_repo_and_committed_alone(tmp_path: Path) -> None:
    repo = repo_with_plans(tmp_path)
    configure(tmp_path / "mac-a", {"plans_dirs": [str(repo / "daily-plans")]})
    (repo / "daily-plans" / "draft.md").write_text("another session's work\n", encoding="utf-8")
    git(repo, "add", "daily-plans/draft.md")  # staged by someone else: never swept into the history's commit
    done = run(tmp_path / "mac-a", "mac-a.local", "record", "--direction", "day-end", "--workspace", "alpha", "--date", TODAY)
    assert done.returncode == 0, done.stderr
    kept = repo / ".agents" / "ritual-history" / "mac-a.jsonl"
    local = (tmp_path / "mac-a" / "history.jsonl").read_text(encoding="utf-8")
    assert kept.read_text(encoding="utf-8") == local  # the same line, under the host's name without `.local`
    assert git(repo, "log", "-1", "--name-only", "--format=") == ".agents/ritual-history/mac-a.jsonl"
    assert git(repo, "diff", "--cached", "--name-only") == "daily-plans/draft.md"
    assert git(repo, "status", "--porcelain", "--", ".agents") == ""
    assert f"ritual history: kept in {kept}" in done.stdout


def test_another_host_reads_both_hosts_each_record_once(tmp_path: Path) -> None:
    repo = repo_with_plans(tmp_path)
    for host in ("mac-a", "mac-b"):
        configure(tmp_path / host, {"plans_dirs": [str(repo / "daily-plans")]})
    assert run(tmp_path / "mac-a", "mac-a", "record", "--direction", "day-end", "--workspace", "alpha", "--date", TODAY).returncode == 0
    seen_on_b = read(tmp_path / "mac-b", "mac-b")[0]  # nothing in mac-b's own log yet: mac-a's close, read from the repo
    assert [(r["direction"], r["date"]) for r in seen_on_b] == [("day-end", TODAY)]
    assert run(tmp_path / "mac-b", "mac-b", "record", "--direction", "day-start", "--workspace", "alpha", "--date", TODAY).returncode == 0
    on_a = read(tmp_path / "mac-a", "mac-a")[0]
    assert sorted(r["direction"] for r in on_a) == ["day-end", "day-start"]  # its own once, though its log and its file both hold it
    last = run(tmp_path / "mac-b", "mac-b", "query", "last", "--workspace", "alpha", "--json")
    assert last.returncode == 0 and TODAY in last.stdout, last.stderr


def test_the_folder_comes_from_the_config_or_is_said_to_be_missing(tmp_path: Path) -> None:
    repo = repo_with_plans(tmp_path)
    configure(tmp_path / "named", {"plans_dirs": [], "history_dir": str(repo / "history")})
    done = run(tmp_path / "named", "mac-a", "record", "--direction", "day-end", "--workspace", "alpha", "--date", TODAY)
    assert done.returncode == 0 and (repo / "history" / "mac-a.jsonl").is_file(), done.stderr
    configure(tmp_path / "none", {"plans_dirs": []})
    done = run(tmp_path / "none", "mac-a", "record", "--direction", "day-end", "--workspace", "alpha", "--date", TODAY)
    assert done.returncode == 0 and "ritual history: kept on this Mac only" in done.stdout, done.stdout


def test_a_history_commit_that_fails_never_fails_the_record(tmp_path: Path) -> None:
    repo = repo_with_plans(tmp_path)
    hook = repo / ".git" / "hooks" / "pre-commit"
    hook.write_text("#!/bin/sh\necho refused by this repository >&2\nexit 1\n", encoding="utf-8")
    hook.chmod(0o755)
    configure(tmp_path / "mac-a", {"plans_dirs": [str(repo / "daily-plans")]})
    done = run(tmp_path / "mac-a", "mac-a", "record", "--direction", "day-end", "--workspace", "alpha", "--date", TODAY)
    assert done.returncode == 0, done.stderr
    assert "not committed" in done.stdout and "refused by this repository" in done.stdout
    assert (repo / ".agents" / "ritual-history" / "mac-a.jsonl").is_file()  # appended, waiting for a commit
