#!/usr/bin/env python3
"""ritual_state.py — the single writer and the single reader of daily-ritual state.

THE INVARIANT
-------------
There is no mutable state file. Every view is DERIVED from one append-only log.
Nothing does read-modify-write, so concurrent seats cannot clobber one another —
not by discipline, but by construction.

WHY THIS EXISTS
---------------
The predecessor kept `~/.synthesis/day-{start,end}/state.json`, each holding a
single `last_day_*` slot, written by every workspace seat. On 2026-09-02 one
seat's close overwrote another's. A lock would NOT have prevented the loss: with
perfect serialization the second writer still replaces the one slot. The fault
was schematic — a single-writer shape with many writers — so the fix is to delete
the shape, not to guard it.

The system already had the pattern: `~/.synthesis/active-project-history/` writes
one file per writer and aggregates by scanning. This applies the same idea with
an append-only log.

TWO CLOCKS
----------
Every record carries BOTH:
  `date` — the logical workday being opened or closed (what streaks count)
  `ts`   — the wall-clock moment the record was written
A principal closes one workspace at 18:00 and may start another at 18:30; closes
are often written the next morning for the prior day. `date` is REQUIRED and never
inferred from `ts` — inferring it is how a 01:30 close lands on the wrong day.

EXERCISING THIS FROM OUTSIDE
---------------------------
`--state-dir DIR` (or the RITUAL_STATE_DIR env var) points every command at an
alternate log + config. Copy the real ones into a scratch directory and any seat
can exercise every arm of the tripwire — including the alarming arms, which
cannot be reached in production because the log is append-only. Raised by the
seat adopting this engine: the two arms that matter were self-attested, and an
escape hatch nobody can find is not an escape hatch.

APPEND ATOMICITY
----------------
POSIX guarantees atomic appends only below PIPE_BUF (typically 4096 bytes).
Records are structured data with a `pointer` to the narrative; prose lives in the
session log. MAX_RECORD_BYTES enforces the bound and fails closed above it.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

MAX_RECORD_BYTES = 2048          # comfortably under PIPE_BUF (4096)
STREAK_LOOKBACK_DAYS = 400       # bound the walk; a longer streak is not credible
OPEN_LOOKBACK_DAYS = 30          # how far back "open workdays" reports
DIRECTIONS = ("day-start", "day-end", "weekly-review")
UNKNOWN_WS = "unknown"

# ---------------------------------------------------------------- paths


def root() -> Path:
    return Path(os.environ.get("RITUAL_STATE_DIR",
                               str(Path.home() / ".synthesis" / "rituals")))


def log_path() -> Path:
    return root() / "history.jsonl"


def config_path() -> Path:
    return root() / "config.json"


LEGACY_STATE = [
    Path.home() / ".synthesis" / "day-end" / "state.json",
    Path.home() / ".synthesis" / "day-start" / "state.json",
]

# ---------------------------------------------------------------- config


DEFAULT_CONFIG = {
    "_comment": (
        "Per-workspace ritual obligation. `streak` selects the metric: "
        "'expected-days' counts an unbroken run over days the workspace is EXPECTED "
        "to close, where working on a non-expected day CREDITS the streak and never "
        "debits it; 'none' disables streaks (right for advisory seats worked "
        "occasionally, where the useful signal is quiet-time, not an unbroken chain). "
        "`weekdays` uses Python weekday numbers, Monday=0. `non_working_dates` holds "
        "company holidays and PTO — a date listed here is never expected, so its "
        "absence cannot break a streak, while a close on it still credits."
    ),
    "defaults": {"streak": "none", "weekdays": [0, 1, 2, 3, 4], "non_working_dates": []},
    "workspaces": {},
}


def load_config() -> dict:
    p = config_path()
    if not p.exists():
        return json.loads(json.dumps(DEFAULT_CONFIG))
    try:
        cfg = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit(f"ritual_state: config unreadable ({exc}) — refusing to guess")
    if not isinstance(cfg, dict) or "workspaces" not in cfg:
        raise SystemExit("ritual_state: config missing 'workspaces' — refusing to guess")
    return cfg


def ws_conf(cfg: dict, workspace: str) -> dict:
    base = dict(cfg.get("defaults") or {})
    base.update(cfg.get("workspaces", {}).get(workspace) or {})
    return base

# ---------------------------------------------------------------- log io


def read_records() -> tuple[list[dict], list[str]]:
    """Return (records, malformed_lines). Never raises on a bad line."""
    p = log_path()
    if not p.exists():
        return [], []
    records, bad = [], []
    for line in p.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            rec = json.loads(line)
            if isinstance(rec, dict) and rec.get("date") and rec.get("direction"):
                records.append(rec)
            else:
                bad.append(line[:120])
        except json.JSONDecodeError:
            bad.append(line[:120])
    return records, bad


def append_record(rec: dict) -> None:
    """Single O_APPEND write, size-capped so the append is atomic."""
    payload = json.dumps(rec, separators=(",", ":"), sort_keys=True) + "\n"
    blob = payload.encode("utf-8")
    if len(blob) > MAX_RECORD_BYTES:
        raise SystemExit(
            f"ritual_state: record is {len(blob)}B, over the {MAX_RECORD_BYTES}B cap. "
            "Records are structured data; put the narrative in the session log and "
            "reference it with --pointer."
        )
    p = log_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(p, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o644)
    try:
        os.write(fd, blob)          # one write, under PIPE_BUF -> atomic
    finally:
        os.close(fd)

# ---------------------------------------------------------------- helpers


def d(s: str) -> date:
    return date.fromisoformat(s)


def is_expected(day: date, conf: dict) -> bool:
    if day.isoformat() in set(conf.get("non_working_dates") or []):
        return False
    return day.weekday() in set(conf.get("weekdays") or [])


def closed_dates(records, workspace, direction="day-end") -> set:
    return {r["date"] for r in records
            if r.get("workspace") == workspace and r.get("direction") == direction}

# ---------------------------------------------------------------- queries


def q_last(records, workspace, direction="day-end"):
    hits = [r for r in records
            if r.get("workspace") == workspace and r.get("direction") == direction]
    return max(hits, key=lambda r: (r["date"], r.get("ts", ""))) if hits else None


def q_streak(records, cfg, workspace, today: date):
    """Unbroken run of expected days closed. A close on a non-expected day credits;
    an absence on a non-expected day is skipped, never a break."""
    conf = ws_conf(cfg, workspace)
    if conf.get("streak") != "expected-days":
        return None
    closed = closed_dates(records, workspace)
    n, day, walked = 0, today, 0
    # Today is not yet over: a close credits, an absence does not break.
    if today.isoformat() in closed:
        n += 1
    day = today - timedelta(days=1)
    while walked < STREAK_LOOKBACK_DAYS:
        iso = day.isoformat()
        if iso in closed:
            n += 1
        elif is_expected(day, conf):
            break
        day -= timedelta(days=1)
        walked += 1
    return n


def q_open(records, today: date, lookback=OPEN_LOOKBACK_DAYS):
    """(workspace, date) pairs with a day-start and no matching day-end."""
    floor = (today - timedelta(days=lookback)).isoformat()
    starts = {(r.get("workspace"), r["date"]) for r in records
              if r.get("direction") == "day-start" and r["date"] >= floor}
    ends = {(r.get("workspace"), r["date"]) for r in records
            if r.get("direction") == "day-end" and r["date"] >= floor}
    return sorted(starts - ends, key=lambda t: (t[1], str(t[0])))


def q_weekly_review(records):
    hits = [r for r in records if r.get("direction") == "weekly-review"]
    return max(hits, key=lambda r: r["date"]) if hits else None


def unknown_count(records) -> int:
    return sum(1 for r in records
               if not r.get("workspace") or r.get("workspace") == UNKNOWN_WS)


def unattributed_status(records, cfg) -> tuple[int, int | None, str]:
    """Compare unattributed records against an ACKNOWLEDGED baseline.

    Legacy records that predate per-seat stamping can never be attributed —
    guessing them would be worse than leaving them out. But a note that appears
    on every call and can never clear is noise, and noise trains a reader to
    skip the line: the same failure as a gap field nothing consumes.

    So the baseline is acknowledged once and then silent. What surfaces is
    DEVIATION: a count above baseline means something is writing unstamped
    records TODAY, which is a live defect; a count below means the log lost
    records. Either is worth interrupting for. Equality is not.
    """
    n = unknown_count(records)
    base = cfg.get("legacy_unattributed_baseline")
    if not isinstance(base, int):
        return n, None, "unacknowledged"
    if n == base:
        return n, base, "baseline"
    return n, base, "above" if n > base else "below"

# ---------------------------------------------------------------- commands


def cmd_record(a) -> int:
    try:
        d(a.date)
    except ValueError:
        raise SystemExit(f"ritual_state: --date {a.date!r} is not YYYY-MM-DD. "
                         "The logical workday is required and never inferred.")
    if a.direction not in DIRECTIONS:
        raise SystemExit(f"ritual_state: --direction must be one of {DIRECTIONS}")
    rec = {
        "ts": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
        "date": a.date,
        "direction": a.direction,
        "workspace": a.workspace,
        "mode": a.mode,
        "outcome": a.outcome,
    }
    if a.session:
        rec["session"] = a.session
    if a.pointer:
        rec["pointer"] = a.pointer
    if a.note:
        rec["note"] = a.note
    counts = {}
    for kv in a.count or []:
        k, _, v = kv.partition("=")
        if not _:
            raise SystemExit(f"ritual_state: --count expects k=v, got {kv!r}")
        counts[k] = int(v) if v.lstrip("-").isdigit() else v
    if counts:
        rec["counts"] = counts
    append_record(rec)
    print(f"recorded {a.direction} {a.workspace} {a.date} ({a.outcome})")
    return 0


def cmd_query(a) -> int:
    records, bad = read_records()
    cfg = load_config()
    today = d(a.today) if a.today else date.today()
    out: dict = {}

    if a.view in ("last", "summary"):
        names = [a.workspace] if a.workspace else sorted(
            {r.get("workspace") for r in records if r.get("workspace")} - {UNKNOWN_WS})
        last = {}
        for w in names:
            e, s = q_last(records, w, "day-end"), q_last(records, w, "day-start")
            last[w] = {
                "last_day_end": {k: e[k] for k in ("date", "mode", "outcome") if k in e} if e else None,
                "last_day_start": {k: s[k] for k in ("date", "mode") if k in s} if s else None,
                "streak": q_streak(records, cfg, w, today),
            }
        out["workspaces"] = last

    if a.view in ("open", "summary"):
        out["open_workdays"] = [{"workspace": w, "date": dt} for w, dt in q_open(records, today)]

    if a.view in ("weekly-review", "summary"):
        wr = q_weekly_review(records)
        out["last_weekly_review"] = wr["date"] if wr else None

    if a.view == "streak":
        if not a.workspace:
            raise SystemExit("ritual_state: query streak needs --workspace")
        out = {"workspace": a.workspace, "streak": q_streak(records, cfg, a.workspace, today)}

    n, base, status = unattributed_status(records, cfg)
    if status == "above":
        out["unattributed_records"] = n
        out["unattributed_alarm"] = (
            f"{n - base} record(s) ABOVE the acknowledged baseline of {base} — something is "
            "writing records with no workspace NOW. Per-workspace views silently omit them.")
    elif status == "below":
        out["unattributed_records"] = n
        out["unattributed_alarm"] = (
            f"{base - n} record(s) BELOW the acknowledged baseline of {base} — the log has "
            "lost records; it is append-only, so this should be impossible.")
    elif status == "unacknowledged" and n:
        out["unattributed_records"] = n
        out["unattributed_alarm"] = (
            f"{n} unattributed record(s) and no acknowledged baseline. Run "
            "`ritual_state.py baseline --accept` once the count is understood; until then "
            "this cannot distinguish legacy residue from a live defect.")
    # status == "baseline": silent. Acknowledged, permanent, and reported by doctor.
    if bad:
        out["malformed_lines"] = len(bad)

    if a.json:
        print(json.dumps(out, indent=2, sort_keys=True))
    else:
        _print_human(out)
    return 0


def _print_human(out: dict) -> None:
    for w, v in (out.get("workspaces") or {}).items():
        e = v["last_day_end"]
        s = v["last_day_start"]
        streak = v["streak"]
        st = f"  streak {streak}" if streak is not None else "  streak n/a"
        print(f"  {w:14} close {e['date'] if e else '—':12} "
              f"start {s['date'] if s else '—':12}{st}")
    if "open_workdays" in out:
        ow = out["open_workdays"]
        print(f"  open workdays: {len(ow)}" + ("" if not ow else ""))
        for o in ow:
            print(f"     OPEN  {o['workspace']:14} {o['date']}")
    if "last_weekly_review" in out:
        print(f"  last weekly review: {out['last_weekly_review'] or '—'}")
    if out.get("unattributed_alarm"):
        print(f"  ALARM: {out['unattributed_alarm']}")
    if out.get("malformed_lines"):
        print(f"  WARNING: {out['malformed_lines']} malformed line(s) in the log")


def cmd_migrate(a) -> int:
    """Fold the legacy logs and state files into one normalized log. Idempotent."""
    if log_path().exists() and not a.force:
        print(f"ritual_state: {log_path()} already exists; use --force to re-run")
        return 1
    merged = []
    for name, direction in (("day-end", "day-end"), ("day-start", "day-start")):
        p = Path.home() / ".synthesis" / name / "history.jsonl"
        if not p.exists():
            continue
        for line in p.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                r = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(r, dict):
                continue
            # Two legacy schemas exist. v1: {type: day_end, for_date: ...}
            # v2: {direction: day-end, date: ..., workspace: ...}. Handle both —
            # reading only v2 silently dropped 15 of 61 records on the first pass.
            rec_date = r.get("date") or r.get("for_date")
            if not rec_date:
                continue
            rec_dir = r.get("direction") or {
                "day_end": "day-end", "day_start": "day-start",
            }.get(r.get("type", ""), direction)
            rec = {
                "ts": r.get("ts") or f"{rec_date}T00:00:00+00:00",
                "date": rec_date,
                "direction": rec_dir,
                "workspace": r.get("workspace") or UNKNOWN_WS,
                "mode": r.get("mode", "?"),
                "outcome": r.get("outcome", "?"),
            }
            if r.get("weekly_review"):
                # v1 recorded the weekly review as a flag on a day-start; it is a
                # first-class person-level event and gets its own record.
                merged.append({
                    "ts": rec["ts"], "date": rec_date, "direction": "weekly-review",
                    "workspace": rec["workspace"], "mode": "derived-from-v1-flag",
                    "outcome": "clean",
                })
            if rec["workspace"] == UNKNOWN_WS:
                rec["workspace_confidence"] = "unstamped-legacy"
            counts = {k: r[k] for k in ("sent", "released", "decided", "carried", "moved")
                      if isinstance(r.get(k), int)}
            if counts:
                rec["counts"] = counts
            if r.get("note"):
                rec["pointer"] = "sessions/ — narrative retained in the legacy note field"
                rec["legacy_note_bytes"] = len(r["note"])
            merged.append(rec)
    # The legacy day-end state carried last_weekly_review as a bare field with no
    # event behind it. Promote it to a record so the log is the only truth.
    for legacy in LEGACY_STATE:
        if not legacy.exists():
            continue
        try:
            st = json.loads(legacy.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        wr = st.get("last_weekly_review") if isinstance(st, dict) else None
        if isinstance(wr, str) and wr and not any(
                r["direction"] == "weekly-review" and r["date"] == wr for r in merged):
            merged.append({
                "ts": f"{wr}T00:00:00+00:00", "date": wr, "direction": "weekly-review",
                "workspace": UNKNOWN_WS, "mode": "derived-from-legacy-state",
                "outcome": "clean",
            })

    merged.sort(key=lambda r: (r["date"], r["ts"], r["direction"]))

    header = {
        "ts": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
        "date": date.today().isoformat(),
        "direction": "day-start",
        "workspace": UNKNOWN_WS,
        "mode": "migration",
        "outcome": "header",
        "note": ("Migrated from day-{start,end}/history.jsonl. Records marked "
                 "workspace_confidence=unstamped-legacy predate per-seat stamping and are "
                 "EXCLUDED from per-workspace views rather than attributed by guess."),
    }
    log_path().parent.mkdir(parents=True, exist_ok=True)
    with open(log_path(), "w", encoding="utf-8") as fh:
        fh.write(json.dumps(header, separators=(",", ":"), sort_keys=True) + "\n")
        for r in merged:
            fh.write(json.dumps(r, separators=(",", ":"), sort_keys=True) + "\n")
    unk = sum(1 for r in merged if r["workspace"] == UNKNOWN_WS)
    _set_baseline(unk + (1 if header["workspace"] == UNKNOWN_WS else 0))
    print(f"migrated {len(merged)} record(s) into {log_path()}")
    print(f"  {unk} unattributed (excluded from per-workspace views, not guessed)")
    print(f"  {len(merged) - unk} attributed")
    return 0


def cmd_doctor(a) -> int:
    ok = True

    def chk(good, msg):
        nonlocal ok
        print(f"  {'ok ' if good else 'FAIL'}  {msg}")
        ok = ok and good

    print("synthesis ritual-state doctor")
    chk(log_path().exists(), f"log present: {log_path()}")
    records, bad = read_records()
    chk(not bad, f"log parses cleanly ({len(records)} records, {len(bad)} malformed)")

    for p in LEGACY_STATE:
        chk(not p.exists(),
            f"legacy mutable state absent: {p}" if not p.exists()
            else f"legacy mutable state STILL PRESENT: {p} — it has no single owner and "
                 f"any writer clobbers the rest; delete it")

    try:
        cfg = load_config()
        chk(True, f"config readable: {len(cfg.get('workspaces', {}))} workspace(s) declared")
    except SystemExit as exc:
        chk(False, str(exc))
        cfg = DEFAULT_CONFIG

    # positive controls: the size cap must trip, and a clean record must pass
    try:
        append_record({"ts": "x", "date": "1970-01-01", "direction": "day-end",
                       "workspace": "selftest", "mode": "m", "outcome": "o",
                       "note": "x" * (MAX_RECORD_BYTES + 10)})
        chk(False, "size cap did NOT trip on an oversized record")
    except SystemExit:
        chk(True, "size cap trips on an oversized record (positive control)")

    over = [r for r in records
            if len(json.dumps(r, separators=(",", ":")).encode()) > MAX_RECORD_BYTES]
    chk(not over, f"every record is within the {MAX_RECORD_BYTES}B atomic-append bound "
                  f"({len(over)} over)")

    n, base, status = unattributed_status(records, cfg)
    if status == "baseline":
        print(f"  note  {n} unattributed legacy record(s) at the acknowledged baseline — "
              f"excluded from per-workspace views by design, and silent in `query` because a "
              f"note that can never clear stops being read")
    elif status == "unacknowledged" and n:
        chk(False, f"{n} unattributed record(s) with no acknowledged baseline — run "
                   f"`baseline --accept` so deviation becomes detectable")
    elif status in ("above", "below"):
        chk(False, f"unattributed count {n} deviates from baseline {base} ({status})")

    print("HEALTHY: ritual state is derived, not stored." if ok
          else "UNHEALTHY: see FAIL lines above.")
    return 0 if ok else 2


def cmd_test(a) -> int:
    """Behavioural suite over a temp log. Exit 0 all pass / 2 failures."""
    import tempfile
    fails = []

    def eq(got, want, label):
        if got != want:
            fails.append(f"{label}: got {got!r}, want {want!r}")

    with tempfile.TemporaryDirectory() as tmp:
        os.environ["RITUAL_STATE_DIR"] = tmp
        cfg = {
            "defaults": {"streak": "none", "weekdays": [0, 1, 2, 3, 4], "non_working_dates": []},
            "workspaces": {
                "w": {"streak": "expected-days", "weekdays": [0, 1, 2, 3, 4],
                      "non_working_dates": ["2026-09-07"]},
                "adv": {"streak": "none"},
            },
        }
        Path(tmp, "config.json").write_text(json.dumps(cfg))

        def rec(dt, direction="day-end", ws="w"):
            append_record({"ts": f"{dt}T12:00:00+00:00", "date": dt,
                           "direction": direction, "workspace": ws,
                           "mode": "full", "outcome": "clean"})

        # Mon 9/7 is a declared non-working day; Tue 9/8 .. Fri 9/11 are expected.
        for dt in ("2026-09-08", "2026-09-09", "2026-09-10", "2026-09-11"):
            rec(dt)
        records, _ = read_records()
        # From Fri 9/11: 4 closes, then Mon 9/7 not expected & unclosed -> skipped,
        # then Fri 9/4 expected & unclosed -> break.
        eq(q_streak(records, cfg, "w", d("2026-09-11")), 4, "streak counts expected days")

        # A weekend close credits without being required.
        rec("2026-09-12")                       # Saturday
        records, _ = read_records()
        eq(q_streak(records, cfg, "w", d("2026-09-12")), 5, "weekend close credits")

        # An absent weekend does not break: from Sunday 9/13, Sat 9/12 closed.
        eq(q_streak(records, cfg, "w", d("2026-09-13")), 5, "absent weekend does not break")

        # Advisory seat has no streak at all.
        eq(q_streak(records, cfg, "adv", d("2026-09-11")), None, "advisory streak disabled")

        # Open workday: a start with no end.
        rec("2026-09-14", "day-start")
        records, _ = read_records()
        eq(q_open(records, d("2026-09-14")), [("w", "2026-09-14")], "open workday detected")
        rec("2026-09-14", "day-end")
        records, _ = read_records()
        eq(q_open(records, d("2026-09-14")), [], "closed workday clears")

        # Two seats on the same date do not collide.
        rec("2026-09-15", "day-end", "w")
        rec("2026-09-15", "day-end", "other")
        records, _ = read_records()
        eq(q_last(records, "w")["date"], "2026-09-15", "seat w preserved")
        eq(q_last(records, "other")["date"], "2026-09-15", "seat other preserved")

        # The unattributable baseline is a TRIPWIRE, not a permanent note.
        cfg_b = dict(cfg); cfg_b["legacy_unattributed_baseline"] = 0
        eq(unattributed_status(records, cfg_b)[2], "baseline",
           "zero unstamped at baseline 0 is silent")
        append_record({"ts": "x", "date": "2026-09-20", "direction": "day-end",
                       "workspace": UNKNOWN_WS, "mode": "m", "outcome": "o"})
        records, _ = read_records()
        eq(unattributed_status(records, cfg_b)[2], "above",
           "a new unstamped record trips the wire")
        cfg_b["legacy_unattributed_baseline"] = 5
        eq(unattributed_status(records, cfg_b)[2], "below",
           "losing records below baseline also trips")
        eq(unattributed_status(records, {})[2], "unacknowledged",
           "no baseline means the count cannot be interpreted")

        # Oversized records are refused.
        try:
            append_record({"ts": "x", "date": "2026-09-16", "direction": "day-end",
                           "workspace": "w", "mode": "m", "outcome": "o",
                           "note": "x" * (MAX_RECORD_BYTES + 10)})
            fails.append("size cap did not trip")
        except SystemExit:
            pass

    for f in fails:
        print(f"  FAIL  {f}")
    print(f"{'all tests pass' if not fails else str(len(fails)) + ' failure(s)'}")
    return 0 if not fails else 2


def _set_baseline(n: int) -> None:
    """Acknowledge the unattributable residue so deviation from it can alarm."""
    p = config_path()
    cfg = json.loads(p.read_text(encoding="utf-8")) if p.exists() else json.loads(json.dumps(DEFAULT_CONFIG))
    cfg["legacy_unattributed_baseline"] = n
    cfg["_legacy_unattributed_baseline_note"] = (
        "Count of records that predate per-seat stamping and can never be attributed. "
        "Acknowledged once so `query` stays silent about it; ANY deviation alarms, because "
        "a rise means something is writing unstamped records now and a fall means the "
        "append-only log lost data.")
    fd, tmp = tempfile.mkstemp(dir=str(p.parent))
    with os.fdopen(fd, "w") as fh:
        json.dump(cfg, fh, indent=2)
        fh.write("\n")
    os.replace(tmp, p)


def cmd_baseline(a) -> int:
    records, _ = read_records()
    n = unknown_count(records)
    if not a.accept:
        cfg = load_config()
        cur = cfg.get("legacy_unattributed_baseline")
        print(f"  unattributed now: {n}   acknowledged baseline: {cur if cur is not None else '(none)'}")
        return 0
    _set_baseline(n)
    print(f"  baseline accepted at {n}; `query` is now silent unless the count moves")
    return 0

# ---------------------------------------------------------------- cli


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description="Derive daily-ritual state from an append-only log. No mutable state file.")
    ap.add_argument(
        "--state-dir", default=None, metavar="DIR",
        help="use this directory's history.jsonl and config.json instead of "
             "~/.synthesis/rituals. Copy the real files into a scratch dir to exercise "
             "behaviour — including the tripwire's alarming arms — without writing to the "
             "production log. Equivalent to the RITUAL_STATE_DIR environment variable.")
    sub = ap.add_subparsers(dest="cmd", required=True)

    r = sub.add_parser("record", help="append one ritual record")
    r.add_argument("--direction", required=True, choices=DIRECTIONS)
    r.add_argument("--workspace", required=True)
    r.add_argument("--date", required=True, help="logical workday, YYYY-MM-DD (never inferred)")
    r.add_argument("--mode", default="full")
    r.add_argument("--outcome", default="clean")
    r.add_argument("--session", default=None)
    r.add_argument("--pointer", default=None, help="path to the narrative (session log)")
    r.add_argument("--note", default=None, help="SHORT structured note; prose belongs in the pointer")
    r.add_argument("--count", action="append", metavar="k=v")
    r.set_defaults(func=cmd_record)

    q = sub.add_parser("query", help="derive a view")
    q.add_argument("view", choices=["last", "open", "streak", "weekly-review", "summary"])
    q.add_argument("--workspace", default=None)
    q.add_argument("--today", default=None, help="override today, YYYY-MM-DD (testing)")
    q.add_argument("--json", action="store_true")
    q.set_defaults(func=cmd_query)

    m = sub.add_parser("migrate", help="fold legacy logs/state into the new log")
    m.add_argument("--force", action="store_true")
    m.set_defaults(func=cmd_migrate)

    b = sub.add_parser("baseline", help="show or accept the unattributable-residue baseline")
    b.add_argument("--accept", action="store_true")
    b.set_defaults(func=cmd_baseline)

    sub.add_parser("doctor", help="self-check; exit 0 HEALTHY / 2 UNHEALTHY").set_defaults(func=cmd_doctor)
    sub.add_parser("test", help="behavioural suite").set_defaults(func=cmd_test)

    a = ap.parse_args(argv)
    if a.state_dir:
        os.environ["RITUAL_STATE_DIR"] = a.state_dir
    return a.func(a)


if __name__ == "__main__":
    sys.exit(main())
