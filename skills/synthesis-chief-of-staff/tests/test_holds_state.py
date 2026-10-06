"""CI coverage for the holds ledger.

The invariant under test is narrow and load-bearing: the agent may release or
move ONLY a hold it placed, matched by id. Everything else here exists to keep
that answer trustworthy when several seats run the principal's rituals against
one calendar at the same time.
"""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path

import pytest

MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "holds_state.py"
SPEC = importlib.util.spec_from_file_location("holds_state", MODULE_PATH)
assert SPEC and SPEC.loader
H = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = H
SPEC.loader.exec_module(H)


@pytest.fixture
def store(tmp_path, monkeypatch):
    monkeypatch.setenv("HOLDS_STATE_DIR", str(tmp_path))
    return tmp_path


def place(hid, start, end, **kw):
    rec = {"event": "place", "id": hid, "ts": "2026-09-01T09:00:00-04:00",
           "by": "seat-a", "calendar": "cal", "title": "Hold",
           "kind": "same-day-shield", "expires": "end-of-day",
           "start": start, "end": end, "purpose": "why"}
    rec.update(kw)
    return H.append_event(rec)


# --------------------------------------------------------------- invariant

def test_only_placed_holds_are_releasable(store) -> None:
    place("mine", "2026-09-04T14:00:00-04:00", "2026-09-04T16:00:00-04:00")
    ids = {h["id"] for h in H.releasable(H.load_events())}
    assert "mine" in ids
    assert "an-event-someone-else-made" not in ids


def test_released_hold_stops_being_releasable(store) -> None:
    place("h", "2026-09-04T14:00:00-04:00", "2026-09-04T16:00:00-04:00")
    H.append_event({"event": "release", "id": "h", "ts": "2026-09-04T15:00:00-04:00",
                    "by": "seat-b", "reason": "yielded to a real meeting"})
    assert "h" not in {x["id"] for x in H.releasable(H.load_events())}


def test_expiry_does_not_gate_releasability(store) -> None:
    """An expired hold is exactly the one that most needs clearing."""
    place("old", "2026-08-31T13:30:00-04:00", "2026-08-31T15:00:00-04:00")
    ev = H.load_events()
    assert {x["id"] for x in H.expired(ev, date(2026, 9, 2))} == {"old"}
    assert "old" in {x["id"] for x in H.releasable(ev)}


def test_release_without_place_is_surfaced_not_swallowed(store) -> None:
    H.append_event({"event": "release", "id": "ghost", "ts": "2026-09-02T10:00:00-04:00",
                    "by": "seat", "reason": "r"})
    assert H.derive(H.load_events())["ghost"]["orphan_release"] is True
    assert "ghost" not in {x["id"] for x in H.releasable(H.load_events())}


def test_cli_is_releasable_exit_codes(store) -> None:
    place("yes", "2026-09-04T14:00:00-04:00", "2026-09-04T16:00:00-04:00")
    env = {**os.environ, "HOLDS_STATE_DIR": str(store)}
    ok = subprocess.run([sys.executable, str(MODULE_PATH), "is-releasable", "yes"],
                        capture_output=True, text=True, env=env)
    no = subprocess.run([sys.executable, str(MODULE_PATH), "is-releasable", "no"],
                        capture_output=True, text=True, env=env)
    assert ok.returncode == 0
    assert no.returncode == 1
    assert "ask the principal" in no.stdout


# ------------------------------------------------------------- concurrency

def test_shared_array_rewrite_loses_holds(tmp_path) -> None:
    """Positive control: the shape this file replaced, under real threads."""
    f = tmp_path / "legacy.json"
    f.write_text(json.dumps({"holds": []}))

    def rmw(i):
        try:
            doc = json.loads(f.read_text())
        except json.JSONDecodeError:
            doc = {"holds": []}
        doc["holds"].append({"id": f"h{i:02d}"})
        f.write_text(json.dumps(doc))

    seats = 12
    with ThreadPoolExecutor(max_workers=seats) as ex:
        list(ex.map(rmw, range(seats)))
    try:
        kept = len(json.loads(f.read_text())["holds"])
    except json.JSONDecodeError:
        kept = 0
    assert kept < seats, (
        "the old single-array ledger kept every hold under concurrency; if "
        "that is now true the control no longer proves anything"
    )


def test_append_only_log_keeps_every_seat(store) -> None:
    seats = 16
    with ThreadPoolExecutor(max_workers=seats) as ex:
        list(ex.map(
            lambda i: place(f"c{i:02d}", "2026-09-04T14:00:00-04:00",
                            "2026-09-04T16:00:00-04:00", by=f"seat-{i}",
                            purpose="x" * 300),
            range(seats)))
    ids = {h["id"] for h in H.load_events()}
    assert ids == {f"c{i:02d}" for i in range(seats)}


def test_records_stay_within_the_atomic_append_bound(store) -> None:
    written = place("big", "2026-09-04T14:00:00-04:00",
                    "2026-09-04T16:00:00-04:00", purpose="y" * 9000)
    blob = json.dumps(written, separators=(",", ":"), sort_keys=True).encode()
    assert len(blob) + 1 <= H.MAX_RECORD_BYTES
    assert written["id"] == "big", "the hold itself must survive trimming"
    assert written["purpose"].endswith("…[trimmed]")


def test_torn_line_is_skipped_not_guessed_at(store) -> None:
    place("good", "2026-09-04T14:00:00-04:00", "2026-09-04T16:00:00-04:00")
    with open(H.log_path(), "a", encoding="utf-8") as fh:
        fh.write('{"event":"place","id":"torn"\n')
    assert {h["id"] for h in H.load_events()} == {"good"}


