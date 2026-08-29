#!/usr/bin/env python3
"""Append-only history of open-item transitions, for weekly and longer reviews.

A tiered context record answers "what is open now". It cannot answer "what did
I miss last week", because the evidence that something was ever open leaves the
record the moment the item is closed out or drops off. Reviews over a week, a
month, or a quarter need the transitions themselves kept somewhere durable.

Design notes worth keeping:

* **Per-workspace, never global.** Engagement workspaces are deletion units. A
  single shared ledger would keep a counterparty's items alive inside a file
  that survives the delete-my-data request they belonged to. Each workspace
  writes only into its own context repo, and reporting federates at read time
  without copying anything into a third place.
* **Expiry is derived, not remembered.** Once open items carry
  `(as of DATE, review Nd)` stamps, "aged out with nobody acting on it" is
  computable from the record itself, so the common case needs no discipline at
  the moment of forgetting — which is exactly the moment discipline fails.
* **Append-only.** A rewritten history cannot answer the question it exists
  for, and a corrupt line loses one event rather than the file.

    review_ledger.py record --source NAME --project P --item TEXT
                            --transition opened|closed|carried|expired-unactioned
    review_ledger.py scan   [--source NAME]
    review_ledger.py report [--window week|month|quarter] [--json]
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

import context_currency

LEDGER_DIR = "review-ledger"
LEDGER_FILE = "events.jsonl"
TRANSITIONS = ("opened", "closed", "carried", "expired-unactioned")
WINDOWS = {"week": 7, "month": 31, "quarter": 92}


def ledger_path(root: Path) -> Path:
    return Path(root) / LEDGER_DIR / LEDGER_FILE


def read_events(root: Path) -> list[dict]:
    """Every readable event. One malformed line costs that line, not the file."""
    path = ledger_path(root)
    events: list[dict] = []
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return events
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            parsed = json.loads(line)
        except ValueError:
            continue
        if isinstance(parsed, dict):
            events.append(parsed)
    return events


def record(
    root: Path,
    project: str,
    item: str,
    transition: str,
    detail: str = "",
    today: date | None = None,
    stamp: str = "",
) -> dict:
    if transition not in TRANSITIONS:
        raise ValueError(f"unknown transition: {transition}")
    event = {
        "ts": (today or date.today()).isoformat(),
        "project": project,
        "item": item.strip(),
        "transition": transition,
        "detail": detail,
    }
    if stamp:
        event["stamp"] = stamp
    path = ledger_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, sort_keys=True) + "\n")
    return event


def _key(project: str, item: str, transition: str) -> tuple[str, str, str]:
    return (project, item.strip(), transition)


def scan(root: Path, today: date | None = None, projects_dir: str = "projects") -> int:
    """Record an expiry for every stamped item now past its review horizon.

    Idempotent per lifecycle, not per text: the same stamp's expiry is never
    recorded twice, but an item that was expired, carried, and re-stamped is a
    NEW lifecycle — its later expiry is a new miss and must be recorded. Keying
    suppression on text alone silenced every expiry cycle after the first.
    """
    moment = today or date.today()
    events = read_events(root)
    seen = {
        (
            e.get("project", ""),
            (e.get("item") or "").strip(),
            e.get("transition", ""),
            e.get("stamp", ""),
        )
        for e in events
    }
    # Events written before stamps were recorded cover the lifecycles current
    # at their recording date: a legacy expiry suppresses stamps no newer than
    # its own timestamp, and nothing after.
    legacy_cover = {
        (e.get("project", ""), (e.get("item") or "").strip()): e.get("ts", "")
        for e in events
        if e.get("transition") == "expired-unactioned" and not e.get("stamp")
    }
    added = 0
    projects = Path(root) / projects_dir
    if not projects.is_dir():
        return 0
    for project in sorted(p for p in projects.iterdir() if p.is_dir()):
        context = project / "CONTEXT.md"
        try:
            text = context.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for item in context_currency.overdue_items(text, today=moment):
            key = (project.name, item["text"].strip(), "expired-unactioned", item["date"])
            if key in seen:
                continue
            legacy_ts = legacy_cover.get((project.name, item["text"].strip()))
            if legacy_ts and item["date"] <= legacy_ts:
                continue
            record(
                root,
                project.name,
                item["text"],
                "expired-unactioned",
                detail=(
                    f"stamped {item['date']}, {item['age_days']} days old, past "
                    f"its {item['horizon_days']}-day review horizon "
                    f"(section '{item['section']}')"
                ),
                today=moment,
                stamp=item["date"],
            )
            seen.add(key)
            added += 1
    return added


def report(
    sources: list[tuple[str, Path]],
    window_days: int,
    today: date | None = None,
) -> dict:
    """Federate the per-workspace ledgers for one window. Copies nothing."""
    moment = today or date.today()
    cutoff = moment - timedelta(days=window_days)
    rows: list[dict] = []
    totals: dict[str, int] = {}
    for name, root in sources:
        for event in read_events(root):
            try:
                stamped = date.fromisoformat(str(event.get("ts", ""))[:10])
            except ValueError:
                continue
            if stamped < cutoff:
                continue
            enriched = dict(event)
            enriched["source"] = name
            rows.append(enriched)
            transition = str(event.get("transition", "unknown"))
            totals[transition] = totals.get(transition, 0) + 1
    rows.sort(key=lambda r: (str(r.get("ts", "")), r.get("source", "")))
    return {
        "window_days": window_days,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "totals": totals,
        "events": rows,
    }


def _configured_sources(selected: str | None) -> list[tuple[str, Path]]:
    import context_doctor

    found = []
    for source in context_doctor.discover_sources([]):
        if selected and source.name != selected:
            continue
        found.append((source.name, source.root))
    return found


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)

    rec = sub.add_parser("record", help="append one transition")
    rec.add_argument("--source", required=True)
    rec.add_argument("--project", required=True)
    rec.add_argument("--item", required=True)
    rec.add_argument("--transition", required=True, choices=TRANSITIONS)
    rec.add_argument("--detail", default="")

    scn = sub.add_parser("scan", help="derive expiries from stamped items")
    scn.add_argument("--source", default=None)

    rep = sub.add_parser("report", help="federated review over a window")
    rep.add_argument("--window", choices=sorted(WINDOWS), default="week")
    rep.add_argument("--source", default=None)
    rep.add_argument("--json", action="store_true")

    args = parser.parse_args(argv)
    sources = _configured_sources(getattr(args, "source", None))
    if not sources:
        print("no matching source in console.yaml", file=sys.stderr)
        return 2

    if args.command == "record":
        root = sources[0][1]
        event = record(
            root, args.project, args.item, args.transition, args.detail
        )
        print(f"recorded {event['transition']}: {event['project']} — {event['item']}")
        return 0

    if args.command == "scan":
        total = 0
        for name, root in sources:
            added = scan(root)
            if added:
                print(f"{name}: {added} newly expired item(s)")
            total += added
        if not total:
            print("no items passed their review horizon")
        return 0

    data = report(sources, WINDOWS[args.window])
    if args.json:
        print(json.dumps(data, indent=2))
        return 0
    if not data["events"]:
        print(f"nothing recorded in the last {data['window_days']} day(s)")
        return 0
    print(f"Review — last {data['window_days']} day(s)")
    for transition in TRANSITIONS:
        count = data["totals"].get(transition)
        if count:
            print(f"  {transition}: {count}")
    missed = [e for e in data["events"] if e["transition"] == "expired-unactioned"]
    if missed:
        print("\nWhat slipped:")
        for event in missed:
            print(f"  [{event['source']}/{event['project']}] {event['item']}")
            if event.get("detail"):
                print(f"      {event['detail']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
