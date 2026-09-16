from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import subprocess
import threading
import time

import pytest


SOURCE = Path(__file__).with_name("repo_sync_check.py")


def load():
    spec = importlib.util.spec_from_file_location("repo_sync_fixture", SOURCE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_parallel_checks_are_bounded_and_preserve_input_order(monkeypatch):
    module = load()
    barrier = threading.Barrier(8, timeout=3)
    lock = threading.Lock()
    active = peak = 0
    completion = []
    repos = [Path(f"/fixture/repo-{index:02}") for index in range(16)]

    def check(repo):
        nonlocal active, peak
        with lock:
            active += 1
            peak = max(peak, active)
        barrier.wait()
        time.sleep((16 - repos.index(repo)) / 1000)
        with lock:
            active -= 1
            completion.append(repo)
        return {"path": str(repo)}

    monkeypatch.setattr(module, "check_repo", check)
    assert module.check_repos(repos) == [{"path": str(repo)} for repo in repos]
    assert peak == 8
    assert completion != repos


def test_empty_scan_starts_no_workers(monkeypatch):
    module = load()
    monkeypatch.setattr(module, "ThreadPoolExecutor", lambda **kwargs: pytest.fail("empty scan started workers"))
    assert module.check_repos([]) == []


def test_worker_exception_stays_an_exception(monkeypatch):
    module = load()

    def check(repo):
        raise ValueError("invalid local counts")

    monkeypatch.setattr(module, "check_repo", check)
    with pytest.raises(ValueError, match="invalid local counts"):
        module.check_repos([Path("/fixture/repo")])


def test_repo_checks_only_issue_local_read_commands(monkeypatch):
    module = load()
    commands = []

    def run(command, **kwargs):
        commands.append(command)
        assert kwargs["env"]["GIT_OPTIONAL_LOCKS"] == "0"
        assert kwargs["env"]["GIT_NO_LAZY_FETCH"] == "1"
        result = {"status": " M modified.txt\n", "branch": "main\n", "rev-list": "2 3\n"}[command[3]]
        return subprocess.CompletedProcess(command, 0, result, "")

    monkeypatch.setattr(module.subprocess, "run", run)
    result = module.check_repos([Path("/fixture/repo")])[0]
    assert [command[3] for command in commands] == ["status", "branch", "rev-list"]
    assert result["issues"] == [
        {"type": "uncommitted", "detail": "1 uncommitted file(s)", "files": [" M modified.txt"], "total": 1},
        {"type": "unpushed", "detail": "3 unpushed commit(s) on main", "count": 3},
        {"type": "behind", "detail": "2 commit(s) behind origin/main", "count": 2},
    ]


@pytest.mark.parametrize("failure", [FileNotFoundError(), subprocess.TimeoutExpired("git", 30)])
def test_git_failures_remain_error_rows(monkeypatch, failure):
    module = load()

    def run(*args, **kwargs):
        raise failure

    monkeypatch.setattr(module.subprocess, "run", run)
    rows = module.check_repos([Path("/fixture/a"), Path("/fixture/b")])
    assert [row["name"] for row in rows] == ["a", "b"]
    assert all(not row["clean"] and row["issues"][0]["type"] == "error" for row in rows)


def test_main_uses_ordered_results_without_reports_when_requested(tmp_path, monkeypatch, capsys):
    module = load()
    repos = [tmp_path / name for name in ("a", "b")]
    rows = [{"name": "a", "path": str(repos[0]), "clean": True, "issues": []},
            {"name": "b", "path": str(repos[1]), "clean": False, "issues": [{"type": "error", "detail": "fixture"}]}]
    monkeypatch.setattr(module, "find_git_repos", lambda *args: repos)
    monkeypatch.setattr(module.subprocess, "run", lambda *args, **kwargs: subprocess.CompletedProcess([], 0))
    calls = []
    monkeypatch.setattr(module, "check_repos", lambda values: calls.append(values) or rows)
    monkeypatch.setattr(module, "write_reports", lambda *args: pytest.fail("unexpected report write"))
    monkeypatch.setattr(module.sys, "argv", [str(SOURCE), "--workspace", str(tmp_path), "--json", "--no-report"])
    assert module.main() == 1
    assert calls == [repos]
    assert json.loads(capsys.readouterr().out) == rows
