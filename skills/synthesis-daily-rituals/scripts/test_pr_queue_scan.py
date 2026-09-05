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
    ("https://github.com/owner/repo.git", "owner/repo"),
    ("git@github.com:owner/repo.git", "owner/repo"),
    ("https://github.com/owner/repo", "owner/repo"),
])
def test_slug_from_url_parses_supported_remotes(url, expected):
    assert mod.slug_from_url(url) == expected


@pytest.mark.parametrize("url", [
    "https://bitbucket.org/team/repo.git",
    "git@gitlab.com:team/repo.git",
    "https://git.internal.example/team/repo.git",
])
def test_slug_from_url_refuses_to_guess_other_hosts(url):
    """A non-GitHub remote yields None so the caller reports it unscanned."""
    assert mod.slug_from_url(url) is None


def test_github_slug_prefers_the_manifest_over_the_working_copy(tmp_path):
    """A PR queue is a remote fact: a declared repo with no clone is still scannable."""
    entry = {"remotes": {"origin": "https://github.com/owner/repo.git"}}
    assert mod.github_slug(entry, tmp_path / "does-not-exist") == "owner/repo"


def test_github_slug_falls_back_to_git_when_manifest_is_silent(monkeypatch, tmp_path):
    tmp_path.mkdir(exist_ok=True)
    monkeypatch.setattr(mod.subprocess, "run",
                        lambda *a, **k: type("R", (), {
                            "returncode": 0, "stdout": "git@github.com:o/r.git"})())
    assert mod.github_slug({}, tmp_path) == "o/r"


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

def test_unscannable_repos_are_named_not_silently_dropped(monkeypatch, tmp_path):
    """A repo that could not be read must never contribute to a clean-looking result."""
    (tmp_path / "present").mkdir()
    repos = [
        {"name": "present", "path": str(tmp_path / "present")},
        {"name": "absent", "path": str(tmp_path / "nope")},
    ]
    monkeypatch.setattr(mod, "github_slug", lambda e, d: None)  # unsupported host

    result = mod.scan(repos, "ws", "me", NOW)

    assert result["found"] == []
    assert result["scanned"] == []
    reasons = {u["repo"]: u["reason"] for u in result["unscanned"]}
    assert set(reasons) == {"present", "absent"}
    assert "no GitHub remote declared" in reasons["present"]
    assert "no GitHub remote declared" in reasons["absent"]


def test_scan_sorts_oldest_first(monkeypatch, tmp_path):
    (tmp_path / "a").mkdir()
    (tmp_path / "b").mkdir()
    monkeypatch.setattr(mod, "github_slug", lambda e, d: "o/" + e["name"])

    def fake_query(slug, login, now):
        n = 200 if slug.endswith("a") else 3
        return ([{"repo": slug, "number": 1, "title": "t", "kind": "review-requested",
                  "draft": False, "age_days": n, "url": ""}], None)

    monkeypatch.setattr(mod, "query_repo", fake_query)
    result = mod.scan(
        [{"name": "a", "path": str(tmp_path / "a")},
         {"name": "b", "path": str(tmp_path / "b")}], "ws", "me", NOW)
    assert [i["age_days"] for i in result["found"]] == [200, 3]


# --- it is a surface, never a gate -------------------------------------------

def test_missing_repos_yaml_exits_zero(monkeypatch, capsys, tmp_path):
    monkeypatch.setattr(mod.sys, "argv", ["pr_queue_scan.py", "--repos-yaml", str(tmp_path / "none.yaml")])
    assert mod.main() == 0
    assert "nothing declared to scan" in capsys.readouterr().out


def test_missing_gh_exits_zero_and_says_not_scanned(monkeypatch, capsys, tmp_path):
    p = write_yaml(tmp_path, "repos:\n  - name: alpha\n    ritual_sync: yes\n")
    monkeypatch.setattr(mod.sys, "argv", ["pr_queue_scan.py", "--repos-yaml", str(p)])
    monkeypatch.setattr(mod.shutil, "which", lambda _: None)
    assert mod.main() == 0
    out = capsys.readouterr().out
    assert "NOT scanned" in out


def test_unauthenticated_gh_exits_zero_and_says_not_scanned(monkeypatch, capsys, tmp_path):
    p = write_yaml(tmp_path, "repos:\n  - name: alpha\n    ritual_sync: yes\n")
    monkeypatch.setattr(mod.sys, "argv", ["pr_queue_scan.py", "--repos-yaml", str(p)])
    monkeypatch.setattr(mod.shutil, "which", lambda _: "/usr/bin/gh")
    monkeypatch.setattr(mod, "gh_login", lambda: None)
    assert mod.main() == 0
    assert "not authenticated" in capsys.readouterr().out
