#!/usr/bin/env python3
"""Tests for pr_queue_scan.

The motivating defect is a coverage lie, not a parsing bug: a review that does
not read the PR queue still reports a clean result. So the tests that matter
most here are the ones asserting that anything NOT read is reported as not read.
"""
from __future__ import annotations

import datetime
import importlib.util
import json
from pathlib import Path

import pytest

SPEC = importlib.util.spec_from_file_location(
    "pr_queue_scan", Path(__file__).with_name("pr_queue_scan.py")
)
mod = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(mod)

NOW = datetime.datetime(2026, 9, 5, 12, 0, tzinfo=datetime.timezone.utc)


def write_yaml(tmp_path: Path, text: str) -> Path:
    p = tmp_path / "repos.yaml"
    p.write_text(text)
    return p


# --- the declared list is the complete decision ------------------------------

def test_declared_repos_does_not_filter_by_ritual_sync(tmp_path):
    """The load-bearing case: skill sources carry ritual_sync: no and still have PRs.

    Filtering a review queue by a source-sync policy is what hid two open pull
    requests authored under the principal's own account.
    """
    p = write_yaml(tmp_path, """
repos:
  - name: alpha
    ritual_sync: yes
  - name: skill-source
    ritual_sync: no
  - name: context-repo
    ritual_sync: no
""")
    names = [r["name"] for r in mod.declared_repos(p)]
    assert names == ["alpha", "skill-source", "context-repo"]


def test_declared_repos_honors_dormant_status(tmp_path):
    """Dormancy is about the repo, not about one workflow's interest in it."""
    p = write_yaml(tmp_path, """
repos:
  - name: alpha
    ritual_sync: yes
  - name: retired
    status: dormant
    ritual_sync: yes
""")
    assert [r["name"] for r in mod.declared_repos(p)] == ["alpha"]


def test_declared_repos_accepts_mapping_form(tmp_path):
    p = write_yaml(tmp_path, """
repos:
  alpha:
    ritual_sync: yes
  beta:
    ritual_sync: no
""")
    assert sorted(r["name"] for r in mod.declared_repos(p)) == ["alpha", "beta"]


# --- host detection ----------------------------------------------------------

@pytest.mark.parametrize("url,expected", [
    ("https://github.com/owner/repo.git", ("github.com", "owner", "repo")),
    ("git@github.com:owner/repo.git", ("github.com", "owner", "repo")),
    ("https://github.com/owner/repo", ("github.com", "owner", "repo")),
    ("https://github.com/owner/repo/", ("github.com", "owner", "repo")),
    ("https://github.com/owner/my.site.git", ("github.com", "owner", "my.site")),
    ("https://bitbucket.org/team/repo.git", ("bitbucket.org", "team", "repo")),
    ("git@bitbucket.org:team/repo.git", ("bitbucket.org", "team", "repo")),
    ("ssh://git@bitbucket.org/team/repo.git", ("bitbucket.org", "team", "repo")),
])
def test_remote_target_parses_supported_remotes(url, expected):
    assert mod.remote_target(url) == expected


@pytest.mark.parametrize("url", [
    "git@gitlab.com:team/repo.git",
    "https://git.internal.example/team/repo.git",
    "https://github.com/owner",
    "",
])
def test_remote_target_refuses_to_guess_other_hosts(url):
    """A remote on neither supported host yields None so the caller reports it unscanned."""
    assert mod.remote_target(url) is None


def test_declared_target_prefers_the_manifest_over_the_working_copy(tmp_path):
    """A PR queue is a remote fact: a declared repo with no clone is still scannable."""
    entry = {"remotes": {"origin": "https://github.com/owner/repo.git"}}
    assert mod.declared_target(entry, tmp_path / "does-not-exist") == (
        ("github.com", "owner", "repo"), None)
    entry = {"remotes": {"origin": "git@bitbucket.org:team/repo.git"}}
    assert mod.declared_target(entry, tmp_path / "does-not-exist") == (
        ("bitbucket.org", "team", "repo"), None)


def test_declared_target_names_an_unsupported_manifest_origin(tmp_path):
    entry = {"remotes": {"origin": "git@gitlab.com:team/repo.git"}}
    target, reason = mod.declared_target(entry, tmp_path)
    assert target is None
    assert reason == "origin git@gitlab.com:team/repo.git is on neither github.com nor bitbucket.org"


