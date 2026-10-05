"""Real Git selection races at the managed owner boundary."""
import json
import os
import shutil
import pytest
import project_state as state
from test_project_state import init_repo, run, board

@pytest.mark.parametrize("change,accepted", [
 ("unrelated", True), ("other-index-entry", True),
 ("project", False), ("selected-index-entry", False),
 ("same-tree-revert", False), ("dirty-with-unrelated-head", False),
 ("new-ref", False), ("deleted-ref", False), ("branch-identity", False),
 ("replacement", False), ("custom-replacement", False),
 ("shallow", False), ("graft", False), ("project-target", False),
 ("new-worktree", False),
])
def test_selection_race_preserves_exact_project_causes(tmp_path, monkeypatch, change, accepted):
    repo, project = init_repo(tmp_path)
    board(tmp_path / "board", [])
    index = repo / "projects/index.yaml"
    index.write_text(index.read_text() + "- id: beta\n  status: active\n")
    run("git", "add", "projects/index.yaml", cwd=repo)
    run("git", "commit", "-m", "Add fixture registry peer", cwd=repo)
    run("git", "branch", "retained-alias", cwd=repo)
    if change == "custom-replacement":
        monkeypatch.setenv("GIT_REPLACE_REF_BASE", "refs/fixture-replacements/")
    original = state._latest_session_date
    fired = False
    observed = {}

    def commit(path, value):
        path.write_text(value)
        run("git", "add", str(path.relative_to(repo)), cwd=repo)
        run("git", "commit", "-m", "Fixture concurrent update", cwd=repo)

    def snapshot():
        heads = state._worktrees(repo)
        refs = state._project_refs(repo)
        head = run("git", "rev-parse", "HEAD", cwd=repo)
        trees = state._trees_at(repo, [head], "projects/alpha")
        return {"worktrees": [[str(p), h, b] for p, h, b in heads],
                "refs": refs, "history": state._project_history_frontier(repo),
                "head": head, "project_metadata": state._project_metadata_at(
                    repo, trees, "projects/alpha")[head],
                "entry": state._index_entry(index.read_text(), "alpha")}

    def race(path):
        nonlocal fired
        answer = original(path)
        if fired:
            return answer
        fired = True
        observed["before"] = snapshot()
        if change in {"unrelated", "dirty-with-unrelated-head"}:
            commit(repo / "other.txt", "unrelated project change\n")
            if change == "dirty-with-unrelated-head":
                (project / "CONTEXT.md").write_text("unattributed selected content\n")
        elif change == "other-index-entry":
            commit(index, index.read_text().replace("id: beta\n  status: active",
                                                   "id: beta\n  status: paused"))
        elif change == "selected-index-entry":
            commit(index, index.read_text().replace("id: alpha\n  status: active",
                                                   "id: alpha\n  status: paused"))
        elif change == "project":
            commit(project / "CONTEXT.md", "selected project changed\n")
        elif change == "same-tree-revert":
            prior = (project / "CONTEXT.md").read_text()
            commit(project / "CONTEXT.md", "temporary selected version\n")
            commit(project / "CONTEXT.md", prior)
        elif change == "new-ref":
            run("git", "branch", "arrived", cwd=repo)
        elif change == "deleted-ref":
            run("git", "branch", "-D", "retained-alias", cwd=repo)
        elif change == "branch-identity":
            run("git", "branch", "-m", "renamed", cwd=repo)
        elif change in {"replacement", "custom-replacement"}:
            old = observed["before"]["head"]
            commit(project / "CONTEXT.md", "replacement project\n")
            newer = run("git", "rev-parse", "HEAD", cwd=repo)
            run("git", "reset", "--hard", old, cwd=repo)
            run("git", "replace", old, newer, cwd=repo)
        elif change == "shallow":
            (repo / ".git/shallow").write_text(observed["before"]["head"] + "\n")
        elif change == "graft":
            (repo / ".git/info/grafts").write_text(observed["before"]["head"] + "\n")
        elif change == "project-target":
            replacement = tmp_path / "replacement"
            shutil.copytree(project, replacement)
            project.rename(tmp_path / "retained-original")
            project.symlink_to(replacement, target_is_directory=True)
        elif change == "new-worktree":
            run("git", "worktree", "add", "--detach", str(tmp_path / "arrived"), cwd=repo)
        observed["after"] = snapshot()
        return answer

    healthy = _managed_resolve(repo, [project], tmp_path)
    assert healthy.status == "PASS", healthy.issues
    observed["healthy_status"] = healthy.status
    monkeypatch.setattr(state, "_latest_session_date", race)
    # Deliberately exercise the managed owner, not outer registry enrollment.
    with state.record_transaction.managed(project):
        report = state._resolve_project_unlocked(
            "alpha", index, fetch=False, repo_guard_root=tmp_path / "guard",
            checkpoint_receipt_root=tmp_path / "checkpoints",
            coordination_board=tmp_path / "board", pointer=tmp_path / "pointer")
    assert fired
    observed.update(change=change, status=report.status, issues=report.issues,
                    selected_path=report.selected_path,
                    expected="PASS" if accepted else "UNKNOWN")
    if destination := os.environ.get("SELECTION_CAUSAL_RECEIPTS"):
        with open(destination, "a") as stream:
            stream.write(json.dumps(observed, sort_keys=True) + "\n")
    if accepted:
        assert observed["before"]["project_metadata"] == observed["after"]["project_metadata"]
        assert observed["before"]["entry"] == observed["after"]["entry"]
        assert report.status == "PASS"
        assert report.selected_path == str(project)
    else:
        assert report.status == "UNKNOWN"
        assert report.selected_path is None and report.selected_head is None
        assert any("changed during" in issue for issue in report.issues)