def test_ledger_is_created_private(store) -> None:
    """Hold purposes name meetings, colleagues and clients.

    The file this replaced was 0600. A store that widens that while fixing a
    concurrency bug trades one defect for a quieter one.
    """
    place("h", "2026-09-04T14:00:00-04:00", "2026-09-04T16:00:00-04:00")
    log = Path(H.log_path())
    assert log.stat().st_mode & 0o777 == 0o600
    assert log.parent.stat().st_mode & 0o777 == 0o700


def test_loose_permissions_are_repaired_on_the_next_append(store) -> None:
    place("h", "2026-09-04T14:00:00-04:00", "2026-09-04T16:00:00-04:00")
    log = Path(H.log_path())
    os.chmod(log, 0o644)
    os.chmod(log.parent, 0o755)
    place("h2", "2026-09-04T16:00:00-04:00", "2026-09-04T17:00:00-04:00")
    assert log.stat().st_mode & 0o777 == 0o600
    assert log.parent.stat().st_mode & 0o777 == 0o700


# ------------------------------------------------- recurring holds (E70)

def _cli(store, *args):
    env = {**os.environ, "HOLDS_STATE_DIR": str(store)}
    return subprocess.run([sys.executable, str(MODULE_PATH), *args], capture_output=True, text=True, env=env)


def _place_recurring(store):
    r = _cli(store, "record", "place", "--id", "series", "--by", "seat-a", "--title", "Day close",
             "--kind", "recurring-ritual-prompt", "--expires", "none", "--recurring",
             "--start", "2026-09-01T18:15:00-04:00", "--end", "2026-09-01T18:30:00-04:00")
    assert r.returncode == 0, r.stderr


def test_releasing_one_instance_keeps_the_series_held(store) -> None:
    _place_recurring(store)
    r = _cli(store, "record", "release", "--id", "series", "--by", "seat-b",
             "--instance", "2026-09-10", "--reason", "that morning was rebuilt")
    assert r.returncode == 0, r.stderr
    ev = H.load_events()
    assert "series" in {h["id"] for h in H.releasable(ev)}
    assert "series" not in {h["id"] for h in H.current(ev, date(2026, 9, 10))}
    assert "series" in {h["id"] for h in H.current(ev, date(2026, 9, 11))}
    assert _cli(store, "is-releasable", "series").returncode == 0


def test_a_bare_release_of_a_recurring_hold_is_refused(store) -> None:
    _place_recurring(store)
    r = _cli(store, "record", "release", "--id", "series", "--by", "seat-b", "--reason", "r")
    assert r.returncode == 2 and "--instance" in r.stderr and "--series" in r.stderr
    assert [e["event"] for e in H.load_events()] == ["place"]


def test_series_release_releases_every_instance(store) -> None:
    _place_recurring(store)
    assert _cli(store, "record", "release", "--id", "series", "--by", "seat-b",
                "--series", "--reason", "ritual retired").returncode == 0
    assert "series" not in {h["id"] for h in H.releasable(H.load_events())}


def test_records_from_before_the_flag_count_as_recurring_by_kind(store) -> None:
    place("legacy", None, None, expires="none", kind="recurring-ritual-prompt",
          legacy_window="18:15-18:30 weekdays", window_unparsed=True)
    r = _cli(store, "record", "release", "--id", "legacy", "--by", "seat", "--reason", "r")
    assert r.returncode == 2
    assert "legacy" in {h["id"] for h in H.current(H.load_events(), date(2027, 1, 1))}  # standing: never expires


def test_instance_release_of_a_one_off_hold_is_refused(store) -> None:
    place("once", "2026-09-04T14:00:00-04:00", "2026-09-04T16:00:00-04:00")
    r = _cli(store, "record", "release", "--id", "once", "--by", "s", "--instance", "2026-09-04", "--reason", "r")
    assert r.returncode == 2 and "not recurring" in r.stderr


def test_release_needs_a_reason_and_place_needs_a_window(store) -> None:
    assert _cli(store, "record", "release", "--id", "x", "--by", "s").returncode == 2
    assert _cli(store, "record", "place", "--id", "x", "--by", "s").returncode == 2


# ------------------------------------------------------ amend and expiry (E71)

def test_amend_moves_a_hold_without_losing_its_identity(store) -> None:
    place("h2", "2026-09-03T13:00:00-04:00", "2026-09-03T14:00:00-04:00")
    H.append_event({"event": "amend", "id": "h2", "ts": "2026-09-02T09:00:00-04:00", "by": "seat-a",
                    "start": "2026-09-03T14:00:00-04:00", "end": "2026-09-03T15:00:00-04:00"})
    held = H.derive(H.load_events())["h2"]
    assert held["start"] == "2026-09-03T14:00:00-04:00" and held["purpose"] == "why"


def test_expiry_is_calculated_from_the_window(store) -> None:
    place("today", "2026-09-02T11:30:00-04:00", "2026-09-02T13:00:00-04:00")
    place("yesterday", "2026-09-01T09:00:00-04:00", "2026-09-01T10:00:00-04:00")
    ev = H.load_events()
    assert {h["id"] for h in H.current(ev, date(2026, 9, 2))} == {"today"}
    assert {h["id"] for h in H.expired(ev, date(2026, 9, 2))} == {"yesterday"}


def test_doctor_reports_an_orphan_release(store) -> None:
    place("ok", "2026-09-04T14:00:00-04:00", "2026-09-04T16:00:00-04:00")
    assert _cli(store, "doctor").returncode == 0
    H.append_event({"event": "release", "id": "ghost", "ts": "2026-09-02T10:00:00-04:00", "by": "s", "reason": "r"})
    r = _cli(store, "doctor")
    assert r.returncode == 1 and "ghost" in r.stdout
