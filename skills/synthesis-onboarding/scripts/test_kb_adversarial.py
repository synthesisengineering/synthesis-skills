"""Independent real-Git controls for checkout identity and concurrent ownership."""

import json
import select
import subprocess
from pathlib import Path

import pytest

import onboard
from test_kb_update_ownership import kb, snapshot


def test_symlinked_workspace_parent_must_not_receive_created_clone(kb):
    elsewhere = kb.root / "outside-workspace"
    elsewhere.mkdir()
    kb.workspaces.mkdir(parents=True)
    (kb.workspaces / "example").symlink_to(elsewhere, target_is_directory=True)
    report, receipts = kb.run(enrolling=True)
    assert report.exit_code() != 0, report.steps
    assert not (elsewhere / "knowledge").exists()
    assert "knowledge" not in receipts.data.get("knowledge_repositories", {})


def test_peer_branch_change_after_final_verification_must_not_be_merged(kb, monkeypatch):
    report, _ = kb.run(enrolling=True)
    assert report.exit_code() == 0, report.steps
    before_head = kb.git("rev-parse", "HEAD", cwd=kb.standard)
    kb.advance()
    original = onboard.git
    peer_snapshot = []

    def git(args, **kwargs):
        result = original(args, **kwargs)
        if args[:2] == ["merge-base", "--is-ancestor"]:
            kb.git("checkout", "-q", "-b", "peer/topic", cwd=kb.standard)
            peer_snapshot.append(snapshot(kb.standard))
        return result

    monkeypatch.setattr(onboard, "git", git)
    report, _ = kb.run()
    assert peer_snapshot
    assert kb.git("rev-parse", "HEAD", cwd=kb.standard) == before_head, report.steps
    assert snapshot(kb.standard) == peer_snapshot[0]
    assert report.exit_code() != 0, report.steps


def test_symlinked_parent_replacement_must_not_update_different_checkout(kb):
    report, _ = kb.run(enrolling=True)
    assert report.exit_code() == 0, report.steps
    parent = kb.workspaces / "example"
    saved_parent = kb.root / "saved-created-workspace"
    parent.rename(saved_parent)
    elsewhere = kb.root / "outside-workspace"
    target = kb.clone(elsewhere / "knowledge")
    parent.symlink_to(elsewhere, target_is_directory=True)
    kb.advance()
    before = snapshot(target)
    report, _ = kb.run()
    assert report.exit_code() != 0, report.steps
    assert snapshot(target) == before


def test_fetch_must_not_apply_unrelated_configured_ref_mappings(kb):
    report, _ = kb.run(enrolling=True)
    assert report.exit_code() == 0, report.steps
    kb.git("branch", "peer/topic", cwd=kb.standard)
    before = kb.git("rev-parse", "refs/heads/peer/topic", cwd=kb.standard)
    kb.git("config", "--add", "remote.origin.fetch",
           "+refs/heads/main:refs/heads/peer/topic", cwd=kb.standard)
    kb.advance()
    report, _ = kb.run()
    assert kb.git("rev-parse", "refs/heads/peer/topic", cwd=kb.standard) == before, report.steps


def test_concurrent_unrelated_fetch_cannot_choose_update_target(kb, monkeypatch):
    report, _ = kb.run(enrolling=True)
    assert report.exit_code() == 0, report.steps
    target = kb.advance()
    source = kb.root / "source"
    kb.git("checkout", "-q", "-b", "peer/topic", cwd=source)
    (source / "peer.md").write_text("Unrelated branch content.\n")
    kb.git("add", "peer.md", cwd=source)
    kb.git("commit", "-q", "-m", "Add branch fixture", cwd=source)
    kb.git("push", str(kb.root / "remote.git"), "peer/topic", cwd=source)
    other = kb.git("rev-parse", "HEAD", cwd=source)
    original = onboard.git

    def git(arguments, **kwargs):
        result = original(arguments, **kwargs)
        if arguments[0] == "fetch":
            kb.git("fetch", "--no-tags", "--refmap=", "origin", "refs/heads/peer/topic",
                   cwd=kb.standard)
            assert kb.git("rev-parse", "FETCH_HEAD", cwd=kb.standard) == other
        return result

    monkeypatch.setattr(onboard, "git", git)
    report, _ = kb.run()
    assert report.exit_code() == 0, report.steps
    assert kb.git("rev-parse", "HEAD", cwd=kb.standard) == target
    assert kb.git("rev-parse", "refs/remotes/origin/main", cwd=kb.standard) == target
    assert not (kb.standard / "peer.md").exists()


