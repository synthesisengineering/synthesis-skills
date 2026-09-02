#!/usr/bin/env python3
"""Per-surface, per-target sync watermarks: the last MOMENT actually written.

A sync window anchored on when the previous run executed cannot see its own
holes, and a watermark that only knows the DAY cannot see the hours: a
surface written at 09:15 counted as current for the rest of the day, so a
mid-day pass that re-read only what the morning had skipped let the morning's
own reads go stale while the agent kept speaking from them. The repair is
structural rather than diligent:

* a watermark is an ISO-8601 timestamp — the last moment actually WRITTEN,
  never the last attempted — so a window starts exactly where the mirror
  stops, and `window` prints the bounds a human can check beside the epoch
  `oldest` a read call takes (a window parameter is a claim about time and
  is computed here, not typed);
* a surface may carry one watermark per declared read target (a Slack
  channel, a DM), so "20 of 60 targets read" is a list of forty keys and not
  a sentence in a report;
* `begin` stamps a run, and `status --since run` blocks on every declared
  surface or target that this run did not re-read — "already read today" is
  a statement about the past, and the gate says so mechanically;
* the watermark advances only after a successful write, so a run that
  fetches nothing, errors, or is interrupted cannot declare coverage;
* a gap that genuinely cannot close is deferred WITH A REASON for one day,
  and a stale deferral is re-surfaced rather than silently honored.

    sync_watermark.py begin    --workspace W [--label L]
    sync_watermark.py window   --workspace W --surface S [--target T]
    sync_watermark.py advance  --workspace W --surface S --through TS [--target T ...]
    sync_watermark.py defer    --workspace W --surface S [--target T] --reason TEXT
    sync_watermark.py status   --workspace W --surface S ... [--target S:T ...]
                               [--targets-from FILE] [--since TS|run] [--max-age 4h]

TS is an ISO-8601 timestamp (naive means local time), the word `now`, or a
bare YYYY-MM-DD meaning complete through the END of that day — which is
refused when that end lies in the future, so a mid-day run cannot stamp
"today" and must record the moment it actually read.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

STORE_DIRNAME = "sync-watermarks"
STORE_SCHEMA = 2
# A deferral silences a gap for one working day, never indefinitely: an
# indefinite silence is how a gap becomes furniture.
DEFERRAL_MAX_AGE = timedelta(days=1)
_DURATION_PART = re.compile(r"(\d+)\s*([dhm])")
_DURATION_UNITS = {
    "d": timedelta(days=1),
    "h": timedelta(hours=1),
    "m": timedelta(minutes=1),
}


# --- time -------------------------------------------------------------------


def now_local() -> datetime:
    return datetime.now().astimezone().replace(microsecond=0)


def _localize(moment: datetime, reference: datetime) -> datetime:
    if moment.tzinfo is None:
        return moment.replace(tzinfo=reference.tzinfo)
    return moment


def parse_moment(text: str, now: datetime) -> datetime:
    """`now`, an ISO-8601 timestamp (naive = local), or a date = END of that day."""
    raw = str(text).strip()
    if raw.lower() == "now":
        return now
    if len(raw) == 10:
        try:
            day = date.fromisoformat(raw)
        except ValueError:
            day = None
        if day is not None:
            end = datetime.combine(day + timedelta(days=1), datetime.min.time())
            return _localize(end, now)
    try:
        moment = datetime.fromisoformat(raw)
    except ValueError as exc:
        raise ValueError(
            f"not a timestamp: {text!r} (use ISO-8601, YYYY-MM-DD, or 'now')"
        ) from exc
    return _localize(moment, now).replace(microsecond=0)


def parse_duration(text: str) -> timedelta:
    compact = re.sub(r"\s+", "", str(text).strip().lower())
    parts = _DURATION_PART.findall(compact)
    if not parts or "".join(f"{n}{u}" for n, u in parts) != compact:
        raise ValueError(f"not a duration: {text!r} (use forms like 90m, 4h, 1d12h)")
    return sum((int(n) * _DURATION_UNITS[u] for n, u in parts), timedelta())


def stamp(moment: datetime) -> str:
    return moment.isoformat(timespec="seconds")


def human(moment: datetime) -> str:
    # Stored offsets parse as fixed-offset zones whose %Z reads "UTC-04:00";
    # render in the machine's local zone so the label is the familiar one.
    return moment.astimezone().strftime("%a %Y-%m-%d %H:%M %Z")


def span(delta: timedelta) -> str:
    total = int(delta.total_seconds())
    sign = "-" if total < 0 else ""
    total = abs(total)
    days, rest = divmod(total, 86400)
    hours, rest = divmod(rest, 3600)
    minutes = rest // 60
    parts = []
    if days:
        parts.append(f"{days}d")
    if hours:
        parts.append(f"{hours}h")
    if minutes or not parts:
        parts.append(f"{minutes}m")
    return sign + " ".join(parts)


def _stored(value) -> datetime | None:
    try:
        return datetime.fromisoformat(str(value))
    except (TypeError, ValueError):
        return None


# --- store --------------------------------------------------------------------


def store_path(workspace: str, home: Path | None = None) -> Path:
    root = home or Path(
        os.environ.get("SYNTHESIS_HOME", str(Path.home() / ".synthesis"))
    )
    safe = "".join(c for c in workspace if c.isalnum() or c in "-_") or "default"
    return root / STORE_DIRNAME / f"{safe}.json"


def _fresh() -> dict:
    return {"schema": STORE_SCHEMA, "run": None, "surfaces": {}, "deferrals": {}}


def _migrate(data: dict, reference: datetime) -> dict:
    """Read a schema-1 store as what it meant: a bare date is complete through
    the END of that day, and a deferral dated to a day started at its midnight."""
    data.setdefault("surfaces", {})
    data.setdefault("deferrals", {})
    data.setdefault("run", None)
    for entry in data["surfaces"].values():
        entry.setdefault("targets", {})
        through = entry.get("through")
        if isinstance(through, str) and len(through) == 10:
            # A schema-1 date meant "that day is written" and was recorded
            # when the write happened. A mirror cannot be complete past the
            # moment it was written, so the earlier of end-of-day and the
            # recorded write time is the honest watermark — and never a
            # moment in the future, which a mid-day "through today" would be.
            end_of_day = parse_moment(through, reference)
            written = _stored(entry.get("updated_at"))
            candidates = [end_of_day, reference]
            if written is not None:
                candidates.append(_localize(written, reference))
            entry["through"] = stamp(min(candidates))
            entry["migrated_from"] = through
    for deferral in data["deferrals"].values():
        if "deferred_at" not in deferral and deferral.get("deferred_on"):
            day = date.fromisoformat(str(deferral["deferred_on"]))
            midnight = datetime.combine(day, datetime.min.time())
            deferral["deferred_at"] = stamp(_localize(midnight, reference))
    data["schema"] = STORE_SCHEMA
    return data


def load(workspace: str, home: Path | None = None, reference: datetime | None = None) -> dict:
    path = store_path(workspace, home)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return _fresh()
    if not isinstance(data, dict):
        return _fresh()
    return _migrate(data, reference or now_local())


def save(workspace: str, data: dict, home: Path | None = None) -> None:
    path = store_path(workspace, home)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp.replace(path)


def _entry(data: dict, surface: str, target: str | None = None) -> dict:
    surface_entry = data["surfaces"].get(surface) or {}
    if target is None:
        return surface_entry
    return (surface_entry.get("targets") or {}).get(target) or {}


def _through(data: dict, surface: str, target: str | None = None) -> datetime | None:
    return _stored(_entry(data, surface, target).get("through"))


def _key(surface: str, target: str | None = None) -> str:
    return surface if target is None else f"{surface}:{target}"


# --- verbs ----------------------------------------------------------------------


def begin(
    workspace: str, label: str = "", now: datetime | None = None, home: Path | None = None
) -> dict:
    """Stamp the run so `status --since run` can ask what THIS run re-read."""
    moment = now or now_local()
    data = load(workspace, home, moment)
    data["run"] = {"started_at": stamp(moment), "label": label.strip()}
    save(workspace, data, home)
    return {"workspace": workspace, "started_at": stamp(moment), "label": label.strip(),
            "human": human(moment)}


def window(
    workspace: str,
    surface: str,
    target: str | None = None,
    now: datetime | None = None,
    home: Path | None = None,
) -> dict:
    """The range this run must cover for one surface or one read target."""
    moment = now or now_local()
    data = load(workspace, home, moment)
    label = surface if target is None else f"{surface} (target {target})"
    source = "surface" if target is None else "target"
    through = _through(data, surface, target)
    if target is not None and through is None and _through(data, surface) is not None:
        through = _through(data, surface)
        source = "surface watermark (this target has never been read on its own)"
    result = {
        "surface": surface,
        "target": target,
        "to": stamp(moment),
        "to_epoch": int(moment.timestamp()),
    }
    if through is None:
        result.update(
            bootstrap=True, source=None, **{"from": None}, from_epoch=None,
            span=None, age=None,
            human=(f"{label}: no watermark yet → read to the workspace's backfill "
                   f"bound and state that bound; latest {human(moment)}"),
            detail=("no watermark yet — this surface has never recorded a "
                    "successful write, so the window cannot be narrowed"),
        )
        return result
    elapsed = moment - through
    result.update(
        bootstrap=False, source=source, **{"from": stamp(through)},
        from_epoch=int(through.timestamp()), span=span(elapsed), age=span(elapsed),
        human=f"{label}: {human(through)} → {human(moment)} ({span(elapsed)})",
        detail=f"mirror complete through {human(through)} ({span(elapsed)} ago)",
    )
    return result


def advance(
    workspace: str,
    surface: str,
    through: str,
    targets: tuple[str, ...] | list[str] = (),
    now: datetime | None = None,
    home: Path | None = None,
    surface_level: bool = False,
) -> dict:
    """Record a successful write. Never moves a watermark backwards or into
    the future; with targets, records each target's own read."""
    moment = now or now_local()
    new = parse_moment(through, moment)
    if new > moment:
        hint = ""
        if len(str(through).strip()) == 10:
            hint = (" — a bare date means complete through the END of that day; "
                    "pass the moment you actually read (an ISO timestamp or 'now')")
        raise ValueError(
            f"refusing a future watermark: {through} resolves to {human(new)}, "
            f"ahead of {human(moment)}{hint}"
        )
    data = load(workspace, home, moment)
    surface_entry = data["surfaces"].setdefault(surface, {})
    surface_entry.setdefault("targets", {})
    entries: list[dict] = []
    if targets:
        slots = [(t, surface_entry["targets"].setdefault(t, {})) for t in targets]
    else:
        if surface_entry.get("targets") and not surface_level:
            # 2026-09-01: a surface-level advance on the Chat surface recorded
            # coverage that no per-space read backed, and four DMs went
            # unsurfaced. Once a surface carries per-target watermarks, a
            # wholesale advance is a claim without evidence — refuse it.
            raise ValueError(
                f"{surface} carries per-target watermarks "
                f"({len(surface_entry['targets'])} target(s)); a surface-level advance would "
                "claim coverage no target read backs — advance the targets you read, or pass "
                "--surface-level to assert whole-surface coverage explicitly"
            )
        slots = [(None, surface_entry)]
    for target, entry in slots:
        key = _key(surface, target)
        old = _stored(entry.get("through"))
        if old is not None and new < old:
            entries.append({"key": key, "through": stamp(old), "moved": False,
                            "detail": f"refused: {human(new)} is behind the recorded {human(old)}"})
            continue
        entry["through"] = stamp(new)
        entry["updated_at"] = stamp(moment)
        entry.pop("migrated_from", None)
        # An entry that just wrote has no outstanding gap, so its deferral is spent.
        data["deferrals"].pop(key, None)
        entries.append({"key": key, "through": stamp(new), "moved": True,
                        "detail": "watermark advanced"})
    save(workspace, data, home)
    return {"surface": surface, "through": stamp(new), "human": human(new),
            "entries": entries, "moved": all(e["moved"] for e in entries)}


