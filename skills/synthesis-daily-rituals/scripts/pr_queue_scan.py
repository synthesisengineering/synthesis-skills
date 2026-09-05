#!/usr/bin/env python3
"""Surface review requests and own open PRs that the weekly review would otherwise never see.

The problem this addresses: the Weekly Loose-Ends Review's declared sources are
daily plans, drafts, decisions, waiting-on rows, project context files, session
logs, and the calendar. **None of them is the PR queue.** So a review request can
age indefinitely and the review will still report a clean result, because the
review reports what it scanned and reads as complete.

The motivating case: a review request sat 139 days with the principal as the
requested reviewer and zero activity since it opened. That same morning the
weekly review reported exactly one waiting-on item past seven days. It had not
missed the PR through carelessness — it had not looked.

Scope is the workspace's OWN declared repos, read from the same
`.agents/repos.yaml` the source-code sync uses. That is deliberate: it makes the
check workspace-scoped by construction, so a personal seat scans personal repos
and a client seat scans that client's repos, with no second list to maintain and
no way for one workspace's queue to leak into another's review.

Design rules, each learned from the condition it fixes:

  - **Never report a clean queue you did not actually read.** A repo whose host
    is unsupported, whose remote is missing, or whose query failed is reported in
    `unscanned` with the reason. Silence about coverage is the very failure this
    script exists to correct.
  - **Oldest first.** Age is the signal; a request that has waited longest is the
    one most likely to have been forgotten by everyone.
  - **Exit 0 always.** This is a surface, not a gate. It must never be the reason
    a ritual fails.
  - **Read-only.** It never comments, merges, closes, or requests review.

Usage:
    pr_queue_scan.py --workspace rajiv
    pr_queue_scan.py --repos-yaml PATH        # skip workspace discovery
    pr_queue_scan.py --threshold 7            # only items older than N days
    pr_queue_scan.py --json                   # for a console or hook
"""
from __future__ import annotations

import argparse
import datetime
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

try:
    import yaml
except ImportError:  # pragma: no cover - environment-dependent
    print("pr_queue_scan: PyYAML unavailable; skipping", file=sys.stderr)
    sys.exit(0)

DEFAULT_THRESHOLD_DAYS = 0
PER_REPO_TIMEOUT_S = 20
GITHUB_HOST_RE = re.compile(r"github\.com[:/]([^/\s]+)/([^/\s.]+)")


def workspace_repos_yaml(workspace: str) -> Path:
    root = Path(os.environ.get("SYNTHESIS_WORKSPACES", str(Path.home() / "workspaces")))
    return root / workspace / ".agents" / "repos.yaml"


def declared_repos(path: Path) -> list[dict]:
    """Every repo the workspace declares, except dormant ones.

    Deliberately NOT filtered by `ritual_sync`. That flag governs whether the
    daily source-code sync fast-forwards a working copy, which is a different
    question from whether the repo has review requests worth surfacing — skill
    sources and context repos carry `ritual_sync: no` precisely because they are
    maintained through their own flows, and their pull requests still wait on a
    human. Filtering a review queue by a sync policy silently hides them.

    `status: dormant` is honored, because dormancy is a statement about the repo
    itself rather than about one workflow's interest in it.
    """
    data = yaml.safe_load(path.read_text()) or {}
    repos = data.get("repos", data)
    if isinstance(repos, dict):
        repos = [dict(name=k, **(v or {})) for k, v in repos.items()]
    return [
        r for r in (repos or [])
        if isinstance(r, dict) and str(r.get("status", "")).lower() != "dormant"
    ]


def repo_path(entry: dict, workspace: str) -> Path:
    """Absolute local path for a manifest entry.

    A manifest `path` is relative to the workspace root unless it is already
    absolute or `~`-prefixed; resolving it against the process CWD instead is
    how this first reported eighteen repos as having no clone.
    """
    root = Path(os.environ.get("SYNTHESIS_WORKSPACES", str(Path.home() / "workspaces")))
    declared = entry.get("path")
    if declared:
        p = Path(os.path.expanduser(str(declared)))
        return p if p.is_absolute() else root / workspace / p
    return root / workspace / str(entry.get("name", ""))


def slug_from_url(url: str) -> str | None:
    """owner/name for a GitHub URL, or None for anything else.

    Anything that is not GitHub is not guessed at. Bitbucket, GitLab and
    self-hosted remotes yield None so the caller reports them unscanned with the
    host named, because a queue nobody looked at must never read as empty.
    """
    m = GITHUB_HOST_RE.search((url or "").strip())
    return "%s/%s" % (m.group(1), m.group(2)) if m else None


