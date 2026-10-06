"""Every declared repository lands in exactly one state, and nothing is pulled over
uncommitted work. Real git repositories in a scratch directory, no network."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "repo_state.py"


@pytest.fixture(autouse=True)
def git_identity(tmp_path, monkeypatch):
    config = tmp_path / "gitconfig"
    config.write_text("[user]\n\temail = test@example.com\n\tname = test\n[init]\n\tdefaultBranch = main\n")
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(config))
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")


def git(path: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(path), *args], check=True, capture_output=True, text=True).stdout.strip()


def commit(path: Path, name: str) -> None:
    (path / name).write_text(name, encoding="utf-8")
    git(path, "add", name)
    git(path, "commit", "-qm", name)


def origin_and_clone(tmp_path: Path, name: str) -> tuple[Path, Path]:
    origin = tmp_path / "origins" / name
    origin.mkdir(parents=True)
    git(origin, "init", "-q")
    commit(origin, "first")
    git(origin, "branch", "develop")
    clone = tmp_path / "ws" / name
    subprocess.run(["git", "clone", "-q", str(origin), str(clone)], check=True)
    git(clone, "branch", "--track", "develop", "origin/develop")
    return origin, clone


def run(*args: str) -> tuple[int, dict]:
    done = subprocess.run([sys.executable, str(SCRIPT), *args, "--json"], capture_output=True, text=True,
                          env={**os.environ})
    assert done.stdout, done.stderr
    report = json.loads(done.stdout)
    return done.returncode, {r["name"]: r for r in report["repositories"]}


def manifest(tmp_path: Path, body: str) -> Path:
    (tmp_path / "ws" / ".agents").mkdir(parents=True, exist_ok=True)
    (tmp_path / "ws" / ".agents" / "repos.yaml").write_text(body, encoding="utf-8")
    return tmp_path / "ws"


def test_every_declared_repo_has_exactly_one_state(tmp_path: Path) -> None:
    origin, _ = origin_and_clone(tmp_path, "behind")
    commit(origin, "second")
    _, current = origin_and_clone(tmp_path, "current")
    git(current, "branch", "--unset-upstream")
    root = manifest(tmp_path, "workspace: demo\nrepos:\n"
                              "  - name: behind\n    ritual_sync: yes\n    default_branches: [main, develop]\n"
                              "  - name: current\n    ritual_sync: yes\n"
                              "  - name: absent\n    ritual_sync: yes\n"
                              "  - name: skipped\n    ritual_sync: no\n")
    code, repos = run("--workspace-root", str(root), "--fetch")
    assert {n: r["state"] for n, r in repos.items()} == {
        "behind": "BEHIND", "current": "BLIND", "absent": "UNREACHABLE", "skipped": "EXCLUDED"}
    assert code == 2  # BLIND and UNREACHABLE are never a clean run


def test_without_fetch_a_level_branch_is_cached_not_current(tmp_path: Path) -> None:
    origin_and_clone(tmp_path, "one")
    root = manifest(tmp_path, "repos:\n  - name: one\n    ritual_sync: yes\n")
    assert run("--workspace-root", str(root))[1]["one"]["state"] == "CACHED"
    assert run("--workspace-root", str(root), "--fetch")[1]["one"]["state"] == "CURRENT"


def test_a_dormant_workspace_syncs_nothing(tmp_path: Path) -> None:
    origin_and_clone(tmp_path, "one")
    root = manifest(tmp_path, "status: dormant\nrepos:\n  - name: one\n    ritual_sync: yes\n")
    assert run("--workspace-root", str(root))[1]["one"]["state"] == "EXCLUDED"


def test_duplicate_or_missing_names_are_refused(tmp_path: Path) -> None:
    root = manifest(tmp_path, "repos:\n  - name: one\n  - name: one\n")
    done = subprocess.run([sys.executable, str(SCRIPT), "--workspace-root", str(root)], capture_output=True, text=True)
    assert done.returncode == 2 and "unique names" in done.stderr


def test_ff_forwards_clean_branches_checked_out_or_not(tmp_path: Path) -> None:
    origin, clone = origin_and_clone(tmp_path, "one")
    commit(origin, "second")
    git(origin, "checkout", "-q", "develop")
    commit(origin, "dev-two")
    root = manifest(tmp_path, "repos:\n  - name: one\n    ritual_sync: yes\n    default_branches: [main, develop]\n")
    code, repos = run("--workspace-root", str(root), "--fetch", "--ff")
    assert repos["one"]["state"] == "CURRENT" and code == 0
    assert git(clone, "rev-parse", "main") == git(origin, "rev-parse", "main")
    assert git(clone, "rev-parse", "develop") == git(origin, "rev-parse", "develop")
    assert (clone / "second").is_file()


def test_uncommitted_changes_are_listed_and_never_pulled_over(tmp_path: Path) -> None:
    """FLEET-AC-10: arriving on a Mac with local edits refuses the pull and lists them."""
    origin, clone = origin_and_clone(tmp_path, "one")
    commit(origin, "second")
    (clone / "first").write_text("local edit", encoding="utf-8")
    before = git(clone, "rev-parse", "HEAD")
    root = manifest(tmp_path, "repos:\n  - name: one\n    ritual_sync: yes\n")
    code, repos = run("--workspace-root", str(root), "--fetch", "--ff")
    assert repos["one"]["state"] == "DIRTY" and code == 1
    assert repos["one"]["dirty"] == [" M first"]
    assert git(clone, "rev-parse", "HEAD") == before
    assert (clone / "first").read_text(encoding="utf-8") == "local edit"


def test_ahead_or_diverged_is_a_decision_and_skip_leaves_a_repo_alone(tmp_path: Path) -> None:
    origin, clone = origin_and_clone(tmp_path, "one")
    commit(clone, "local-only")
    root = manifest(tmp_path, "repos:\n  - name: one\n    ritual_sync: yes\n")
    code, repos = run("--workspace-root", str(root), "--fetch", "--ff")
    assert repos["one"]["state"] == "DECISION" and repos["one"]["branches"][0]["ahead"] == 1 and code == 1
    commit(origin, "remote-only")
    _, repos = run("--workspace-root", str(root), "--fetch", "--ff")
    branch = repos["one"]["branches"][0]
    assert repos["one"]["state"] == "DECISION" and (branch["ahead"], branch["behind"]) == (1, 1)
    held_origin, held = origin_and_clone(tmp_path, "held")
    commit(held_origin, "second")
    root = manifest(tmp_path, "repos:\n  - name: held\n    ritual_sync: yes\n")
    _, repos = run("--workspace-root", str(root), "--fetch", "--ff", "--skip", "held")
    assert repos["held"]["state"] == "BEHIND" and not (held / "second").exists()


def test_discover_finds_every_repo_and_reports_a_detached_head(tmp_path: Path) -> None:
    _, one = origin_and_clone(tmp_path, "one")
    _, two = origin_and_clone(tmp_path, "two")
    git(two, "checkout", "-q", "--detach")
    nested = tmp_path / "ws" / "group" / "three"
    nested.mkdir(parents=True)
    git(nested, "init", "-q")
    git(one, "worktree", "add", "-q", str(tmp_path / "ws" / "group" / "linked"), "-b", "side")
    code, repos = run("--discover", str(tmp_path / "ws"))
    assert set(repos) == {"one", "two", "group/three"}  # a linked worktree is its repo's, not a second repo
    assert repos["two"]["state"] == "BLIND" and repos["group/three"]["state"] == "BLIND"
    assert code == 2
