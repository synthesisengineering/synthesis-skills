#!/usr/bin/env python3
"""Open pull requests on one Bitbucket Cloud repository, read through `bkt`.

This is the Bitbucket half of the weekly PR-queue scan in synthesis-daily-rituals
(`scripts/pr_queue_scan.py`), which dispatches by origin host and loads this
module by path. It answers one question per repository: which open pull
requests are the authenticated user's to act on, and which could not be read.

Buckets match the scan's, so a console sees one shape whatever the host:

  - `review-requested` — the user is a requested reviewer
  - `own-open`         — the user opened it
  - `in-your-repo`     — nobody was asked to review it; in a repo the workspace
                         declares, that is the user's to merge or close
                         (where dependency bots land)

Identity comes from `bkt api /user`, matched on `uuid` and `account_id` — the
two keys Bitbucket guarantees unique. Names and nicknames are never used to
decide ownership.

Design rules:

  - **The repository slug is passed to bkt on its own.** `--workspace <ws>
    --repo <slug>`; a slug carrying a `/` is refused before any command runs,
    because `--repo team/name` is exactly the form that 404s.
  - **A failed query is an `unscanned` record, never an empty queue.** A 404, a
    non-zero exit, a timeout, an unparseable body, or an identity that cannot be
    resolved all return `{"status": "unscanned", "reason": ...}` with no
    `items` key at all, so a caller cannot mistake it for a clean result.
  - **An empty queue is a scanned record, never a failure.** bkt writes
    `{"pull_requests": null, ...}` — null, not `[]` — for a repository with no
    open pull requests. Either spelling is a queue that was read and found
    empty. A body with no `pull_requests` key, or one whose value is neither
    null nor a list, is unscanned with the shape it saw named in the reason.
  - **Read-only.** `bkt pr list` and `bkt api /user` are the only commands.
  - **No network in tests.** Every entry point takes a `runner` with the
    signature of `subprocess.run`.

Usage from another script:

    identity, err = bkt_identity()
    record = list_open_prs("team", "repo-slug", identity=identity)
"""
from __future__ import annotations

import datetime
import json
import subprocess

PER_REPO_TIMEOUT_S = 20
IDENTITY_TIMEOUT_S = 15
IDENTITY_KEYS = ("uuid", "account_id")


def age_days(iso: str, now: datetime.datetime) -> int:
    """Whole days since an ISO-8601 timestamp; 0 when it does not parse.

    Bitbucket writes `2026-04-19T12:00:00.123456+00:00`; a trailing `Z` is
    accepted too so a caller can hand over any RFC 3339 form.
    """
    try:
        created = datetime.datetime.fromisoformat(iso.replace("Z", "+00:00"))
    except ValueError:
        return 0
    return max(0, (now - created).days)


def _failure(out, tool: str) -> str:
    """The last stderr line, or the exit code when bkt said nothing."""
    lines = (out.stderr or "").strip().splitlines()
    return lines[-1] if lines else "%s exited %d" % (tool, out.returncode)


def bkt_identity(runner=subprocess.run) -> tuple[dict | None, str | None]:
    """The authenticated Bitbucket user as {uuid, account_id, username}. (identity, error)."""
    cmd = ["bkt", "api", "/user", "--json"]
    try:
        out = runner(cmd, capture_output=True, text=True, timeout=IDENTITY_TIMEOUT_S)
    except subprocess.TimeoutExpired:
        return None, "bkt api /user timed out after %ds" % IDENTITY_TIMEOUT_S
    except OSError as exc:
        return None, "could not run bkt: %s" % exc
    if out.returncode != 0:
        return None, "bkt api /user failed: %s" % _failure(out, "bkt")
    try:
        user = json.loads(out.stdout or "")
    except json.JSONDecodeError:
        return None, "bkt api /user returned unparseable JSON"
    if not isinstance(user, dict):
        return None, "bkt api /user returned %s, not a user object" % type(user).__name__
    identity = {k: user.get(k) for k in ("uuid", "account_id", "username")}
    if not any(identity[k] for k in IDENTITY_KEYS):
        return None, "bkt api /user returned neither uuid nor account_id; cannot tell which pull requests are yours"
    return identity, None


def _keys(user: dict | None) -> set[str]:
    """The unique identifiers a Bitbucket user object carries."""
    return {str(v) for k in IDENTITY_KEYS for v in [(user or {}).get(k)] if v}


def _reviewers(pr: dict) -> list[dict]:
    """Requested reviewers: the `reviewers` list, else participants with role REVIEWER.

    The REST pull-request object carries both; the list form bkt emits carries
    `reviewers`, while a raw object read elsewhere may carry only
    `participants`. Either names the same people.
    """
    if pr.get("reviewers") is not None:
        return [r for r in pr["reviewers"] if isinstance(r, dict)]
    return [
        (p.get("user") or {}) for p in (pr.get("participants") or [])
        if isinstance(p, dict) and p.get("role") == "REVIEWER"
    ]


