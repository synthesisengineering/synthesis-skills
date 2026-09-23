#!/usr/bin/env python3
"""Pre-dispatch search-budget check for research fan-outs.

The incident: six parallel research agents silently exhausted one
session-wide WebSearch budget because each assumed its own. The
doctrine fix (briefs carry a per-agent allocation) is prose; this
check is mechanical. Before dispatching N research agents, run::

    search_budget.py check --agents N [--json]

The per-agent cap comes from ``SYNTHESIS_SEARCH_BUDGET_PER_AGENT``
(an integer number of searches per agent). The check fails closed
when the cap is unset or malformed — a fan-out against an undivided
pool is the plan that produced the incident — and otherwise prints
the split the briefs must carry. Exit 0: dispatch with the printed
split. Exit 1: set the cap first. Exit 2: bad arguments.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

ENV_VAR = "SYNTHESIS_SEARCH_BUDGET_PER_AGENT"


def read_cap() -> tuple[int | None, str]:
    raw = os.environ.get(ENV_VAR, "").strip()
    if not raw:
        return None, (f"{ENV_VAR} is unset — a research fan-out without a "
                       f"per-agent cap shares one undivided pool. Set it, e.g. "
                       f"export {ENV_VAR}=25, then re-run this check.")
    try:
        cap = int(raw)
    except ValueError:
        return None, f"{ENV_VAR}={raw!r} is not an integer"
    if cap <= 0:
        return None, f"{ENV_VAR}={cap} must be positive"
    return cap, ""


def cmd_check(agents: int, as_json: bool) -> int:
    if agents <= 0:
        print("check: --agents must be a positive integer", file=sys.stderr)
        return 2
    cap, problem = read_cap()
    if cap is None:
        print(f"check: {problem}", file=sys.stderr)
        return 1
    if as_json:
        print(json.dumps({"per_agent_cap": cap, "agents": agents,
                          "allowance": cap * agents}))
        return 0
    print(f"search budget: {agents} agents x {cap} searches = "
          f"{cap * agents} total; each brief carries its share of {cap}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    p_check = sub.add_parser("check", help="verify the split before dispatch")
    p_check.add_argument("--agents", type=int, required=True)
    p_check.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    if args.command == "check":
        return cmd_check(args.agents, args.json)
    parser.error(f"unknown command {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
