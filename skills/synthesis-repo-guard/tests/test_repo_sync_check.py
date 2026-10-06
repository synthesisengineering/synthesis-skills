"""repo_sync_check: a read-only scan, a report the console reads, and an alert with no names."""

import importlib.util
import json
import os
import subprocess
from pathlib import Path

import pytest

SOURCE = Path(__file__).resolve().parents[1] / "scripts" / "repo_sync_check.py"
spec = importlib.util.spec_from_file_location("repo_sync_check", SOURCE)
rsc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rsc)


@pytest.fixture
def home(tmp_path, monkeypatch):
    config = tmp_path / "gitconfig"
    config.write_text("[user]\n\temail = test@example.com\n\tname = test\n", encoding="utf-8")
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(config))
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    (tmp_path / "home").mkdir()
    return tmp_path / "home"


def _repo(path, *files):
    subprocess.run(["git", "init", "-q", "-b", "main", str(path)], check=True)
    for name in files:
        (path / name).write_text("x\n", encoding="utf-8")
    return path


def _git(repo, *args):
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)


def test_each_kind_of_stranded_work_is_reported_and_a_clean_repo_is_not(home, tmp_path, capsys):
    ws = tmp_path / "ws"
    clean = _repo(ws / "client-alpha" / "clean", "a.md")
    _git(clean, "add", "-A"), _git(clean, "commit", "-qm", "one")
    _repo(ws / "client-alpha" / "dirty", " leading-space.md")
    origin = tmp_path / "origin.git"
    subprocess.run(["git", "init", "-q", "--bare", str(origin)], check=True)
    ahead = _repo(ws / "ahead", "a.md")
    _git(ahead, "add", "-A"), _git(ahead, "commit", "-qm", "one"), _git(ahead, "remote", "add", "origin", str(origin))
    _git(ahead, "push", "-q", "origin", "main"), _git(ahead, "fetch", "-q", "origin")
    (ahead / "b.md").write_text("b\n"), _git(ahead, "add", "-A"), _git(ahead, "commit", "-qm", "two")
    detached = _repo(ws / "detached", "a.md")
    _git(detached, "add", "-A"), _git(detached, "commit", "-qm", "one"), _git(detached, "checkout", "-q", "--detach")
    assert rsc.main(["--workspace", str(ws)]) == 1
    out = capsys.readouterr().out
    assert "dirty" in out and "[uncommitted] 1 uncommitted file(s)" in out and "[unpushed] 1 unpushed commit(s) on main" in out
    assert "2 of 4 repositories need attention" in out
    report = json.loads((home / ".synthesis" / "repo-guard" / "last-report.json").read_text())
    assert set(report) == {"generated_at", "host", "total_repos", "dirty_count", "repos"}
    assert report["total_repos"] == 4 and report["dirty_count"] == 2
    files = next(r for r in report["repos"] if r["name"] == "dirty")["issues"][0]["files"]
    assert files == ["?? \" leading-space.md\""]  # status columns survive: nothing is stripped
    assert sorted(p.name for p in (home / ".synthesis" / "repo-guard").iterdir()) == ["last-report.json"]


def test_the_report_is_replaced_whole_never_written_in_place(home, tmp_path, monkeypatch):
    """The Console polls last-report.json; a reader must see the old report or the new one, never half of one."""
    (tmp_path / "ws").mkdir()
    replaced = []
    monkeypatch.setattr(rsc.os, "replace", lambda a, b: (replaced.append((Path(a).name, Path(b).name)), os.rename(a, b)))
    rsc.main(["--workspace", str(tmp_path / "ws"), "--quiet"])
    assert replaced and replaced[0][1] == "last-report.json" and replaced[0][0].startswith(".last-report.")


def test_the_scan_only_reads(home, tmp_path, monkeypatch):
    repo = _repo(tmp_path / "ws" / "r", "a.md")
    calls = []
    real = rsc.git
    monkeypatch.setattr(rsc, "git", lambda r, *a: (calls.append(a[0]), real(r, *a))[1])
    rsc.main(["--workspace", str(tmp_path / "ws"), "--quiet", "--no-report"])
    assert set(calls) <= {"status", "branch", "rev-list"}
    assert not (home / ".synthesis" / "repo-guard").exists() and repo.exists()


def test_the_alert_carries_a_count_and_a_pointer_never_a_name(home, tmp_path, monkeypatch):
    _repo(tmp_path / "ws" / "client-alpha-private", "secret-plan.md")
    spoken = []
    monkeypatch.setattr(rsc.sys, "platform", "darwin")
    monkeypatch.setattr(rsc.subprocess, "run", lambda argv, **kw: spoken.append(argv) or subprocess.CompletedProcess(argv, 0, "", ""))
    monkeypatch.setattr(rsc, "check", lambda repo: {"name": repo.name, "path": str(repo), "clean": False, "issues": []})
    assert rsc.main(["--workspace", str(tmp_path / "ws"), "--alert", "--quiet"]) == 1
    text = " ".join(" ".join(argv) for argv in spoken)
    assert "1 repository needs attention" in text and "client-alpha" not in text and "secret-plan" not in text
    spoken.clear()
    (home / ".synthesis").mkdir(exist_ok=True)
    (home / ".synthesis" / "quiet-audio").touch()
    rsc.main(["--workspace", str(tmp_path / "ws"), "--alert", "--quiet"])
    assert spoken == []


def test_a_git_failure_is_an_error_row_and_a_missing_workspace_exits_2(home, tmp_path, monkeypatch):
    _repo(tmp_path / "ws" / "r", "a.md")
    monkeypatch.setattr(rsc, "git", lambda repo, *a: (128, "fatal: unsafe repository"))
    assert rsc.check(tmp_path / "ws" / "r")["issues"] == [{"type": "error", "detail": "fatal: unsafe repository"}]
    assert rsc.main(["--workspace", str(tmp_path / "absent")]) == 2
