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
    "git push origin main", "git push", "git push origin HEAD:main", "git push origin HEAD", "git push --follow-tags",
    "git push origin refs/heads/main", "git push -u origin main",
    "git push origin :main", "git push --force-with-lease origin main", "git add -A && git commit -m x && git push origin main",
])
def test_a_push_that_moves_the_default_branch_is_refused_with_the_route(repo, command):
    commit(repo, "second")
    reason = push(repo, command)
    assert reason and "acme/skills" in reason and "pull request" in reason and "main" in reason


@pytest.mark.parametrize("command", ['git push origin "$(git branch --show-current)"', "git push origin $BRANCH",
                                     "git push origin --delete main", "git push -d origin main",
                                     "sh -c 'git push origin main'", 'bash -c "cd . && git push"',
                                     "git push $REMOTE main", "git push `pick-remote` HEAD:main"])
def test_a_branch_named_through_a_variable_a_delete_and_a_nested_shell_are_refused(repo, command):
    commit(repo, "second")
    reason = push(repo, command)
    assert reason and "acme/skills" in reason and "pull request" in reason


def test_a_forced_push_to_the_default_branch_is_still_refused_outright(repo):
    commit(repo, "second")
    assert push(repo, "git push origin +main") == "refusing a force push to a default branch"  # no code admits this one


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


def test_a_push_that_names_the_default_branch_is_held_even_with_nothing_ahead(repo):
    """Two reviews found every hole in the first versions where the guard predicted what git would move. It no
    longer predicts: the default branch is not pushed from here, level or not, and a level push is a no-op to lose."""
    for command in ("git push origin main", "git push", "git push origin --delete main", "git push --force-with-lease origin main"):
        assert "pull request" in push(repo, command), command


@pytest.mark.parametrize("command", ["git push --all", "git push --all origin", "git push --mirror origin", "git push --branches origin",
                                     "git push origin :", "git push origin 'refs/heads/*:refs/heads/*'",
                                     "git push origin 'refs/heads/release/*:refs/heads/*'"])
def test_a_push_of_every_branch_or_a_pattern_of_branches_is_held(repo, command):
    git(repo, "switch", "-q", "-c", "feature")
    reason = push(repo, command)
    assert reason and "acme/skills" in reason and "pull request" in reason and "could not be read" in reason


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


# --- found by an independent review of the first version (2026-11-11) -----------------------------


def test_a_commit_and_a_push_in_one_command_is_held_on_the_default_branch(repo):
    (repo / "first").write_text("changed", encoding="utf-8")
    assert "pull request" in push(repo, "git commit -am change && git push origin main")
    assert "pull request" in push(repo, "./make-a-commit.sh; git push")
    assert "pull request" in push(repo, "git fetch upstream main:main && git push origin main")


@pytest.mark.parametrize("command", [
    "git push -u origin feature", "git push", "git push origin HEAD", "git add -A && git commit -m work && git push",
    "npm test && git push -u origin feature", "sh -c 'git push origin feature'", "git push origin feature:feature",
    "git push origin feature v1.0.0", "git status && git fetch origin && git push origin HEAD:refs/heads/feature",
])
def test_the_pushes_an_agent_makes_all_day_on_a_branch_pass(repo, command):
    git(repo, "switch", "-q", "-c", "feature")
    commit(repo, "second")
    git(repo, "tag", "v1.0.0")
    assert push(repo, command) is None, command


def test_a_branch_made_or_switched_to_earlier_on_the_line_is_the_one_judged(repo):
    commit(repo, "second")
    assert push(repo, "git checkout -b topic && git commit -am work && git push -u origin HEAD") is None
    assert push(repo, "git switch -c topic && git push") is None
    git(repo, "switch", "-q", "-c", "feature")
    assert "pull request" in push(repo, "git switch main && git push origin HEAD")
    assert "pull request" in push(repo, "git checkout main && git push")
    assert "could not be read" in push(repo, "git checkout - && git push")
    assert "could not be read" in push(repo, 'git switch "$TARGET" && git push origin HEAD')
    assert push(repo, "git checkout -- first && git push") is None  # a path restored, no branch changed