def test_declared_target_falls_back_to_git_when_manifest_is_silent(monkeypatch, tmp_path):
    tmp_path.mkdir(exist_ok=True)
    monkeypatch.setattr(mod.subprocess, "run",
                        lambda *a, **k: type("R", (), {
                            "returncode": 0, "stdout": "git@github.com:o/r.git"})())
    assert mod.declared_target({}, tmp_path) == (("github.com", "o", "r"), None)


def test_declared_target_names_a_missing_clone(tmp_path):
    target, reason = mod.declared_target({}, tmp_path / "nope")
    assert target is None
    assert reason == "no origin declared in the manifest, and no local clone at %s" % (tmp_path / "nope")


def test_declared_target_names_an_unsupported_working_copy_origin(monkeypatch, tmp_path):
    monkeypatch.setattr(mod.subprocess, "run",
                        lambda *a, **k: type("R", (), {
                            "returncode": 0, "stdout": "git@gitlab.com:o/r.git\n"})())
    target, reason = mod.declared_target({}, tmp_path)
    assert target is None
    assert reason == "origin git@gitlab.com:o/r.git of %s is on neither github.com nor bitbucket.org" % tmp_path


def test_repo_path_resolves_manifest_paths_against_the_workspace_root(monkeypatch, tmp_path):
    """The manifest writes `path: name/`, relative to the workspace root.

    Resolving that against the process CWD instead is what once made every
    declared repo look like it had no local clone.
    """
    monkeypatch.setenv("SYNTHESIS_WORKSPACES", str(tmp_path))
    got = mod.repo_path({"name": "alpha", "path": "alpha/"}, "ws")
    assert got == tmp_path / "ws" / "alpha"
    assert got.is_absolute()


def test_repo_path_leaves_absolute_paths_alone(monkeypatch, tmp_path):
    monkeypatch.setenv("SYNTHESIS_WORKSPACES", str(tmp_path))
    assert mod.repo_path({"name": "a", "path": "/opt/a"}, "ws") == Path("/opt/a")


def test_age_days_counts_from_created_at():
    assert mod.age_days("2026-08-29T12:00:00Z", NOW) == 7
    assert mod.age_days("not-a-date", NOW) == 0


# --- classification ----------------------------------------------------------

def _fake_gh(rows):
    def run(cmd, **kwargs):
        return type("R", (), {"returncode": 0, "stdout": json.dumps(rows), "stderr": ""})()
    return run


def test_query_repo_splits_review_requested_from_own(monkeypatch):
    monkeypatch.setattr(mod.subprocess, "run", _fake_gh([
        {"number": 1, "title": "theirs, awaiting me", "createdAt": "2026-04-19T12:00:00Z",
         "author": {"login": "someone"}, "reviewRequests": [{"login": "me"}], "isDraft": False},
        {"number": 2, "title": "mine", "createdAt": "2026-09-01T12:00:00Z",
         "author": {"login": "me"}, "reviewRequests": [], "isDraft": True},
        {"number": 3, "title": "unrelated", "createdAt": "2026-09-01T12:00:00Z",
         "author": {"login": "other"}, "reviewRequests": [{"login": "third"}], "isDraft": False},
    ]))
    items, err = mod.query_repo("o/r", "me", NOW)
    assert err is None
    kinds = {i["number"]: i["kind"] for i in items}
    assert kinds == {1: "review-requested", 2: "own-open"}
    assert [i for i in items if i["number"] == 1][0]["age_days"] == 139


def test_query_repo_claims_unreviewed_prs_in_your_own_namespace(monkeypatch):
    """A bot's PR in your own repo is yours to merge or close.

    Without this bucket a maintainer's dependency backlog is invisible in the
    maintainer's own repositories, which is where it matters most.
    """
    monkeypatch.setattr(mod.subprocess, "run", _fake_gh([
        {"number": 10, "title": "Bump a dependency", "createdAt": "2026-09-01T12:00:00Z",
         "author": {"login": "dependabot[bot]"}, "reviewRequests": [], "isDraft": False},
    ]))
    items, err = mod.query_repo("anyorg/myrepo", "me", NOW)
    assert err is None
    assert [i["kind"] for i in items] == ["in-your-repo"]


