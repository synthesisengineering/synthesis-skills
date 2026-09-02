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
and none can overwrite another. Nothing is ever rewritten in place.

The legacy file also stored windows as prose ("end of its own day",
"2026-09-02 11:30-13:00 EDT"), which is why automatic expiry was aspirational:
nothing could compute it. Windows here are ISO-8601 with an offset, so expiry
is a calculation rather than a request that someone interpret a sentence.

`--state-dir DIR` (or HOLDS_STATE_DIR) points every command at an alternate
root, so tests and a second machine never touch the live ledger.

Commands:
  record place|release|amend   append one event
  query current|all|releasable|expired|for-date
  is-releasable <id>          the invariant, answered mechanically (exit 0/1)
  migrate                     import the legacy holds-ledger.json
  doctor                      integrity checks
  test                        self-test
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

MAX_RECORD_BYTES = 2048          # comfortably under PIPE_BUF (4096)
FREE_TEXT_FIELDS = ("purpose", "reason", "note")
EVENTS = ("place", "release", "amend")


# ---------------------------------------------------------------- location

def root() -> Path:
    return Path(os.environ.get(
        "HOLDS_STATE_DIR", str(Path.home() / ".synthesis" / "chief-of-staff")))


def log_path() -> Path:
    return root() / "holds" / "events.jsonl"


def legacy_path() -> Path:
    return root() / "holds-ledger.json"


# ---------------------------------------------------------------- writing

def _fit(rec: dict) -> dict:
    """Trim free text until the record fits the atomic-append bound.

    Structured fields are never touched: they carry the invariant. Losing the
    tail of a purpose costs some context; refusing the write would lose the
    fact that a hold exists at all, which is the failure this file prevents.
    """
    rec = dict(rec)
    for field in FREE_TEXT_FIELDS:
        while (len(json.dumps(rec, separators=(",", ":"), sort_keys=True)
                   .encode()) + 1 > MAX_RECORD_BYTES
               and isinstance(rec.get(field), str) and len(rec[field]) > 40):
            keep = max(40, int(len(rec[field]) * 0.8))
            rec[field] = rec[field][:keep].rstrip() + " …[trimmed]"
    return rec


