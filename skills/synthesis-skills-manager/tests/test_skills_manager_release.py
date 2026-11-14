"""release.py: preflight, one releaser at a time, atomic publication read back from the remote,
and verification of installed bytes against the tag."""

import base64
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
for path in (ROOT, ROOT / "skills" / "synthesis-onboarding" / "scripts", Path(__file__).resolve().parents[1] / "scripts"):
    sys.path.insert(0, str(path))

import build_collections  # noqa: E402
import release  # noqa: E402
import setup  # noqa: E402
from synthesis import board  # noqa: E402


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("SYNTHESIS_HOME", str(tmp_path / "home" / ".synthesis" / "v5"))
    gitconfig = tmp_path / "gitconfig"
    gitconfig.write_text("[user]\n\temail = t@example.com\n\tname = t\n[init]\n\tdefaultBranch = main\n")
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(gitconfig))
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    for key in ("CLAUDE_CODE_SESSION_ID", "CODEX_THREAD_ID", "MUSE_SESSION_ID", "SYNTHESIS_SESSION"):
        monkeypatch.delenv(key, raising=False)


def git(repo, *args):
    return subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True).stdout.strip()


# The collections a release publishes beside the whole set: here one, the core, holding the one skill.
COLLECTIONS = {"core": "core", "branch": "collections", "marketplace": {"name": "demo-collections"},
               "collections": {"core": {"name": "demo-core", "description": "The core."}}}


def source_repo(tmp_path, version="5.1.0", changelog=None, remotes=1):
    repo = tmp_path / "synthesis-skills"
    for name in release.MANIFESTS:
        (repo / name).parent.mkdir(parents=True, exist_ok=True)
        (repo / name).write_text(json.dumps({"name": "synthesis-skills", "version": version}))
    (repo / "skills" / "demo").mkdir(parents=True)
    (repo / "skills" / "demo" / "SKILL.md").write_text("---\nname: demo\nmetadata:\n  category: core\n---\n")
    (repo / build_collections.LIST).parent.mkdir(parents=True)
    (repo / build_collections.LIST).write_text(json.dumps(COLLECTIONS))
    for name in build_collections.LICENSES:
        (repo / name).write_text(f"{name} terms.\n")
    (repo / "CHANGELOG.md").write_text(changelog or f"# Changelog\n\n## [{version}] - 2026-10-05\n\n- x\n")
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    git(repo, "add", ".")
    git(repo, "commit", "-qm", "init")
    for i in range(remotes):
        bare = tmp_path / f"remote{i}.git"
        subprocess.run(["git", "init", "-q", "--bare", str(bare)], check=True)
        git(repo, "remote", "add", "origin" if i == 0 else f"mirror{i}", str(bare))
    git(repo, "push", "-q", "origin", "main")
    git(repo, "remote", "set-head", "origin", "main")
    return repo


green = lambda repo, sha: (True, "CI passed")  # noqa: E731


# ---- preflight ----------------------------------------------------------------

def test_a_coherent_repository_passes_preflight(tmp_path):
    version, problems = release.preflight(source_repo(tmp_path), False, ci=green)
    assert version == "5.1.0" and problems == []


@pytest.mark.parametrize("break_it, message", [
    (lambda r: (r / ".muse-plugin" / "plugin.json").write_text('{"version": "5.0.9"}'), "disagree"),
    (lambda r: (r / "CHANGELOG.md").write_text("## [5.0.9]\n"), "CHANGELOG's newest entry is 5.0.9"),
    (lambda r: (r / "stray.txt").write_text("x"), "uncommitted changes"),
    (lambda r: git(r, "checkout", "-qb", "feature"), "not the default branch"),
])
def test_preflight_refuses_before_pushing(tmp_path, break_it, message):
    repo = source_repo(tmp_path)
    break_it(repo)
    _, problems = release.preflight(repo, False, ci=green)
    assert any(message in p for p in problems)


def test_preflight_refuses_a_plugin_cache_as_the_repository(tmp_path):
    cache = tmp_path / "plugins" / "cache" / "synthesis-engineering" / "synthesis-skills" / "5.1.0"
    cache.mkdir(parents=True)
    version, problems = release.preflight(cache, False, ci=green)
    assert version is None and "installed plugin copy" in problems[0]


def test_preflight_refuses_when_ci_has_not_passed(tmp_path):
    repo = source_repo(tmp_path)
    _, problems = release.preflight(repo, False, ci=lambda r, sha: (False, "CI for abc: failed ['test']"))
    assert problems == ["CI for abc: failed ['test']"]


def test_ci_state_reads_github_runs():
    def gh(runs, code=0):
        return lambda argv, *a, **k: subprocess.CompletedProcess(argv, code, json.dumps(runs), "not signed in")
    ok = [{"status": "completed", "conclusion": "success", "workflowName": "CI"}]
    assert release.ci_state(Path("."), "a" * 40, run=gh(ok))[0] is True
    assert release.ci_state(Path("."), "a" * 40, run=gh([]))[1].startswith("no CI run")
    running = [{"status": "in_progress", "conclusion": "", "workflowName": "CI"}]
    assert "running ['CI']" in release.ci_state(Path("."), "a" * 40, run=gh(running))[1]
    failed = [{"status": "completed", "conclusion": "failure", "workflowName": "CI"}]
    assert "failed ['CI']" in release.ci_state(Path("."), "a" * 40, run=gh(failed))[1]
    assert release.ci_state(Path("."), "a" * 40, run=gh(None, 4))[0] is False  # unknown is not passed


