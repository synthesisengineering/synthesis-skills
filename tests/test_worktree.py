"""R2.7 worktrees: create under a claim, retire only what nothing would lose, land merged work."""

import os
import subprocess
import time
from types import SimpleNamespace

import pytest

from synthesis import board, worktree


def git(path, *args):
    return subprocess.run(["git", "-C", str(path), *args], check=True, capture_output=True, text=True).stdout.strip()


def commit(path, name, text, message=None):
    target = os.path.join(str(path), name)
    os.makedirs(os.path.dirname(target), exist_ok=True)
    with open(target, "w", encoding="utf-8") as handle:
        handle.write(text)
    git(path, "add", name)
    git(path, "commit", "-q", "-m", message or f"add {name}")
    return git(path, "rev-parse", "HEAD")


def exists(path, ref):
    return subprocess.run(["git", "-C", str(path), "rev-parse", "--verify", "--quiet", ref],
                          capture_output=True).returncode == 0


@pytest.fixture
def repo(tmp_path):
    """A remote with one commit on main, the main checkout cloned from it, and a second clone
    that stands in for another machine or a merge made on the hosting service."""
    root = os.path.realpath(str(tmp_path))
    remote, seed = f"{root}/remote.git", f"{root}/seed"
    git(root, "init", "-q", "--bare", "-b", "main", remote)
    git(root, "init", "-q", "-b", "main", seed)
    commit(seed, "README.md", "hello\n")
    git(seed, "push", "-q", remote, "main")
    git(root, "clone", "-q", remote, f"{root}/main")
    git(root, "clone", "-q", remote, f"{root}/elsewhere")
    return SimpleNamespace(root=root, remote=remote, main=f"{root}/main", elsewhere=f"{root}/elsewhere",
                           wt=f"{root}/worktrees/feature")


def merged_feature(repo, session="S1"):
    """A worktree whose one commit is on the remote's main (a fast-forward merge) and its own branch."""
    worktree.create(repo.main, repo.wt, "feature", session_id=session)
    commit(repo.wt, "feature.txt", "work\n")
    git(repo.wt, "push", "-q", "-u", "origin", "feature")
    git(repo.wt, "push", "-q", "origin", "HEAD:main")
    return repo.wt


# create

def test_create_claims_the_path_for_this_session_then_adds_the_worktree(repo):
    out = worktree.create(repo.main, repo.wt, "feature", session_id="S1")
    assert board.load("S1").claims == [f"{repo.wt}/**"]
    assert git(repo.wt, "branch", "--show-current") == "feature"
    assert git(repo.wt, "rev-parse", "HEAD") == git(repo.main, "rev-parse", "HEAD")
    assert "Created worktree" in out and "temporary directory" in out


def test_create_starts_a_new_branch_from_the_given_ref(repo):
    first = git(repo.main, "rev-parse", "HEAD")
    commit(repo.main, "later.txt", "later\n")
    worktree.create(repo.main, repo.wt, "feature", first, session_id="S1")
    assert git(repo.wt, "rev-parse", "HEAD") == first


def test_create_refuses_a_path_another_live_session_claims_and_changes_nothing(repo):
    board.claim("S2", [f"{repo.root}/worktrees/**"], project="beta", goal="sorting worktrees")
    with pytest.raises(worktree.Refused, match="held by S2 .*sorting worktrees"):
        worktree.create(repo.main, repo.wt, "feature", session_id="S1")
    assert not os.path.exists(repo.wt)
    assert not exists(repo.main, "refs/heads/feature")
    assert board.load("S1") is None


def test_create_takes_over_a_stale_claim_only_when_asked_and_tells_the_holder(repo):
    board.claim("S2", [f"{repo.wt}/**"])
    old = board.load("S2")
    old.seen = time.time() - board.STALE_SECONDS - 1
    board.save(old)
    with pytest.raises(worktree.Refused, match="stale"):
        worktree.create(repo.main, repo.wt, "feature", session_id="S1")
    worktree.create(repo.main, repo.wt, "feature", session_id="S1", take=True)
    assert board.load("S2").claims == [] and "Took over" in board.inbox("S2")[0]["text"]


