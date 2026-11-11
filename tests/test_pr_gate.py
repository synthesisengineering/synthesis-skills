"""A repository that takes changes only through pull requests refuses a direct push to its default branch.

From 2026-10-01 to 2026-11-10 one private skills repository took 61 commits pushed straight to
`main` beside 35 merged pull requests; its instructions said "push every remote", and the
hosting plan offered no branch protection. With `pr_gated` in the config, the guard refuses a
push that would move a gated repository's default branch, the principal's code admits one exact
push, and the doctor names any commit that reached the branch without a pull request.
Committed before the code.
"""

import subprocess
from pathlib import Path

import pytest

from synthesis import doctor, guards

GATED = {"pr_gated": {"acme/skills": {"since": "2026-11-11"}}}


def git(where, *args, date="2026-11-12T10:00:00"):
    env = {"GIT_AUTHOR_DATE": date, "GIT_COMMITTER_DATE": date, "PATH": __import__("os").environ["PATH"],
           "HOME": str(where), "GIT_CONFIG_GLOBAL": __import__("os").environ["GIT_CONFIG_GLOBAL"], "GIT_CONFIG_NOSYSTEM": "1"}
    done = subprocess.run(["git", "-C", str(where), *args], capture_output=True, text=True, env=env)
    assert done.returncode == 0, done.stderr
    return done.stdout.strip()


def commit(where, name, date="2026-11-12T10:00:00"):
    (Path(where) / name).write_text(name, encoding="utf-8")
    git(where, "add", name)
    git(where, "commit", "-q", "-m", f"add {name}", date=date)
    return git(where, "rev-parse", "--short", "HEAD")


@pytest.fixture
def repo(tmp_path):
    """A clone of acme/skills on `main`, level with its remote, plus a second remote that is not gated."""
    remote, other, work = tmp_path / "acme" / "skills.git", tmp_path / "someone" / "fork.git", tmp_path / "ws" / "skills"
    for bare in (remote, other):
        bare.mkdir(parents=True)
        git(bare, "init", "-q", "--bare", "-b", "main")
    work.mkdir(parents=True)
    git(work, "init", "-q", "-b", "main")
    commit(work, "first", date="2026-11-10T09:00:00")
    git(work, "remote", "add", "origin", str(remote))
    git(work, "remote", "add", "fork", str(other))
    git(work, "push", "-q", "-u", "origin", "main")
    git(work, "remote", "set-head", "origin", "main")
    return work


@pytest.fixture(autouse=True)
def _principal(principal):
    global _approve
    _approve = principal


def push(repo, command, config=GATED, cwd=None):
    return guards.check("Bash", {"command": command}, config, cwd=str(cwd or repo))


@pytest.mark.parametrize("command", [
    "git push origin main", "git push", "git push origin HEAD:main", "git push origin HEAD", "git push origin +main",
    "git push origin refs/heads/main", "git push -u origin main", "git push --all", "git push --mirror origin",
    "git push origin :main", "git push --force-with-lease origin main", "git add -A && git commit -m x && git push origin main",
])
def test_a_push_that_moves_the_default_branch_is_refused_with_the_route(repo, command):
    commit(repo, "second")
    reason = push(repo, command)
    assert reason and "acme/skills" in reason and "pull request" in reason and "main" in reason


def test_a_branch_carrying_the_same_commits_to_the_default_branch_is_refused(repo):
    git(repo, "switch", "-q", "-c", "feature")
    commit(repo, "second")
    assert "pull request" in push(repo, "git push origin feature:main")
    assert push(repo, "git push -u origin feature") is None  # the pull-request route itself


@pytest.mark.parametrize("command", ["git push origin v1.0.0", "git push --tags", "git push origin --tags",
                                     "git push --dry-run origin main", "git push -n", "git push fork main"])
def test_tags_dry_runs_and_another_repository_pass(repo, command):
    commit(repo, "second")
    git(repo, "tag", "v1.0.0")
    assert push(repo, command) is None