def test_install_only_needs_the_tag_on_head(tmp_path):
    repo = source_repo(tmp_path)
    assert "v5.1.0 is missing" in release.preflight(repo, True)[1][0]
    git(repo, "tag", "v5.1.0")
    assert release.preflight(repo, True) == ("5.1.0", [])


# ---- the release train ----------------------------------------------------------

def test_a_second_session_is_refused_with_the_first_ones_name(tmp_path):
    repo = source_repo(tmp_path)
    release.hold_train(repo, "session-a", "5.1.0")
    with pytest.raises(setup.SetupError, match="session-a"):
        release.hold_train(repo, "session-b", "5.1.0")
    release.hold_train(repo, "session-a", "5.1.0")  # the holder may run again


def test_releases_from_two_worktrees_claim_the_same_file(tmp_path):
    repo = source_repo(tmp_path)
    worktree = tmp_path / "wt"
    git(repo, "worktree", "add", "-q", str(worktree), "-b", "other")
    assert release.train_path(worktree) == release.train_path(repo) == str(repo.resolve() / "CHANGELOG.md")


def test_main_refuses_while_another_session_releases(tmp_path, monkeypatch, capsys):
    repo = source_repo(tmp_path)
    board.claim("other-session", [release.train_path(repo)], goal="release v5.1.0")
    monkeypatch.setattr(release, "ci_state", green)
    monkeypatch.setattr(release, "preflight", lambda r, i: ("5.1.0", []))
    assert release.main(["--repo-root", str(repo), "--session", "me", "--clients", ""]) == 1
    assert "another release is under way" in capsys.readouterr().out and not git(repo, "tag")


# ---- publication -------------------------------------------------------------

def test_publish_pushes_main_stable_and_the_tag_to_every_remote(tmp_path):
    repo = source_repo(tmp_path, remotes=2)
    lines = release.publish(repo, "5.1.0")
    head = git(repo, "rev-parse", "HEAD")
    for bare in (tmp_path / "remote0.git", tmp_path / "remote1.git"):
        assert git(bare, "rev-parse", "main", "stable", "v5.1.0^{commit}").split() == [head] * 3
    assert len(lines) == 2 and all(head[:12] in line for line in lines)


def test_a_rejected_push_is_caught_by_reading_the_remote(tmp_path):
    repo = source_repo(tmp_path)
    other = tmp_path / "other"
    subprocess.run(["git", "clone", "-q", str(tmp_path / "remote0.git"), str(other)], check=True)
    (other / "x").write_text("x")
    git(other, "add", ".")
    git(other, "commit", "-qm", "ahead")
    git(other, "push", "-q", "origin", "main")  # the remote moved: our non-forced atomic push must fail
    with pytest.raises(setup.SetupError, match="do not point at"):
        release.publish(repo, "5.1.0")
    assert "v5.1.0" not in git(tmp_path / "remote0.git", "tag")  # atomic: the tag did not go either
    assert git(tmp_path / "remote0.git", "for-each-ref", "refs/heads/collections") == ""  # nor the collections


def test_dry_run_publishes_nothing(tmp_path):
    repo = source_repo(tmp_path)
    line = release.publish(repo, "5.1.0", dry_run=True)[0]
    assert line.startswith("would tag v5.1.0") and line.endswith(", with the collections built from it as collections")
    assert git(repo, "tag") == "" and git(tmp_path / "remote0.git", "for-each-ref", "refs/heads/collections") == ""


# ---- the collections, published as a branch of built folders ---------------------------

def collections_tree(repo):
    """The git tree of the collections built from HEAD's commit, as the release builds them."""
    files, modes = build_collections.build(repo, commit=True)
    return build_collections.tree(repo, files, modes)


def test_publish_pushes_the_collections_beside_main_stable_and_the_tag(tmp_path):
    """Each harness installs a collection from a folder of its own, with its own manifests: on a branch of this
    repository each one can name, by ref (the probe of 2026-11-14)."""
    repo = source_repo(tmp_path, remotes=2)
    lines = release.publish(repo, "5.1.0")
    tree = collections_tree(repo)
    for bare in (tmp_path / "remote0.git", tmp_path / "remote1.git"):
        assert git(bare, "rev-parse", "collections^{tree}") == tree
        assert git(bare, "rev-list", "--count", "collections") == "1"
        made = json.loads(git(bare, "show", "collections:core/.claude-plugin/plugin.json"))
        assert (made["name"], made["version"]) == ("demo-core", "5.1.0")
        assert git(bare, "show", "collections:core/skills/demo/SKILL.md") == git(repo, "show", "HEAD:skills/demo/SKILL.md")
    head = git(repo, "rev-parse", "HEAD")
    moved = {"origin": git(tmp_path / "remote0.git", "rev-parse", "collections"),
             "mirror1": git(tmp_path / "remote1.git", "rev-parse", "collections")}
    assert sorted(lines) == sorted(f"{remote}: main, stable and v5.1.0 at {head[:12]}, collections at {commit[:12]}"
                                   for remote, commit in moved.items())


