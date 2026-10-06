#!/usr/bin/env python3
"""Fetch and count every declared repository, so no repo goes unreported.

    repo_state.py --workspace-root W [--fetch] [--ff] [--skip NAME] [--json]   # .agents/repos.yaml
    repo_state.py --discover ROOT    [--fetch] [--ff] [--skip NAME] [--json]   # every repo under ROOT

Declared mode reads `W/.agents/repos.yaml` (the declared list is the complete
decision; no judgment about which repos feel active) and checks each declared
default branch. Discover mode finds every git repository under ROOT (depth 3)
and checks the checked-out branch: the leave-a-Mac and day-end strand scan.
Every repository lands in exactly one state, worst first:

  UNREACHABLE  no clone, or the fetch failed (the world's problem)
  BLIND        a branch with no upstream, or a detached HEAD (our defect; it once
               hid seven repos and 39 commits for weeks)
  DIRTY        uncommitted changes (listed; never pulled over)
  DECISION     ahead of its upstream, or diverged: push, rebase or merge is a decision
  BEHIND       behind only: a fast-forward is safe (`--ff` takes it when the tree is clean)
  CURRENT      level with an upstream fetched this run (CACHED without --fetch)
  EXCLUDED     dormant workspace or repo, or `ritual_sync: no`

It never merges, rebases, pushes or force-anything. Exit 2 when any repo is
UNREACHABLE or BLIND, 1 when any is DIRTY or DECISION, else 0.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from simple_yaml import load  # noqa: E402

ORDER = ("UNREACHABLE", "BLIND", "DIRTY", "DECISION", "BEHIND", "CURRENT", "CACHED", "EXCLUDED")


def git(repo: Path, *args: str, timeout: int = 60) -> str:
    done = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, timeout=timeout,
                          env={**os.environ, "GIT_TERMINAL_PROMPT": "0"})
    if done.returncode:
        lines = (done.stderr or done.stdout).strip().splitlines()
        raise RuntimeError(lines[-1] if lines else f"git {args[0]} failed")
    return done.stdout.rstrip("\n")


def declared(root: Path) -> list[dict]:
    data = load((root / ".agents" / "repos.yaml").read_text(encoding="utf-8")) or {}
    rows = data.get("repos") or []
    rows = [{"name": k, **(v or {})} for k, v in rows.items()] if isinstance(rows, dict) else rows
    names = [r.get("name") for r in rows]
    if not rows or len(set(names)) != len(names) or not all(names):
        raise ValueError(f"{root}/.agents/repos.yaml: repos must be a non-empty list with unique names")
    for row in rows:
        excluded = "dormant" in (data.get("status"), row.get("status")) or row.get("ritual_sync") is not True
        path = Path(str(row.get("path") or row["name"])).expanduser()
        row.update(path=path if path.is_absolute() else root / path, excluded=excluded,
                   branches=row.get("default_branches") or None)
    return rows


def discovered(root: Path) -> list[dict]:
    found = sorted({p.parent for depth in ("*", "*/*") for p in root.glob(depth + "/.git") if p.is_dir()})
    return [{"name": str(p.relative_to(root)), "path": p, "excluded": False, "branches": None} for p in found]


def check(row: dict, fetch: bool, ff: bool) -> dict:
    out = {"name": row["name"], "path": str(row["path"]), "branches": []}
    if row["excluded"]:
        return {**out, "state": "EXCLUDED"}
    try:
        if not (row["path"] / ".git").exists():
            raise RuntimeError("no clone at this path")
        if fetch:
            git(row["path"], "fetch", "--all", "--prune", "--no-recurse-submodules", timeout=120)
        current = git(row["path"], "branch", "--show-current")
        dirty = git(row["path"], "status", "--porcelain").splitlines()
    except (RuntimeError, OSError, subprocess.TimeoutExpired) as exc:
        return {**out, "state": "UNREACHABLE", "reason": str(exc)}
    states = ["BLIND"] if not current else []
    for branch in row["branches"] or ([current] if current else []):
        item = {"branch": branch}
        try:
            upstream = git(row["path"], "rev-parse", "--abbrev-ref", f"{branch}@{{upstream}}")
            local, remote = git(row["path"], "rev-parse", f"refs/heads/{branch}", f"{upstream}^{{commit}}").split()
            ahead, behind = map(int, git(row["path"], "rev-list", "--left-right", "--count",
                                         f"{local}...{remote}").split())
            item.update(upstream=upstream, ahead=ahead, behind=behind,
                        state="DECISION" if ahead else "BEHIND" if behind else ("CURRENT" if fetch else "CACHED"))
            if ff and item["state"] == "BEHIND" and not (branch == current and dirty):
                if branch == current:
                    git(row["path"], "merge", "--ff-only", "--quiet", remote)
                else:  # compare-and-swap: refused if the branch moved since it was read
                    git(row["path"], "update-ref", f"refs/heads/{branch}", remote, local)
                item.update(state="CURRENT", forwarded=behind)
        except (RuntimeError, ValueError, subprocess.TimeoutExpired) as exc:
            item.update(state="BLIND", reason=f"no upstream or unreadable: {exc}")
        out["branches"].append(item)
        states.append(item["state"])
    if dirty:
        states.append("DIRTY")
        out["dirty"] = dirty[:20] + ([f"... {len(dirty) - 20} more"] if len(dirty) > 20 else [])
    return {**out, "state": min(states or ["CACHED"], key=ORDER.index)}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--workspace-root", type=Path)
    source.add_argument("--discover", type=Path)
    parser.add_argument("--fetch", action="store_true")
    parser.add_argument("--ff", action="store_true", help="fast-forward BEHIND branches whose tree is clean")
    parser.add_argument("--skip", action="append", default=[], help="repo name to leave untouched (a live claim)")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    try:
        rows = declared(args.workspace_root.expanduser()) if args.workspace_root else discovered(args.discover.expanduser())
    except (OSError, ValueError) as exc:
        print(f"repo_state: refused: {exc}", file=sys.stderr)
        return 2
    report = [check(r, args.fetch, args.ff and r["name"] not in args.skip) for r in rows]
    counts = {s: sum(r["state"] == s for r in report) for s in ORDER}
    if args.json:
        print(json.dumps({"fetched": args.fetch, "counts": counts, "repositories": report}, indent=2))
    else:
        for r in sorted(report, key=lambda r: ORDER.index(r["state"])):
            detail = ", ".join(f"{b['branch']} {b['state'].lower()}" + (f" +{b['ahead']}/-{b['behind']}" if "ahead" in b else "")
                               + (f" (forwarded {b['forwarded']})" if "forwarded" in b else "") for b in r["branches"])
            print(f"  {r['state']:11} {r['name']:36} {detail}{'  ' + r['reason'] if 'reason' in r else ''}")
            for line in r.get("dirty", []):
                print(f"      {line}")
        print(f"{counts['CURRENT'] + counts['CACHED']} of {len(report)} current"
              f"{'' if args.fetch else ' (cached: not fetched this run)'}, {counts['BEHIND']} behind, "
              f"{counts['DECISION']} decisions, {counts['DIRTY']} dirty, {counts['BLIND']} blind, "
              f"{counts['UNREACHABLE']} unreachable, {counts['EXCLUDED']} excluded")
    return 2 if counts["UNREACHABLE"] or counts["BLIND"] else 1 if counts["DIRTY"] or counts["DECISION"] else 0


if __name__ == "__main__":
    sys.exit(main())