def test_a_push_with_nothing_to_move_passes(repo):
    assert push(repo, "git push origin main") is None  # level with the remote, as after a merged pull request


def test_the_push_is_judged_where_it_runs(repo, tmp_path):
    commit(repo, "second")
    assert "pull request" in push(repo, f"git -C {repo} push origin main", cwd=tmp_path)
    assert "pull request" in push(repo, f"cd {repo} && git push", cwd=tmp_path)
    tree = tmp_path / "ws" / "tree"
    git(repo, "worktree", "add", "-q", "--detach", str(tree))
    assert "pull request" in push(repo, "git push origin HEAD:main", cwd=tree)  # a linked worktree is the same repository


def test_other_repositories_and_configs_without_the_key_are_untouched(repo):
    commit(repo, "second")
    assert push(repo, "git push origin main", config={}) is None
    assert push(repo, "git push origin main", config={"pr_gated": {"acme/other": {"since": "2026-11-11"}}}) is None


def test_the_principals_code_admits_one_exact_push(repo):
    commit(repo, "second")
    reason = push(repo, "git push origin main")
    assert "approve" in reason
    _approve(reason)
    assert push(repo, "git push origin main") is None
    assert "pull request" in push(repo, "git push origin main")  # one code, one push


def test_a_push_this_cannot_read_is_refused_in_a_gated_repository(repo):
    commit(repo, "second")
    reason = push(repo, 'git push origin "$(pick-branch')
    assert reason and "acme/skills" in reason and "pull request" in reason


@pytest.mark.parametrize("broken", [["acme/skills"], "acme/skills", {"skills": {}}])
def test_a_setting_that_cannot_be_read_blocks_pushes_and_nothing_else(repo, broken):
    reason = push(repo, "git push origin feature", config={"pr_gated": broken})
    assert "pr_gated" in reason
    assert push(repo, "git status", config={"pr_gated": broken}) is None


# --- the doctor ----------------------------------------------------------------------------------


def test_the_doctor_names_a_commit_that_reached_the_default_branch_without_a_pull_request(repo, tmp_path):
    direct = commit(repo, "second")
    git(repo, "push", "-q", "origin", "main")
    check = doctor.check_pr_gate(GATED["pr_gated"], [repo.parent, repo])
    assert check.status == "fail" and check.name == "pr gate"
    assert "acme/skills" in check.detail and direct in check.detail and "1 commit" in check.detail


def test_merged_pull_requests_and_listed_exceptions_are_clean(repo):
    git(repo, "switch", "-q", "-c", "feature")
    commit(repo, "second")
    git(repo, "switch", "-q", "main")
    git(repo, "merge", "-q", "--no-ff", "feature", "-m", "Merge pull request #7 from acme/feature")
    (repo / "third").write_text("third", encoding="utf-8")
    git(repo, "add", "third")
    git(repo, "commit", "-q", "-m", "Squashed change (#8)")
    excepted = commit(repo, "fourth")
    git(repo, "push", "-q", "origin", "main")
    config = {"acme/skills": {"since": "2026-11-11", "direct_ok": [excepted]}}
    check = doctor.check_pr_gate(config, [repo])
    assert check.status == "ok" and "1 gated" in check.detail, check.detail


def test_commits_from_before_the_gate_began_do_not_count(repo):
    check = doctor.check_pr_gate(GATED["pr_gated"], [repo])  # the first commit is dated 2026-11-10
    assert check.status == "ok", check.detail


def test_a_gated_repository_with_no_checkout_or_no_start_date_is_named(repo, tmp_path):
    check = doctor.check_pr_gate({"acme/skills": {"since": "2026-11-11"}, "acme/absent": {"since": "2026-11-11"}}, [repo])
    assert check.status == "warn" and "acme/absent" in check.detail and "no checkout" in check.detail
    check = doctor.check_pr_gate({"acme/skills": {}}, [repo])
    assert check.status == "fail" and "since" in check.detail