def test_routing_changed_earlier_on_the_line_makes_the_push_unreadable(repo):
    git(repo, "switch", "-q", "-c", "feature")
    for command in ("git config remote.origin.push HEAD:main && git push origin feature",
                    "git remote set-url --push fork ../acme/skills.git && git push fork feature"):
        assert "could not be read" in push(repo, command), command


@pytest.mark.parametrize("command", [
    "git -c remote.origin.push=HEAD:main push origin",
    "git -c alias.ship='push origin HEAD:main' ship",
    "git -c push.default=upstream push",
    "git push --repo=origin",
    "git push origin :",
    "git push origin 'refs/heads/*:refs/heads/*'",
])
def test_config_given_on_the_command_line_and_refspecs_that_match_every_branch_are_refused(repo, command):
    commit(repo, "second")
    reason = push(repo, command)
    assert reason and "acme/skills" in reason and "pull request" in reason, command


def test_a_push_through_an_alias_or_a_configured_refspec_is_read(repo):
    commit(repo, "second")
    git(repo, "config", "alias.ship", "push origin HEAD:main")
    assert "pull request" in push(repo, "git ship")
    git(repo, "switch", "-q", "-c", "feature")
    git(repo, "config", "remote.origin.push", "HEAD:main")
    assert "pull request" in push(repo, "git push origin")  # no refspec on the line: the remote's own is used


def test_a_branch_whose_push_destination_is_the_default_branch_is_refused(repo):
    git(repo, "switch", "-q", "-c", "feature", "--track", "origin/main")
    git(repo, "config", "push.default", "upstream")
    commit(repo, "second")
    assert "pull request" in push(repo, "git push")


def test_a_remote_that_fetches_from_one_repository_and_pushes_to_a_gated_one_is_gated(repo, tmp_path):
    commit(repo, "second")
    git(repo, "remote", "set-url", "--push", "fork", str(tmp_path / "acme" / "skills.git"))
    assert "pull request" in push(repo, "git push fork HEAD:main")


def test_a_destination_given_as_an_option_is_read(repo, tmp_path):
    commit(repo, "second")
    git(repo, "remote", "remove", "origin")
    assert "pull request" in push(repo, f"git push --repo={tmp_path / 'acme' / 'skills.git'}")  # no repository named: this is it


def test_a_configured_refspec_that_maps_a_named_branch_elsewhere_is_held(repo):
    git(repo, "switch", "-q", "-c", "feature")
    git(repo, "config", "remote.origin.push", "refs/heads/feature:refs/heads/main")
    assert "could not be read" in push(repo, "git push origin feature")  # the refspec sends feature to main
    assert push(repo, "git push origin feature:feature") is None           # both sides named: nothing to consult


def test_a_bare_push_through_another_remote_with_its_own_refspec_is_held(repo, tmp_path):
    git(repo, "switch", "-q", "-c", "feature")
    git(repo, "remote", "add", "publish", str(tmp_path / "acme" / "skills.git"))
    git(repo, "config", "branch.feature.pushRemote", "publish")
    git(repo, "config", "remote.publish.push", "HEAD:main")
    assert "could not be read" in push(repo, "git push")


def test_a_remote_defined_on_the_command_line_is_read_from_the_command(repo, tmp_path):
    git(repo, "remote", "remove", "origin")
    command = f"git -c remote.new.url={tmp_path / 'acme' / 'skills.git'} push new HEAD:main"
    assert "pull request" in push(repo, command)


def test_an_alias_of_an_alias_and_an_alias_that_starts_with_options_are_followed(repo):
    git(repo, "switch", "-q", "-c", "feature")
    git(repo, "config", "alias.publish", "push origin HEAD:main")
    git(repo, "config", "alias.ship", "publish")
    git(repo, "config", "alias.route", "-c remote.origin.push=HEAD:main push origin")
    for command in ("git ship", "git publish", "git route"):
        assert "pull request" in push(repo, command), command
    git(repo, "config", "alias.up", "push -u origin feature")
    assert push(repo, "git up") is None