def test_create_releases_its_claim_when_git_refuses(repo):
    with pytest.raises(worktree.Refused, match="claim was released"):
        worktree.create(repo.main, repo.wt, "main", session_id="S1")  # main is checked out in the main checkout
    assert board.load("S1").claims == []


def test_create_checks_out_an_existing_branch_only_without_a_start_point(repo):
    git(repo.main, "branch", "existing")
    with pytest.raises(worktree.Refused, match="already exists"):
        worktree.create(repo.main, repo.wt, "existing", "HEAD", session_id="S1")
    assert "existing branch existing" in worktree.create(repo.main, repo.wt, "existing", session_id="S1")


@pytest.mark.parametrize("problem", ["no session", "relative path", "occupied path", "not the repo top",
                                     "bad branch", "bad start"])
def test_create_refuses_unclear_requests(repo, problem):
    os.makedirs(f"{repo.main}/sub")
    args = {"repo": repo.main, "path": repo.wt, "branch": "feature", "ref": None, "session_id": "S1"}
    if problem == "no session":
        args["session_id"] = ""
    elif problem == "relative path":
        args["path"] = "worktrees/feature"
    elif problem == "occupied path":
        os.makedirs(repo.wt)
        open(f"{repo.wt}/keep.txt", "w").close()
    elif problem == "not the repo top":
        args["repo"] = f"{repo.main}/sub"
    elif problem == "bad branch":
        args["branch"] = "-x"
    else:
        args["ref"] = "no-such-commit"
    with pytest.raises(worktree.Refused):
        worktree.create(args.pop("repo"), args.pop("path"), args.pop("branch"), args.pop("ref"), **args)
    assert not exists(repo.main, "refs/heads/feature")
    assert board.load("S1") is None or board.load("S1").claims == []


# retire

def test_retire_removes_the_worktree_its_branch_and_only_this_sessions_claims_under_it(repo):
    merged_feature(repo)
    board.claim("S1", [f"{repo.wt}/notes.md", f"{repo.root}/elsewhere/**", f"{repo.root}/worktrees/**"])
    out = worktree.retire(repo.wt, session_id="S1")
    assert not os.path.exists(repo.wt)
    assert not exists(repo.main, "refs/heads/feature")
    assert exists(repo.main, "refs/remotes/origin/feature")  # the remote branch stays unless asked
    assert board.load("S1").claims == [f"{repo.root}/elsewhere/**", f"{repo.root}/worktrees/**"]
    assert "merged" in out and "Released" in out


def test_retire_refuses_tracked_changes_and_untracked_files_and_names_them(repo):
    merged_feature(repo)
    with open(f"{repo.wt}/feature.txt", "a") as handle:
        handle.write("more\n")
    open(f"{repo.wt}/scratch.txt", "w").close()
    with pytest.raises(worktree.Refused, match=r"(?s)not clean.*feature\.txt.*scratch\.txt"):
        worktree.retire(repo.wt, session_id="S1")
    assert os.path.exists(f"{repo.wt}/scratch.txt") and exists(repo.main, "refs/heads/feature")


def test_retire_refuses_ignored_files_removal_would_destroy_except_pycache(repo):
    worktree.create(repo.main, repo.wt, "feature", session_id="S1")
    commit(repo.wt, ".gitignore", "__pycache__/\n*.db\nbuild/\n")
    git(repo.wt, "push", "-q", "origin", "HEAD:main")
    os.makedirs(f"{repo.wt}/pkg/__pycache__")
    open(f"{repo.wt}/pkg/__pycache__/mod.cpython-39.pyc", "w").close()
    open(f"{repo.wt}/pkg/data.db", "w").close()
    with pytest.raises(worktree.Refused, match="pkg/data.db") as refusal:
        worktree.retire(repo.wt, session_id="S1")
    assert "__pycache__" not in str(refusal.value)
    os.remove(f"{repo.wt}/pkg/data.db")
    os.makedirs(f"{repo.wt}/build/__pycache__")  # an ignored folder is judged whole, even with a cache inside
    open(f"{repo.wt}/build/output.bin", "w").close()
    with pytest.raises(worktree.Refused, match="build/"):
        worktree.retire(repo.wt, session_id="S1")
    subprocess.run(["rm", "-r", f"{repo.wt}/build"], check=True)
    worktree.retire(repo.wt, session_id="S1")
    assert not os.path.exists(repo.wt)