def test_a_run_again_moves_nothing_and_the_next_release_adds_a_commit_on_top(tmp_path):
    repo, bare = source_repo(tmp_path), tmp_path / "remote0.git"
    release.publish(repo, "5.1.0")
    first = git(bare, "rev-parse", "collections")
    release.publish(repo, "5.1.0")  # a run again, as after a server error: the folders on the branch are this release's
    assert git(bare, "rev-parse", "collections") == first
    for name in release.MANIFESTS:
        (repo / name).write_text(json.dumps({"name": "synthesis-skills", "version": "5.1.1"}))
    (repo / "CHANGELOG.md").write_text("# Changelog\n\n## [5.1.1] - 2026-10-06\n\n- y\n")
    git(repo, "commit", "-qam", "5.1.1")
    release.publish(repo, "5.1.1")
    assert git(bare, "rev-parse", "collections^") == first  # a fast-forward: no release rewrites the branch
    assert git(bare, "rev-parse", "collections^{tree}") == collections_tree(repo)
    assert json.loads(git(bare, "show", "collections:core/.codex-plugin/plugin.json"))["version"] == "5.1.1"


@pytest.mark.parametrize("dry_run", [False, True])
def test_collections_that_fail_their_checks_stop_the_release_before_anything_is_published(tmp_path, dry_run):
    repo = source_repo(tmp_path)
    (repo / "skills" / "demo" / "SKILL.md").write_text("---\nname: demo\n---\n")  # in no collection
    git(repo, "commit", "-qam", "no collection")
    with pytest.raises(setup.SetupError, match=r"the collections fail 1 check, so nothing was published: "
                                               r"skills/demo/SKILL.md: in no collection"):
        release.publish(repo, "5.1.0", dry_run=dry_run)
    assert git(repo, "tag") == "" and git(tmp_path / "remote0.git", "for-each-ref", "refs/heads/collections") == ""
    (repo / build_collections.LIST).write_text("{")
    git(repo, "commit", "-qam", "a collections file that cannot be read")
    with pytest.raises(setup.SetupError, match="cannot build the collections: "):
        release.publish(repo, "5.1.0", dry_run=dry_run)


# ---- the GitHub release -------------------------------------------------------

def gh_fake(exists=False, latest="v5.1.0", create_rc=0):
    calls = []

    def run(argv, **kwargs):
        calls.append(argv)
        if argv[:3] == ["gh", "release", "view"]:
            return subprocess.CompletedProcess(argv, 0 if exists else 1, "", "")
        if argv[:3] == ["gh", "release", "create"]:
            return subprocess.CompletedProcess(argv, create_rc, "", "HTTP 403" if create_rc else "")
        listed = [{"tagName": latest, "isLatest": True}, {"tagName": "v4.149.7", "isLatest": False}]
        return subprocess.CompletedProcess(argv, 0, json.dumps(listed), "")
    return run, calls


def test_github_release_is_created_from_the_changelog_and_read_back_as_latest(tmp_path):
    repo = source_repo(tmp_path, changelog="# Changelog\n\n## [5.1.0] - 2026-11-02\n\n- **One** thing.\n\n"
                                          "## [5.0.9] - 2026-11-01\n\n- older\n")
    git(repo, "remote", "add", "github", "https://github.com/example/demo.git")
    run, calls = gh_fake()
    assert release.github_release(repo, "5.1.0", run=run) == ["example/demo: GitHub release v5.1.0, latest"]
    create = next(c for c in calls if c[:3] == ["gh", "release", "create"])
    assert create[3:] == ["v5.1.0", "-R", "example/demo", "--verify-tag", "--latest", "--title", "Synthesis 5.1.0",
                          "--notes", "- **One** thing."]


def test_an_existing_github_release_is_not_created_twice(tmp_path):
    repo = source_repo(tmp_path)
    git(repo, "remote", "add", "github", "git@github.com:example/demo.git")
    run, calls = gh_fake(exists=True)
    assert release.github_release(repo, "5.1.0", run=run) == ["example/demo: GitHub release v5.1.0, latest"]
    assert not [c for c in calls if c[:3] == ["gh", "release", "create"]]


def test_a_github_release_that_fails_or_is_not_latest_stops_the_release(tmp_path):
    repo = source_repo(tmp_path)
    git(repo, "remote", "add", "github", "https://github.com/example/demo")
    with pytest.raises(setup.SetupError, match="cannot create the GitHub release v5.1.0: HTTP 403"):
        release.github_release(repo, "5.1.0", run=gh_fake(create_rc=1)[0])
    with pytest.raises(setup.SetupError, match="GitHub shows v4.149.7 as latest, not v5.1.0"):
        release.github_release(repo, "5.1.0", run=gh_fake(latest="v4.149.7")[0])


def test_without_a_github_remote_or_in_a_dry_run_no_github_release_is_made(tmp_path):
    repo = source_repo(tmp_path)
    run, calls = gh_fake()
    assert release.github_release(repo, "5.1.0", run=run) == ["no GitHub remote, so no GitHub release"]
    git(repo, "remote", "add", "github", "https://github.com/example/demo.git")
    assert release.github_release(repo, "5.1.0", dry_run=True, run=run)[0].startswith(
        "would create the GitHub release v5.1.0 on example/demo")
    assert calls == []


# ---- the Homebrew formula -------------------------------------------------------

OLD_SHA = "4ea2592feaf1d8664a210205d636d8fdf404c1d094675adfe0ef14f441dd73e4"
FORMULA_RB = f"""class Synthesis < Formula
  url "https://github.com/synthesisengineering/synthesis-skills/archive/refs/tags/v5.0.3.tar.gz"
  sha256 "{OLD_SHA}"
end
"""
DIGEST = "ab" * 32
PR = "https://github.com/synthesisengineering/homebrew-tap/pull/16"


