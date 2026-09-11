#!/usr/bin/env python3
"""Tests for the Bitbucket Cloud PR-queue helper.

Every test injects a runner; none reaches the bkt CLI or the network. The
contract under test is the one the daily-rituals scan depends on: pull requests
bucketed by the authenticated user's uuid, the repository slug passed to bkt on
its own (never workspace/slug), and a failed query reported as unscanned rather
than as an empty queue.
"""
from __future__ import annotations

import datetime
import importlib.util
import json
import subprocess
from pathlib import Path

import pytest

SPEC = importlib.util.spec_from_file_location(
    "pr_queue", Path(__file__).with_name("pr_queue.py")
)
mod = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(mod)

NOW = datetime.datetime(2026, 9, 5, 12, 0, tzinfo=datetime.timezone.utc)
ME = {"uuid": "{me-uuid}", "account_id": "me-account", "username": "me"}
USER_JSON = dict(ME, display_name="Me", nickname="me", type="user")

PR_LIST_JSON = {
    "workspace": "team",
    "repo": "repo",
    "pull_requests": [
        {"id": 1, "title": "theirs, awaiting me", "state": "OPEN", "draft": False,
         "created_on": "2026-04-19T12:00:00.000000+00:00",
         "updated_on": "2026-04-19T12:00:00.000000+00:00",
         "author": {"uuid": "{someone}", "display_name": "Someone"},
         "reviewers": [{"uuid": "{me-uuid}", "display_name": "Me"}],
         "links": {"html": {"href": "https://bitbucket.org/team/repo/pull-requests/1"}}},
        {"id": 2, "title": "mine", "state": "OPEN", "draft": True,
         "created_on": "2026-09-01T12:00:00.000000+00:00",
         "updated_on": "2026-09-01T12:00:00.000000+00:00",
         "author": {"uuid": "{me-uuid}", "display_name": "Me"},
         "reviewers": []},
        {"id": 3, "title": "unrelated", "state": "OPEN", "draft": False,
         "created_on": "2026-09-01T12:00:00.000000+00:00",
         "updated_on": "2026-09-01T12:00:00.000000+00:00",
         "author": {"uuid": "{other}", "display_name": "Other"},
         "reviewers": [{"uuid": "{third}", "display_name": "Third"}]},
        {"id": 4, "title": "bot bump, nobody asked", "state": "OPEN", "draft": False,
         "created_on": "2026-09-01T12:00:00.000000+00:00",
         "updated_on": "2026-09-01T12:00:00.000000+00:00",
         "author": {"uuid": "{bot}", "display_name": "Renovate"},
         "reviewers": []},
    ],
}