def github_slug(entry: dict, repo_dir: Path) -> str | None:
    """Resolve owner/name, preferring the manifest over the working copy.

    A pull-request queue is a fact about the REMOTE, not about the local disk,
    so a declared repo with no local clone is still scannable. The manifest
    already records `remotes.origin`; git is only consulted when it does not.
    """
    declared = ((entry.get("remotes") or {}) or {}).get("origin")
    slug = slug_from_url(str(declared)) if declared else None
    if slug:
        return slug
    if not repo_dir.exists():
        return None
    try:
        out = subprocess.run(
            ["git", "-C", str(repo_dir), "remote", "get-url", "origin"],
            capture_output=True, text=True, timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return slug_from_url(out.stdout) if out.returncode == 0 else None


def age_days(iso: str, now: datetime.datetime) -> int:
    try:
        created = datetime.datetime.fromisoformat(iso.replace("Z", "+00:00"))
    except ValueError:
        return 0
    return max(0, (now - created).days)


def query_repo(slug: str, login: str, now: datetime.datetime) -> tuple[list[dict], str | None]:
    """Open PRs for one repo, split into review-requested and own. (items, error)."""
    cmd = [
        "gh", "pr", "list", "--repo", slug, "--state", "open", "--limit", "100",
        "--json", "number,title,createdAt,author,reviewRequests,isDraft,url",
    ]
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=PER_REPO_TIMEOUT_S)
    except subprocess.TimeoutExpired:
        return [], "timed out after %ds" % PER_REPO_TIMEOUT_S
    except OSError as exc:
        return [], "could not run gh: %s" % exc
    if out.returncode != 0:
        return [], (out.stderr.strip().splitlines() or ["gh exited %d" % out.returncode])[-1]
    try:
        rows = json.loads(out.stdout or "[]")
    except json.JSONDecodeError:
        return [], "gh returned unparseable JSON"

    owner = slug.split("/", 1)[0]
    items = []
    for pr in rows:
        reviewers = {
            (r or {}).get("login") for r in (pr.get("reviewRequests") or [])
        }
        author = ((pr.get("author") or {}).get("login")) or ""
        if login and login in reviewers:
            kind = "review-requested"
        elif login and author == login:
            kind = "own-open"
        elif not reviewers:
            # A pull request with nobody asked to review it, in a repo THIS
            # WORKSPACE DECLARES, is the user's to merge or close whoever opened
            # it — the bucket dependency bots land in.
            #
            # Declaration is the ownership signal, deliberately, rather than the
            # GitHub namespace: a personal repo frequently lives under an org the
            # user runs, so comparing owner to login misses exactly the repos
            # they care most about. The manifest already means "these are mine".
            kind = "in-your-repo"
        else:
            continue
        items.append({
            "repo": slug,
            "number": pr.get("number"),
            "title": (pr.get("title") or "")[:100],
            "kind": kind,
            "draft": bool(pr.get("isDraft")),
            "age_days": age_days(pr.get("createdAt") or "", now),
            "url": pr.get("url"),
        })
    return items, None


def gh_login() -> str | None:
    try:
        out = subprocess.run(
            ["gh", "api", "user", "--jq", ".login"],
            capture_output=True, text=True, timeout=15,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return out.stdout.strip() or None if out.returncode == 0 else None


def scan(repos: list[dict], workspace: str, login: str, now: datetime.datetime) -> dict:
    found: list[dict] = []
    unscanned: list[dict] = []
    scanned: list[str] = []

    for entry in repos:
        name = str(entry.get("name", "?"))
        rdir = repo_path(entry, workspace)
        slug = github_slug(entry, rdir)
        if not slug:
            reason = ("origin is not a GitHub remote" if (entry.get("remotes") or {}).get("origin")
                      else "no GitHub remote declared, and no local clone at %s" % rdir)
            unscanned.append({"repo": name, "reason": reason})
            continue
        items, err = query_repo(slug, login, now)
        if err:
            unscanned.append({"repo": name, "reason": err})
            continue
        scanned.append(name)
        found.extend(items)

    found.sort(key=lambda i: (-i["age_days"], i["repo"]))
    return {"found": found, "unscanned": unscanned, "scanned": scanned}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--workspace")
    ap.add_argument("--repos-yaml", type=Path)
    ap.add_argument("--threshold", type=int, default=DEFAULT_THRESHOLD_DAYS)
    ap.add_argument("--login", help="GitHub login; auto-detected from gh when omitted")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    path = args.repos_yaml or (workspace_repos_yaml(args.workspace) if args.workspace else None)
    if not path or not path.exists():
        msg = "pr_queue_scan: no repos.yaml (looked at %s); nothing declared to scan" % path
        print(json.dumps({"error": msg}) if args.json else "  " + msg)
        return 0

    if not shutil.which("gh"):
        msg = "pr_queue_scan: gh CLI not installed; PR queue NOT scanned"
        print(json.dumps({"error": msg}) if args.json else "  " + msg)
        return 0

    login = args.login or gh_login()
    if not login:
        msg = "pr_queue_scan: gh is not authenticated; PR queue NOT scanned"
        print(json.dumps({"error": msg}) if args.json else "  " + msg)
        return 0

    workspace = args.workspace or path.parent.parent.name
    now = datetime.datetime.now(datetime.timezone.utc)
    result = scan(declared_repos(path), workspace, login, now)
    result["workspace"] = workspace
    result["login"] = login
    hits = [i for i in result["found"] if i["age_days"] >= args.threshold]
    result["found"] = hits

    if args.json:
        print(json.dumps(result, indent=2))
        return 0

    buckets = [
        ("review-requested", "Waiting on your review"),
        ("own-open", "Your own open PRs"),
        ("in-your-repo", "Open in your repos, nobody else asked to review"),
    ]

    print("PR queue — %d repo(s) scanned, %d not scanned" %
          (len(result["scanned"]), len(result["unscanned"])))
    shown = 0
    for kind, label in buckets:
        rows = [i for i in hits if i["kind"] == kind]
        if not rows:
            continue
        shown += len(rows)
        print("\n  %s (%d) — oldest first:" % (label, len(rows)))
        for i in rows:
            draft = " [draft]" if i["draft"] else ""
            print("    %4dd  %s#%s%s  %s" % (i["age_days"], i["repo"], i["number"], draft, i["title"]))
    if not shown:
        print("\n  Nothing in the queue for you across the repos actually scanned.")
    if result["unscanned"]:
        # Named, never silent: an unscanned repo is not an empty queue.
        print("\n  NOT SCANNED — these are unknown, not clean:")
        for u in result["unscanned"]:
            print("    %-28s %s" % (u["repo"], u["reason"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