def tap_fake(served=FORMULA_RB, open_pr="", views=(), merged_text=None, create_502s=0, delete_err="",
             run_views=()):
    """gh against the tap: the formula on main, the pull request's states in turn, and main after the merge;
    GitHub may answer the first pull request creations with a 502, as it did on 2026-11-05; `gh run view` answers
    with the runs behind the checks in turn."""
    calls, state = [], {"text": served, "views": list(views), "create_502s": create_502s, "runs": list(run_views)}

    def run(argv, **kwargs):
        calls.append(argv)
        reply = lambda out="", rc=0, err="": subprocess.CompletedProcess(argv, rc, out, err)  # noqa: E731
        if argv[:2] == ["gh", "api"] and argv[2].startswith(f"repos/{release.TAP}/contents/"):
            encoded = base64.b64encode(state["text"].encode()).decode()
            return reply(json.dumps({"content": encoded, "sha": "blob1"}))
        if argv[:3] == ["gh", "pr", "list"]:
            return reply(json.dumps([{"url": open_pr}] if open_pr else []))
        if argv[:3] == ["gh", "api", f"repos/{release.TAP}/git/ref/heads/main"]:
            return reply(json.dumps({"object": {"sha": "main1"}}))
        if argv[:3] == ["gh", "pr", "create"]:
            if state["create_502s"]:
                state["create_502s"] -= 1
                return reply(rc=1, err="pull request create failed: HTTP 502: 502 Bad Gateway (https://api.github.com/graphql)")
            return reply(PR + "\n")
        if argv[:4] == ["gh", "api", "-X", "DELETE"]:
            return reply(rc=1 if delete_err else 0, err=delete_err)
        if argv[:3] == ["gh", "run", "view"]:
            return reply(json.dumps(state["runs"].pop(0)))
        if argv[:3] == ["gh", "pr", "view"]:
            view = state["views"].pop(0)
            if view["state"] == "MERGED":
                state["text"] = merged_text if merged_text is not None else state["pushed"]
            return reply(json.dumps(view))
        if argv[:4] == ["gh", "api", "-X", "PUT"]:
            state["pushed"] = base64.b64decode(argv[-1].split("=", 1)[1]).decode()
        return reply()
    return run, calls, state


def canonical_repo(tmp_path):
    repo = source_repo(tmp_path)
    git(repo, "remote", "add", "github", "https://github.com/synthesisengineering/synthesis-skills.git")
    return repo


def test_the_formula_follows_the_tag_through_a_pull_request_the_tap_tests_merge(tmp_path):
    """2026-11-03: the formula still pointed at v5.0.3 after eleven releases, so `brew install` ran an onboarding
    without 5.3.3's prerequisite checks."""
    run, calls, state = tap_fake(views=[{"state": "OPEN", "statusCheckRollup": [{"name": "ci", "status": "QUEUED"}]},
                                        {"state": "MERGED", "statusCheckRollup": [{"conclusion": "SUCCESS"}]}])
    lines, formula = release.homebrew_formula(canonical_repo(tmp_path), "5.1.0", run=run, fetch=lambda url: DIGEST)
    assert lines == [f"{release.TAP}: {PR} points the formula at v5.1.0 and merges when its install tests pass"]
    assert f'url "{release.archive("5.1.0")}"' in state["pushed"] and f'sha256 "{DIGEST}"' in state["pushed"]
    assert "class Synthesis < Formula" in state["pushed"] and "v5.0.3" not in state["pushed"]
    assert ["gh", "pr", "merge", PR, "-R", release.TAP, "--auto", "--merge"] in calls
    assert release.homebrew_merged(formula, run=run, sleep=lambda s: None) == [
        f"{release.TAP}: Homebrew serves synthesis 5.1.0 ({PR} merged)"]
    assert calls[-1] == ["gh", "api", "-X", "DELETE", f"repos/{release.TAP}/git/refs/heads/synthesis-5.1.0"]


def test_a_formula_already_serving_the_tag_or_an_open_pull_request_is_not_made_twice(tmp_path):
    current = FORMULA_RB.replace("v5.0.3", "v5.1.0").replace(OLD_SHA, DIGEST)
    run, calls, _ = tap_fake(served=current)
    assert release.homebrew_formula(canonical_repo(tmp_path), "5.1.0", run=run, fetch=lambda url: DIGEST) == (
        [f"{release.TAP}: Homebrew already serves synthesis 5.1.0"], None)
    run, calls, _ = tap_fake(open_pr=PR)
    assert release.homebrew_formula(canonical_repo(tmp_path / "again"), "5.1.0", run=run,
                                    fetch=lambda url: DIGEST)[1] == {"pr": PR, "version": "5.1.0", "sha256": DIGEST,
                                                       "branch": "synthesis-5.1.0"}
    assert not [c for c in calls if c[:3] == ["gh", "pr", "create"] or c[:4] == ["gh", "api", "-X", "PUT"]]