def append_event(rec: dict) -> dict:
    """Single O_APPEND write, size-capped so the append is atomic."""
    rec = _fit(rec)
    payload = json.dumps(rec, separators=(",", ":"), sort_keys=True) + "\n"
    blob = payload.encode("utf-8")
    if len(blob) > MAX_RECORD_BYTES:
        raise SystemExit(
            f"holds_state: record is {len(blob)}B, over the {MAX_RECORD_BYTES}B "
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


def tighten(p: Path, want: int = 0o600) -> bool:
    """Keep the ledger private. Returns True when it had to change something.

    Hold purposes name meetings, colleagues and clients. The predecessor file
    was 0600; a store that widens that while replacing it trades one defect
    for a quieter one. The mode is enforced on every write rather than only at
    creation, because the file outlives the umask that made it.
    """
    try:
        cur = os.stat(p).st_mode & 0o777
        if cur != want:
            os.chmod(p, want)
            return True
    except OSError:
        pass
    return False


def load_events() -> list[dict]:
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


def derive(events: list[dict]) -> dict[str, dict]:
    """Replay the log into per-id hold state. The log is the truth."""
    holds: dict[str, dict] = {}
    for rec in events:
        hid = rec.get("id")
        if not hid:
            continue
        kind = rec["event"]
        if kind == "place":
            holds[hid] = {k: v for k, v in rec.items() if k != "event"}
            holds[hid]["released"] = None
        elif kind == "amend":
            if hid in holds:
                for k, v in rec.items():
                    if k not in ("event", "id", "ts", "by"):
                        holds[hid][k] = v
                holds[hid].setdefault("amended", []).append(rec.get("ts"))
        elif kind == "release":
            if hid in holds:
                holds[hid]["released"] = {
                    "ts": rec.get("ts"), "by": rec.get("by"),
                    "reason": rec.get("reason")}
            else:
                # A release with no matching place: record it so the doctor
                # can surface it rather than letting it vanish silently.
                holds[hid] = {"id": hid, "orphan_release": True,
                              "released": {"ts": rec.get("ts"),
                                           "by": rec.get("by"),
                                           "reason": rec.get("reason")}}
    return holds


def is_expired(h: dict, as_of: date) -> bool:
    exp = h.get("expires")
    if exp in (None, "", "none"):
        return False                      # standing hold
    if exp == "end-of-day":
        end = _parse_dt(h.get("end"))
        if end is None:
            return False                  # unparsed window cannot expire
        return end.date() < as_of
    try:
        return date.fromisoformat(exp) < as_of
    except (TypeError, ValueError):
        return False


def current(events, as_of: date) -> list[dict]:
    return [h for h in derive(events).values()
            if not h.get("released") and not h.get("orphan_release")
            and not is_expired(h, as_of)]


def expired(events, as_of: date) -> list[dict]:
    return [h for h in derive(events).values()
            if not h.get("released") and not h.get("orphan_release")
            and is_expired(h, as_of)]


def releasable(events) -> list[dict]:
    """Agent-placed and not already released. Expiry does not gate this:
    an expired hold is exactly the one that most needs clearing."""
    return [h for h in derive(events).values()
            if not h.get("released") and not h.get("orphan_release")]


# ---------------------------------------------------------------- migration

def _parse_legacy_window(w: str):
    """Return (start, end) ISO strings, or (None, None) when unparsable.

    Deliberately narrow. A window this cannot read keeps its prose and is
    flagged; inventing a start time for a calendar hold would be worse than
    admitting the record is unstructured.
    """
    if not isinstance(w, str):
        return None, None
    parts = w.strip().split()
    if len(parts) < 2:
        return None, None
    day, span = parts[0], parts[1]
    offsets = {"EDT": "-04:00", "EST": "-05:00",
               "PDT": "-07:00", "PST": "-08:00", "UTC": "+00:00"}
    off = offsets.get(parts[2].upper()) if len(parts) > 2 else None
    if off is None or "-" not in span:
        return None, None
    try:
        date.fromisoformat(day)
        a, b = span.split("-", 1)
        datetime.strptime(a, "%H:%M")
        datetime.strptime(b, "%H:%M")
    except ValueError:
        return None, None
    return f"{day}T{a}:00{off}", f"{day}T{b}:00{off}"


def migrate(dry_run: bool = False) -> list[dict]:
    lp = legacy_path()
    if not lp.exists():
        print(f"holds_state: no legacy ledger at {lp}; nothing to migrate.")
        return []
    legacy = json.loads(lp.read_text(encoding="utf-8"))
    seen = {e.get("id") for e in load_events() if e.get("event") == "place"}
    out = []
    for h in legacy.get("holds", []):
        hid = h.get("id")
        if not hid or hid in seen:
            continue
        start, end = _parse_legacy_window(h.get("window", ""))
        exp = h.get("expires") or ""
        if "none" in exp.lower():
            expires = "none"
        elif "end" in exp.lower():
            expires = "end-of-day"
        else:
            expires = "end-of-day"
        place = {"event": "place", "id": hid,
                 "ts": h.get("created") or h.get("recorded") or "",
                 "by": h.get("created_by") or "unrecorded",
                 "calendar": h.get("calendar") or "",
                 "title": h.get("title") or "",
                 "kind": h.get("kind") or "",
                 "expires": expires,
                 "purpose": h.get("purpose") or "",
                 "migrated_from": "holds-ledger.json v%s" % legacy.get("version")}
        if start:
            place["start"], place["end"] = start, end
        else:
            # No invented structure. The prose is preserved and flagged.
            place["legacy_window"] = h.get("window") or ""
            place["window_unparsed"] = True
        out.append(place)
        if h.get("released"):
            out.append({"event": "release", "id": hid,
                        "ts": h.get("released"),
                        "by": h.get("released_by") or "unrecorded",
                        "reason": h.get("release_reason") or ""})
    if dry_run:
        return out
    for rec in out:
        append_event(rec)
    return out


# ---------------------------------------------------------------- doctor

def run_doctor() -> int:
    bad = 0

    def report(good, label, detail=""):
        nonlocal bad
        if not good:
            bad += 1
        print("  %s %s%s" % ("ok " if good else "FAIL", label,
                             (": " + detail) if detail else ""))

    p = log_path()
    report(True, "event log", str(p) if p.exists()
           else "%s (not yet created — normal before first hold)" % p)
    events = load_events()
    holds = derive(events)
    today = date.today()

    raw = 0
    if p.exists():
        raw = len([l for l in p.read_text(encoding="utf-8").splitlines()
                   if l.strip() and not l.strip().startswith("#")])
    report(raw == len(events), "every log line parses as an event",
           "%d line(s) unreadable — a torn or hand-edited record"
           % (raw - len(events)) if raw != len(events)
           else "%d event(s)" % len(events))

    over = [e for e in events
            if len(json.dumps(e, separators=(",", ":")).encode())
            > MAX_RECORD_BYTES]
    report(not over, "every record is within the atomic-append bound",
           "%d over %dB — those appends were not atomic"
           % (len(over), MAX_RECORD_BYTES) if over
           else "<= %dB each" % MAX_RECORD_BYTES)

    orphans = [h for h in holds.values() if h.get("orphan_release")]
    report(not orphans, "no release without a matching place",
           "ids %s were released but never placed here; the agent released "
           "something it could not prove it created"
           % ", ".join(sorted(h["id"] for h in orphans)) if orphans
           else "the invariant holds")

    unparsed = [h for h in holds.values()
                if h.get("window_unparsed") and not h.get("released")]
    report(True, "window structure",
           "%d live hold(s) carry prose windows (migrated); they cannot "
           "expire automatically — %s"
           % (len(unparsed), ", ".join(sorted(h["id"] for h in unparsed)))
           if unparsed else "all live holds carry ISO windows")

    stale = expired(events, today)
    report(True, "expired-but-unreleased",
           "%d hold(s) past their day still open: %s — calendar debt, clear "
           "them" % (len(stale), ", ".join(sorted(h["id"] for h in stale)))
           if stale else "none")

    live = current(events, today)
    report(True, "live holds", "%d" % len(live))

    if p.exists():
        fmode = os.stat(p).st_mode & 0o777
        dmode = os.stat(p.parent).st_mode & 0o777
        report(fmode == 0o600 and dmode == 0o700, "ledger is private",
               "log %o, dir %o — hold purposes name meetings and people; "
               "expected 600/700 (the next append repairs this)"
               % (fmode, dmode) if (fmode != 0o600 or dmode != 0o700)
               else "600/700")

    legacy = legacy_path()
    if legacy.exists():
        try:
            n = len(json.loads(legacy.read_text(encoding="utf-8"))
                    .get("holds", []))
        except (json.JSONDecodeError, OSError):
            n = -1
        placed = {e["id"] for e in events if e.get("event") == "place"}
        try:
            ids = {h.get("id") for h in
                   json.loads(legacy.read_text(encoding="utf-8")).get("holds", [])}
        except (json.JSONDecodeError, OSError):
            ids = set()
        missing = ids - placed
        report(not missing,
               "legacy ledger fully migrated",
               "%d of %d legacy hold(s) absent from the log: %s — run migrate"
               % (len(missing), n, ", ".join(sorted(str(m) for m in missing)))
               if missing else "all %d imported" % n)
    else:
        report(True, "legacy ledger", "none present")

    print("\n  %s" % ("doctor: clean" if not bad else "doctor: %d FAILING" % bad))
    return 1 if bad else 0


# ---------------------------------------------------------------- self-test

def run_tests() -> int:
    import tempfile
    from concurrent.futures import ThreadPoolExecutor

    results = []

    def chk(good, label):
        results.append((good, label))
        print("  %s %s" % ("ok " if good else "FAIL", label))

    tmp = tempfile.mkdtemp(prefix="holds-test-")
    os.environ["HOLDS_STATE_DIR"] = tmp
    today = date(2026, 9, 2)

    def place(hid, start, end, **kw):
        rec = {"event": "place", "id": hid, "ts": "2026-09-01T09:00:00-04:00",
               "by": "seat-a", "calendar": "c", "title": "Hold",
               "kind": "same-day-shield", "expires": "end-of-day",
               "start": start, "end": end, "purpose": "p"}
        rec.update(kw)
        return append_event(rec)

    place("h1", "2026-09-02T11:30:00-04:00", "2026-09-02T13:00:00-04:00")
    place("h2", "2026-09-03T13:00:00-04:00", "2026-09-03T14:00:00-04:00")
    place("h3", "2026-09-01T09:00:00-04:00", "2026-09-01T10:00:00-04:00")

    ev = load_events()
    chk(len(current(ev, today)) == 2, "expired hold drops out of current")
    chk({h["id"] for h in expired(ev, today)} == {"h3"},
        "yesterday's hold is reported expired, not vanished")

    append_event({"event": "release", "id": "h1", "ts": "2026-09-02T10:00:00-04:00",
                  "by": "seat-b", "reason": "yielded"})
    ev = load_events()
    chk({h["id"] for h in current(ev, today)} == {"h2"}, "release removes a hold")
    chk(derive(ev)["h1"]["released"]["by"] == "seat-b", "release records who")

    # THE INVARIANT
    chk({h["id"] for h in releasable(ev)} == {"h2", "h3"},
        "releasable = agent-placed and not yet released (expiry does not gate)")
    chk("unknown-id" not in {h["id"] for h in releasable(ev)},
        "an id the agent never placed is NEVER releasable")

    append_event({"event": "amend", "id": "h2", "ts": "2026-09-02T09:00:00-04:00",
                  "by": "seat-a", "start": "2026-09-03T14:00:00-04:00",
                  "end": "2026-09-03T15:00:00-04:00"})
    ev = load_events()
    chk(derive(ev)["h2"]["start"] == "2026-09-03T14:00:00-04:00",
        "amend moves a hold without losing its identity")
    chk(derive(ev)["h2"]["purpose"] == "p", "amend preserves unamended fields")

    # standing holds never expire
    place("h4", None, None, expires="none", kind="recurring-ritual-prompt",
          legacy_window="18:15-18:30 weekdays", window_unparsed=True)
    ev = load_events()
    chk("h4" in {h["id"] for h in current(ev, date(2027, 1, 1))},
        "a standing hold never expires")

    # --- concurrency: the reason this file exists ---
    # Positive control against the old shape, so a pass below is evidence.
    legacy_file = os.path.join(tmp, "old-array.json")
    with open(legacy_file, "w") as fh:
        json.dump({"holds": []}, fh)

    def rmw(i):                      # read-modify-write, as the old file did
        try:
            with open(legacy_file) as fh:
                doc = json.load(fh)
        except (json.JSONDecodeError, OSError):
            # Another seat had the file truncated mid-write. The old shape
            # does not merely lose updates; it hands a reader a corrupt
            # ledger, and a ledger that cannot be read authorises nothing.
            doc = {"holds": [], "corrupt_read": True}
        doc["holds"].append({"id": "old%02d" % i})
        with open(legacy_file, "w") as fh:
            json.dump(doc, fh)

    seats = 12
    with ThreadPoolExecutor(max_workers=seats) as ex:
        list(ex.map(rmw, range(seats)))
    try:
        with open(legacy_file) as fh:
            kept = len(json.load(fh)["holds"])
    except (json.JSONDecodeError, OSError):
        kept = 0                      # ended corrupt: every hold unreadable
    chk(kept < seats,
        "positive control: shared-array read-modify-write loses holds (%d/%d "
        "kept)" % (kept, seats))

    before = len(load_events())
    with ThreadPoolExecutor(max_workers=seats) as ex:
        list(ex.map(lambda i: append_event(
            {"event": "place", "id": "c%02d" % i, "ts": "2026-09-02T09:00:00-04:00",
             "by": "seat-%d" % i, "calendar": "c", "title": "Hold",
             "kind": "same-day-shield", "expires": "end-of-day",
             "start": "2026-09-02T09:00:00-04:00",
             "end": "2026-09-02T10:00:00-04:00", "purpose": "x" * 200}),
            range(seats)))
    ev = load_events()
    chk(len(ev) == before + seats,
        "append-only log keeps every concurrent seat's hold (%d/%d)"
        % (len(ev) - before, seats))
    chk(len({h["id"] for h in ev if h.get("event") == "place"}
            & {"c%02d" % i for i in range(seats)}) == seats,
        "every concurrent id is present and distinct")

    over = [e for e in ev
            if len(json.dumps(e, separators=(",", ":")).encode())
            > MAX_RECORD_BYTES]
    chk(not over, "every record stayed within the atomic-append bound")

    huge = append_event({"event": "place", "id": "big",
                         "ts": "2026-09-02T09:00:00-04:00", "by": "seat",
                         "calendar": "c", "title": "Hold", "kind": "k",
                         "expires": "end-of-day",
                         "start": "2026-09-02T09:00:00-04:00",
                         "end": "2026-09-02T10:00:00-04:00",
                         "purpose": "y" * 5000})
    chk(huge["purpose"].endswith("…[trimmed]") and huge["id"] == "big",
        "an oversized purpose is trimmed, never dropping the hold itself")

    # torn line
    with open(log_path(), "a") as fh:
        fh.write('{"event":"place","id":"torn"\n')
    chk(len(load_events()) == len(ev) + 1,
        "a torn line is skipped, not guessed at")

    # window parsing
    s, e = _parse_legacy_window("2026-09-02 11:30-13:00 EDT")
    chk(s == "2026-09-02T11:30:00-04:00" and e == "2026-09-02T13:00:00-04:00",
        "legacy window parses to an ISO instant")
    chk(_parse_legacy_window("18:15-18:30 weekdays") == (None, None),
        "an unparsable window yields nothing rather than an invented time")
    chk(_parse_legacy_window("2026-09-02 11:30-13:00") == (None, None),
        "a window with no zone is not assumed to be local")

    passed = sum(1 for good, _ in results if good)
    print("\n  %d/%d passed" % (passed, len(results)))
    return 0 if passed == len(results) else 1


# ---------------------------------------------------------------- cli

def main() -> int:
    ap = argparse.ArgumentParser(
        description="Append-only holds ledger for synthesis-chief-of-staff.")
    ap.add_argument("--state-dir", default=None, metavar="DIR",
                    help="alternate root (also HOLDS_STATE_DIR)")
    sub = ap.add_subparsers(dest="cmd", required=True)

    rec = sub.add_parser("record", help="append one event")
    rec.add_argument("event", choices=EVENTS)
    rec.add_argument("--id", required=True)
    rec.add_argument("--by", required=True, help="seat/session that acted")
    rec.add_argument("--calendar", default=None)
    rec.add_argument("--title", default=None)
    rec.add_argument("--kind", default=None)
    rec.add_argument("--start", default=None, help="ISO-8601 with offset")
    rec.add_argument("--end", default=None, help="ISO-8601 with offset")
    rec.add_argument("--expires", default=None,
                     choices=["end-of-day", "none"], help="default end-of-day")
    rec.add_argument("--purpose", default=None)
    rec.add_argument("--reason", default=None, help="for release")

    q = sub.add_parser("query")
    q.add_argument("what", choices=["current", "all", "releasable", "expired",
                                    "for-date"])
    q.add_argument("--date", default=None, help="YYYY-MM-DD (default today)")
    q.add_argument("--json", action="store_true")

    isr = sub.add_parser("is-releasable",
                         help="exit 0 if the agent placed it and has not "
                              "released it; exit 1 otherwise")
    isr.add_argument("id")

    mig = sub.add_parser("migrate")
    mig.add_argument("--dry-run", action="store_true")
    sub.add_parser("doctor")
    sub.add_parser("test")

    a = ap.parse_args()
    if a.state_dir:
        os.environ["HOLDS_STATE_DIR"] = a.state_dir

    if a.cmd == "record":
        if a.event == "place" and not (a.start and a.end) :
            print("holds_state: place needs --start and --end (ISO-8601 with "
                  "offset) so the hold can expire mechanically.", file=sys.stderr)
            return 2
        if a.event == "release" and not a.reason:
            print("holds_state: release needs --reason. A hold released "
                  "without a recorded reason is indistinguishable from one "
                  "lost.", file=sys.stderr)
            return 2
        out = {"event": a.event, "id": a.id, "by": a.by,
               "ts": datetime.now().astimezone().isoformat(timespec="seconds")}
        for k in ("calendar", "title", "kind", "start", "end", "expires",
                  "purpose", "reason"):
            v = getattr(a, k)
            if v is not None:
                out[k] = v
        if a.event == "place":
            out.setdefault("expires", "end-of-day")
        written = append_event(out)
        print("recorded %s %s" % (a.event, a.id))
        if written.get("purpose", "").endswith("…[trimmed]"):
            print("  note: purpose trimmed to fit the atomic-append bound")
        return 0

    if a.cmd == "query":
        as_of = date.fromisoformat(a.date) if a.date else date.today()
        ev = load_events()
        if a.what == "current" or a.what == "for-date":
            rows = current(ev, as_of)
        elif a.what == "expired":
            rows = expired(ev, as_of)
        elif a.what == "releasable":
            rows = releasable(ev)
        else:
            rows = list(derive(ev).values())
        if a.json:
            print(json.dumps(rows, indent=2, sort_keys=True))
            return 0
        if not rows:
            print("  (none)")
            return 0
        for h in sorted(rows, key=lambda x: (x.get("start") or "", x.get("id"))):
            win = ("%s → %s" % (h.get("start"), h.get("end"))
                   if h.get("start") else h.get("legacy_window", "(no window)"))
            print("  %s  %-22s %s" % (h.get("id"), h.get("title", ""), win))
            if h.get("purpose"):
                print("      %s" % h["purpose"][:100])
        return 0

    if a.cmd == "is-releasable":
        ok = a.id in {h["id"] for h in releasable(load_events())}
        print("%s: %s" % (a.id, "releasable — this agent placed it"
                          if ok else
                          "NOT releasable — no place event for this id. Do not "
                          "touch the event; ask the principal."))
        return 0 if ok else 1

    if a.cmd == "migrate":
        out = migrate(dry_run=a.dry_run)
        print("%s %d event(s) from the legacy ledger"
              % ("would append" if a.dry_run else "appended", len(out)))
        for rec_ in out:
            print("  %-8s %s" % (rec_["event"], rec_["id"]))
        return 0

    if a.cmd == "doctor":
        return run_doctor()
    if a.cmd == "test":
        return run_tests()
    return 2


if __name__ == "__main__":
    sys.exit(main())
