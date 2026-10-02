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

  - **Explicit repository binding.** The bkt API path contains both workspace
    and repository; neither a shared context nor a response URL selects it.
  - **Explicit reviewer custody.** bkt's ordinary PR list omits reviewers.
    Request them through the authenticated API instead of treating omissions
    as proof that nobody was asked to review.
  - **Complete bounded pagination.** Every page must pass before classifying
    any rows. Missing reviewer fields, malformed pages, duplicate PR IDs,
    changed pagination scope, the page cap or the total deadline produce an
    unscanned record without partial items. An explicit empty values list on
    the terminal page is a scanned empty queue.
  - **Read-only.** Only bkt API GET operations run; no per-PR detail loop.
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
import re
import time
from urllib.parse import parse_qs, urlsplit

PER_REPO_TIMEOUT_S = 20
IDENTITY_TIMEOUT_S = 15
IDENTITY_KEYS = ("uuid", "account_id")
PAGE_SIZE = 50
MAX_PAGES = 100
FIELDS = ("values.id,values.title,values.state,values.draft,values.created_on,"
          "values.author,values.reviewers,next")


def age_days(iso: str, now: datetime.datetime) -> int:
    """Whole days since an ISO-8601 timestamp; 0 when it does not parse.

    Bitbucket writes `2026-04-19T12:00:00.123456+00:00`; a trailing `Z` is
    accepted too so a caller can hand over any RFC 3339 form.
    """
    try:
        created = datetime.datetime.fromisoformat(iso.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return 0
    if created.tzinfo is None:
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
    if not isinstance(user, dict):
        return set()
    return {v for k in IDENTITY_KEYS for v in [user.get(k)]
            if isinstance(v, str) and v}


def _unscanned(workspace: str, repo_slug: str, reason: str) -> dict:
    return {"workspace": workspace, "repo": repo_slug, "status": "unscanned", "reason": reason}


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON field")
        result[key] = value
    return result


def _identity_present(user) -> bool:
    return isinstance(user, dict) and any(
        isinstance(user.get(k), str) and user[k] for k in IDENTITY_KEYS)


def _rows(data) -> tuple[list | None, str | None]:
    """Validate the explicitly projected API page before accepting any rows."""
    if not isinstance(data, dict) or not isinstance(data.get("values"), list):
        return None, "bkt API returned no values list"
    rows = data["values"]
    if len(rows) > PAGE_SIZE:
        return None, "bkt API exceeded the requested page size"
    for row in rows:
        if (not isinstance(row, dict) or type(row.get("id")) is not int
                or row["id"] <= 0 or row.get("state") != "OPEN"
                or not isinstance(row.get("title"), str)
                or not isinstance(row.get("created_on"), str)
                or type(row.get("draft")) is not bool
                or not _identity_present(row.get("author"))):
            return None, "bkt API returned an incomplete or invalid open PR"
        if (not isinstance(row.get("reviewers"), list)
                or any(not _identity_present(user) for user in row["reviewers"])):
            return None, "bkt API did not provide complete reviewer identities"
    return rows, None


def _list_rows(workspace, repo_slug, runner):
    endpoint = "/repositories/%s/%s/pullrequests" % (workspace, repo_slug)
    deadline = time.monotonic() + PER_REPO_TIMEOUT_S
    rows, seen = [], set()
    for page in range(1, MAX_PAGES + 1):
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return None, "timed out after %ds" % PER_REPO_TIMEOUT_S
        params = {"state": "OPEN", "pagelen": str(PAGE_SIZE),
                  "fields": FIELDS, "page": str(page)}
        cmd = ["bkt", "api", endpoint, "--method", "GET", "--json"]
        for key, value in params.items():
            cmd.extend(["--param", key + "=" + value])
        try:
            out = runner(cmd, capture_output=True, text=True, timeout=remaining)
        except subprocess.TimeoutExpired:
            return None, "timed out after %ds" % PER_REPO_TIMEOUT_S
        except OSError as exc:
            return None, "could not run bkt: %s" % exc
        if time.monotonic() >= deadline:
            return None, "timed out after %ds" % PER_REPO_TIMEOUT_S
        if out.returncode != 0:
            return None, _failure(out, "bkt")
        try:
            if len(out.stdout or "") > 4 * 1024 * 1024:
                return None, "bkt API page exceeds the response limit"
            data = json.loads(out.stdout or "", object_pairs_hook=_unique_object)
        except (ValueError, RecursionError):
            return None, "bkt returned unparseable JSON"
        values, reason = _rows(data)
        if reason:
            return None, reason
        for row in values:
            if row["id"] in seen:
                return None, "bkt API repeated a PR across the inventory"
            seen.add(row["id"])
            rows.append(row)
        if time.monotonic() >= deadline:
            return None, "timed out after %ds" % PER_REPO_TIMEOUT_S
        next_url = data.get("next")
        if next_url is None:
            return rows, None
        if not isinstance(next_url, str) or not values:
            return None, "bkt API returned invalid pagination"
        try:
            parsed = urlsplit(next_url)
            query = parse_qs(parsed.query, strict_parsing=True)
        except ValueError:
            return None, "bkt API returned invalid pagination"
        expected = {key: [value] for key, value in params.items()}
        expected["page"] = [str(page + 1)]
        if (parsed.scheme != "https" or parsed.netloc != "api.bitbucket.org"
                or parsed.path != "/2.0" + endpoint or parsed.fragment
                or query != expected):
            return None, "bkt API pagination changed the repository or query scope"
        # Construct the next request from the verified scope; never execute or
        # send credentials to a response-provided URL.
    return None, "bkt API pagination exceeded %d pages" % MAX_PAGES

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

    if any(not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", value)
           or value in {".", ".."} for value in (workspace, repo_slug)):
        raise ValueError("workspace and repository must be literal slugs")

    if identity is None:
        identity, err = bkt_identity(runner)
        if err:
            return _unscanned(workspace, repo_slug, err)
    mine = _keys(identity)
    if not mine:
        return _unscanned(
            workspace, repo_slug,
            "identity carries neither uuid nor account_id; cannot tell which pull requests are yours")

    rows, reason = _list_rows(workspace, repo_slug, runner)
    if reason:
        return _unscanned(workspace, repo_slug, reason)

    now = now or datetime.datetime.now(datetime.timezone.utc)
    display = "%s/%s" % (workspace, repo_slug)
    items = []
    for pr in rows:
        if not isinstance(pr, dict):
            continue
        reviewers: set[str] = set()
        for reviewer in pr["reviewers"]:
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
        # Both the repository and positive integer ID were validated above.
        # Optional provider link metadata cannot redirect or break the scan.
        url = "https://bitbucket.org/%s/pull-requests/%s" % (display, number)
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