def test_prepared_update_excludes_real_concurrent_git_writers(kb, monkeypatch):
    report, _ = kb.run(enrolling=True)
    assert report.exit_code() == 0, report.steps
    target = kb.advance()
    kb.git("branch", "peer/topic", cwd=kb.standard)
    original = onboard.run
    attempts = []

    def run(cmd, **kwargs):
        if cmd[:2] == ["git", "read-tree"]:
            for arguments in (["checkout", "peer/topic"],
                              ["symbolic-ref", "HEAD", "refs/heads/peer/topic"],
                              ["update-ref", "refs/heads/main", target]):
                result = subprocess.run(["git", *arguments], cwd=kb.standard,
                                        capture_output=True, text=True)
                attempts.append((arguments, result.returncode, result.stderr))
        return original(cmd, **kwargs)

    monkeypatch.setattr(onboard, "run", run)
    report, _ = kb.run()
    assert len(attempts) == 3, attempts
    assert all(code != 0 and ".lock" in error for _, code, error in attempts), attempts
    assert report.exit_code() == 0, report.steps
    assert kb.git("symbolic-ref", "HEAD", cwd=kb.standard) == "refs/heads/main"
    assert kb.git("rev-parse", "HEAD", cwd=kb.standard) == target


@pytest.mark.parametrize("lock", ["HEAD.lock", "index.lock", "refs/heads/main.lock"])
def test_preexisting_git_locks_are_preserved(kb, lock):
    report, _ = kb.run(enrolling=True)
    assert report.exit_code() == 0, report.steps
    kb.advance()
    path = kb.standard / ".git" / lock
    path.write_text("Peer lock.\n")
    before = (kb.standard / "content.md").read_bytes()
    index = (kb.standard / ".git/index").read_bytes()
    report, _ = kb.run()
    assert report.exit_code() != 0, report.steps
    assert path.read_text() == "Peer lock.\n"
    assert (kb.standard / "content.md").read_bytes() == before
    assert (kb.standard / ".git/index").read_bytes() == index


def test_failed_index_activation_retains_new_index_and_recovery_identity(kb, monkeypatch):
    report, _ = kb.run(enrolling=True)
    assert report.exit_code() == 0, report.steps
    before = kb.git("rev-parse", "HEAD", cwd=kb.standard)
    target = kb.advance()
    original_index = (kb.standard / ".git/index").read_bytes()
    original = onboard.os.replace

    def replace(source, destination):
        if str(destination) == str(kb.standard / ".git/index"):
            raise OSError("Fixture index activation failure")
        return original(source, destination)

    monkeypatch.setattr(onboard.os, "replace", replace)
    report, _ = kb.run()
    assert report.exit_code() != 0, report.steps
    assert kb.git("rev-parse", "HEAD", cwd=kb.standard) == target
    assert (kb.standard / ".git/index").read_bytes() == original_index
    records = list((kb.standard / ".git").glob(".synthesis-index-*.recovery.json"))
    assert len(records) == 1
    recovery = json.loads(records[0].read_text())
    assert recovery["before"] == before
    assert recovery["target"] == target
    assert recovery["ref_committed"] is True
    assert onboard.file_digest(recovery["index"]) == recovery["index_sha256"]
    assert not (kb.standard / ".git/index.lock").exists()


def test_real_read_tree_refusal_preserves_new_peer_file(kb, monkeypatch):
    report, _ = kb.run(enrolling=True)
    assert report.exit_code() == 0, report.steps
    before_head = kb.git("rev-parse", "HEAD", cwd=kb.standard)
    original_index = (kb.standard / ".git/index").read_bytes()
    kb.advance()
    original = onboard.run
    injected = []

    def run(cmd, **kwargs):
        if cmd[:2] == ["git", "read-tree"] and not injected:
            (kb.standard / "content.md").write_text("Peer edit at checkout boundary.\n")
            injected.append(True)
        return original(cmd, **kwargs)

    monkeypatch.setattr(onboard, "run", run)
    report, _ = kb.run()
    assert report.exit_code() != 0, report.steps
    assert kb.git("rev-parse", "HEAD", cwd=kb.standard) == before_head
    assert (kb.standard / "content.md").read_text() == "Peer edit at checkout boundary.\n"
    assert (kb.standard / ".git/index").read_bytes() == original_index