def test_retire_refuses_work_that_is_not_on_the_remote_default_branch(repo):
    worktree.create(repo.main, repo.wt, "feature", session_id="S1")
    commit(repo.wt, "feature.txt", "work\n")
    git(repo.wt, "push", "-q", "origin", "feature")  # pushed, but not merged
    with pytest.raises(worktree.Refused, match="not merged into origin/main"):
        worktree.retire(repo.wt, session_id="S1")
    git(repo.main, "merge", "-q", "--ff-only", "feature")  # merged only in the local checkout
    with pytest.raises(worktree.Refused, match="not merged into origin/main"):
        worktree.retire(repo.wt, session_id="S1")
    assert os.path.exists(repo.wt) and exists(repo.main, "refs/heads/feature")


def test_retire_fetches_first_so_a_merge_made_elsewhere_counts(repo):
    worktree.create(repo.main, repo.wt, "feature", session_id="S1")
    commit(repo.wt, "feature.txt", "work\n")
    git(repo.wt, "push", "-q", "origin", "feature")
    git(repo.elsewhere, "fetch", "-q", "origin")
    git(repo.elsewhere, "merge", "-q", "--ff-only", "origin/feature")
    git(repo.elsewhere, "push", "-q", "origin", "main")
    assert git(repo.main, "rev-parse", "origin/main") != git(repo.wt, "rev-parse", "HEAD")  # stale until fetched
    worktree.retire(repo.wt, session_id="S1")
    assert not os.path.exists(repo.wt)


def squash_merge_elsewhere(repo):
    git(repo.elsewhere, "fetch", "-q", "origin")
    git(repo.elsewhere, "merge", "-q", "--squash", "origin/feature")
    git(repo.elsewhere, "commit", "-q", "-m", "squash feature")
    git(repo.elsewhere, "push", "-q", "origin", "main")


def test_retire_accepts_a_squash_merge_by_identical_tree(repo):
    worktree.create(repo.main, repo.wt, "feature", session_id="S1")
    commit(repo.wt, "a.txt", "a\n")
    commit(repo.wt, "b.txt", "b\n")
    git(repo.wt, "push", "-q", "origin", "feature")
    squash_merge_elsewhere(repo)
    out = worktree.retire(repo.wt, session_id="S1")
    assert "identical tree" in out and not exists(repo.main, "refs/heads/feature")


def test_retire_accepts_a_squash_merge_after_the_default_branch_moved_on(repo):
    worktree.create(repo.main, repo.wt, "feature", session_id="S1")
    commit(repo.wt, "a.txt", "a\n")
    git(repo.wt, "push", "-q", "origin", "feature")
    squash_merge_elsewhere(repo)
    commit(repo.elsewhere, "other.txt", "another session's work\n")
    git(repo.elsewhere, "push", "-q", "origin", "main")
    assert "content already in the default branch" in worktree.retire(repo.wt, session_id="S1")


def test_retire_refuses_a_squash_merge_that_left_part_of_the_work_out(repo):
    worktree.create(repo.main, repo.wt, "feature", session_id="S1")
    commit(repo.wt, "a.txt", "a\n")
    git(repo.wt, "push", "-q", "origin", "feature")
    squash_merge_elsewhere(repo)
    commit(repo.wt, "b.txt", "written after the merge\n")
    with pytest.raises(worktree.Refused, match="not merged"):
        worktree.retire(repo.wt, session_id="S1")