def test_failed_install_tests_a_closed_pull_request_or_no_merge_leave_the_release_incomplete():
    formula = {"pr": PR, "version": "5.1.0", "sha256": DIGEST, "branch": "synthesis-5.1.0"}
    failing = [{"state": "OPEN", "statusCheckRollup": [{"name": "formulas (macos-latest)", "conclusion": "FAILURE"}]}]
    with pytest.raises(setup.SetupError, match=r"did not merge \(formulas \(macos-latest\)\)"):
        release.homebrew_merged(formula, run=tap_fake(views=failing)[0], sleep=lambda s: None)
    with pytest.raises(setup.SetupError, match=r"did not merge \(closed\)"):
        release.homebrew_merged(formula, run=tap_fake(views=[{"state": "CLOSED"}])[0], sleep=lambda s: None)
    with pytest.raises(setup.SetupError, match="had not merged after 2 minutes"):
        release.homebrew_merged(formula, run=tap_fake(views=[{"state": "OPEN"}] * 6)[0], sleep=lambda s: None,
                                interval=20, timeout=120)
    with pytest.raises(setup.SetupError, match="does not serve v5.1.0"):
        release.homebrew_merged(formula, run=tap_fake(views=[{"state": "MERGED"}], merged_text=FORMULA_RB)[0],
                                sleep=lambda s: None)


# GitHub's own answers for tap #17 on 2026-11-05: `gh run view --attempt 1 --json status,conclusion,jobs` for the run
# whose macOS job got no runner, and `gh pr view --json state,statusCheckRollup` once its rerun merged it.
FIXTURES = Path(__file__).resolve().parent / "fixtures"
NEVER_RAN = json.loads((FIXTURES / "tap-run-no-runner.json").read_text())
CHECKS = json.loads((FIXTURES / "tap-pull-request-checks.json").read_text())["statusCheckRollup"]
NO_RUNNER = {"state": "OPEN", "statusCheckRollup": [  # the checks as the pull request showed them before the rerun
    dict(c, conclusion={"formulas (macos-latest)": "CANCELLED", "ci": "FAILURE"}.get(c["name"], c["conclusion"]))
    for c in CHECKS]}
RERUN = ["gh", "run", "rerun", "42095650840", "-R", release.TAP, "--failed"]


def test_a_tap_job_github_never_ran_is_run_again_and_the_release_waits_for_the_merge(capsys):
    formula = {"pr": PR, "version": "5.1.0", "sha256": DIGEST, "branch": "synthesis-5.1.0"}
    served = FORMULA_RB.replace("v5.0.3", "v5.1.0").replace(OLD_SHA, DIGEST)
    running = {"state": "OPEN", "statusCheckRollup": [{"name": "formulas (macos-latest)", "status": "IN_PROGRESS"}]}
    run, calls, _ = tap_fake(views=[NO_RUNNER, running, {"state": "MERGED"}], merged_text=served,
                             run_views=[NEVER_RAN])
    assert release.homebrew_merged(formula, run=run, sleep=lambda s: None) == [
        f"{release.TAP}: Homebrew serves synthesis 5.1.0 ({PR} merged)"]
    assert calls.count(RERUN) == 1 and "GitHub gave a job no runner; rerun 1 of 3" in capsys.readouterr().out


def test_a_tap_job_that_failed_in_its_steps_stops_the_release_without_a_rerun():
    formula = {"pr": PR, "version": "5.1.0", "sha256": DIGEST, "branch": "synthesis-5.1.0"}
    failed = dict(NEVER_RAN, jobs=[dict(job, conclusion="failure", steps=[{"name": "Install"}])
                                   if job["name"] == "formulas (macos-latest)" else job for job in NEVER_RAN["jobs"]])
    run, calls, _ = tap_fake(views=[NO_RUNNER], run_views=[failed])
    with pytest.raises(setup.SetupError, match=r"did not merge \(ci, formulas \(macos-latest\)\)"):
        release.homebrew_merged(formula, run=run, sleep=lambda s: None)
    assert RERUN not in calls


def test_a_job_that_never_gets_a_runner_is_run_again_three_times_then_the_release_stops():
    formula = {"pr": PR, "version": "5.1.0", "sha256": DIGEST, "branch": "synthesis-5.1.0"}
    run, calls, _ = tap_fake(views=[NO_RUNNER] * 4, run_views=[NEVER_RAN] * 4)
    with pytest.raises(setup.SetupError, match="did not merge"):
        release.homebrew_merged(formula, run=run, sleep=lambda s: None)
    assert calls.count(RERUN) == 3


def test_a_failed_check_whose_run_is_running_again_is_waited_for():
    """Right after a rerun, the pull request can still show the failed checks while their run is queued again."""
    formula = {"pr": PR, "version": "5.1.0", "sha256": DIGEST, "branch": "synthesis-5.1.0"}
    served = FORMULA_RB.replace("v5.0.3", "v5.1.0").replace(OLD_SHA, DIGEST)
    queued = {"status": "queued", "jobs": [{"name": "formulas (macos-latest)", "conclusion": "", "steps": []}]}
    run, calls, _ = tap_fake(views=[NO_RUNNER, {"state": "MERGED"}], merged_text=served, run_views=[queued])
    assert release.homebrew_merged(formula, run=run, sleep=lambda s: None) == [
        f"{release.TAP}: Homebrew serves synthesis 5.1.0 ({PR} merged)"]
    assert RERUN not in calls


def test_a_fork_or_a_dry_run_leaves_the_formula_alone(tmp_path):
    repo = source_repo(tmp_path)
    git(repo, "remote", "add", "github", "https://github.com/example/synthesis-skills.git")
    run, calls, _ = tap_fake()
    assert release.homebrew_formula(repo, "5.1.0", run=run)[0] == [
        "not the canonical repository, so the Homebrew formula is left alone"]
    assert release.homebrew_formula(canonical_repo(tmp_path / "canonical"), "5.1.0", dry_run=True,
                                    run=run)[0][0].startswith(f"would point {release.TAP} {release.FORMULA} at v5.1.0")
    assert calls == []


