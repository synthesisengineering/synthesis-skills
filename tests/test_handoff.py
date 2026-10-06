"""R1.4: one command commits and pushes only the records this session changed, and refuses to
call anything ready that another machine could not resume from (code evaluation, section 3)."""

import os
import subprocess

import pytest

from synthesis import board, project


def _git(repo, *args):
    return subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True).stdout.strip()


@pytest.fixture
def kb(tmp_path):
    """A records checkout tracking a bare remote, with one published commit."""
    remote = tmp_path / "remote.git"
    subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(remote)], check=True)
    repo = tmp_path / "kb"
    subprocess.run(["git", "clone", "-q", str(remote), str(repo)], check=True, capture_output=True)
    for folder in ("mine", "theirs"):
        (repo / folder).mkdir()
        (repo / folder / "CONTEXT.md").write_text(f"{folder}\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "start")
    _git(repo, "push", "-q", "origin", "main")
    board.claim("S1", [f"{repo}/mine/**"], project="alpha")
    return repo


def _remote_files(tmp_path):
    return _git(tmp_path / "remote.git", "log", "-1", "--name-only", "--format=")


def test_only_changes_inside_this_sessions_claims_are_committed_and_pushed(kb, tmp_path):
    (kb / "mine" / "CONTEXT.md").write_text("mine, updated\n", encoding="utf-8")
    (kb / "mine" / "new.md").write_text("a new record\n", encoding="utf-8")
    (kb / "theirs" / "CONTEXT.md").write_text("theirs, updated\n", encoding="utf-8")
    _git(kb, "add", "theirs/CONTEXT.md")  # another session's staged work must not be swept in
    report = project.handoff("S1", "Update alpha records")
    assert "committed 2 file(s)" in report[0] and "pushed to origin/main" in report[0]
    assert report[-1].startswith("READY")
    assert sorted(_remote_files(tmp_path).split()) == ["mine/CONTEXT.md", "mine/new.md"]
    assert _git(kb, "diff", "--cached", "--name-only") == "theirs/CONTEXT.md"  # still staged, still theirs


def test_a_session_without_claims_is_never_ready(kb):
    assert project.handoff("nobody")[-1].startswith("NOT READY")


def test_a_branch_without_an_upstream_is_refused_and_listed(kb):
    _git(kb, "checkout", "-q", "-b", "local-only")
    (kb / "mine" / "CONTEXT.md").write_text("on a local branch\n", encoding="utf-8")
    report = project.handoff("S1")
    assert any("has no upstream" in line for line in report)
    assert report[-1].startswith("NOT READY")


def test_a_refusing_hook_is_read_from_git_not_from_a_missing_error_line(kb, tmp_path):
    ran = tmp_path / "hook-ran"
    hook = kb / ".git" / "hooks" / "pre-commit"
    hook.write_text(f"#!/bin/sh\ntouch {ran}\nexit 1\n", encoding="utf-8")  # refuses silently
    hook.chmod(0o755)
    before = _git(kb, "rev-parse", "HEAD")
    (kb / "mine" / "CONTEXT.md").write_text("blocked\n", encoding="utf-8")
    (kb / "mine" / "new.md").write_text("blocked too\n", encoding="utf-8")
    report = project.handoff("S1")
    assert ran.exists()  # the hook ran: hooks are never bypassed
    assert "NOT committed" in report[0] and report[-1].startswith("NOT READY")
    assert _git(kb, "rev-parse", "HEAD") == before
    assert _git(kb, "diff", "--cached", "--name-only") == ""  # the new file is not left half-added


def test_an_index_lock_is_left_alone_and_nothing_is_committed(kb):
    lock = kb / ".git" / "index.lock"
    lock.write_text("", encoding="utf-8")
    (kb / "mine" / "CONTEXT.md").write_text("waiting\n", encoding="utf-8")
    before = _git(kb, "rev-parse", "HEAD")
    report = project.handoff("S1")
    assert "index.lock exists" in report[0] and report[-1].startswith("NOT READY")
    assert lock.exists()
    lock.unlink()
    assert _git(kb, "rev-parse", "HEAD") == before


def test_a_diverged_branch_is_neither_pushed_nor_forced(kb, tmp_path):
    other = tmp_path / "other"
    subprocess.run(["git", "clone", "-q", str(tmp_path / "remote.git"), str(other)], check=True, capture_output=True)
    (other / "theirs" / "CONTEXT.md").write_text("from the other Mac\n", encoding="utf-8")
    _git(other, "commit", "-qam", "other Mac")
    _git(other, "push", "-q", "origin", "main")
    remote_head = _git(tmp_path / "remote.git", "rev-parse", "main")
    (kb / "mine" / "CONTEXT.md").write_text("here\n", encoding="utf-8")
    report = project.handoff("S1")
    assert any("diverged (1 local, 1 remote" in line for line in report)
    assert report[-1].startswith("NOT READY")
    assert _git(tmp_path / "remote.git", "rev-parse", "main") == remote_head
    assert _git(kb, "log", "-1", "--format=%s") == "Update project records"  # safe locally


def test_a_detached_head_is_refused(kb):
    _git(kb, "checkout", "-q", "--detach")
    (kb / "mine" / "CONTEXT.md").write_text("detached\n", encoding="utf-8")
    report = project.handoff("S1")
    assert "detached HEAD" in report[0] and report[-1].startswith("NOT READY")


def test_earlier_unpushed_commits_are_pushed_and_being_behind_is_only_a_note(kb, tmp_path):
    (kb / "mine" / "CONTEXT.md").write_text("committed earlier\n", encoding="utf-8")
    _git(kb, "commit", "-qam", "earlier")
    report = project.handoff("S1")
    assert "pushed 1 earlier commit(s)" in report[0] and report[-1].startswith("READY")
    other = tmp_path / "other"
    subprocess.run(["git", "clone", "-q", str(tmp_path / "remote.git"), str(other)], check=True, capture_output=True)
    (other / "theirs" / "CONTEXT.md").write_text("later\n", encoding="utf-8")
    _git(other, "commit", "-qam", "later")
    _git(other, "push", "-q", "origin", "main")
    report = project.handoff("S1")
    assert any("1 commit(s) behind origin/main" in line for line in report) and report[-1].startswith("READY")


def test_a_claim_outside_any_checkout_is_skipped_and_named(kb, tmp_path):
    loose = tmp_path / "scratch"
    loose.mkdir()
    board.claim("S1", [f"{loose}/**"])
    report = project.handoff("S1")
    assert any("not inside a git checkout" in line for line in report) and report[-1].startswith("READY")


def test_the_cli_handoff_command_reports_through_the_same_function(kb, monkeypatch, capsys):
    from synthesis import cli
    (kb / "mine" / "CONTEXT.md").write_text("via cli\n", encoding="utf-8")
    monkeypatch.setenv("SYNTHESIS_SESSION", "S1")
    cli.main(["handoff", "-m", "Records via the CLI"])
    assert "READY" in capsys.readouterr().out
    assert _git(kb, "log", "-1", "--format=%s") == "Records via the CLI"
    assert os.path.exists(kb / "mine" / "CONTEXT.md")