def _managed_resolve(repo, projects, tmp_path):
    from contextlib import ExitStack
    with ExitStack() as stack:
        for project in projects:
            stack.enter_context(state.record_transaction.managed(project))
        return state._resolve_project_unlocked(
            "alpha", repo / "projects/index.yaml", fetch=False,
            repo_guard_root=tmp_path / "guard", checkpoint_receipt_root=tmp_path / "receipts",
            coordination_board=tmp_path / "board", pointer=tmp_path / "pointer")


def test_unrelated_churn_during_equivalence_read_is_not_retried(tmp_path, monkeypatch):
    repo, project = init_repo(tmp_path)
    board(tmp_path / "board", [])
    original_date = state._latest_session_date
    original_metadata = state._project_metadata_at
    reads = 0
    def advance(label):
        (repo / "unrelated").write_text(label)
        run("git", "add", "unrelated", cwd=repo)
        run("git", "commit", "-m", "Unrelated fixture update", cwd=repo)
    def date(path):
        result = original_date(path)
        advance("first")
        return result
    def metadata(*args, **kwargs):
        nonlocal reads
        reads += 1
        result = original_metadata(*args, **kwargs)
        if reads == 2:
            advance("second")
        return result
    monkeypatch.setattr(state, "_latest_session_date", date)
    monkeypatch.setattr(state, "_project_metadata_at", metadata)
    report = _managed_resolve(repo, [project], tmp_path)
    assert report.status == "UNKNOWN" and report.selected_path is None
    assert reads == 2  # There is no retry of a moving selection.


def test_unrelated_linked_worktree_advance_keeps_selection(tmp_path, monkeypatch):
    repo, project = init_repo(tmp_path)
    board(tmp_path / "board", [])
    peer = tmp_path / "peer"
    run("git", "worktree", "add", "-b", "peer", str(peer), cwd=repo)
    other = peer / "projects/alpha"
    original = state._latest_session_date
    def date(path):
        result = original(path)
        (peer / "unrelated").write_text("other project")
        run("git", "add", "unrelated", cwd=peer)
        run("git", "commit", "-m", "Unrelated fixture update", cwd=peer)
        return result
    monkeypatch.setattr(state, "_latest_session_date", date)
    report = _managed_resolve(repo, [project, other], tmp_path)
    assert report.status == "PASS" and report.selected_path == str(project)