# --- found by the third review round (2026-11-11) -------------------------------------------------


def test_a_tag_pushed_onto_the_default_branch_is_held_and_a_tag_named_like_it_is_not(repo):
    commit(repo, "second")
    git(repo, "tag", "v1")
    git(repo, "tag", "main-2026")
    assert "pull request" in push(repo, "git push origin refs/tags/v1:refs/heads/main")
    assert "pull request" in push(repo, "git push origin v1:main")
    git(repo, "switch", "-q", "-c", "feature")
    assert push(repo, "git push origin tag main-2026") is None
    assert push(repo, "git push origin refs/tags/v1") is None


def test_a_remote_configured_as_a_mirror_sends_every_branch(repo):
    git(repo, "switch", "-q", "-c", "feature")
    git(repo, "config", "remote.origin.mirror", "true")
    assert "could not be read" in push(repo, "git push origin")
    assert "could not be read" in push(repo, "git push")


@pytest.mark.parametrize("command, held", [
    ("git push origin main --dry-run --no-dry-run", True), ("git push --mir origin", True), ("git push --al origin", True),
    ("git push --del origin main", True), ("git push -qn origin main", False), ("git push -nq origin main", False),
    ("git push --dry origin main", False), ("git push --frobnicate origin feature", True),
])
def test_options_are_read_as_git_reads_them(repo, command, held):
    """git takes any unambiguous start of a long option, the last of a pair of opposites, and short options run together."""
    commit(repo, "second")
    assert bool(push(repo, command)) is held, command


def test_a_branch_switch_that_may_not_have_run_does_not_change_what_is_judged(repo):
    git(repo, "branch", "feature")
    commit(repo, "second")  # on main
    assert "pull request" in push(repo, "false && git switch feature; git push origin HEAD")
    assert "pull request" in push(repo, "git switch feature || true; git push")
    assert push(repo, "git switch feature && git push origin HEAD") is None      # the push runs only if the switch did
    assert push(repo, 'git checkout -b topic && git commit -m "one; two" && git push -u origin HEAD') is None


@pytest.mark.parametrize("command", [
    "GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=remote.origin.push GIT_CONFIG_VALUE_0=HEAD:main git push origin",
    "export GIT_CONFIG_GLOBAL=/tmp/other; git push origin feature",
    "GIT_DIR=../elsewhere/.git git push origin feature",
])
def test_git_configuration_set_through_the_environment_makes_the_push_unreadable(repo, command):
    git(repo, "switch", "-q", "-c", "feature")
    assert "could not be read" in push(repo, command)


def test_a_default_branch_that_is_not_main_is_protected_when_the_checkout_or_the_config_names_it(repo):
    git(repo, "switch", "-q", "-c", "develop")
    commit(repo, "second")
    git(repo, "push", "-q", "-u", "origin", "develop")
    git(repo, "symbolic-ref", "refs/remotes/origin/HEAD", "refs/remotes/origin/develop")
    assert "pull request" in push(repo, "git push origin develop") and push(repo, "git push origin main") is None
    git(repo, "symbolic-ref", "-d", "refs/remotes/origin/HEAD")
    named = {"pr_gated": {"acme/skills": {"since": "2026-11-11", "branch": "develop"}}}
    assert "pull request" in push(repo, "git push origin develop", config=named)
    assert push(repo, "git push origin main", config=named) is None


@pytest.mark.parametrize("command", [
    "git config --get remote.origin.url && git push", "git branch --show-current && git push", "git remote -v && git push",
    "git rebase origin/main && git push", "git rebase origin/main && git push origin HEAD", "git config --list; git push origin feature",
    "git pull --rebase && git push", "git stash && git push", "git push --force-with-lease", "git push --no-verify -q origin feature",
])
def test_reads_and_a_rebase_before_a_push_do_not_hold_it(repo, command):
    git(repo, "switch", "-q", "-c", "feature")
    commit(repo, "second")
    assert push(repo, command) is None, command