def test_prepared_destination_changed_before_lock_is_refused(kb, monkeypatch):
    report, _ = kb.run(enrolling=True)
    assert report.exit_code() == 0, report.steps
    kb.advance()
    kb.git("branch", "peer/topic", cwd=kb.standard)
    before = kb.git("rev-parse", "HEAD", cwd=kb.standard)
    index = (kb.standard / ".git/index").read_bytes()
    original = subprocess.Popen

    def popen(cmd, *args, **kwargs):
        if cmd[:3] == ["git", "update-ref", "--stdin"]:
            kb.git("symbolic-ref", "HEAD", "refs/heads/peer/topic", cwd=kb.standard)
        return original(cmd, *args, **kwargs)

    monkeypatch.setattr(subprocess, "Popen", popen)
    report, _ = kb.run()
    assert report.exit_code() != 0, report.steps
    assert kb.git("symbolic-ref", "HEAD", cwd=kb.standard) == "refs/heads/peer/topic"
    assert kb.git("rev-parse", "HEAD", cwd=kb.standard) == before
    assert (kb.standard / ".git/index").read_bytes() == index


def test_native_reference_process_abort_restores_worktree_and_index(kb, monkeypatch):
    report, _ = kb.run(enrolling=True)
    assert report.exit_code() == 0, report.steps
    kb.advance()
    before_head = kb.git("rev-parse", "HEAD", cwd=kb.standard)
    content = (kb.standard / "content.md").read_bytes()
    index = (kb.standard / ".git/index").read_bytes()
    original_popen, original_run = subprocess.Popen, onboard.run
    processes, aborted = [], []

    def popen(cmd, *args, **kwargs):
        process = original_popen(cmd, *args, **kwargs)
        if cmd[:3] == ["git", "update-ref", "--stdin"]:
            processes.append(process)
        return process

    def run(cmd, **kwargs):
        result = original_run(cmd, **kwargs)
        if cmd[:2] == ["git", "read-tree"] and not aborted:
            assert result[0] == 0, result
            processes[0].terminate()
            processes[0].wait(timeout=5)
            aborted.append(True)
        return result

    monkeypatch.setattr(subprocess, "Popen", popen)
    monkeypatch.setattr(onboard, "run", run)
    report, _ = kb.run()
    assert report.exit_code() != 0, report.steps
    assert kb.git("rev-parse", "HEAD", cwd=kb.standard) == before_head
    assert (kb.standard / "content.md").read_bytes() == content
    assert (kb.standard / ".git/index").read_bytes() == index
    assert not list((kb.standard / ".git").glob("*.lock"))
    assert not list((kb.standard / ".git").glob(".synthesis-index-*"))


def test_read_tree_failure_after_write_recovers_original_state(kb, monkeypatch):
    report, _ = kb.run(enrolling=True)
    assert report.exit_code() == 0, report.steps
    kb.advance()
    before_head = kb.git("rev-parse", "HEAD", cwd=kb.standard)
    content = (kb.standard / "content.md").read_bytes()
    index = (kb.standard / ".git/index").read_bytes()
    original = onboard.run
    failed = []

    def run(cmd, **kwargs):
        result = original(cmd, **kwargs)
        if cmd[:2] == ["git", "read-tree"] and not failed:
            assert result[0] == 0, result
            failed.append(True)
            return 1, "", "Fixture failure after checkout write"
        return result

    monkeypatch.setattr(onboard, "run", run)
    report, _ = kb.run()
    assert report.exit_code() != 0, report.steps
    assert kb.git("rev-parse", "HEAD", cwd=kb.standard) == before_head
    assert (kb.standard / "content.md").read_bytes() == content
    assert (kb.standard / ".git/index").read_bytes() == index