@pytest.mark.parametrize("merged", [True, False])
def test_the_release_is_complete_only_once_homebrew_serves_the_tag(tmp_path, monkeypatch, capsys, merged):
    formula = {"pr": PR, "version": "5.1.0", "sha256": DIGEST, "branch": "synthesis-5.1.0"}

    def homebrew_merged(found):
        if not merged:
            raise setup.SetupError(f"{PR} did not merge (ci)")
        return [f"{release.TAP}: Homebrew serves synthesis 5.1.0"]
    monkeypatch.setattr(release, "preflight", lambda repo, install_only: ("5.1.0", []))
    monkeypatch.setattr(release, "hold_train", lambda repo, session, version: "train")
    monkeypatch.setattr(release.board, "release", lambda session, paths: None)
    monkeypatch.setattr(release, "publish", lambda repo, version, dry_run: ["pushed"])
    monkeypatch.setattr(release, "github_release", lambda repo, version, dry_run: ["github"])
    monkeypatch.setattr(release, "homebrew_formula", lambda repo, version, dry_run: (["tap pull request"], formula))
    monkeypatch.setattr(release, "install_and_verify", lambda *a: (["installed"], {"claude": tmp_path}, ["claude"]))
    monkeypatch.setattr(release.install, "install", lambda source: "runtime")
    monkeypatch.setattr(release.doctor, "run_checks", lambda: [release.doctor.Check("ok", "runtime", "current")])
    monkeypatch.setattr(release, "homebrew_merged", homebrew_merged)
    assert release.main(["--session", "s1"]) == (0 if merged else 1)
    out = capsys.readouterr().out
    assert ("release complete: v5.1.0" if merged else "release NOT complete: v5.1.0") in out
    assert "tap pull request" in out and ("Homebrew serves" in out if merged else f"Homebrew: {PR} did not merge" in out)


@pytest.mark.parametrize("failing, detail, complete", [
    ("codex hook trust", "needs /hooks approval: pre_tool_use:0:0 untrusted", True),  # the person approves in the harness
    ("muse hook approval", "run `muse plugins approve synthesis-skills`: synthesis-pre-tool-use", True),
    ("runtime", "needs approval", False),
    # 5.21.0: the same line can name a fault of setup, which is no approval the person can give
    ("codex hook trust", "hooks.json:pre_tool_use:0:0 is not switched off, so it runs beside the user-level PreToolUse",
     False),
    ("codex hook trust", "the installed plugin has no hooks/hooks.json", False),
    ("muse hook approval", "the installed plugin registers no hooks", False),
])
def test_an_approval_only_the_person_can_give_does_not_hold_the_release(tmp_path, monkeypatch, capsys, failing,
                                                                          detail, complete):
    """2026-11-05: Codex ties a hook approval to the plugin's files, so every release leaves it to be given again."""
    monkeypatch.setattr(release, "preflight", lambda repo, install_only: ("5.1.0", []))
    monkeypatch.setattr(release, "hold_train", lambda repo, session, version: "train")
    monkeypatch.setattr(release.board, "release", lambda session, paths: None)
    monkeypatch.setattr(release, "publish", lambda repo, version, dry_run: ["pushed"])
    monkeypatch.setattr(release, "github_release", lambda repo, version, dry_run: ["github"])
    monkeypatch.setattr(release, "homebrew_formula", lambda repo, version, dry_run: (["tap: nothing to move"], None))
    monkeypatch.setattr(release, "install_and_verify", lambda *a: (["installed"], {"codex": tmp_path}, ["codex"]))
    monkeypatch.setattr(release.install, "install", lambda source: "runtime")
    monkeypatch.setattr(release.doctor, "run_checks", lambda: [release.doctor.Check("fail", failing, detail)])
    assert release.main(["--session", "s1"]) == (0 if complete else 1)
    out = capsys.readouterr().out
    assert ("release complete: v5.1.0" if complete else "release NOT complete: v5.1.0") in out
    assert (f"waiting on your approval ({failing}): {detail}" in out) == complete


# ---- GitHub server errors ------------------------------------------------------

def flaky(errors, result=("done",)):
    """A stage that fails with each of `errors` in turn, then returns `result`."""
    queue = list(errors)

    def stage(*args, **kwargs):
        if queue:
            raise setup.SetupError(queue.pop(0))
        return list(result)
    return stage


def test_a_github_server_error_runs_the_stage_again_and_any_other_error_stops_it():
    waits = []
    stage = flaky(["cannot create the GitHub release v5.1.0: HTTP 502: Server Error",
                   "cannot prepare tap: unexpected end of JSON input"])
    assert release.retrying(stage, sleep=waits.append) == ["done"] and waits == [20, 40]
    waits.clear()
    with pytest.raises(setup.SetupError, match="HTTP 403"):
        release.retrying(flaky(["cannot create the GitHub release v5.1.0: HTTP 403"]), sleep=waits.append)
    assert waits == []
    with pytest.raises(setup.SetupError, match="503 Service Unavailable"):
        release.retrying(flaky(["503 Service Unavailable"] * 3), sleep=waits.append)
    assert waits == [20, 40]