@pytest.mark.parametrize("command", ["git branch -m main && git push", "git symbolic-ref HEAD refs/heads/main && git push",
                                     "git remote set-url origin ../elsewhere.git && git push origin feature",
                                     "git config push.default upstream && git push"])
def test_writes_to_the_branch_or_the_routing_before_a_push_still_hold_it(repo, command):
    git(repo, "switch", "-q", "-c", "feature")
    assert "could not be read" in push(repo, command), command


# --- found by the fourth review round (2026-11-11) ------------------------------------------------


def test_a_checkout_that_records_no_default_branch_holds_every_branch_push(repo):
    """Nothing can be shown to leave the default branch alone when the guard cannot tell which branch that is."""
    git(repo, "switch", "-q", "-c", "develop")
    commit(repo, "second")
    git(repo, "tag", "v1.0.0")
    git(repo, "symbolic-ref", "-d", "refs/remotes/origin/HEAD")
    for command in ("git push origin develop", "git push origin main", "git push", "git push origin develop:develop"):
        reason = push(repo, command)
        assert reason and "acme/skills" in reason and "set-head" in reason and '"branch"' in reason, command
    for command in ("git push origin tag v1.0.0", "git push origin refs/tags/v1.0.0", "git push --tags", "git push -n origin develop"):
        assert push(repo, command) is None, command  # a push that says it is a tag, and a dry run, move no branch
    assert "set-head" in push(repo, "git push origin v1.0.0")  # a bare name could be a branch
    named = {"pr_gated": {"acme/skills": {"since": "2026-11-11", "branch": "main"}}}
    assert push(repo, "git push origin develop", config=named) is None


@pytest.mark.parametrize("value, held", [("1", True), ("True", True), ("yes", True), ("ON", True), ("false", False), ("0", False), ("No", False)])
def test_a_mirror_setting_is_read_as_git_reads_a_boolean(repo, value, held):
    git(repo, "switch", "-q", "-c", "feature")
    git(repo, "config", "remote.origin.mirror", value)
    assert bool(push(repo, "git push origin")) is held


def test_a_switch_inside_a_nested_shell_counts_only_when_the_push_there_needs_it(repo):
    git(repo, "branch", "feature")
    commit(repo, "second")  # on main
    assert "pull request" in push(repo, "sh -c 'git switch feature; git push origin HEAD'")
    assert "pull request" in push(repo, 'bash -c "git switch feature || true; git push"')
    assert "pull request" in push(repo, "git switch feature; sh -c 'git push origin HEAD'")
    assert push(repo, "sh -c 'git switch feature && git push origin HEAD'") is None


@pytest.mark.parametrize("command", [
    "git switch main || git switch -c topic && git push origin HEAD",  # the first switch succeeds and the push still runs
    "! git switch -c topic && git push origin HEAD",                    # the push runs only if the switch failed
    "if ! git switch -c topic; then git push origin HEAD; fi",
    "git switch -c topic | cat && git push origin HEAD",
    "(git switch -c topic) && git push origin HEAD",
    "git switch -c topic & git push origin HEAD",
])
def test_a_switch_the_push_does_not_depend_on_leaves_the_branch_before_it_in_play(repo, command):
    commit(repo, "second")  # on main
    assert "pull request" in push(repo, command), command


@pytest.mark.parametrize("command", [
    "git checkout -b topic && git push -u origin HEAD\n",
    "git checkout -b topic &&\n  git push -u origin HEAD",
    "git checkout -b topic && git add -A && git commit -m work && git push -u origin HEAD\n\n",
    "git fetch origin; git switch -c topic && git push -u origin HEAD",
    "git stash || true; git switch -c topic && git push",
])
def test_a_trailing_or_continuing_newline_does_not_break_a_chain(repo, command):
    commit(repo, "second")  # on main
    assert push(repo, command) is None, command


