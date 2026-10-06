#!/usr/bin/env python3
"""Holds ledger for synthesis-chief-of-staff — append-only event log.

THE INVARIANT this exists to protect: the agent may release or move ONLY a
hold it placed, matched by id. A calendar event that merely looks like a hold
is not releasable; absence from the ledger means ask the principal.

The predecessor was one JSON file with a `holds` array, read-modify-written by
every seat. Two seats run the principal's rituals on the same calendar — one
per workspace, sometimes more — and a read-modify-write of a shared array is a
lost update: seat A reads, seat B reads, A writes, B writes, and A's hold is
gone. That is not a race a lock could fix at the edges. It is the shape: one
slot, N writers. Both directions of loss cause real calendar errors.

  - A lost `place` record makes a real calendar event unreleasable. The agent
    finds an event it cannot prove it created, and correctly refuses to touch
    it. The hold becomes calendar debt that only the principal can clear.
  - A lost `release` record leaves a freed window looking still-held, so the
    shield defends space that is already gone.

Here the log is the only truth and state is always derived. Every event is one
O_APPEND write under PIPE_BUF, so concurrent seats interleave whole records
and none can overwrite another. Nothing is ever rewritten in place; a mistake
is repaired by appending a corrective event.

Windows are ISO-8601 with an offset, so expiry is a calculation rather than a
request that someone interpret a sentence.

A recurring hold is one calendar id for every instance, so "release" alone
cannot say which day (lesson 2026-09-03: releasing one day's instance marked
the whole series released). A release of a recurring hold must therefore name
either `--instance YYYY-MM-DD` (that day only; the series stays held) or
`--series` (every instance); with neither it is refused.

`--state-dir DIR` (or HOLDS_STATE_DIR) points every command at an alternate
root, so tests and a second machine never touch the live ledger.

Commands:
  record place|release|amend   append one event
  query current|all|releasable|expired|for-date
  is-releasable <id>          the invariant, answered mechanically (exit 0/1)
  doctor                      integrity checks
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date, datetime
from pathlib import Path

MAX_RECORD_BYTES = 2048          # comfortably under PIPE_BUF (4096)
FREE_TEXT_FIELDS = ("purpose", "reason", "note")
EVENTS = ("place", "release", "amend")


def root() -> Path:
    return Path(os.environ.get(
        "HOLDS_STATE_DIR", str(Path.home() / ".synthesis" / "chief-of-staff")))


def log_path() -> Path:
    return root() / "holds" / "events.jsonl"


# ---------------------------------------------------------------- writing

def _fit(rec: dict) -> dict:
    """Trim free text until the record fits the atomic-append bound.

    Structured fields are never touched: they carry the invariant. Losing the
    tail of a purpose costs some context; refusing the write would lose the
    fact that a hold exists at all, which is the failure this file prevents.
    """
    rec = dict(rec)
    for field in FREE_TEXT_FIELDS:
        while (len(json.dumps(rec, separators=(",", ":"), sort_keys=True).encode()) + 1 > MAX_RECORD_BYTES
               and isinstance(rec.get(field), str) and len(rec[field]) > 40):
            keep = max(40, int(len(rec[field]) * 0.8))
            rec[field] = rec[field][:keep].rstrip() + " …[trimmed]"
    return rec


def tighten(p: Path, want: int = 0o600) -> None:
    """Keep the ledger private. Hold purposes name meetings, colleagues and
    clients; the mode is enforced on every write because the file outlives the
    umask that made it."""
    try:
        if os.stat(p).st_mode & 0o777 != want:
            os.chmod(p, want)
    except OSError:
        pass


def append_event(rec: dict) -> dict:
    """Single O_APPEND write, size-capped so the append is atomic."""
    rec = _fit(rec)
    blob = (json.dumps(rec, separators=(",", ":"), sort_keys=True) + "\n").encode("utf-8")
    if len(blob) > MAX_RECORD_BYTES:
        raise SystemExit(f"holds_state: record is {len(blob)}B, over the {MAX_RECORD_BYTES}B "
                         "cap even after trimming free text. Shorten the structured fields.")
    p = log_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(p, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
    try:
        os.write(fd, blob)          # one write, under PIPE_BUF -> atomic
    finally:
        os.close(fd)
    tighten(p)
    tighten(p.parent, 0o700)
    return rec


def load_events() -> list:
    p = log_path()
    if not p.exists():
        return []
    out = []
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue            # a torn line is skipped, never guessed at
        if isinstance(rec, dict) and rec.get("event") in EVENTS:
            out.append(rec)
    return out


# ---------------------------------------------------------------- deriving

def _parse_dt(s):
    if not isinstance(s, str) or not s:
        return None
    try:
        return datetime.fromisoformat(s)
    except ValueError:
        return None


def is_recurring(h: dict) -> bool:
    """Placed with --recurring, or (records from before that flag) a kind that says so."""
    return bool(h.get("recurring")) or "recurring" in str(h.get("kind") or "")


def derive(events: list) -> dict:
    """Replay the log into per-id hold state. The log is the truth."""
    holds: dict = {}
    for rec in events:
        hid = rec.get("id")
        if not hid:
            continue
        kind = rec["event"]
        if kind == "place":
            holds[hid] = {k: v for k, v in rec.items() if k != "event"}
            holds[hid]["released"] = None
            holds[hid]["released_instances"] = []
        elif kind == "amend":
            if hid in holds:
                for k, v in rec.items():
                    if k not in ("event", "id", "ts", "by"):
                        holds[hid][k] = v
                holds[hid].setdefault("amended", []).append(rec.get("ts"))
        elif kind == "release":
            note = {"ts": rec.get("ts"), "by": rec.get("by"), "reason": rec.get("reason")}
            if hid not in holds:
                # A release with no matching place: keep it visible for the doctor.
                holds[hid] = {"id": hid, "orphan_release": True, "released": note}
            elif rec.get("instance"):
                holds[hid]["released_instances"].append(dict(note, instance=rec["instance"]))
            else:
                holds[hid]["released"] = note
    return holds


def _live(h: dict) -> bool:
    return not h.get("released") and not h.get("orphan_release")


def is_expired(h: dict, as_of: date) -> bool:
    exp = h.get("expires")
    if exp in (None, "", "none"):
        return False                      # standing hold
    if exp == "end-of-day":
        end = _parse_dt(h.get("end"))
        return end is not None and end.date() < as_of   # an unparsed window cannot expire
    try:
        return date.fromisoformat(exp) < as_of
    except (TypeError, ValueError):
        return False


def instance_released(h: dict, day: date) -> bool:
    return any(r.get("instance") == day.isoformat() for r in h.get("released_instances", []))


def current(events, as_of: date) -> list:
    """Holds in force on `as_of`: live, unexpired, and not released for that day."""
    return [h for h in derive(events).values()
            if _live(h) and not is_expired(h, as_of) and not instance_released(h, as_of)]


def expired(events, as_of: date) -> list:
    return [h for h in derive(events).values() if _live(h) and is_expired(h, as_of)]


def releasable(events) -> list:
    """Agent-placed and not already released. Expiry does not gate this:
    an expired hold is exactly the one that most needs clearing."""
    return [h for h in derive(events).values() if _live(h)]


# ---------------------------------------------------------------- doctor

def run_doctor() -> int:
    bad = 0

    def report(good, label, detail=""):
        nonlocal bad
        bad += 0 if good else 1
        print("  %s %s%s" % ("ok " if good else "FAIL", label, (": " + detail) if detail else ""))

    p = log_path()
    report(True, "event log", str(p) if p.exists() else "%s (not yet created — normal before first hold)" % p)
    events = load_events()
    holds = derive(events)
    raw = 0
    if p.exists():
        raw = len([x for x in p.read_text(encoding="utf-8").splitlines() if x.strip() and not x.strip().startswith("#")])
    report(raw == len(events), "every log line parses as an event",
           "%d line(s) unreadable — a torn or hand-edited record" % (raw - len(events))
           if raw != len(events) else "%d event(s)" % len(events))
    over = [e for e in events if len(json.dumps(e, separators=(",", ":")).encode()) > MAX_RECORD_BYTES]
    report(not over, "every record is within the atomic-append bound",
           "%d over %dB — those appends were not atomic" % (len(over), MAX_RECORD_BYTES) if over
           else "<= %dB each" % MAX_RECORD_BYTES)
    orphans = sorted(h["id"] for h in holds.values() if h.get("orphan_release"))
    report(not orphans, "no release without a matching place",
           "ids %s were released but never placed here; the agent released something it could "
           "not prove it created" % ", ".join(orphans) if orphans else "the invariant holds")
    unparsed = sorted(h["id"] for h in holds.values() if h.get("window_unparsed") and _live(h))
    report(True, "window structure",
           "%d live hold(s) carry prose windows; they cannot expire automatically — %s"
           % (len(unparsed), ", ".join(unparsed)) if unparsed else "all live holds carry ISO windows")
    stale = sorted(h["id"] for h in expired(events, date.today()))
    report(True, "expired-but-unreleased",
           "%d hold(s) past their day still open: %s — calendar debt, clear them" % (len(stale), ", ".join(stale))
           if stale else "none")
    report(True, "live holds", "%d" % len(current(events, date.today())))
    if p.exists():
        fmode, dmode = os.stat(p).st_mode & 0o777, os.stat(p.parent).st_mode & 0o777
        report(fmode == 0o600 and dmode == 0o700, "ledger is private",
               "log %o, dir %o — hold purposes name meetings and people; expected 600/700 "
               "(the next append repairs this)" % (fmode, dmode) if (fmode, dmode) != (0o600, 0o700) else "600/700")
    print("\n  %s" % ("doctor: clean" if not bad else "doctor: %d FAILING" % bad))
    return 1 if bad else 0


# ---------------------------------------------------------------- cli

def _release_problem(a, hold) -> str:
    """Why this release must not be written, or "" when it may (lesson 2026-09-03)."""
    if not a.reason:
        return "release needs --reason. A hold released without a recorded reason is indistinguishable from one lost."
    if a.instance and a.series:
        return "pass --instance or --series, not both."
    if hold is None or not _live(hold):
        return ""  # recorded as an orphan or a repeat; the doctor reports orphans
    if is_recurring(hold) and not (a.instance or a.series):
        return (f"{a.id} is a recurring hold: one id covers every instance. Pass --instance YYYY-MM-DD "
                "to release one day (the series stays held), or --series to release all of it.")
    if a.instance and not is_recurring(hold):
        return f"{a.id} is not recurring; release it without --instance."
    if a.instance:
        try:
            date.fromisoformat(a.instance)
        except ValueError:
            return "--instance must be a date, YYYY-MM-DD."
    return ""


def _print_rows(rows) -> None:
    if not rows:
        print("  (none)")
    for h in sorted(rows, key=lambda x: (x.get("start") or "", x.get("id"))):
        win = ("%s → %s" % (h.get("start"), h.get("end")) if h.get("start")
               else h.get("legacy_window", "(no window)"))
        tag = "  [recurring]" if is_recurring(h) else ""
        print("  %s  %-22s %s%s" % (h.get("id"), h.get("title", ""), win, tag))
        if h.get("purpose"):
            print("      %s" % h["purpose"][:100])
        days = [r["instance"] for r in h.get("released_instances", [])]
        if days:
            print("      released instances: %s" % ", ".join(days))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Append-only holds ledger for synthesis-chief-of-staff.")
    ap.add_argument("--state-dir", default=None, metavar="DIR", help="alternate root (also HOLDS_STATE_DIR)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    rec = sub.add_parser("record", help="append one event")
    rec.add_argument("event", choices=EVENTS)
    rec.add_argument("--id", required=True)
    rec.add_argument("--by", required=True, help="seat/session that acted")
    for name in ("calendar", "title", "kind", "purpose"):
        rec.add_argument("--" + name, default=None)
    rec.add_argument("--start", default=None, help="ISO-8601 with offset")
    rec.add_argument("--end", default=None, help="ISO-8601 with offset")
    rec.add_argument("--expires", default=None, choices=["end-of-day", "none"], help="default end-of-day")
    rec.add_argument("--recurring", action="store_true", help="place: one id covers a recurring series")
    rec.add_argument("--reason", default=None, help="release: why")
    rec.add_argument("--instance", default=None, metavar="YYYY-MM-DD", help="release: one day of a recurring hold")
    rec.add_argument("--series", action="store_true", help="release: every instance of a recurring hold")
    q = sub.add_parser("query")
    q.add_argument("what", choices=["current", "all", "releasable", "expired", "for-date"])
    q.add_argument("--date", default=None, help="YYYY-MM-DD (default today)")
    q.add_argument("--json", action="store_true")
    isr = sub.add_parser("is-releasable", help="exit 0 if the agent placed it and has not released it; exit 1 otherwise")
    isr.add_argument("id")
    sub.add_parser("doctor")
    a = ap.parse_args(argv)
    if a.state_dir:
        os.environ["HOLDS_STATE_DIR"] = a.state_dir

    if a.cmd == "record":
        if a.event == "place" and not (a.start and a.end):
            print("holds_state: place needs --start and --end (ISO-8601 with offset) so the hold can "
                  "expire mechanically.", file=sys.stderr)
            return 2
        if a.event == "release":
            problem = _release_problem(a, derive(load_events()).get(a.id))
            if problem:
                print("holds_state: " + problem, file=sys.stderr)
                return 2
        out = {"event": a.event, "id": a.id, "by": a.by,
               "ts": datetime.now().astimezone().isoformat(timespec="seconds")}
        for k in ("calendar", "title", "kind", "start", "end", "expires", "purpose", "reason", "instance"):
            if getattr(a, k) is not None:
                out[k] = getattr(a, k)
        if a.event == "place":
            out.setdefault("expires", "end-of-day")
            if a.recurring:
                out["recurring"] = True
        written = append_event(out)
        print("recorded %s %s%s" % (a.event, a.id, " for %s only" % a.instance if a.instance else ""))
        if written.get("purpose", "").endswith("…[trimmed]"):
            print("  note: purpose trimmed to fit the atomic-append bound")
        return 0

    if a.cmd == "query":
        as_of = date.fromisoformat(a.date) if a.date else date.today()
        ev = load_events()
        rows = {"current": lambda: current(ev, as_of), "for-date": lambda: current(ev, as_of),
                "expired": lambda: expired(ev, as_of), "releasable": lambda: releasable(ev),
                "all": lambda: list(derive(ev).values())}[a.what]()
        if a.json:
            print(json.dumps(rows, indent=2, sort_keys=True))
        else:
            _print_rows(rows)
        return 0

    if a.cmd == "is-releasable":
        ok = a.id in {h["id"] for h in releasable(load_events())}
        print("%s: %s" % (a.id, "releasable — this agent placed it" if ok else
                          "NOT releasable — no place event for this id. Do not touch the event; ask the principal."))
        return 0 if ok else 1

    return run_doctor()


if __name__ == "__main__":
    sys.exit(main())