def test_reference_protocol_timeout_is_non_green_and_releases_owned_locks(kb, monkeypatch):
    report, _ = kb.run(enrolling=True)
    assert report.exit_code() == 0, report.steps
    kb.advance()
    before_head = kb.git("rev-parse", "HEAD", cwd=kb.standard)
    index = (kb.standard / ".git/index").read_bytes()
    original = select.select
    calls = []

    def timeout(read, write, exceptional, duration):
        calls.append(True)
        return ([], [], []) if len(calls) == 2 else original(read, write, exceptional, duration)

    monkeypatch.setattr(select, "select", timeout)
    report, _ = kb.run()
    assert report.exit_code() != 0, report.steps
    assert kb.git("rev-parse", "HEAD", cwd=kb.standard) == before_head
    assert (kb.standard / ".git/index").read_bytes() == index
    assert not list((kb.standard / ".git").glob("*.lock"))


def test_lost_commit_acknowledgement_preserves_committed_tree_and_staged_index(kb, monkeypatch):
    report, _ = kb.run(enrolling=True)
    assert report.exit_code() == 0, report.steps
    before = kb.git("rev-parse", "HEAD", cwd=kb.standard)
    original_index = (kb.standard / ".git/index").read_bytes()
    target = kb.advance()
    original = select.select
    calls = []

    def timeout(read, write, exceptional, duration):
        calls.append(True)
        ready = original(read, write, exceptional, duration)
        if len(calls) == 3:
            assert ready[0]
            assert kb.git("rev-parse", "refs/heads/main", cwd=kb.standard) == target
            return [], [], []
        return ready

    monkeypatch.setattr(select, "select", timeout)
    report, _ = kb.run()
    assert report.exit_code() != 0, report.steps
    assert kb.git("rev-parse", "HEAD", cwd=kb.standard) == target
    assert (kb.standard / "content.md").read_text() == "Initial content.\nPublished content.\n"
    assert (kb.standard / ".git/index").read_bytes() == original_index
    records = list((kb.standard / ".git").glob(".synthesis-index-*.recovery.json"))
    assert len(records) == 1
    recovery = json.loads(records[0].read_text())
    assert recovery["ref_committed"] is True
    assert recovery["before"] == before
    assert recovery["target"] == target
    assert onboard.file_digest(recovery["index"]) == recovery["index_sha256"]
    assert not list((kb.standard / ".git").glob("*.lock"))


def test_lock_cleanup_failure_is_non_green_without_losing_committed_index(kb, monkeypatch):
    report, _ = kb.run(enrolling=True)
    assert report.exit_code() == 0, report.steps
    target = kb.advance()
    original = Path.unlink
    lock = kb.standard / ".git/index.lock"

    def unlink(path, *args, **kwargs):
        if path == lock:
            raise OSError("Fixture cleanup failure")
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "unlink", unlink)
    report, _ = kb.run()
    assert report.exit_code() != 0, report.steps
    assert kb.git("rev-parse", "HEAD", cwd=kb.standard) == target
    assert kb.git("--no-optional-locks", "status", "--porcelain", cwd=kb.standard) == ""
    assert lock.exists()


def test_real_filesystem_checkout_failure_preserves_original_state(kb):
    source = kb.root / "source"
    locked_source = source / "locked"
    locked_source.mkdir()
    (locked_source / "keep.txt").write_text("Original content.\n")
    kb.git("add", "locked", cwd=source)
    kb.git("commit", "-q", "-m", "Seed checkout fixture", cwd=source)
    kb.git("push", str(kb.root / "remote.git"), "main", cwd=source)
    report, _ = kb.run(enrolling=True)
    assert report.exit_code() == 0, report.steps
    before_head = kb.git("rev-parse", "HEAD", cwd=kb.standard)
    content = (kb.standard / "content.md").read_bytes()
    index = (kb.standard / ".git/index").read_bytes()
    kb.advance()
    (locked_source / "new.txt").write_text("New content.\n")
    kb.git("add", "locked", cwd=source)
    kb.git("commit", "-q", "-m", "Extend checkout fixture", cwd=source)
    kb.git("push", str(kb.root / "remote.git"), "main", cwd=source)
    locked = kb.standard / "locked"
    locked.chmod(0o555)
    try:
        report, _ = kb.run()
    finally:
        locked.chmod(0o755)
    assert report.exit_code() != 0, report.steps
    assert kb.git("rev-parse", "HEAD", cwd=kb.standard) == before_head
    assert (kb.standard / "content.md").read_bytes() == content
    assert (kb.standard / ".git/index").read_bytes() == index
