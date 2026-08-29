#!/usr/bin/env python3
"""Surface a small number of stale-active projects as decisions, not as a report.

The problem this addresses: a project index has an intake and no outflow.
Projects enter it and never leave. On the corpus that motivated this, 37 of 63
projects claiming to be live had not moved in over 90 days — one for 619 — and
nobody noticed, because noticing required reading the whole index.

The context doctor already computes freshness. It reports it among 200+ other
warnings, and a signal inside 200 warnings is not a signal. This promotes the
same information to a capped decision surface.

Design rules, each learned from the condition it fixes:

  - **Cap the output.** Three decisions a day clears a large backlog in a
    couple of weeks and never feels like a task. An uncapped list gets skipped,
    and a skipped check protects nothing.
  - **Oldest first.** The most-stale project is the most likely to be dead.
  - **Never decide.** Print the options; a human picks. Closing someone's
    project is not an inference an agent should make from elapsed time.
  - **Exit 0 always.** This is a surface, not a gate. It must never be the
    reason a day-start ritual fails.

`active` is taken to mean: *I intend to touch this within 30 days.* That
definition is what makes the check meaningful. Without it, `active` covers both
"moving" and "still care about someday", and the index cannot distinguish them.

Usage:
    portfolio_review.py                    # 3 oldest, >30 days stale
    portfolio_review.py --threshold 90     # only badly stale
    portfolio_review.py --all              # full picture, no cap
    portfolio_review.py --json             # for a console or hook
    portfolio_review.py --index PATH       # one index, skipping discovery
    portfolio_review.py --source ROOT      # a source root (repeatable)
"""
from __future__ import annotations

import argparse
import datetime
import json
import os
import re
import subprocess
import sys
from pathlib import Path

try:
    import yaml
except ImportError:  # pragma: no cover - environment-dependent
    print("portfolio_review: PyYAML unavailable; skipping", file=sys.stderr)
    sys.exit(0)

# A project claiming any of these is asserting that it wants attention.
# `paused` deliberately asserts the opposite, which is the whole point of
# pausing something, so it is never surfaced here.
CLAIMS_LIVE = {"active", "ongoing", "new"}

DEFAULT_THRESHOLD_DAYS = 30
DEFAULT_LIMIT = 3


def console_config_path() -> Path:
    home = Path(os.environ.get("SYNTHESIS_HOME", str(Path.home() / ".synthesis")))
    return home / "console.yaml"


def discover_indexes(explicit_index: list[Path], explicit_source: list[Path]) -> list[Path]:
    """Find every projects/index.yaml this run should read.

    Order of preference: an explicit index, then explicit source roots, then the
    console configuration. A discovery that finds nothing returns an empty list
    rather than raising: this is a surface, and a missing config must not break
    the ritual that calls it.
    """
    if explicit_index:
        return [p for p in explicit_index if p.is_file()]

    roots: list[Path] = list(explicit_source)
    if not roots:
        config = console_config_path()
        if not config.is_file():
            return []
        try:
            data = yaml.safe_load(config.read_text(encoding="utf-8")) or {}
        except Exception:
            return []
        for entry in data.get("sources") or []:
            if not isinstance(entry, dict):
                continue
            root = entry.get("root")
            projects_dir = entry.get("projects_dir")
            if not root or not projects_dir:
                # A source with no projects_dir cannot be audited. Skipping it
                # silently is how a whole repo goes unreviewed, so say so.
                if root:
                    print(f"portfolio_review: {root} declares no projects_dir; "
                          "not reviewed", file=sys.stderr)
                continue
            roots.append(Path(root).expanduser() / str(projects_dir))
        found = [r / "index.yaml" for r in roots]
        return [p for p in found if p.is_file()]

    found = []
    for root in roots:
        root = Path(root).expanduser()
        for candidate in (root / "index.yaml", root / "projects" / "index.yaml"):
            if candidate.is_file():
                found.append(candidate)
                break
    return found