def test_retire_refuses_the_main_checkout(repo):
    with pytest.raises(worktree.Refused, match="main checkout"):
        worktree.retire(repo.main, session_id="S1")


def test_retire_refuses_when_the_current_directory_is_inside_the_worktree(repo, monkeypatch):
    merged_feature(repo)
    os.makedirs(f"{repo.wt}/docs")
    monkeypatch.chdir(f"{repo.wt}/docs")
    with pytest.raises(worktree.Refused, match="current directory"):
        worktree.retire(repo.wt, session_id="S1")
    assert os.path.exists(repo.wt)


def test_retire_refuses_a_worktree_inside_another_live_sessions_claim(repo):
    merged_feature(repo, session="S2")
    board.touch("S2", goal="reviewing the feature")
    with pytest.raises(worktree.Refused, match="held by S2 .*reviewing the feature"):
        worktree.retire(repo.wt, session_id="S1")
    assert os.path.exists(repo.wt)
    stale = board.load("S2")
    stale.seen = time.time() - board.STALE_SECONDS - 1
    board.save(stale)
    out = worktree.retire(repo.wt, session_id="S1")  # a stale claim does not hold the tree
    assert not os.path.exists(repo.wt) and "stale claims of S2" in out
    assert board.load("S2").claims == [] and "Retired worktree" in board.inbox("S2")[0]["text"]
    worktree.create(repo.main, repo.wt, "feature", session_id="S1")  # so the path is free again


def test_retire_refuses_a_locked_worktree(repo):
    merged_feature(repo)
    git(repo.main, "worktree", "lock", "--reason", "on a removable disk", repo.wt)
    with pytest.raises(worktree.Refused, match="locked .*removable disk"):
        worktree.retire(repo.wt, session_id="S1")


@pytest.mark.parametrize("path", ["", "relative/path", "missing", "subfolder", "plain folder"])
def test_retire_refuses_anything_that_is_not_a_worktree_top(repo, path, monkeypatch):
    merged_feature(repo)
    os.makedirs(f"{repo.wt}/sub")
    os.makedirs(f"{repo.root}/plain")
    monkeypatch.chdir(repo.main)  # an empty or relative path must never fall back to the current directory
    given = {"missing": f"{repo.root}/gone", "subfolder": f"{repo.wt}/sub",
             "plain folder": f"{repo.root}/plain"}.get(path, path)
    with pytest.raises(worktree.Refused):
        worktree.retire(given, session_id="S1")
    assert os.path.exists(repo.wt) and os.path.exists(repo.main)


def test_retire_with_a_detached_head_deletes_no_branch(repo):
    merged_feature(repo)
    git(repo.wt, "checkout", "-q", "--detach")
    out = worktree.retire(repo.wt, session_id="S1")
    assert "no branch to delete" in out and exists(repo.main, "refs/heads/feature")


def test_delete_remote_removes_the_remote_branch_at_the_verified_commit(repo):
    merged_feature(repo)
    out = worktree.retire(repo.wt, session_id="S1", delete_remote=True)
    assert "Deleted remote branch origin refs/heads/feature" in out
    assert not exists(repo.remote, "refs/heads/feature")


def test_delete_remote_keeps_a_remote_branch_that_moved_on(repo):
    merged_feature(repo)
    git(repo.elsewhere, "fetch", "-q", "origin")
    git(repo.elsewhere, "checkout", "-q", "-b", "feature", "origin/feature")
    moved = commit(repo.elsewhere, "late.txt", "pushed from another machine\n")
    git(repo.elsewhere, "push", "-q", "origin", "feature")
    out = worktree.retire(repo.wt, session_id="S1", delete_remote=True)
    assert "Kept remote branch" in out
    assert git(repo.remote, "rev-parse", "refs/heads/feature") == moved