@pytest.mark.parametrize("advance", [True, False])
def test_existing_ref_requires_causal_equivalence_and_forward_history(tmp_path, monkeypatch, advance):
    import subprocess
    repo, project = init_repo(tmp_path)
    board(tmp_path / "board", [])
    old = run("git", "rev-parse", "HEAD", cwd=repo)
    tree = run("git", "rev-parse", "HEAD^{tree}", cwd=repo)
    new = subprocess.run(["git", "commit-tree", tree, "-p", old], cwd=repo,
                         input="unrelated empty commit\n", text=True,
                         check=True, capture_output=True).stdout.strip()
    run("git", "update-ref", "refs/heads/movable", old if advance else new, cwd=repo)
    original = state._latest_session_date
    def date(path):
        result = original(path)
        run("git", "update-ref", "refs/heads/movable", new if advance else old, cwd=repo)
        return result
    monkeypatch.setattr(state, "_latest_session_date", date)
    report = _managed_resolve(repo, [project], tmp_path)
    assert report.status == ("PASS" if advance else "UNKNOWN")
    if not advance:
        assert report.selected_path is None

@pytest.mark.parametrize("timing", ["after-candidates", "during-first-dirty"])
@pytest.mark.parametrize("change", ["appearance", "parent-replacement"])
def test_missing_worktree_project_cannot_appear_during_unrelated_advance(tmp_path, monkeypatch, change, timing):
    import subprocess
    repo, project = init_repo(tmp_path)
    board(tmp_path / "board", [])
    empty_tree = subprocess.run(["git", "hash-object", "-t", "tree", "--stdin"],
        cwd=repo, input="", text=True, check=True, capture_output=True).stdout.strip()
    empty_commit = subprocess.run(["git", "commit-tree", empty_tree],
        cwd=repo, input="empty fixture history\n", text=True,
        check=True, capture_output=True).stdout.strip()
    run("git", "update-ref", "refs/heads/empty-peer", empty_commit, cwd=repo)
    peer = tmp_path / "empty-peer"
    run("git", "worktree", "add", str(peer), "empty-peer", cwd=repo)
    (peer / "projects").mkdir()
    assert not (peer / "projects/alpha").exists()
    healthy = _managed_resolve(repo, [project], tmp_path)
    assert healthy.status == "PASS", healthy.issues
    original = state._latest_session_date
    def date(path):
        result = original(path)
        if change == "appearance":
            appeared = peer / "projects/alpha"
            appeared.mkdir()
            (appeared / "CONTEXT.md").write_text("new unadmitted retained project\n")
        else:
            (peer / "projects").rename(peer / "retained-projects")
            (peer / "projects").mkdir()
        (peer / "unrelated").write_text("unrelated committed change\n")
        run("git", "add", "unrelated", cwd=peer)
        run("git", "commit", "-m", "Unrelated fixture advance", cwd=peer)
        return result
    if timing == "after-candidates":
        monkeypatch.setattr(state, "_latest_session_date", date)
    else:
        original_dirty = state._dirty_project_files
        fired = False
        def dirty(*args, **kwargs):
            nonlocal fired
            result = original_dirty(*args, **kwargs)
            if not fired:
                fired = True
                date(project)
            return result
        monkeypatch.setattr(state, "_dirty_project_files", dirty)
    report = _managed_resolve(repo, [project], tmp_path)
    assert report.status == "UNKNOWN"
    assert report.selected_path is None and report.selected_head is None
    if change == "appearance" and timing == "during-first-dirty":
        assert report.issues == ["project worktree appeared after managed read admission"]
    else:
        assert any("changed during" in issue for issue in report.issues)