def test_query_repo_leaves_someone_elses_review_alone(monkeypatch):
    """If another person is the requested reviewer, it is not the user's queue."""
    monkeypatch.setattr(mod.subprocess, "run", _fake_gh([
        {"number": 11, "title": "theirs", "createdAt": "2026-09-01T12:00:00Z",
         "author": {"login": "someone"}, "reviewRequests": [{"login": "third"}],
         "isDraft": False},
    ]))
    items, _ = mod.query_repo("me/myrepo", "me", NOW)
    assert items == []


def test_query_repo_claims_unreviewed_prs_regardless_of_namespace(monkeypatch):
    """Declaration is the ownership signal, not the GitHub namespace.

    A personal repo often lives under an org the user runs, so comparing owner
    to login misses exactly the repos they care most about. Being in the
    workspace manifest at all is what makes a repo theirs.
    """
    monkeypatch.setattr(mod.subprocess, "run", _fake_gh([
        {"number": 12, "title": "bot bump in my org repo", "createdAt": "2026-09-01T12:00:00Z",
         "author": {"login": "app/dependabot"}, "reviewRequests": [], "isDraft": False},
    ]))
    items, _ = mod.query_repo("someorg-i-run/repo", "me", NOW)
    assert [i["kind"] for i in items] == ["in-your-repo"]


def test_query_repo_reports_error_rather_than_empty(monkeypatch):
    def failing(cmd, **kwargs):
        return type("R", (), {"returncode": 1, "stdout": "", "stderr": "HTTP 404"})()
    monkeypatch.setattr(mod.subprocess, "run", failing)
    items, err = mod.query_repo("o/r", "me", NOW)
    assert items == []
    assert err == "HTTP 404"


# --- the invariant this script exists for ------------------------------------

def _no_cli(monkeypatch):
    """Fail loudly if a scan reaches for a host CLI the test did not stub."""
    def refuse(*a, **k):
        raise AssertionError("scan reached a host CLI: %r" % (a[:1],))
    monkeypatch.setattr(mod, "gh_login", refuse)
    monkeypatch.setattr(mod, "bkt_identity", refuse)
    monkeypatch.setattr(mod, "query_repo", refuse)
    monkeypatch.setattr(mod, "query_bitbucket_repo", refuse)


def test_unscannable_repos_are_named_not_silently_dropped(monkeypatch, tmp_path):
    """A repo that could not be read must never contribute to a clean-looking result."""
    _no_cli(monkeypatch)
    (tmp_path / "present").mkdir()
    repos = [
        {"name": "present", "path": str(tmp_path / "present")},
        {"name": "absent", "path": str(tmp_path / "nope")},
        {"name": "elsewhere", "remotes": {"origin": "git@gitlab.com:team/repo.git"}},
    ]
    monkeypatch.setattr(mod.subprocess, "run",
                        lambda *a, **k: type("R", (), {
                            "returncode": 0, "stdout": "https://git.internal.example/t/r.git"})())

    result = mod.scan(repos, "ws", "me", NOW)

    assert result["found"] == []
    assert result["scanned"] == []
    reasons = {u["repo"]: u["reason"] for u in result["unscanned"]}
    assert set(reasons) == {"present", "absent", "elsewhere"}
    assert reasons["present"] == (
        "origin https://git.internal.example/t/r.git of %s is on neither github.com nor bitbucket.org"
        % (tmp_path / "present"))
    assert reasons["absent"] == (
        "no origin declared in the manifest, and no local clone at %s" % (tmp_path / "nope"))
    assert reasons["elsewhere"] == (
        "origin git@gitlab.com:team/repo.git is on neither github.com nor bitbucket.org")


def test_scan_sorts_oldest_first(monkeypatch, tmp_path):
    _no_cli(monkeypatch)

    def fake_query(slug, login, now):
        n = 200 if slug.endswith("a") else 3
        return ([{"repo": slug, "number": 1, "title": "t", "kind": "review-requested",
                  "draft": False, "age_days": n, "url": ""}], None)

    monkeypatch.setattr(mod, "query_repo", fake_query)
    result = mod.scan(
        [{"name": "a", "remotes": {"origin": "https://github.com/o/a.git"}},
         {"name": "b", "remotes": {"origin": "https://github.com/o/b.git"}}], "ws", "me", NOW)
    assert [i["age_days"] for i in result["found"]] == [200, 3]
    assert result["login"] == "me"


