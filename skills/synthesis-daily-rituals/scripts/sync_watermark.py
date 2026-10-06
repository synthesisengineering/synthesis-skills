#!/usr/bin/env python3
"""Sync watermarks: per surface and per read target, the last MOMENT actually written.

A window anchored on when the previous run executed cannot see its own holes,
and a watermark that only knows the day cannot see the hours: on 2026-09-01 a
DM read at 09:15 counted as current all day, and at 17:51 the agent called a
question unanswered that had been answered at 09:27. So:

* a watermark is an ISO-8601 moment, the last one actually written, never the
  last attempted; `window` prints the epoch `oldest` a read call takes beside
  human-readable bounds (a window is computed, never typed);
* a surface may carry one watermark per declared target (a channel, a DM, a
  mailbox), and once it does, a surface-level advance is refused unless
  `--surface-level` asserts whole-surface coverage (2026-09-01: a wholesale
  advance on the Chat surface claimed coverage no per-space read backed);
* `begin` stamps a run and `status --since run` blocks on every declared
  surface or target this run did not re-read; the store only knows what has
  been written, so status refuses an empty declared set;
* a watermark advances only after a successful write, never backwards, never
  into the future; a gap that cannot close is deferred with a reason, for one day.
A read through the harness's own connectors advances like any other: no token
or receipt is required (2026-10-01: requiring them stopped every bookmark).

    sync_watermark.py begin   --workspace W [--label L]
    sync_watermark.py window  --workspace W --surface S [--target T]
    sync_watermark.py advance --workspace W --surface S --through TS [--target T ...] [--surface-level]
    sync_watermark.py defer   --workspace W --surface S [--target T] --reason TEXT
    sync_watermark.py status  --workspace W --surface S ... [--target S:T ...] [--targets-from FILE]
                              [--since run|TS] [--max-age 4h]

TS is ISO-8601 (naive means local), epoch seconds as `window` prints them
(1789397434) or as Slack's ts carries them (1789397434.123456; the fraction is
dropped, never rounded up), `now`, or YYYY-MM-DD meaning complete through the
END of that day, which is refused until that day is over. The store keeps
ISO-8601 to the second with an offset, so `window`'s `latest=` is `advance`'s `--through`.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

DEFERRAL_MAX_AGE = timedelta(days=1)  # an indefinite silence is how a gap becomes furniture
_EPOCH = re.compile(r"\A([1-9]\d{9})(?:\.\d+)?\Z")  # ten digits, no leading zero
_EPOCH_MS = re.compile(r"\A[1-9]\d{12}\Z")
ACCEPTED = ("ISO-8601 such as 2026-09-14T09:15:00-04:00, YYYY-MM-DD for complete through the END of "
            "that day, Unix epoch seconds as `window` prints them (1789397434) or as Slack's ts carries "
            "them (1789397434.123456), or 'now'")


def now_local() -> datetime:
    return datetime.now().astimezone().replace(microsecond=0)


def parse_moment(text: str, now: datetime) -> datetime:
    raw = str(text).strip()
    if raw.lower() == "now":
        return now.replace(microsecond=0)
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", raw):
        try:
            end = datetime.combine(date.fromisoformat(raw) + timedelta(days=1), datetime.min.time())
            return end.replace(tzinfo=now.tzinfo)
        except ValueError:
            pass
    epoch = _EPOCH.fullmatch(raw)
    if epoch:
        return datetime.fromtimestamp(int(epoch.group(1)), tz=now.tzinfo)
    if _EPOCH_MS.fullmatch(raw):
        raise ValueError(f"not a timestamp: {text!r}: thirteen digits reads as epoch milliseconds; "
                         f"pass epoch seconds ({raw[:10]}) (use {ACCEPTED})")
    try:
        moment = datetime.fromisoformat(raw)
    except ValueError as exc:
        raise ValueError(f"not a timestamp: {text!r} (use {ACCEPTED})") from exc
    return (moment if moment.tzinfo else moment.replace(tzinfo=now.tzinfo)).replace(microsecond=0)


def parse_duration(text: str) -> timedelta:
    compact = re.sub(r"\s+", "", str(text).lower())
    parts = re.findall(r"(\d+)([dhm])", compact)
    if not parts or "".join(n + u for n, u in parts) != compact:
        raise ValueError(f"not a duration: {text!r} (use forms like 90m, 4h, 1d12h)")
    return sum((int(n) * {"d": timedelta(days=1), "h": timedelta(hours=1), "m": timedelta(minutes=1)}[u]
                for n, u in parts), timedelta())


def stamp(moment: datetime) -> str:
    return moment.isoformat(timespec="seconds")


def human(moment: datetime) -> str:
    """To the second: a refusal that sets two moments side by side must show two times."""
    return moment.astimezone().strftime("%a %Y-%m-%d %H:%M:%S %Z")


def span(delta: timedelta) -> str:
    minutes = int(delta.total_seconds()) // 60
    days, hours, minutes = minutes // 1440, minutes % 1440 // 60, minutes % 60
    return " ".join(f"{n}{u}" for n, u in ((days, "d"), (hours, "h"), (minutes, "m")) if n) or "0m"


def _stored(value) -> datetime | None:
    try:
        return datetime.fromisoformat(str(value))
    except (TypeError, ValueError):
        return None


def store_path(workspace: str, home: Path | None = None) -> Path:
    if not workspace.strip():
        raise ValueError("--workspace is empty (an unset variable?); a store names its workspace")
    home = home or Path(os.environ.get("SYNTHESIS_HOME") or Path.home() / ".synthesis" / "v5")
    return home / "sync-watermarks" / ("".join(c for c in workspace if c.isalnum() or c in "-_") + ".json")


def load(workspace: str, home: Path | None = None, reference: datetime | None = None) -> dict:
    try:
        data = json.loads(store_path(workspace, home).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        data = {}
    data = data if isinstance(data, dict) else {}
    return {"schema": 2, "run": data.get("run"), "surfaces": data.get("surfaces") or {},
            "deferrals": data.get("deferrals") or {}}


def save(workspace: str, data: dict, home: Path | None = None) -> None:
    path = store_path(workspace, home)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    tmp.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def _entry(data: dict, surface: str, target: str | None = None) -> dict:
    entry = data["surfaces"].get(surface) or {}
    return entry if target is None else (entry.get("targets") or {}).get(target) or {}


def _key(surface: str, target: str | None = None) -> str:
    return surface if target is None else f"{surface}:{target}"


def begin(workspace: str, label: str = "", now: datetime | None = None, home: Path | None = None) -> dict:
    moment = now or now_local()
    data = load(workspace, home)
    data["run"] = {"started_at": stamp(moment), "label": label.strip()}
    save(workspace, data, home)
    return {"started_at": stamp(moment), "label": label.strip(), "human": human(moment)}


def window(workspace: str, surface: str, target: str | None = None, now: datetime | None = None,
           home: Path | None = None) -> dict:
    moment = now or now_local()
    data = load(workspace, home)
    through, source = _stored(_entry(data, surface, target).get("through")), "own watermark"
    if target is not None and through is None and _stored(_entry(data, surface).get("through")):
        through, source = _stored(_entry(data, surface).get("through")), "surface watermark (target never read alone)"
    label = surface if target is None else f"{surface} (target {target})"
    oldest = int(through.timestamp()) if through else None
    return {"surface": surface, "target": target, "to": stamp(moment), "to_epoch": int(moment.timestamp()),
            "latest": int(moment.timestamp()), "from": stamp(through) if through else None,
            "from_epoch": oldest, "oldest": oldest, "source": source if through else None,
            "bootstrap": through is None, "span": span(moment - through) if through else None,
            "human": (f"{label}: {human(through)} → {human(moment)} ({span(moment - through)})" if through else
                      f"{label}: no watermark yet → read to the workspace's backfill bound and state that bound")}


def advance(workspace: str, surface: str, through: str, targets=(), now: datetime | None = None,
            home: Path | None = None, surface_level: bool = False) -> dict:
    """Record a successful write; never backwards, never into the future."""
    moment = now or now_local()
    new = parse_moment(through, moment)
    if new > moment:
        hint = (" (a bare date means complete through the END of that day; pass the moment you read)"
                if re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(through).strip()) else "")
        raise ValueError(f"refusing a future watermark: {through} is {human(new)}, after {human(moment)}{hint}")
    data = load(workspace, home)
    entry = data["surfaces"].setdefault(surface, {})
    entry.setdefault("targets", {})
    if not targets and entry["targets"] and not surface_level:
        raise ValueError(f"{surface} carries per-target watermarks ({len(entry['targets'])}); a surface-level "
                         "advance would claim coverage no target read backs. Advance the targets you read, or "
                         "pass --surface-level to assert whole-surface coverage")
    slots = [(t, entry["targets"].setdefault(t, {})) for t in targets] if targets else [(None, entry)]
    rows = []
    for target, slot in slots:
        old = _stored(slot.get("through"))
        if old is not None and new < old:
            rows.append({"key": _key(surface, target), "moved": False, "through": stamp(old),
                         "detail": f"refused: {human(new)} is behind the recorded {human(old)}"})
            continue
        slot.update(through=stamp(new), updated_at=stamp(moment))
        data["deferrals"].pop(_key(surface, target), None)  # a write spends the deferral
        rows.append({"key": _key(surface, target), "moved": True, "through": stamp(new), "detail": "advanced"})
    save(workspace, data, home)
    return {"surface": surface, "through": stamp(new), "entries": rows, "moved": all(r["moved"] for r in rows)}


def defer(workspace: str, surface: str, reason: str, target: str | None = None,
          now: datetime | None = None, home: Path | None = None) -> dict:
    if not reason.strip():
        raise ValueError("a deferral requires a reason")
    moment = now or now_local()
    data = load(workspace, home)
    data["deferrals"][_key(surface, target)] = {"reason": reason.strip(), "deferred_at": stamp(moment)}
    save(workspace, data, home)
    return {"key": _key(surface, target), "deferred_at": stamp(moment)}


def _judge(data: dict, key: str, through, moment: datetime, since, max_age) -> dict:
    deferral = data["deferrals"].get(key) or {}
    at = _stored(deferral.get("deferred_at"))
    live = at is not None and moment - at <= DEFERRAL_MAX_AGE and (since is None or at >= since)  # this run's, not an earlier one's
    fresh = through is not None and (since is None or through >= since) and (max_age is None or moment - through <= max_age)
    state = "current" if fresh else ("deferred" if live else ("missing" if through is None else "stale"))
    return {"key": key, "through": stamp(through) if through else None, "state": state,
            "blocking": state in ("missing", "stale"), "deferral_reason": deferral.get("reason") if live else None,
            "stale_deferral": bool(at and not live)}


def status(workspace: str, surfaces=(), targets: dict | None = None, *, since=None, max_age=None,
           now: datetime | None = None, home: Path | None = None) -> dict:
    moment = now or now_local()
    data = load(workspace, home)
    targets = targets or {}
    names = sorted(set(surfaces) | set(targets))
    if not names:
        raise ValueError("status requires the declared surface set: every surface with --surface and every "
                         "target with --target or --targets-from; an empty set cannot vouch for a ritual")
    bound_source = "explicit"
    if since == "run" or (since is None and max_age is None):
        since, bound_source = _stored((data.get("run") or {}).get("started_at")), "run"
        if since is None:
            raise ValueError("status needs a freshness bound: --since run (after `begin`), --since <moment>, "
                             "or --max-age <duration>")
    rows, blocking = [], []
    for surface in names:
        surface_row = _judge(data, surface, _stored(_entry(data, surface).get("through")), moment, since, max_age)
        target_rows = [_judge(data, _key(surface, t), _stored(_entry(data, surface, t).get("through")),
                              moment, since, max_age) for t in targets.get(surface, [])]
        if target_rows and surface_row["state"] != "deferred":
            blocked = [t["key"] for t in target_rows if t["blocking"]]
            throughs = [t["through"] for t in target_rows]
            surface_row.update(state="stale" if blocked else "current", blocking=bool(blocked),
                               through=min(throughs) if all(throughs) else None)
            blocking += blocked
        elif surface_row["blocking"]:
            blocking.append(surface)
        rows.append({**surface_row, "targets": [dict(t, state="deferred", blocking=False) for t in target_rows] if surface_row["state"] == "deferred" else target_rows})
    return {"workspace": workspace, "as_of": stamp(moment), "since": stamp(since) if since else None,
            "bound_source": bound_source, "surfaces": rows, "blocking": blocking}


def parse_targets(entries, path: str | None) -> dict:
    pairs = [e.split(":", 1) if ":" in e else [e, ""] for e in entries or []]
    if path:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        if isinstance(payload, dict) and all(isinstance(v, list) for v in payload.values()):
            pairs += [[s, str(t)] for s, ids in payload.items() for t in ids]
        elif isinstance(payload, list) and all(isinstance(e, str) for e in payload):
            pairs += [e.split(":", 1) if ":" in e else [e, ""] for e in payload]
        else:
            raise ValueError('--targets-from expects {"surface": ["id", ...]} or ["surface:id", ...]')
    declared: dict = {}
    for surface, target in pairs:
        if not surface.strip() or not target.strip():
            raise ValueError(f"a target needs the form surface:id, got {surface}:{target}")
        declared.setdefault(surface.strip(), [])
        if target.strip() not in declared[surface.strip()]:
            declared[surface.strip()].append(target.strip())
    return declared


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    moment_help = "ISO-8601, YYYY-MM-DD (END of that day), epoch seconds as `window` prints them or Slack's ts, or now"
    for name in ("begin", "window", "advance", "defer", "status"):
        p = sub.add_parser(name)
        p.add_argument("--workspace", required=True)
        p.add_argument("--json", action="store_true")
        if name == "begin":
            p.add_argument("--label", default="")
        if name in ("window", "advance", "defer"):
            p.add_argument("--surface", required=True)
        if name in ("window", "defer"):
            p.add_argument("--target")
        if name == "advance":
            p.add_argument("--through", required=True, help=moment_help)
            p.add_argument("--target", action="append", default=[])
            p.add_argument("--surface-level", action="store_true")
        if name == "defer":
            p.add_argument("--reason", required=True)
        if name == "status":
            p.add_argument("--surface", action="append", default=[])
            p.add_argument("--target", action="append", default=[], help="surface:id, repeatable")
            p.add_argument("--targets-from", help='JSON: {"surface": ["id"]} or ["surface:id"]')
            p.add_argument("--since", help=moment_help + ", or run (the last begin)")
            p.add_argument("--max-age", help="90m, 4h, 1d")
    args = parser.parse_args(argv)
    try:
        if args.command == "begin":
            result = begin(args.workspace, args.label)
        elif args.command == "window":
            result = window(args.workspace, args.surface, args.target)
        elif args.command == "advance":
            result = advance(args.workspace, args.surface, args.through, tuple(args.target),
                             surface_level=args.surface_level)
        elif args.command == "defer":
            result = defer(args.workspace, args.surface, args.reason, args.target)
        else:
            moment = now_local()
            since = None if not args.since else ("run" if args.since.strip() == "run" else parse_moment(args.since, moment))
            result = status(args.workspace, args.surface, parse_targets(args.target, args.targets_from), since=since,
                            max_age=parse_duration(args.max_age) if args.max_age else None, now=moment)
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    if args.json or args.command in ("advance", "defer"):
        print(json.dumps(result, indent=2))
    elif args.command == "begin":
        print(f"run started {result['human']}" + (f" ({result['label']})" if result["label"] else ""))
    elif args.command == "window":
        print(result["human"])
        print(f"oldest={result['oldest']} latest={result['latest']}" if result["oldest"] else f"latest={result['latest']}")
    else:
        for row in result["surfaces"]:
            for item in [row] + [t for t in row["targets"] if t["state"] != "current"]:
                note = (f" ({item['deferral_reason']})" if item["deferral_reason"]
                        else " (deferral expired)" if item["stale_deferral"] else "")
                print(f"  {'BLOCKING' if item['blocking'] else item['state']:9} {item['key']:30} "
                      f"through {item['through'] or 'never'}{note}")
        if result["blocking"]:
            print(f"{len(result['blocking'])} not re-read this run: {', '.join(result['blocking'])}. Read each now, "
                  "or record a reason with `defer`. A gap in prose is not a closed gap.")
    return 1 if args.command == "status" and result["blocking"] else (2 if args.command == "advance" and not result["moved"] else 0)


if __name__ == "__main__":
    sys.exit(main())