def test_a_newline_between_a_switch_and_a_push_is_not_a_chain(repo):
    git(repo, "branch", "feature")
    commit(repo, "second")  # on main
    assert "pull request" in push(repo, "git switch feature\ngit push origin HEAD")


@pytest.mark.parametrize("command", [
    "git rebase origin/main main && git push origin HEAD", "git rebase --onto origin/main HEAD~1 main && git push",
    "git rebase --root main && git push", "git rebase origin/main main -X theirs && git push origin HEAD",
])
def test_a_rebase_that_names_the_branch_to_rebase_checks_it_out(repo, command):
    git(repo, "switch", "-q", "-c", "feature")
    assert "pull request" in push(repo, command), command


@pytest.mark.parametrize("command", [
    "git rebase main && git push --force-with-lease", "git rebase -i origin/main && git push",
    "git rebase --onto origin/main HEAD~1 && git push --force-with-lease origin HEAD", "git rebase origin/main feature && git push",
    "git rebase --continue && git push", "git symbolic-ref --short HEAD && git push", "git symbolic-ref refs/remotes/origin/HEAD; git push",
])
def test_a_rebase_onto_the_default_branch_and_a_read_of_head_do_not_hold_a_push(repo, command):
    git(repo, "switch", "-q", "-c", "feature")
    commit(repo, "second")
    assert push(repo, command) is None, command


def test_a_stash_turned_into_a_branch_is_a_branch_change(repo):
    git(repo, "switch", "-q", "-c", "feature")
    assert "could not be read" in push(repo, "git stash branch main && git push origin HEAD")
    assert push(repo, "git stash pop && git push") is None


def test_a_push_in_a_folder_that_does_not_exist_yet_is_unreadable(repo, tmp_path):
    """A clone or a new worktree made earlier on the line: none of its remotes or branches can be read beforehand."""
    remote = tmp_path / "acme" / "skills.git"
    assert "could not be read" in push(repo, f"git clone {remote} fresh && cd fresh && git push origin main", cwd=tmp_path)
    assert "could not be read" in push(repo, "git worktree add ../tree main && cd ../tree && git push")
    assert push(repo, "cd ../nowhere && git push origin main", cwd=tmp_path) is None  # no gated repository anywhere on the line
    reason = push(repo, "git worktree add ../tree -b topic && cd ../tree && git push -u origin topic")
    assert "could not be read" in reason and "by itself" in reason  # held, with the way through


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


def test_history_the_doctor_cannot_read_is_not_reported_clean(repo):
    def failing(argv, **kwargs):
        return subprocess.CompletedProcess(argv, 128, "", "fatal: bad object") if "log" in argv else subprocess.run(argv, **kwargs)
    check = doctor.check_pr_gate(GATED["pr_gated"], [repo], run=failing)
    assert check.status == "warn" and "cannot read" in check.detail and "acme/skills" in check.detail


def test_a_checkout_that_records_no_default_branch_is_named(repo):
    git(repo, "symbolic-ref", "-d", "refs/remotes/origin/HEAD")
    check = doctor.check_pr_gate(GATED["pr_gated"], [repo])
    assert check.status == "warn" and "default branch" in check.detail and "set-head" in check.detail
    named = doctor.check_pr_gate({"acme/skills": {"since": "2026-11-11", "branch": "main"}}, [repo])
    assert named.status == "ok", named.detail


def test_a_gated_repository_with_no_checkout_or_no_start_date_is_named(repo, tmp_path):
    check = doctor.check_pr_gate({"acme/skills": {"since": "2026-11-11"}, "acme/absent": {"since": "2026-11-11"}}, [repo])
    assert check.status == "warn" and "acme/absent" in check.detail and "no checkout" in check.detail
    check = doctor.check_pr_gate({"acme/skills": {}}, [repo])
    assert check.status == "fail" and "since" in check.detail