# --- dispatch by host --------------------------------------------------------

ME = {"uuid": "{me-uuid}", "account_id": "me-account", "username": "me"}


def _bkt_runner(pr_rows, user=ME, pr_rc=0, pr_stderr=""):
    """A stand-in for subprocess.run that answers only bkt, recording argv."""
    def run(cmd, **kwargs):
        run.calls.append(list(cmd))
        if cmd[:2] == ["bkt", "api"]:
            return type("R", (), {"returncode": 0, "stdout": json.dumps(user), "stderr": ""})()
        if cmd[:3] == ["bkt", "pr", "list"]:
            body = json.dumps({"workspace": cmd[4], "repo": cmd[6], "pull_requests": pr_rows})
            return type("R", (), {"returncode": pr_rc, "stdout": body if pr_rc == 0 else "",
                                  "stderr": pr_stderr})()
        raise AssertionError("unexpected invocation: %r" % (cmd,))
    run.calls = []
    return run


def _inject_bkt_runner(monkeypatch, run):
    """Route the real sibling helper's subprocess calls through `run`.

    The helper is the actual synthesis-bitbucket/scripts/pr_queue.py, loaded
    the way the scan loads it, so this exercises the dispatch end to end with
    only the process boundary replaced.
    """
    import functools
    helper = mod.bitbucket_helper()
    monkeypatch.setattr(helper, "list_open_prs",
                        functools.partial(helper.list_open_prs, runner=run))
    monkeypatch.setattr(helper, "bkt_identity",
                        functools.partial(helper.bkt_identity, runner=run))
    monkeypatch.setattr(mod.shutil, "which", lambda name: "/opt/homebrew/bin/bkt" if name == "bkt" else None)
    return helper


def test_bitbucket_helper_is_the_sibling_skill_module():
    helper = mod.bitbucket_helper()
    expected = Path(__file__).resolve().parents[2] / "synthesis-bitbucket" / "scripts" / "pr_queue.py"
    assert Path(helper.__file__) == expected
    assert callable(helper.list_open_prs) and callable(helper.bkt_identity)
    assert mod.bitbucket_helper() is helper  # loaded once per process


def test_scan_dispatches_bitbucket_origins_to_the_bitbucket_helper(monkeypatch):
    """A bitbucket.org origin is scanned through bkt, bucketed by uuid, slug passed alone."""
    monkeypatch.setattr(mod, "gh_login", lambda: (_ for _ in ()).throw(AssertionError("gh called")))
    monkeypatch.setattr(mod, "query_repo", lambda *a, **k: (_ for _ in ()).throw(AssertionError("gh called")))
    run = _bkt_runner([
        {"id": 41, "title": "theirs, awaiting me", "state": "OPEN", "draft": False,
         "created_on": "2026-04-19T12:00:00.000000+00:00",
         "author": {"uuid": "{someone}"}, "reviewers": [{"uuid": "{me-uuid}"}]},
        {"id": 42, "title": "mine", "state": "OPEN", "draft": True,
         "created_on": "2026-09-01T12:00:00.000000+00:00",
         "author": {"uuid": "{me-uuid}"}, "reviewers": []},
        {"id": 43, "title": "someone else's review", "state": "OPEN", "draft": False,
         "created_on": "2026-09-01T12:00:00.000000+00:00",
         "author": {"uuid": "{other}"}, "reviewers": [{"uuid": "{third}"}]},
    ])
    _inject_bkt_runner(monkeypatch, run)

    result = mod.scan(
        [{"name": "csa", "remotes": {"origin": "git@bitbucket.org:team/content-scaling-agents.git"}}],
        "ws", None, NOW)

    assert result["scanned"] == ["csa"]
    assert result["unscanned"] == []
    assert [(i["number"], i["kind"], i["age_days"], i["repo"]) for i in result["found"]] == [
        (41, "review-requested", 139, "team/content-scaling-agents"),
        (42, "own-open", 4, "team/content-scaling-agents"),
    ]
    assert run.calls == [
        ["bkt", "api", "/user", "--json"],
        ["bkt", "pr", "list", "--workspace", "team", "--repo", "content-scaling-agents",
         "--state", "OPEN", "--limit", "0", "--json"],
    ]