def test_a_path_a_retirement_removed_can_be_created_again(repo):
    merged_feature(repo)
    worktree.retire(repo.wt, session_id="S1", delete_remote=True)
    worktree.create(repo.main, repo.wt, "feature", session_id="S1")
    assert git(repo.wt, "branch", "--show-current") == "feature"
    assert board.load("S1").claims == [f"{repo.wt}/**"]
    commit(repo.wt, "second.txt", "second round\n")
    git(repo.wt, "push", "-q", "-u", "origin", "feature")
    git(repo.wt, "push", "-q", "origin", "HEAD:main")
    worktree.retire(repo.wt, session_id="S1")
    assert not os.path.exists(repo.wt) and board.load("S1").claims == []


def test_retire_lands_the_merged_work_in_a_clean_main_checkout(repo):
    merged_feature(repo)
    out = worktree.retire(repo.wt, session_id="S1")
    assert "Landed" in out
    assert os.path.exists(f"{repo.main}/feature.txt")


# land

def advance_remote_main(repo):
    commit(repo.elsewhere, "news.txt", "from another session\n")
    git(repo.elsewhere, "push", "-q", "origin", "main")
    return git(repo.elsewhere, "rev-parse", "HEAD")


def test_land_fast_forwards_a_clean_main_checkout_that_is_behind(repo):
    head = advance_remote_main(repo)
    open(f"{repo.main}/untracked-note.md", "w").close()  # untracked files never block a fast-forward
    assert worktree.land(repo.main)[0]
    assert git(repo.main, "rev-parse", "HEAD") == head
    assert worktree.land(repo.main) == (True, f"Main checkout {repo.main} is already at origin/main ({head[:12]})")


def test_land_names_why_it_did_not_move_the_main_checkout(repo):
    before = git(repo.main, "rev-parse", "HEAD")
    advance_remote_main(repo)
    with open(f"{repo.main}/README.md", "a") as handle:
        handle.write("edit in progress\n")
    landed, why = worktree.land(repo.main)
    assert not landed and "uncommitted changes" in why and "README.md" in why
    git(repo.main, "checkout", "-q", "--", "README.md")
    commit(repo.main, "local.txt", "local only\n")
    landed, why = worktree.land(repo.main)
    assert not landed and "diverged" in why
    git(repo.main, "reset", "-q", "--hard", "origin/main")
    commit(repo.main, "ahead.txt", "not pushed\n")
    landed, why = worktree.land(repo.main)
    assert not landed and "ahead" in why
    git(repo.main, "checkout", "-q", "-b", "side", before)
    landed, why = worktree.land(repo.main)
    assert not landed and "is on side, not main" in why


def test_land_reports_a_fast_forward_that_would_overwrite_an_untracked_file(repo):
    advance_remote_main(repo)
    with open(f"{repo.main}/news.txt", "w") as handle:
        handle.write("my own notes\n")
    landed, why = worktree.land(repo.main)
    assert not landed and "fast-forward" in why
    assert open(f"{repo.main}/news.txt").read() == "my own notes\n"


def test_land_accepts_any_checkout_of_the_repository(repo):
    worktree.create(repo.main, repo.wt, "feature", session_id="S1")
    head = advance_remote_main(repo)
    assert worktree.land(repo.wt)[0] and git(repo.main, "rev-parse", "HEAD") == head


# command line

def test_main_uses_the_harness_session_and_reports_refusals(repo, monkeypatch, capsys):
    monkeypatch.setenv("SYNTHESIS_SESSION", "S7")
    assert worktree.main(["create", repo.main, repo.wt, "feature"]) == 0
    assert board.load("S7").claims == [f"{repo.wt}/**"]
    assert worktree.main(["--session", "S8", "create", repo.main, f"{repo.wt}/inner", "other"]) == 1
    assert "held by S7" in capsys.readouterr().err
    assert worktree.main(["retire", repo.wt]) == 0  # no commits of its own, so already on main
    assert board.load("S7").claims == []
    assert worktree.main(["land", repo.main]) == 0
    advance_remote_main(repo)
    with open(f"{repo.main}/README.md", "a") as handle:
        handle.write("edit in progress\n")
    assert worktree.main(["land", repo.main]) == 1
    assert "uncommitted changes" in capsys.readouterr().out
