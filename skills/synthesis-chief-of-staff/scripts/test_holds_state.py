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

MODULE_PATH = Path(__file__).with_name("holds_state.py")
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


# --------------------------------------------------------------- migration

def test_unparsable_window_keeps_prose_rather_than_inventing_a_time() -> None:
    assert H._parse_legacy_window("18:15-18:30 weekdays") == (None, None)
    assert H._parse_legacy_window("2026-09-02 11:30-13:00") == (None, None), \
        "a window with no zone must not be assumed local"
    assert H._parse_legacy_window("2026-09-02 11:30-13:00 EDT") == (
        "2026-09-02T11:30:00-04:00", "2026-09-02T13:00:00-04:00")


def test_migration_is_idempotent(store) -> None:
    (store / "holds-ledger.json").write_text(json.dumps({
        "version": 1,
        "holds": [{"id": "a", "calendar": "c", "title": "Hold",
                   "kind": "same-day-shield",
                   "window": "2026-09-04 14:00-16:00 EDT",
                   "created": "2026-09-01", "created_by": "seat",
                   "expires": "end of its own day", "purpose": "p"}]}))
    assert len(H.migrate()) == 1
    assert len(H.migrate()) == 0, "re-running migrate must not duplicate holds"
    assert len([e for e in H.load_events() if e["event"] == "place"]) == 1


def test_engine_self_test_passes() -> None:
    proc = subprocess.run([sys.executable, str(MODULE_PATH), "test"],
                          capture_output=True, text=True)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "FAIL" not in proc.stdout, proc.stdout


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