def _unscanned(workspace: str, repo_slug: str, reason: str) -> dict:
    return {"workspace": workspace, "repo": repo_slug, "status": "unscanned", "reason": reason}


def _rows(data) -> tuple[list | None, str | None]:
    """The pull-request rows in a parsed `bkt pr list --json` body. (rows, reason).

    bkt wraps the rows in `{"workspace", "repo", "pull_requests"}` and writes
    `pull_requests: null` — not `[]` — when the repository has no open pull
    requests, so null is an empty queue that was read. A bare list is taken as
    the rows themselves. Anything else is a body this module does not
    understand, reported with the shape it saw.
    """
    if isinstance(data, list):
        return data, None
    if not isinstance(data, dict):
        return None, "bkt returned %s, not a pull_requests envelope" % type(data).__name__
    if "pull_requests" not in data:
        return None, "bkt returned JSON without a pull_requests list"
    rows = data["pull_requests"]
    if rows is None:
        return [], None
    if not isinstance(rows, list):
        return None, "bkt returned pull_requests as %s, not a list" % type(rows).__name__
    return rows, None


def list_open_prs(workspace: str, repo_slug: str, runner=subprocess.run,
                  identity: dict | None = None,
                  now: datetime.datetime | None = None) -> dict:
    """Open pull requests in one repository, bucketed for the authenticated user.

    Returns `{"workspace", "repo", "status": "scanned", "items": [...]}` where
    each item is `{repo, number, title, kind, draft, age_days, url}` with
    `repo` as `workspace/slug`, or `{"workspace", "repo", "status":
    "unscanned", "reason"}` with no `items` key when the queue was not read.

    `identity` is the result of `bkt_identity()`; it is resolved here when not
    given, so a caller scanning many repositories resolves it once and passes
    it through.
    """
    if not workspace or not repo_slug:
        raise ValueError(
            "workspace and repo_slug must both be non-empty; got workspace=%r repo_slug=%r"
            % (workspace, repo_slug))
    if "/" in repo_slug:
        raise ValueError(
            "repo_slug %r contains '/'; pass the repository slug alone (the part after the "
            "workspace, e.g. 'content-scaling-agents'), with --workspace carrying the workspace"
            % repo_slug)

    if identity is None:
        identity, err = bkt_identity(runner)
        if err:
            return _unscanned(workspace, repo_slug, err)
    mine = _keys(identity)
    if not mine:
        return _unscanned(
            workspace, repo_slug,
            "identity carries neither uuid nor account_id; cannot tell which pull requests are yours")

    cmd = [
        "bkt", "pr", "list", "--workspace", workspace, "--repo", repo_slug,
        "--state", "OPEN", "--limit", "0", "--json",
    ]
    try:
        out = runner(cmd, capture_output=True, text=True, timeout=PER_REPO_TIMEOUT_S)
    except subprocess.TimeoutExpired:
        return _unscanned(workspace, repo_slug, "timed out after %ds" % PER_REPO_TIMEOUT_S)
    except OSError as exc:
        return _unscanned(workspace, repo_slug, "could not run bkt: %s" % exc)
    if out.returncode != 0:
        return _unscanned(workspace, repo_slug, _failure(out, "bkt"))
    try:
        data = json.loads(out.stdout or "")
    except json.JSONDecodeError:
        return _unscanned(workspace, repo_slug, "bkt returned unparseable JSON")
    rows, reason = _rows(data)
    if reason:
        return _unscanned(workspace, repo_slug, reason)

    now = now or datetime.datetime.now(datetime.timezone.utc)
    display = "%s/%s" % (workspace, repo_slug)
    items = []
    for pr in rows:
        if not isinstance(pr, dict):
            continue
        reviewers: set[str] = set()
        for reviewer in _reviewers(pr):
            reviewers |= _keys(reviewer)
        author = _keys(pr.get("author"))
        if mine & reviewers:
            kind = "review-requested"
        elif mine & author:
            kind = "own-open"
        elif not reviewers:
            kind = "in-your-repo"
        else:
            continue
        number = pr.get("id")
        url = (((pr.get("links") or {}).get("html") or {}).get("href")
               or "https://bitbucket.org/%s/pull-requests/%s" % (display, number))
        items.append({
            "repo": display,
            "number": number,
            "title": (pr.get("title") or "")[:100],
            "kind": kind,
            "draft": bool(pr.get("draft")),
            "age_days": age_days(pr.get("created_on") or "", now),
            "url": url,
        })
    return {"workspace": workspace, "repo": repo_slug, "status": "scanned", "items": items}
