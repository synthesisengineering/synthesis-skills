"""Real Git controls for bounded operator-resolution work, not wall-clock claims."""
from __future__ import annotations

from collections import Counter
from pathlib import Path

import pytest

import project_state as state
from test_project_state import init_repo, commit_version, run


def traced(monkeypatch):
    calls = []
    original = state._run

    def record(repo, *args, **kwargs):
        calls.append((str(repo), args))
        return original(repo, *args, **kwargs)

    monkeypatch.setattr(state, "_run", record)
    return calls


def test_aliases_do_not_repeat_immutable_project_history(tmp_path, monkeypatch):
    repo, project = init_repo(tmp_path)
    for number in range(30):
        run("git", "branch", f"alias-{number}", cwd=repo)
    calls = traced(monkeypatch)
    report = state.resolve_project("alpha", repo / "projects/index.yaml", fetch=False)
    assert report.status == "PASS"
    assert report.selected_path == str(project)
    refs = [item for item in report.candidates if item.source == "ref"]
    assert len(refs) == 32  # Every alias remains visible, including main and origin/main.
    assert len({item.project_tree for item in refs}) == 1
    history = [args for _, args in calls if args[0] in {"log", "show"} or
               (args[0] == "rev-parse" and ":projects/alpha" in " ".join(args))]
    assert len(history) <= 3, history
    assert not any(args[0] in {"fetch", "update-ref", "reset", "merge", "checkout"} for _, args in calls)


def test_read_memo_is_discarded_before_next_request(tmp_path, monkeypatch):
    repo, project = init_repo(tmp_path)
    first = state.resolve_project("alpha", repo / "projects/index.yaml", fetch=False)
    new_head = commit_version(repo, project, "2.0.0")
    second = state.resolve_project("alpha", repo / "projects/index.yaml", fetch=False)
    assert second.status == "PASS"
    assert second.selected_head == new_head != first.selected_head
    assert second.selected_tree != first.selected_tree


@pytest.mark.parametrize("mutation", ["head", "ref", "worktree", "replace"])
def test_moving_git_selection_is_unresolved_not_stale_pass(tmp_path, monkeypatch, mutation):
    repo, project = init_repo(tmp_path)
    old = run("git", "rev-parse", "HEAD", cwd=repo)
    run("git", "checkout", "-b", "newer", cwd=repo)
    newer = commit_version(repo, project, "2.0.0")
    run("git", "checkout", "main", cwd=repo)
    original = state._run
    fired = False

    def race(path, *args, **kwargs):
        nonlocal fired
        result = original(path, *args, **kwargs)
        if args[0] == "log" and not fired:
            fired = True
            if mutation == "head":
                run("git", "reset", "--hard", newer, cwd=repo)
            elif mutation == "ref":
                run("git", "update-ref", "refs/heads/moved-during-read", newer, cwd=repo)
            elif mutation == "worktree":
                run("git", "worktree", "add", "--detach", str(tmp_path / "arrived"), old, cwd=repo)
            else:
                run("git", "replace", old, newer, cwd=repo)
        return result

    monkeypatch.setattr(state, "_run", race)
    report = state.resolve_project("alpha", repo / "projects/index.yaml", fetch=False)
    assert fired
    assert report.status == "UNKNOWN"
    assert report.selected_path is None
    assert report.selected_head is None
    assert any("changed during" in issue for issue in report.issues)


def test_aliases_cannot_hide_divergent_causal_states(tmp_path, monkeypatch):
    repo, project = init_repo(tmp_path)
    run("git", "checkout", "-b", "diverged", cwd=repo)
    commit_version(repo, project, "2.0.0")
    for number in range(8):
        run("git", "branch", f"alias-{number}", cwd=repo)
    run("git", "checkout", "main", cwd=repo)
    commit_version(repo, project, "3.0.0")
    calls = traced(monkeypatch)
    report = state.resolve_project("alpha", repo / "projects/index.yaml", fetch=False)
    assert report.status == "CONFLICT"
    pairs = [args for _, args in calls if args[0] == "merge-base"]
    assert max(Counter(pairs).values(), default=0) <= 1


def test_each_physical_worktree_keeps_its_fresh_dirty_scan(tmp_path, monkeypatch):
    repo, project = init_repo(tmp_path)
    other = tmp_path / "other"
    run("git", "worktree", "add", "--detach", str(other), cwd=repo)
    dirty = other / "projects/alpha/CONTEXT.md"
    dirty.write_text(dirty.read_text() + "unattributed retained work\n")
    calls = traced(monkeypatch)
    report = state.resolve_project("alpha", repo / "projects/index.yaml", fetch=False)
    assert report.status == "CONFLICT"
    assert report.selected_path is None
    assert "unattributed retained work" in dirty.read_text()
    scanned = {Path(path) for path, args in calls if args[0] == "status"}
    assert {repo, other} <= scanned


@pytest.mark.parametrize("mutation", ["shallow", "grafts", "custom-replace"])
def test_moving_history_interpretation_invalidates_pinned_commit_read(tmp_path, monkeypatch, mutation):
    repo, project = init_repo(tmp_path)
    old = run("git", "rev-parse", "HEAD", cwd=repo)
    newer = commit_version(repo, project, "2.0.0")
    if mutation == "custom-replace":
        monkeypatch.setenv("GIT_REPLACE_REF_BASE", "refs/fixture-replacements/")
    original = state._run
    fired = False

    def race(path, *args, **kwargs):
        nonlocal fired
        result = original(path, *args, **kwargs)
        if args[0] == "log" and not fired:
            fired = True
            if mutation == "shallow":
                (repo / ".git/shallow").write_text(newer + "\n")
            elif mutation == "grafts":
                (repo / ".git/info/grafts").write_text(newer + "\n")
            else:
                run("git", "replace", old, newer, cwd=repo)
        return result

    monkeypatch.setattr(state, "_run", race)
    report = state.resolve_project("alpha", repo / "projects/index.yaml", fetch=False)
    assert fired
    assert report.status == "UNKNOWN"
    assert report.selected_path is None and report.selected_head is None
    assert any("changed during" in issue for issue in report.issues)