def stale_projects(index_path: Path, threshold: int, today: datetime.date) -> list[dict]:
    try:
        data = yaml.safe_load(index_path.read_text(encoding="utf-8")) or {}
    except Exception as exc:
        print(f"portfolio_review: {index_path} did not parse: {exc}", file=sys.stderr)
        return []
    out = []
    for project in data.get("projects") or []:
        if not isinstance(project, dict):
            continue
        if str(project.get("status", "")).strip().lower() not in CLAIMS_LIVE:
            continue
        pid = project.get("id")
        if not pid:
            continue
        row = {"id": pid, "status": project.get("status"),
               "index": str(index_path), "age_days": None, "last_session": None}
        last = project.get("last_session")
        if last is None:
            out.append(row)
            continue
        if isinstance(last, str):
            try:
                last = datetime.date.fromisoformat(last)
            except ValueError:
                continue
        if not isinstance(last, datetime.date):
            continue
        age = (today - last).days
        if age > threshold:
            row["age_days"] = age
            row["last_session"] = last.isoformat()
            out.append(row)
    return out


def last_commit(index_path: Path, pid: str) -> str:
    """The project's real newest commit, which often postdates `last_session`.

    Worth showing: a bulk repo-wide sweep touches a project without anyone
    working it, so a recent commit is not by itself evidence of life.
    """
    repo = index_path.parent.parent
    try:
        proc = subprocess.run(
            ["git", "log", "-1", "--pretty=format:%ai %s", "--",
             f"{index_path.parent.name}/{pid}"],
            cwd=repo, capture_output=True, text=True, timeout=10, check=False)
        return proc.stdout.strip()[:90] or "(no commits)"
    except Exception:
        return "(git unavailable)"


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--index", type=Path, action="append", default=[])
    ap.add_argument("--source", type=Path, action="append", default=[])
    ap.add_argument("--threshold", type=int, default=DEFAULT_THRESHOLD_DAYS,
                    help="days since last_session before a live project is stale")
    ap.add_argument("--limit", type=int, default=DEFAULT_LIMIT)
    ap.add_argument("--all", action="store_true", help="ignore the cap")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    indexes = discover_indexes(args.index, args.source)
    if not indexes:
        print("portfolio_review: no project index found; nothing to review",
              file=sys.stderr)
        return 0

    today = datetime.date.today()
    stale: list[dict] = []
    for index_path in indexes:
        stale.extend(stale_projects(index_path, args.threshold, today))
    # Undated first (no last_session is the most suspect state), then oldest.
    stale.sort(key=lambda r: (r["age_days"] is not None, -(r["age_days"] or 0)))
    shown = stale if args.all else stale[: args.limit]

    if args.json:
        print(json.dumps({
            "generated": today.isoformat(),
            "threshold_days": args.threshold,
            "indexes": [str(p) for p in indexes],
            "stale_total": len(stale),
            "shown": shown,
        }, indent=2))
        return 0

    if not stale:
        print(f"Portfolio review: nothing claims active while stale "
              f"(>{args.threshold}d) across {len(indexes)} index(es). "
              "The record is honest.")
        return 0

    print(f"Portfolio review: {len(stale)} project(s) claim active but have not "
          f"moved in >{args.threshold} days.")
    print(f"Showing {len(shown)}. For each: close it, pause it, or pick it up today.\n")
    for row in shown:
        age = "undated" if row["age_days"] is None else f"{row['age_days']}d"
        print(f"  {row['id']}  [{row['status']}]  stale {age}")
        print(f"    last_session: {row['last_session'] or 'none recorded'}")
        print(f"    last commit:  {last_commit(Path(row['index']), row['id'])}")
        print("    -> completed (it shipped) | paused (not now) | active (working it today)\n")
    if len(stale) > len(shown):
        print(f"  ...and {len(stale) - len(shown)} more. Three a day clears a large "
              "backlog in a couple of weeks; --all shows the full picture.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
