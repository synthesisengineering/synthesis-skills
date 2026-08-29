#!/usr/bin/env python3
"""Per-surface sync watermarks: the last date actually WRITTEN, not last run.

A sync window anchored on when the previous run executed cannot see its own
holes. Skip a run and the hole is never revisited, because the next window
starts at now-minus-a-bit rather than at the last day on disk. Nothing persists
"the mirror is complete through date X", so no run can detect what it missed.

A watermark fixes that by construction rather than by diligence:

* the window is computed from the watermark, so a hole is revisited
  automatically on the next run — no one has to notice it;
* the watermark advances only on a successful WRITE, so a run that fetches
  nothing, errors, or is interrupted cannot silently declare the day covered;
* `status` exits non-zero while any surface has an unclosed, undeferred gap,
  which is what makes a recorded gap load-bearing instead of prose. A gap that
  genuinely cannot close this run must be deferred WITH A REASON, and the
  deferral is itself dated and re-surfaced.

That last point is the whole design. Detection that nothing consumes changes
nothing: three consecutive artifacts recorded the same gap in prose and no run
ever read those lines back.

    sync_watermark.py window   --workspace W --surface S
    sync_watermark.py advance  --workspace W --surface S --through YYYY-MM-DD
    sync_watermark.py defer    --workspace W --surface S --reason TEXT
    sync_watermark.py status   --workspace W [--json]
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

STORE_DIRNAME = "sync-watermarks"
# A deferral silences a gap for one working day, never indefinitely: an
# indefinite silence is how a gap becomes furniture.
DEFERRAL_MAX_AGE = timedelta(days=1)


def store_path(workspace: str, home: Path | None = None) -> Path:
    root = home or Path(
        os.environ.get("SYNTHESIS_HOME", str(Path.home() / ".synthesis"))
    )
    safe = "".join(c for c in workspace if c.isalnum() or c in "-_") or "default"
    return root / STORE_DIRNAME / f"{safe}.json"


def load(workspace: str, home: Path | None = None) -> dict:
    path = store_path(workspace, home)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"surfaces": {}, "deferrals": {}}
    if not isinstance(data, dict):
        return {"surfaces": {}, "deferrals": {}}
    data.setdefault("surfaces", {})
    data.setdefault("deferrals", {})
    return data


def save(workspace: str, data: dict, home: Path | None = None) -> None:
    path = store_path(workspace, home)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp.replace(path)


def _as_date(text: str) -> date | None:
    try:
        return date.fromisoformat(str(text)[:10])
    except (TypeError, ValueError):
        return None


def window(
    workspace: str, surface: str, today: date | None = None, home: Path | None = None
) -> dict:
    """The range this run must cover for one surface."""
    moment = today or date.today()
    data = load(workspace, home)
    entry = data["surfaces"].get(surface) or {}
    through = _as_date(entry.get("through", ""))
    if through is None:
        return {
            "surface": surface,
            "bootstrap": True,
            "from": None,
            "to": moment.isoformat(),
            "gap_days": None,
            "detail": "no watermark yet — this surface has never recorded a "
                      "successful write, so the window cannot be narrowed",
        }
    start = through + timedelta(days=1)
    return {
        "surface": surface,
        "bootstrap": False,
        "from": start.isoformat(),
        "to": moment.isoformat(),
        "gap_days": max((moment - through).days - 1, 0),
        "detail": f"mirror complete through {through.isoformat()}",
    }


def advance(
    workspace: str,
    surface: str,
    through: str,
    today: date | None = None,
    home: Path | None = None,
) -> dict:
    """Record a successful write. Never moves a watermark backwards."""
    moment = today or date.today()
    new = _as_date(through)
    if new is None:
        raise ValueError(f"not a date: {through}")
    if new > moment:
        raise ValueError(f"refusing a future watermark: {through} > {moment}")
    data = load(workspace, home)
    entry = data["surfaces"].get(surface) or {}
    old = _as_date(entry.get("through", ""))
    if old is not None and new < old:
        return {"surface": surface, "through": old.isoformat(), "moved": False,
                "detail": f"refused: {through} is behind the recorded {old}"}
    data["surfaces"][surface] = {
        "through": new.isoformat(),
        "updated_at": datetime.now().isoformat(timespec="seconds"),
    }
    # A surface that just wrote has no outstanding gap, so its deferral is spent.
    data["deferrals"].pop(surface, None)
    save(workspace, data, home)
    return {"surface": surface, "through": new.isoformat(), "moved": True,
            "detail": "watermark advanced"}


def defer(
    workspace: str,
    surface: str,
    reason: str,
    today: date | None = None,
    home: Path | None = None,
) -> dict:
    if not reason.strip():
        raise ValueError("a deferral requires a reason")
    moment = today or date.today()
    data = load(workspace, home)
    data["deferrals"][surface] = {
        "reason": reason.strip(),
        "deferred_on": moment.isoformat(),
    }
    save(workspace, data, home)
    return {"surface": surface, "deferred_on": moment.isoformat()}


def status(
    workspace: str,
    surfaces: list[str] | None = None,
    today: date | None = None,
    home: Path | None = None,
) -> dict:
    moment = today or date.today()
    data = load(workspace, home)
    names = sorted(set(surfaces or []) | set(data["surfaces"]))
    rows, blocking = [], []
    for surface in names:
        info = window(workspace, surface, moment, home)
        gap = info["bootstrap"] or (info["gap_days"] or 0) > 0
        deferral = data["deferrals"].get(surface) or {}
        deferred_on = _as_date(deferral.get("deferred_on", ""))
        live_deferral = (
            deferred_on is not None and (moment - deferred_on) <= DEFERRAL_MAX_AGE
        )
        row = {
            "surface": surface,
            "through": (data["surfaces"].get(surface) or {}).get("through"),
            "gap": gap,
            "gap_days": info["gap_days"],
            "bootstrap": info["bootstrap"],
            "deferred": bool(live_deferral),
            "deferral_reason": deferral.get("reason") if live_deferral else None,
            "stale_deferral": bool(deferred_on and not live_deferral),
        }
        rows.append(row)
        if gap and not live_deferral:
            blocking.append(surface)
    return {"workspace": workspace, "as_of": moment.isoformat(),
            "surfaces": rows, "blocking": blocking}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("window", "advance", "defer", "status"):
        p = sub.add_parser(name)
        p.add_argument("--workspace", required=True)
        p.add_argument("--json", action="store_true")
        if name != "status":
            p.add_argument("--surface", required=True)
        else:
            p.add_argument("--surface", action="append", default=[])
        if name == "advance":
            p.add_argument("--through", required=True)
        if name == "defer":
            p.add_argument("--reason", required=True)
    args = parser.parse_args(argv)

    if args.command == "status" and not args.surface:
        # The declared surface set must come from the caller (the ritual's
        # config), because the store only knows surfaces that have already
        # been written: a declared surface with no successful write is
        # exactly the gap this gate exists to block, and a status that
        # consults only the store exits 0 straight past it.
        print(
            "error: status requires the declared surface set — pass every "
            "declared surface with --surface (repeatable); an empty set "
            "cannot authorize a ritual",
            file=sys.stderr,
        )
        return 2

    try:
        if args.command == "window":
            result = window(args.workspace, args.surface)
        elif args.command == "advance":
            result = advance(args.workspace, args.surface, args.through)
        elif args.command == "defer":
            result = defer(args.workspace, args.surface, args.reason)
        else:
            result = status(args.workspace, args.surface)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    if getattr(args, "json", False):
        print(json.dumps(result, indent=2))
    elif args.command == "status":
        for row in result["surfaces"]:
            state = (
                "BLOCKING" if row["gap"] and not row["deferred"]
                else "deferred" if row["gap"] else "current"
            )
            through = row["through"] or "never written"
            extra = f" — {row['deferral_reason']}" if row["deferred"] else ""
            print(f"  {state:9s} {row['surface']:22s} through {through}{extra}")
        if result["blocking"]:
            print(
                f"\n{len(result['blocking'])} surface(s) with an unclosed gap: "
                + ", ".join(result["blocking"])
                + "\nClose them this run, or record an explicit reason with "
                "`sync_watermark.py defer`. A gap in prose is not a closed gap."
            )
    else:
        print(json.dumps(result, indent=2))

    if args.command == "status" and result["blocking"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