def defer(
    workspace: str,
    surface: str,
    reason: str,
    target: str | None = None,
    now: datetime | None = None,
    home: Path | None = None,
) -> dict:
    if not reason.strip():
        raise ValueError("a deferral requires a reason")
    moment = now or now_local()
    data = load(workspace, home, moment)
    key = _key(surface, target)
    data["deferrals"][key] = {"reason": reason.strip(), "deferred_at": stamp(moment)}
    save(workspace, data, home)
    return {"key": key, "deferred_at": stamp(moment)}


def _judge(
    data: dict,
    key: str,
    through: datetime | None,
    moment: datetime,
    since: datetime | None,
    max_age: timedelta | None,
) -> dict:
    deferral = data["deferrals"].get(key) or {}
    deferred_at = _stored(deferral.get("deferred_at"))
    live = deferred_at is not None and (moment - deferred_at) <= DEFERRAL_MAX_AGE
    if through is None:
        state = "missing"
    elif since is not None and through < since:
        state = "stale"
    elif max_age is not None and (moment - through) > max_age:
        state = "stale"
    else:
        state = "current"
    return {
        "key": key,
        "through": stamp(through) if through else None,
        "age": span(moment - through) if through else None,
        "state": "deferred" if (state != "current" and live) else state,
        "blocking": state != "current" and not live,
        "deferral_reason": deferral.get("reason") if live else None,
        "stale_deferral": bool(deferred_at and not live),
    }


