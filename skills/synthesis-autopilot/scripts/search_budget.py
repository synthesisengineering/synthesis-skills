#!/usr/bin/env python3
"""Reserve and reconcile searches in the durable shared run ledger.

``check`` is an arithmetic preview, never dispatch admission. ``reserve``
atomically reserves a total fan-out allocation; each nested worker reserves
its share from that parent. ``settle`` records observed usage or unknown.
The ledger governs Synthesis admissions; it cannot intercept native tools
called outside this protocol or manufacture unavailable provider accounting.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
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
                          "allowance": cap * agents, "admitted": False,
                          "scope": "arithmetic only; durable reservation required before dispatch"}))
        return 0
    print(f"search budget: {agents} agents x {cap} searches = "
          f"{cap * agents} total; arithmetic preview only. Reserve from the durable run before dispatch.")
    return 0


def _command(project, run_id, actor, runtime_root, expected_revision, command_id, name, payload):
    from autopilot import engine
    from workflow import budget_summary
    state = engine().apply_command(project, run_id, name, payload, actor=actor,
        runtime_root=runtime_root, expected_revision=expected_revision, command_id=command_id)
    return {"run_id": state["run_id"], "revision": state["revision"],
            "budget": budget_summary(state)["searches"],
            "scope": "shared run admission; native calls outside the protocol are not intercepted"}


def reserve_searches(*, project, run_id, actor, runtime_root, expected_revision, command_id,
                     reservation_id, agents, per_agent, parent_id=None):
    if type(agents) is not int or type(per_agent) is not int or not 1 <= agents <= 256 or per_agent <= 0:
        raise ValueError("agents and per-agent allocation must be positive bounded integers")
    result = _command(project, run_id, actor, runtime_root, expected_revision, command_id,
        "workflow.reserve", {"reservation_id": reservation_id, "amounts": {"searches": agents * per_agent},
                             "category": "work", "parent_id": parent_id})
    return {**result, "admitted": True, "reservation_id": reservation_id,
            "agents": agents, "per_agent": per_agent}


def settle_searches(*, project, run_id, actor, runtime_root, expected_revision, command_id,
                    reservation_id, actual):
    if actual is not None and (type(actual) is not int or actual < 0):
        raise ValueError("actual searches must be a nonnegative integer or unknown")
    return _command(project, run_id, actor, runtime_root, expected_revision, command_id,
        "workflow.settle", {"reservation_id": reservation_id,
                            "actual": None if actual is None else {"searches": actual}})


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    p_check = sub.add_parser("check", help="verify the split before dispatch")
    p_check.add_argument("--agents", type=int, required=True)
    p_check.add_argument("--json", action="store_true")
    for action in ("reserve", "settle"):
        p = sub.add_parser(action)
        for name in ("project", "actor"):
            p.add_argument("--" + name, type=Path, required=True)
        for name in ("run-id", "reservation-id", "command-id"):
            p.add_argument("--" + name, required=True)
        p.add_argument("--expected-revision", type=int, required=True)
        if action == "reserve":
            p.add_argument("--agents", type=int, required=True)
            p.add_argument("--per-agent", type=int, required=True)
            p.add_argument("--parent-id")
        else:
            usage = p.add_mutually_exclusive_group(required=True)
            usage.add_argument("--actual", type=int)
            usage.add_argument("--unknown", action="store_true")
    args = parser.parse_args(argv)
    if args.command == "check":
        return cmd_check(args.agents, args.json)
    try:
        from autopilot import read_json, default_runtime_root
        kwargs = {"project": args.project, "actor": read_json(args.actor), "runtime_root": default_runtime_root(),
                  "run_id": args.run_id, "reservation_id": args.reservation_id,
                  "expected_revision": args.expected_revision, "command_id": args.command_id}
        result = (reserve_searches(**kwargs, agents=args.agents, per_agent=args.per_agent, parent_id=args.parent_id)
                  if args.command == "reserve" else settle_searches(**kwargs, actual=args.actual))
        print(json.dumps(result, indent=2))
        return 0
    except (ValueError, OSError) as exc:
        parser.exit(2, f"search budget: {exc}\n")


if __name__ == "__main__":
    raise SystemExit(main())