def test_a_release_github_created_while_answering_502_is_not_created_twice(tmp_path):
    """2026-11-05: GitHub answered 502 to `gh release create` and published the release anyway."""
    repo = source_repo(tmp_path)
    git(repo, "remote", "add", "github", "https://github.com/example/demo.git")
    calls, made = [], []

    def run(argv, **kwargs):
        calls.append(argv)
        if argv[:3] == ["gh", "release", "view"]:
            return subprocess.CompletedProcess(argv, 0 if made else 1, "", "")
        if argv[:3] == ["gh", "release", "create"]:
            made.append(argv)
            return subprocess.CompletedProcess(argv, 1, "", "HTTP 502: Server Error (https://api.github.com/repos)")
        return subprocess.CompletedProcess(argv, 0, json.dumps([{"tagName": "v5.1.0", "isLatest": True}]), "")
    assert release.retrying(release.github_release, repo, "5.1.0", run=run, sleep=lambda s: None) == [
        "example/demo: GitHub release v5.1.0, latest"]
    assert len(made) == 1


def test_a_tap_pull_request_answered_502_is_opened_on_the_next_attempt(tmp_path):
    run, calls, _ = tap_fake(create_502s=1)
    lines, formula = release.retrying(release.homebrew_formula, canonical_repo(tmp_path), "5.1.0", run=run,
                                      fetch=lambda url: DIGEST, sleep=lambda s: None)
    assert formula["pr"] == PR and lines[0].startswith(f"{release.TAP}: {PR} points the formula at v5.1.0")
    assert len([c for c in calls if c[:3] == ["gh", "pr", "create"]]) == 2  # the second one opened it
    assert ["gh", "pr", "merge", PR, "-R", release.TAP, "--auto", "--merge"] in calls


def test_ci_state_reads_again_after_a_server_error():
    replies = [subprocess.CompletedProcess([], 1, "", "HTTP 502: Bad Gateway"),
               subprocess.CompletedProcess([], 0, json.dumps([{"status": "completed", "conclusion": "success",
                                                              "workflowName": "CI"}]), "")]
    waits = []
    assert release.ci_state(Path("."), "a" * 40, run=lambda *a, **k: replies.pop(0), sleep=waits.append)[0] is True
    assert waits == [10]


@pytest.mark.parametrize("answer, note", [
    ("", ""),  # the release deleted it
    # gh's words, read 2026-11-05, for a branch already gone: the tap deletes a merged branch itself
    ("gh: Reference does not exist (HTTP 422)", ""),
    ("gh: Resource not accessible by integration (HTTP 403)",
     "; branch synthesis-5.1.0 left: gh: Resource not accessible by integration (HTTP 403)"),
])
def test_a_merged_tap_branch_is_gone_after_the_release_and_one_left_is_reported_not_fatal(answer, note):
    formula = {"pr": PR, "version": "5.1.0", "sha256": DIGEST, "branch": "synthesis-5.1.0"}
    served = FORMULA_RB.replace("v5.0.3", "v5.1.0").replace(OLD_SHA, DIGEST)
    run = tap_fake(views=[{"state": "MERGED"}], merged_text=served, delete_err=answer)[0]
    assert release.homebrew_merged(formula, run=run, sleep=lambda s: None) == [
        f"{release.TAP}: Homebrew serves synthesis 5.1.0 ({PR} merged{note})"]


# ---- installed bytes against the tag -------------------------------------------

def test_installed_bytes_must_equal_the_tag_whatever_the_label(tmp_path):
    repo = source_repo(tmp_path)
    git(repo, "tag", "v5.1.0")
    installed = tmp_path / "installed"
    setup.export_tree(repo, installed, "v5.1.0")
    assert release.tree_differences(repo, "v5.1.0", installed) == []
    (installed / "skills" / "demo" / "SKILL.md").write_text("stale\n")  # an unbumped edit: same label, old bytes
    (installed / "skills" / "demo" / "extra.md").write_text("x")
    (installed / "skills" / "demo" / "__pycache__").mkdir()
    (installed / "skills" / "demo" / "__pycache__" / "x.pyc").write_bytes(b"\0")
    (installed / ".claude-plugin" / "plugin.json").unlink()
    assert release.tree_differences(repo, "v5.1.0", installed) == [
        "missing .claude-plugin/plugin.json", "differs skills/demo/SKILL.md", "extra skills/demo/extra.md"]


def test_verification_reads_the_folder_the_harness_reports(tmp_path, monkeypatch):
    repo = source_repo(tmp_path)
    git(repo, "tag", "v5.1.0")
    good, stale = tmp_path / "good", tmp_path / "stale"
    setup.export_tree(repo, good, "v5.1.0")
    setup.export_tree(repo, stale, "v5.1.0")
    (stale / "skills" / "demo" / "SKILL.md").write_text("old\n")
    roots = {"claude": (good, "5.1.0"), "codex": (stale, "5.1.0")}
    monkeypatch.setattr(release.doctor, "find_client", lambda name: name if name in roots else None)
    monkeypatch.setattr(setup, "install_plugin", lambda client, binary, **k: f"{client}: updated")
    monkeypatch.setattr(release, "installed_root", lambda client, binary: roots[client])
    lines, verified, found = release.install_and_verify(repo, "5.1.0", ["claude", "codex", "muse"])
    assert set(verified) == {"claude"} and found == ["claude", "codex"]
    assert "muse: not on this Mac; skipped" in lines
    assert any(line.startswith("codex: NOT verified") and "differs skills/demo/SKILL.md" in line for line in lines)