def status(
    workspace: str,
    surfaces: list[str] | None = None,
    targets: dict[str, list[str]] | None = None,
    *,
    since: datetime | None = None,
    max_age: timedelta | None = None,
    now: datetime | None = None,
    home: Path | None = None,
) -> dict:
    """Which declared surfaces and targets are current under one freshness
    bound: `since` (a run start, typically), `max_age`, or both."""
    moment = now or now_local()
    data = load(workspace, home, moment)
    declared_targets = {s: list(ids) for s, ids in (targets or {}).items()}
    names = sorted(set(surfaces or []) | set(declared_targets))
    if not names:
        raise ValueError(
            "status requires the declared surface set — pass every declared "
            "surface with --surface (repeatable) or targets with --target / "
            "--targets-from; an empty set cannot authorize a ritual"
        )
    bound_source = None
    if since == "run" or (since is None and max_age is None):
        run = data.get("run") or {}
        started = _stored(run.get("started_at"))
        if started is None:
            raise ValueError(
                "status needs a freshness bound: --since run (after `begin`), "
                "--since <timestamp>, or --max-age <duration>"
            )
        since, bound_source = started, "run"
    rows, blocking = [], []
    for surface in names:
        declared = declared_targets.get(surface) or []
        if declared:
            target_rows = []
            for target in declared:
                row = _judge(data, _key(surface, target), _through(data, surface, target),
                             moment, since, max_age)
                row["target"] = target
                target_rows.append(row)
            throughs = [_through(data, surface, t) for t in declared]
            effective = min(throughs) if all(throughs) else None
            row = _judge(data, surface, effective, moment, since, max_age)
            surface_deferred = row["state"] == "deferred"
            blocked = [] if surface_deferred else [t["key"] for t in target_rows if t["blocking"]]
            row["blocking"] = bool(blocked)
            if not blocked and not surface_deferred:
                row["state"] = "current"
            blocking.extend(blocked)
        else:
            target_rows = []
            row = _judge(data, surface, _through(data, surface), moment, since, max_age)
            if row["blocking"]:
                blocking.append(surface)
        row["surface"] = surface
        row["targets"] = target_rows
        rows.append(row)
    return {
        "workspace": workspace,
        "as_of": stamp(moment),
        "since": stamp(since) if since else None,
        "max_age": span(max_age) if max_age else None,
        "bound_source": bound_source or ("explicit" if (since or max_age) else None),
        "surfaces": rows,
        "blocking": blocking,
    }