def test_scan_resolves_the_bitbucket_identity_once_for_many_repos(monkeypatch):
    run = _bkt_runner([])
    _inject_bkt_runner(monkeypatch, run)
    result = mod.scan(
        [{"name": "a", "remotes": {"origin": "git@bitbucket.org:team/a.git"}},
         {"name": "b", "remotes": {"origin": "https://bitbucket.org/team/b.git"}}], "ws", None, NOW)
    assert result["scanned"] == ["a", "b"]
    assert [c[:2] for c in run.calls].count(["bkt", "api"]) == 1
    assert [c[6] for c in run.calls if c[:3] == ["bkt", "pr", "list"]] == ["a", "b"]


def test_scan_reports_a_bitbucket_404_as_unscanned_not_empty(monkeypatch):
    run = _bkt_runner([], pr_rc=1, pr_stderr="Error: HTTP 404 Not Found: repository team/gone")
    _inject_bkt_runner(monkeypatch, run)
    result = mod.scan(
        [{"name": "gone", "remotes": {"origin": "git@bitbucket.org:team/gone.git"}}], "ws", None, NOW)
    assert result["scanned"] == []
    assert result["found"] == []
    assert result["unscanned"] == [
        {"repo": "gone", "reason": "Error: HTTP 404 Not Found: repository team/gone"}]


def test_scan_marks_bitbucket_repos_unscanned_when_bkt_is_missing(monkeypatch):
    monkeypatch.setattr(mod.shutil, "which", lambda name: None)
    monkeypatch.setattr(mod, "query_bitbucket_repo",
                        lambda *a, **k: (_ for _ in ()).throw(AssertionError("queried without bkt")))
    result = mod.scan(
        [{"name": "csa", "remotes": {"origin": "git@bitbucket.org:team/csa.git"}}], "ws", None, NOW)
    assert result["scanned"] == []
    assert result["unscanned"] == [{"repo": "csa", "reason": "bkt CLI not installed"}]


def test_scan_marks_bitbucket_repos_unscanned_when_bkt_is_unauthenticated(monkeypatch):
    def run(cmd, **kwargs):
        assert cmd == ["bkt", "api", "/user", "--json"]
        return type("R", (), {"returncode": 1, "stdout": "", "stderr": "Error: not logged in"})()
    _inject_bkt_runner(monkeypatch, run)
    result = mod.scan(
        [{"name": "csa", "remotes": {"origin": "git@bitbucket.org:team/csa.git"}}], "ws", None, NOW)
    assert result["unscanned"] == [{"repo": "csa", "reason": "bkt api /user failed: Error: not logged in"}]


def test_scan_marks_github_repos_unscanned_when_gh_is_missing_and_still_scans_bitbucket(monkeypatch):
    """One host's missing CLI must not hide the other host's queue."""
    run = _bkt_runner([
        {"id": 5, "title": "mine", "state": "OPEN", "draft": False,
         "created_on": "2026-09-01T12:00:00+00:00", "author": {"uuid": "{me-uuid}"}, "reviewers": []},
    ])
    _inject_bkt_runner(monkeypatch, run)
    monkeypatch.setattr(mod.shutil, "which", lambda name: "/opt/homebrew/bin/bkt" if name == "bkt" else None)
    monkeypatch.setattr(mod, "query_repo",
                        lambda *a, **k: (_ for _ in ()).throw(AssertionError("gh queried while missing")))
    result = mod.scan(
        [{"name": "gh-repo", "remotes": {"origin": "https://github.com/o/gh-repo.git"}},
         {"name": "bb-repo", "remotes": {"origin": "git@bitbucket.org:team/bb-repo.git"}}], "ws", None, NOW)
    assert result["scanned"] == ["bb-repo"]
    assert result["unscanned"] == [{"repo": "gh-repo", "reason": "gh CLI not installed"}]
    assert [i["number"] for i in result["found"]] == [5]
    assert result["login"] is None


