#!/usr/bin/env python3
"""Find repositories with work stranded on this Mac: uncommitted, unpushed, behind, or detached.

    repo_sync_check.py [--workspace DIR] [--max-depth N] [--json] [--quiet] [--alert] [--no-report]

Reads only; it never commits, fetches or pushes. Writes the full report to
~/.synthesis/repo-guard/last-report.json (the pull channel synthesis-console renders):
{"generated_at", "host", "total_repos", "dirty_count", "repos": [{"name", "path", "clean",
"issues": [{"type": "uncommitted" | "unpushed" | "behind" | "detached" | "error", "detail",
"files"?, "total"?, "count"?}]}]}.
--alert speaks and shows a banner with a count and a pointer only, never a repository,
workspace or client name (speakers are overheard, banners are screen-shared), and stays silent
while ~/.synthesis/quiet-audio exists. Exit 0 all clean, 1 something needs attention, 2 error.
"""

from __future__ import annotations

import argparse
import json
import os
import socket
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path


def find_repos(root: Path, depth: int) -> list[Path]:
    if (root / ".git").exists():
        return [root]  # never descend into a repository's own folders
    if depth <= 0:
        return []
    try:
        children = sorted(c for c in root.iterdir() if c.is_dir() and not c.name.startswith("."))
    except OSError:
        return []
    return [r for c in children for r in find_repos(c, depth - 1)]


def git(repo: Path, *args: str) -> tuple[int, str]:
    env = {**os.environ, "GIT_OPTIONAL_LOCKS": "0", "GIT_NO_LAZY_FETCH": "1"}
    try:
        out = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, timeout=30, env=env)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return -1, str(exc)
    return out.returncode, out.stdout if out.returncode == 0 else out.stderr


def check(repo: Path) -> dict:
    issues = []
    code, status = git(repo, "status", "--porcelain")  # never strip: the first column carries meaning
    if code != 0:
        return {"name": repo.name, "path": str(repo), "clean": False, "issues": [{"type": "error", "detail": status.strip()}]}
    lines = [line for line in status.splitlines() if line.strip()]
    if lines:
        issues.append({"type": "uncommitted", "detail": f"{len(lines)} uncommitted file(s)", "files": lines[:10], "total": len(lines)})
    code, branch = git(repo, "branch", "--show-current")
    if code != 0 or not branch.strip():
        if not lines:  # noted, but a clean detached checkout strands nothing
            issues.append({"type": "detached", "detail": "detached HEAD or no branch"})
    else:
        branch = branch.strip()
        code, counts = git(repo, "rev-list", "--left-right", "--count", f"origin/{branch}...{branch}")
        behind, ahead = (int(n) for n in counts.split()) if code == 0 and len(counts.split()) == 2 else (0, 0)
        if ahead:
            issues.append({"type": "unpushed", "detail": f"{ahead} unpushed commit(s) on {branch}", "count": ahead})
        if behind:
            issues.append({"type": "behind", "detail": f"{behind} commit(s) behind origin/{branch}", "count": behind})
    return {"name": repo.name, "path": str(repo), "clean": all(i["type"] == "detached" for i in issues), "issues": issues}


def alert(count: int) -> None:
    """A generic ping: a count and a pointer, never a name. Silent while quiet-audio is set."""
    if sys.platform != "darwin" or (Path.home() / ".synthesis" / "quiet-audio").exists():
        return
    noun = "repository needs" if count == 1 else "repositories need"
    message = f"{count} {noun} attention. Details are in your synthesis console."
    subprocess.run(["osascript", "-e", f'display notification "{message}" with title "Repo guard"'], capture_output=True)
    subprocess.run(["say", f"Repo guard: {message}"], capture_output=True)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--workspace", type=Path, default=Path.home() / "workspaces")
    parser.add_argument("--max-depth", type=int, default=3)
    parser.add_argument("--json", action="store_true", help="print the repositories that need attention as JSON")
    parser.add_argument("--quiet", action="store_true", help="print nothing; the exit code and report still say it")
    parser.add_argument("--alert", action="store_true", help="a generic banner and spoken count when something needs attention")
    parser.add_argument("--no-report", action="store_true", help="do not write last-report.json")
    args = parser.parse_args(argv)
    root = args.workspace.expanduser()
    if not root.is_dir():
        print(f"workspace not found: {root}", file=sys.stderr)
        return 2
    repos = find_repos(root, args.max_depth)
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(check, repos))
    dirty = [r for r in results if not r["clean"]]
    if not args.no_report:
        report = {"generated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "host": socket.gethostname(),
                  "total_repos": len(results), "dirty_count": len(dirty), "repos": results}
        folder = Path.home() / ".synthesis" / "repo-guard"
        folder.mkdir(parents=True, exist_ok=True)
        partial = folder / f".last-report.{os.getpid()}.json"  # the Console polls the file; it never sees half of it
        partial.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        os.replace(partial, folder / "last-report.json")
    if args.json and not args.quiet:
        print(json.dumps(dirty, indent=2))
    elif not args.quiet:
        for repo in dirty:
            print(f"{repo['path']}\n" + "".join(f"  [{i['type']}] {i['detail']}\n" for i in repo["issues"]), end="")
        print(f"{len(dirty)} of {len(results)} repositories need attention." if dirty else f"All {len(results)} repositories are clean and synced.")
    if dirty and args.alert:
        alert(len(dirty))
    return 1 if dirty else 0


if __name__ == "__main__":
    sys.exit(main())