# --- CLI ---------------------------------------------------------------------------


def _parse_targets(entries: list[str], path: str | None) -> dict[str, list[str]]:
    declared: dict[str, list[str]] = {}

    def add(surface: str, target: str) -> None:
        surface, target = surface.strip(), target.strip()
        if not surface or not target:
            raise ValueError("a target needs the form surface:id")
        declared.setdefault(surface, [])
        if target not in declared[surface]:
            declared[surface].append(target)

    for entry in entries or []:
        if ":" not in entry:
            raise ValueError(f"--target needs the form surface:id, got {entry!r}")
        add(*entry.split(":", 1))
    if path:
        try:
            payload = json.loads(Path(path).read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise ValueError(f"--targets-from {path}: {exc}") from exc
        if isinstance(payload, dict):
            for surface, ids in payload.items():
                if not isinstance(ids, list):
                    raise ValueError(f"--targets-from: {surface} must map to a list of ids")
                for target in ids:
                    add(surface, str(target))
        elif isinstance(payload, list):
            for entry in payload:
                if not isinstance(entry, str) or ":" not in entry:
                    raise ValueError("--targets-from: list entries need the form surface:id")
                add(*entry.split(":", 1))
        else:
            raise ValueError("--targets-from: expected {surface: [ids]} or [\"surface:id\"]")
    return declared


def _print_status(result: dict) -> None:
    bound = result["since"] and f"since {human(datetime.fromisoformat(result['since']))}"
    if result["max_age"]:
        bound = ((bound + ", ") if bound else "") + f"max age {result['max_age']}"
    print(f"as of {human(datetime.fromisoformat(result['as_of']))} — bound: {bound}"
          + (f" ({result['bound_source']})" if result["bound_source"] == "run" else ""))
    for row in result["surfaces"]:
        _print_row(row, row["surface"])
        for target in row["targets"]:
            if target["state"] != "current":
                _print_row(target, "  " + target["key"])
    if result["blocking"]:
        print(
            f"\n{len(result['blocking'])} entr{'y' if len(result['blocking']) == 1 else 'ies'} "
            "with an unclosed gap: " + ", ".join(result["blocking"])
            + "\nRead them this run, or record an explicit reason with "
            "`sync_watermark.py defer`. A gap in prose is not a closed gap."
        )


def _print_row(row: dict, label: str) -> None:
    state = "BLOCKING" if row["blocking"] else row["state"]
    if row["through"]:
        through = f"through {human(datetime.fromisoformat(row['through']))} ({row['age']} ago)"
    else:
        through = "never written"
    extra = f" — {row['deferral_reason']}" if row["deferral_reason"] else ""
    if row["stale_deferral"]:
        extra += " — deferral expired"
    print(f"  {state:9s} {label:28s} {through}{extra}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("begin", "window", "advance", "defer", "status"):
        p = sub.add_parser(name)
        p.add_argument("--workspace", required=True)
        p.add_argument("--json", action="store_true")
        if name == "begin":
            p.add_argument("--label", default="")
        if name in ("window", "advance", "defer"):
            p.add_argument("--surface", required=True)
        if name == "window" or name == "defer":
            p.add_argument("--target")
        if name == "advance":
            p.add_argument("--through", required=True)
            p.add_argument("--target", action="append", default=[])
            p.add_argument("--surface-level", action="store_true",
                           help="assert whole-surface coverage on a surface that carries targets")
        if name == "defer":
            p.add_argument("--reason", required=True)
        if name == "status":
            p.add_argument("--surface", action="append", default=[])
            p.add_argument("--target", action="append", default=[],
                           help="declared read target as surface:id (repeatable)")
            p.add_argument("--targets-from",
                           help='JSON file: {"surface": ["id", ...]} or ["surface:id", ...]')
            p.add_argument("--since", help="ISO timestamp, or `run` for the last `begin`")
            p.add_argument("--max-age", help="duration such as 90m, 4h, 1d")
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
            declared = _parse_targets(args.target, args.targets_from)
            moment = now_local()
            since = None
            if args.since:
                since = ("run" if args.since.strip().lower() == "run"
                         else parse_moment(args.since, moment))
            max_age = parse_duration(args.max_age) if args.max_age else None
            result = status(args.workspace, args.surface, declared, since=since,
                            max_age=max_age, now=moment)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    if getattr(args, "json", False):
        print(json.dumps(result, indent=2))
    elif args.command == "status":
        _print_status(result)
    elif args.command == "window":
        print(result["human"])
        if result["bootstrap"]:
            print(f"latest={result['to_epoch']}  ({result['detail']})")
        else:
            print(f"oldest={result['from_epoch']} latest={result['to_epoch']}")
    elif args.command == "begin":
        print(f"run started {result['human']}" + (f" ({result['label']})" if result["label"] else ""))
    else:
        print(json.dumps(result, indent=2))

    if args.command == "status" and result["blocking"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