def test_scan_never_calls_a_host_cli_the_manifest_does_not_need(monkeypatch):
    """A GitHub-only workspace must not touch bkt, and a --login skips gh entirely."""
    monkeypatch.setattr(mod, "bkt_identity",
                        lambda: (_ for _ in ()).throw(AssertionError("bkt api /user called needlessly")))
    monkeypatch.setattr(mod, "gh_login",
                        lambda: (_ for _ in ()).throw(AssertionError("gh api user called despite --login")))
    monkeypatch.setattr(mod, "query_repo", lambda slug, login, now: ([], None))
    result = mod.scan(
        [{"name": "a", "remotes": {"origin": "https://github.com/o/a.git"}}], "ws", "me", NOW)
    assert result["scanned"] == ["a"]


# --- it is a surface, never a gate -------------------------------------------

def test_missing_repos_yaml_exits_zero(monkeypatch, capsys, tmp_path):
    monkeypatch.setattr(mod.sys, "argv", ["pr_queue_scan.py", "--repos-yaml", str(tmp_path / "none.yaml")])
    assert mod.main() == 0
    assert "nothing declared to scan" in capsys.readouterr().out


def test_missing_gh_exits_zero_and_names_each_github_repo_not_scanned(monkeypatch, capsys, tmp_path):
    p = write_yaml(tmp_path, """
repos:
  - name: alpha
    remotes:
      origin: https://github.com/o/alpha.git
""")
    monkeypatch.setattr(mod.sys, "argv", ["pr_queue_scan.py", "--repos-yaml", str(p)])
    monkeypatch.setattr(mod.shutil, "which", lambda _: None)
    assert mod.main() == 0
    out = capsys.readouterr().out
    assert "0 repo(s) scanned, 1 not scanned" in out
    assert "NOT SCANNED" in out
    assert "alpha" in out and "gh CLI not installed" in out


def test_unauthenticated_gh_exits_zero_and_names_each_github_repo_not_scanned(monkeypatch, capsys, tmp_path):
    p = write_yaml(tmp_path, """
repos:
  - name: alpha
    remotes:
      origin: https://github.com/o/alpha.git
""")
    monkeypatch.setattr(mod.sys, "argv", ["pr_queue_scan.py", "--repos-yaml", str(p)])
    monkeypatch.setattr(mod.shutil, "which", lambda _: "/usr/bin/gh")
    monkeypatch.setattr(mod, "gh_login", lambda: (None, "gh is not authenticated"))
    assert mod.main() == 0
    out = capsys.readouterr().out
    assert "NOT SCANNED" in out
    assert "alpha" in out and "gh is not authenticated" in out


def test_main_prints_bitbucket_hits_and_json_carries_both_hosts(monkeypatch, capsys, tmp_path):
    p = write_yaml(tmp_path, """
repos:
  - name: csa
    remotes:
      origin: git@bitbucket.org:team/csa.git
  - name: alpha
    remotes:
      origin: https://github.com/o/alpha.git
""")
    created = "2026-04-19T12:00:00+00:00"
    run = _bkt_runner([
        {"id": 9, "title": "awaiting me", "state": "OPEN", "draft": False,
         "created_on": created,
         "author": {"uuid": "{someone}"}, "reviewers": [{"uuid": "{me-uuid}"}]},
    ])
    _inject_bkt_runner(monkeypatch, run)
    monkeypatch.setattr(mod, "query_repo", lambda slug, login, now: ([], None))
    monkeypatch.setattr(mod.sys, "argv", ["pr_queue_scan.py", "--repos-yaml", str(p), "--login", "me"])
    assert mod.main() == 0
    out = capsys.readouterr().out
    assert "2 repo(s) scanned, 0 not scanned" in out
    assert "Waiting on your review (1)" in out
    # main() reads the real clock, so the age is computed the same way it is.
    age = mod.age_days(created, datetime.datetime.now(datetime.timezone.utc))
    assert "%4dd  team/csa#9  awaiting me" % age in out

    monkeypatch.setattr(mod.sys, "argv", ["pr_queue_scan.py", "--repos-yaml", str(p), "--login", "me", "--json"])
    assert mod.main() == 0
    data = json.loads(capsys.readouterr().out)
    assert data["scanned"] == ["csa", "alpha"]
    assert data["login"] == "me"
    assert [i["url"] for i in data["found"]] == ["https://bitbucket.org/team/csa/pull-requests/9"]
