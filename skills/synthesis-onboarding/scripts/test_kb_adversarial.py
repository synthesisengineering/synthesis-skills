"""Independent real-Git controls for checkout identity and concurrent ownership."""

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