class Completed:
    def __init__(self, returncode=0, stdout="", stderr=""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def fake_bkt(pr_list=PR_LIST_JSON, user=USER_JSON, pr_list_rc=0, pr_list_stderr="",
             user_rc=0, user_stderr=""):
    """A runner that answers `bkt pr list` and `bkt api /user`, recording argv."""
    def run(cmd, **kwargs):
        run.calls.append(list(cmd))
        if cmd[:2] == ["bkt", "api"]:
            return Completed(user_rc, json.dumps(user) if user_rc == 0 else "", user_stderr)
        if cmd[:3] == ["bkt", "pr", "list"]:
            return Completed(pr_list_rc, json.dumps(pr_list) if pr_list_rc == 0 else "",
                             pr_list_stderr)
        raise AssertionError("unexpected bkt invocation: %r" % (cmd,))
    run.calls = []
    return run


# --- buckets ------------------------------------------------------------------

def test_list_open_prs_buckets_by_uuid():
    rec = mod.list_open_prs("team", "repo", runner=fake_bkt(), identity=ME, now=NOW)
    assert rec["status"] == "scanned"
    assert rec["workspace"] == "team" and rec["repo"] == "repo"
    kinds = {i["number"]: i["kind"] for i in rec["items"]}
    assert kinds == {1: "review-requested", 2: "own-open", 4: "in-your-repo"}
    first = [i for i in rec["items"] if i["number"] == 1][0]
    assert first["age_days"] == 139
    assert first["repo"] == "team/repo"
    assert first["title"] == "theirs, awaiting me"
    assert first["url"] == "https://bitbucket.org/team/repo/pull-requests/1"
    assert first["draft"] is False
    mine = [i for i in rec["items"] if i["number"] == 2][0]
    assert mine["draft"] is True
    assert mine["url"] == "https://bitbucket.org/team/repo/pull-requests/2"


def test_list_open_prs_matches_identity_by_account_id_when_reviewer_has_no_uuid():
    rows = {"workspace": "team", "repo": "repo", "pull_requests": [
        {"id": 7, "title": "awaiting me by account id", "state": "OPEN", "draft": False,
         "created_on": "2026-09-01T12:00:00+00:00",
         "author": {"account_id": "someone-account"},
         "reviewers": [{"account_id": "me-account"}]},
    ]}
    rec = mod.list_open_prs("team", "repo", runner=fake_bkt(pr_list=rows), identity=ME, now=NOW)
    assert [i["kind"] for i in rec["items"]] == ["review-requested"]


def test_list_open_prs_reads_participants_when_reviewers_key_is_absent():
    """The REST object carries reviewer state under participants[].role."""
    rows = {"workspace": "team", "repo": "repo", "pull_requests": [
        {"id": 8, "title": "awaiting me via participants", "state": "OPEN", "draft": False,
         "created_on": "2026-09-01T12:00:00+00:00",
         "author": {"uuid": "{someone}"},
         "participants": [{"role": "REVIEWER", "user": {"uuid": "{me-uuid}"}},
                          {"role": "PARTICIPANT", "user": {"uuid": "{other}"}}]},
    ]}
    rec = mod.list_open_prs("team", "repo", runner=fake_bkt(pr_list=rows), identity=ME, now=NOW)
    assert [i["kind"] for i in rec["items"]] == ["review-requested"]


def test_list_open_prs_refuses_identity_without_uuid_or_account_id():
    """No unique key means no way to tell which pull requests are the user's."""
    rec = mod.list_open_prs("team", "repo", runner=fake_bkt(),
                            identity={"username": "me"}, now=NOW)
    assert rec["status"] == "unscanned"
    assert "uuid" in rec["reason"] and "account_id" in rec["reason"]
    assert "items" not in rec


# --- argv: the slug alone -----------------------------------------------------

def test_list_open_prs_passes_workspace_and_slug_alone():
    run = fake_bkt()
    mod.list_open_prs("team", "repo", runner=run, identity=ME, now=NOW)
    assert run.calls == [[
        "bkt", "pr", "list", "--workspace", "team", "--repo", "repo",
        "--state", "OPEN", "--limit", "0", "--json",
    ]]


@pytest.mark.parametrize("slug", ["team/repo", "bitbucket.org/team/repo", "repo/"])
def test_list_open_prs_rejects_owner_slash_name(slug):
    run = fake_bkt()
    with pytest.raises(ValueError) as exc:
        mod.list_open_prs("team", slug, runner=run, identity=ME, now=NOW)
    assert "/" in str(exc.value) and "slug alone" in str(exc.value)
    assert run.calls == []


@pytest.mark.parametrize("workspace,slug", [("", "repo"), ("team", "")])
def test_list_open_prs_rejects_empty_workspace_or_slug(workspace, slug):
    run = fake_bkt()
    with pytest.raises(ValueError) as exc:
        mod.list_open_prs(workspace, slug, runner=run, identity=ME, now=NOW)
    assert "empty" in str(exc.value)
    assert run.calls == []


# --- identity from bkt api /user ----------------------------------------------

def test_bkt_identity_reads_uuid_account_id_and_username():
    run = fake_bkt()
    identity, err = mod.bkt_identity(runner=run)
    assert err is None
    assert identity == ME
    assert run.calls == [["bkt", "api", "/user", "--json"]]


def test_bkt_identity_reports_failure_not_anonymous():
    identity, err = mod.bkt_identity(runner=fake_bkt(user_rc=1, user_stderr="Error: not logged in\nrun bkt auth login"))
    assert identity is None
    assert err == "bkt api /user failed: run bkt auth login"


def test_list_open_prs_resolves_identity_when_none_is_given():
    run = fake_bkt()
    rec = mod.list_open_prs("team", "repo", runner=run, now=NOW)
    assert run.calls[0] == ["bkt", "api", "/user", "--json"]
    assert {i["number"]: i["kind"] for i in rec["items"]} == {
        1: "review-requested", 2: "own-open", 4: "in-your-repo"}


def test_list_open_prs_is_unscanned_when_identity_cannot_be_resolved():
    run = fake_bkt(user_rc=1, user_stderr="HTTP 401 Unauthorized")
    rec = mod.list_open_prs("team", "repo", runner=run, now=NOW)
    assert rec["status"] == "unscanned"
    assert rec["reason"] == "bkt api /user failed: HTTP 401 Unauthorized"
    assert "items" not in rec
    assert all(c[:3] != ["bkt", "pr", "list"] for c in run.calls)


# --- a failed query is never an empty queue -----------------------------------

def test_404_is_unscanned_with_the_stderr_reason():
    run = fake_bkt(pr_list_rc=1, pr_list_stderr="Error: HTTP 404 Not Found: repository team/repo")
    rec = mod.list_open_prs("team", "repo", runner=run, identity=ME, now=NOW)
    assert rec["status"] == "unscanned"
    assert rec["reason"] == "Error: HTTP 404 Not Found: repository team/repo"
    assert "items" not in rec


def test_nonzero_exit_without_stderr_names_the_exit_code():
    run = fake_bkt(pr_list_rc=3)
    rec = mod.list_open_prs("team", "repo", runner=run, identity=ME, now=NOW)
    assert rec["status"] == "unscanned"
    assert rec["reason"] == "bkt exited 3"


def test_unparseable_json_is_unscanned():
    def run(cmd, **kwargs):
        return Completed(0, "not json", "")
    rec = mod.list_open_prs("team", "repo", runner=run, identity=ME, now=NOW)
    assert rec["status"] == "unscanned"
    assert "unparseable JSON" in rec["reason"]


def test_json_without_pull_requests_key_is_unscanned():
    """An envelope that never mentions pull_requests was not a queue read."""
    run = fake_bkt(pr_list={"workspace": "team", "repo": "repo"})
    rec = mod.list_open_prs("team", "repo", runner=run, identity=ME, now=NOW)
    assert rec["status"] == "unscanned"
    assert rec["reason"] == "bkt returned JSON without a pull_requests list"
    assert "items" not in rec


def test_pull_requests_as_string_is_unscanned():
    """A value that is neither null nor a list is a body this module does not understand."""
    run = fake_bkt(pr_list={"workspace": "team", "repo": "repo", "pull_requests": "58 open"})
    rec = mod.list_open_prs("team", "repo", runner=run, identity=ME, now=NOW)
    assert rec["status"] == "unscanned"
    assert rec["reason"] == "bkt returned pull_requests as str, not a list"
    assert "items" not in rec


# --- an empty queue is a scanned repository ----------------------------------

def test_null_pull_requests_is_a_scanned_empty_queue():
    """bkt writes `pull_requests: null`, not `[]`, when a repository has no open PRs.

    Verified live 2026-09-10: `bkt pr list --state OPEN --limit 0 --json` on a
    repository with no open pull requests returns
    `{"pull_requests": null, "repo": "<slug>", "workspace": "<ws>"}`. That is
    a queue that was read and found empty, never an unscanned repository.
    """
    run = fake_bkt(pr_list={"pull_requests": None, "repo": "repo", "workspace": "team"})
    rec = mod.list_open_prs("team", "repo", runner=run, identity=ME, now=NOW)
    assert rec == {"workspace": "team", "repo": "repo", "status": "scanned", "items": []}
    assert "reason" not in rec


def test_empty_pull_requests_list_is_a_scanned_empty_queue():
    run = fake_bkt(pr_list={"pull_requests": [], "repo": "repo", "workspace": "team"})
    rec = mod.list_open_prs("team", "repo", runner=run, identity=ME, now=NOW)
    assert rec == {"workspace": "team", "repo": "repo", "status": "scanned", "items": []}
    assert "reason" not in rec


def test_timeout_is_unscanned():
    def run(cmd, **kwargs):
        raise subprocess.TimeoutExpired(cmd, kwargs.get("timeout", 0))
    rec = mod.list_open_prs("team", "repo", runner=run, identity=ME, now=NOW)
    assert rec["status"] == "unscanned"
    assert rec["reason"] == "timed out after %ds" % mod.PER_REPO_TIMEOUT_S


def test_missing_bkt_binary_is_unscanned():
    def run(cmd, **kwargs):
        raise FileNotFoundError(2, "No such file or directory", "bkt")
    rec = mod.list_open_prs("team", "repo", runner=run, identity=ME, now=NOW)
    assert rec["status"] == "unscanned"
    assert rec["reason"].startswith("could not run bkt:")


def test_age_days_handles_bitbucket_timestamps():
    """Whole days, floored: Bitbucket's microsecond stamps parse and round down like gh's."""
    assert mod.age_days("2026-08-29T11:00:00.123456+00:00", NOW) == 7
    assert mod.age_days("2026-08-29T12:00:00.123456+00:00", NOW) == 6
    assert mod.age_days("2026-08-29T12:00:00Z", NOW) == 7
    assert mod.age_days("not-a-date", NOW) == 0