def test_a_release_keeps_codexs_user_level_declaration_in_step_with_the_plugin_it_verified(tmp_path, monkeypatch):
    """Review round 1 of 5.21.0, R1-19: the option's step moved out of install_plugin, so a refusal there no longer hides
    the install's line; the release runs it itself against the folder it verified."""
    repo = source_repo(tmp_path)
    git(repo, "tag", "v5.1.0")
    good = tmp_path / "good"
    setup.export_tree(repo, good, "v5.1.0")
    monkeypatch.setattr(release.doctor, "find_client", lambda name: name if name == "codex" else None)
    monkeypatch.setattr(setup, "install_plugin", lambda client, binary, **k: f"{client}: updated")
    monkeypatch.setattr(release, "installed_root", lambda client, binary: (good, "5.1.0"))
    monkeypatch.setattr(setup, "codex_user_hooks_on", lambda: True)
    asked = []
    monkeypatch.setattr(setup, "codex_user_hooks", lambda want, root=None, dry_run=False: asked.append((want, root))
                        or ["codex user hooks: already declared"])
    lines, verified, _ = release.install_and_verify(repo, "5.1.0", ["codex"])
    assert asked == [(None, good)] and "codex user hooks: already declared" in lines and set(verified) == {"codex"}

def test_a_wrong_reported_version_fails_even_with_matching_bytes(tmp_path, monkeypatch):
    repo = source_repo(tmp_path)
    git(repo, "tag", "v5.1.0")
    good = tmp_path / "good"
    setup.export_tree(repo, good, "v5.1.0")
    monkeypatch.setattr(release.doctor, "find_client", lambda name: name)
    monkeypatch.setattr(setup, "install_plugin", lambda client, binary, **k: "updated")
    monkeypatch.setattr(release, "installed_root", lambda client, binary: (good, "5.0.9"))
    lines, verified, _ = release.install_and_verify(repo, "5.1.0", ["claude"])
    assert not verified and "reports 5.0.9, not 5.1.0" in lines[-1]


def test_the_script_runs_with_no_folder_of_the_callers_on_its_path():
    """Python's isolated mode (-I) leaves even the script's own folder off its path; the release loads the collections
    builder beside it, which a check under Apple's Python 3.9 found it could not do (5.22.0, before merging)."""
    script = Path(release.__file__).resolve()
    ran = subprocess.run([sys.executable, "-I", str(script), "--help"], capture_output=True, text=True)
    assert ran.returncode == 0 and ran.stdout.startswith("usage: release.py"), ran.stderr[-500:]


# ---- one collections commit for one release, on every remote (R1-22 of 5.22.0's review) -------------

def test_every_remote_gets_one_collections_commit_for_one_release_even_after_a_refusal(tmp_path, monkeypatch):
    """The commit was made for each remote and stamped with the time of the call, so two remotes, or a run again after
    one refused, ended with different commits for one release: a mirror could not serve a commit the other named."""
    repo, late = source_repo(tmp_path), tmp_path / "late.git"
    git(repo, "remote", "add", "zeta", str(late))  # after origin, and not there yet: this remote refuses
    for moment, refused in (("2026-11-14T09:00:00+00:00", True), ("2026-11-14T10:30:00+00:00", False)):
        monkeypatch.setenv("GIT_AUTHOR_DATE", moment)
        monkeypatch.setenv("GIT_COMMITTER_DATE", moment)
        if refused:
            with pytest.raises(setup.SetupError, match="zeta"):
                release.publish(repo, "5.1.0")
            subprocess.run(["git", "init", "-q", "--bare", str(late)], check=True)
        else:
            release.publish(repo, "5.1.0")  # the run again, an hour and a half later
    assert git(tmp_path / "remote0.git", "rev-parse", "collections") == git(late, "rev-parse", "collections")


def test_the_collections_commit_takes_the_release_commit_s_identity_and_time_and_names_it(tmp_path):
    repo = source_repo(tmp_path, remotes=2)
    release.publish(repo, "5.1.0")
    stamp, head = git(repo, "log", "-1", "--format=%cn|%ce|%cI", "HEAD"), git(repo, "rev-parse", "HEAD")
    for bare in (tmp_path / "remote0.git", tmp_path / "remote1.git"):
        made = git(bare, "log", "-1", "--format=%an|%ae|%aI%n%cn|%ce|%cI%n%B", "collections").splitlines()
        assert made[0] == made[1] == stamp and f"Built from {head}" in "\n".join(made[2:])
    assert git(tmp_path / "remote0.git", "rev-parse", "collections") == git(tmp_path / "remote1.git", "rev-parse", "collections")


def test_a_refused_push_says_where_the_collections_branch_should_have_pointed(tmp_path):
    repo = source_repo(tmp_path)
    other = tmp_path / "other"
    subprocess.run(["git", "clone", "-q", str(tmp_path / "remote0.git"), str(other)], check=True)
    (other / "x").write_text("x")
    git(other, "add", ".")
    git(other, "commit", "-qm", "ahead")
    git(other, "push", "-q", "origin", "main")  # the remote moved, so the atomic push refuses every ref
    with pytest.raises(setup.SetupError) as refused:
        release.publish(repo, "5.1.0")
    said = str(refused.value)
    assert re.search(r"refs/heads/main, refs/heads/stable, refs/tags/v5\.1\.0 do not point at [0-9a-f]{12}", said), said
    assert re.search(r"refs/heads/collections does not point at [0-9a-f]{12}", said), said
