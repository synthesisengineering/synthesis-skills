"""A ritual is not recorded while an in-person event in the days ahead lacks its travel.

On 2026-11-11 an evening event 28 miles from a principal's home had been carried through three daily plans and
that morning's day-start with no travel time, route or fare. A rule about realistic travel was on file and no
step ran it. A workspace can now turn the travel check on: its rituals then run `travel_check.py` (in
synthesis-chief-of-staff) over the next days and hand the result to `ritual_state.py record`, which refuses
without one, with one for other days, or while it holds an event that lacks its travel. Committed before the
change to the script.
"""
from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
import ritual_state  # noqa: E402

DAY = "2026-11-11"
WHOLE = {"summary": "Book launch at the Grand Theatre", "start": "2026-11-11T19:00:00-05:00", "end": "2026-11-11T22:00:00-05:00",
         "location": "The Grand Theatre, 149 Main St, Harbor Town", "lacks": [], "leave": "17:05", "home": "23:20"}
BARE = {"summary": "Book launch at the Grand Theatre", "start": "2026-11-11T19:00:00-05:00", "end": "2026-11-11T22:00:00-05:00",
        "location": "Harbor Town (address on the invitation)",
        "lacks": ['no exact address: the location reads "Harbor Town (address on the invitation)"',
                  "no travel block before it (leave, route, arrive, backup, fare, ticket)"]}


def declare(state: Path, **workspaces) -> None:
    state.mkdir(parents=True, exist_ok=True)
    (state / "config.json").write_text(json.dumps({"workspaces": workspaces}), encoding="utf-8")


def result(tmp_path: Path, *events, first=DAY, through="2026-11-17") -> str:
    flagged = sum(bool(e["lacks"]) for e in events)
    saved = tmp_path / "travel.json"
    saved.write_text(json.dumps({"window": {"from": first, "through": through}, "in_person": len(events), "flagged": flagged,
                                 "verdict": "REFUSE" if flagged else "OK", "events": list(events)}), encoding="utf-8")
    return str(saved)


@pytest.fixture
def record(monkeypatch, capsys):
    def run(state: Path, *extra, workspace="desk", day=DAY):
        monkeypatch.setenv("RITUAL_STATE_DIR", str(state))
        monkeypatch.setattr(ritual_state, "today", lambda: date.fromisoformat(day), raising=False)
        try:
            code, refusal = ritual_state.main(["record", "--direction", "day-start", "--workspace", workspace, "--date", day, *extra]), ""
        except SystemExit as exc:
            code, refusal = 1, str(exc)
        return code, capsys.readouterr().out, refusal
    return run


def history(state: Path) -> str:
    log = state / "history.jsonl"
    return log.read_text(encoding="utf-8") if log.exists() else ""


def test_a_workspace_that_has_not_turned_the_check_on_records_as_before(tmp_path, record):
    state = tmp_path / "state"
    declare(state, desk={"plans_dirs": []})
    code, out, refusal = record(state)
    assert code == 0, refusal
    assert "travel" not in out and '"workspace":"desk"' in history(state)


def test_with_the_check_on_a_record_needs_a_travel_result(tmp_path, record):
    state = tmp_path / "state"
    declare(state, desk={"plans_dirs": [], "travel_check": True})
    code, _, refusal = record(state)
    assert code != 0 and "travel_check.py" in refusal and "--travel" in refusal and "7 days" in refusal
    assert history(state) == ""


def test_an_event_that_lacks_its_travel_keeps_the_ritual_from_being_recorded(tmp_path, record):
    state = tmp_path / "state"
    declare(state, desk={"plans_dirs": [], "travel_check": True})
    code, _, refusal = record(state, "--travel", result(tmp_path, BARE))
    assert code != 0 and history(state) == ""
    assert "1 in-person event(s)" in refusal and "Book launch at the Grand Theatre" in refusal
    assert "no exact address" in refusal and "no travel block before it" in refusal and "the principal" in refusal


def test_when_every_event_has_its_travel_the_ritual_is_recorded_and_says_so(tmp_path, record):
    state = tmp_path / "state"
    declare(state, desk={"plans_dirs": [], "travel_check": True})
    code, out, refusal = record(state, "--travel", result(tmp_path, WHOLE))
    assert code == 0, refusal
    assert "travel: 1 in-person event through 2026-11-17, each with its travel" in out
    assert '"workspace":"desk"' in history(state)
    code, out, refusal = record(state, "--travel", result(tmp_path))
    assert code == 0 and "travel: 0 in-person events through 2026-11-17" in out


@pytest.mark.parametrize("window, says", [
    ({"first": "2026-11-10", "through": "2026-11-17"}, "2026-11-10"),   # yesterday's result
    ({"first": DAY, "through": "2026-11-14"}, "2026-11-17"),            # too few days
])
def test_a_result_for_other_days_is_not_a_result(tmp_path, record, window, says):
    state = tmp_path / "state"
    declare(state, desk={"plans_dirs": [], "travel_check": True})
    code, _, refusal = record(state, "--travel", result(tmp_path, WHOLE, **window))
    assert code != 0 and says in refusal and history(state) == ""


def test_a_result_it_cannot_read_is_refused_and_a_workspace_can_ask_for_other_days(tmp_path, record):
    state = tmp_path / "state"
    declare(state, desk={"plans_dirs": [], "travel_check": {"days": 3}})
    broken = tmp_path / "broken.json"
    broken.write_text("{not json", encoding="utf-8")
    code, _, refusal = record(state, "--travel", str(broken))
    assert code != 0 and "cannot be read" in refusal
    code, _, refusal = record(state, "--travel", str(tmp_path / "missing.json"))
    assert code != 0 and "cannot be read" in refusal
    code, out, refusal = record(state, "--travel", result(tmp_path, WHOLE, through="2026-11-13"))
    assert code == 0, refusal
    assert "through 2026-11-13" in out


# --- after a second model's review (2026-11-11): a result must read as the check's own output -------------

@pytest.mark.parametrize("change", [
    {"window": {"from": DAY}},                                  # no last day
    {"window": {"from": DAY, "through": None}},
    {"window": {"from": DAY, "through": "tomorrow"}},
    {"flagged": 1},                                             # counts and verdict that its own events contradict
    {"verdict": "REFUSE"},
    {"in_person": 3},
    {"events": "none"},
    {"events": [{"summary": "an event with no word on what it lacks"}]},
])
def test_a_result_that_does_not_read_as_the_checks_own_output_is_refused(tmp_path, record, change):
    state = tmp_path / "state"
    declare(state, desk={"plans_dirs": [], "travel_check": True})
    saved = Path(result(tmp_path, WHOLE))
    saved.write_text(json.dumps({**json.loads(saved.read_text(encoding="utf-8")), **change}), encoding="utf-8")
    code, _, refusal = record(state, "--travel", str(saved))
    assert code != 0 and "travel" in refusal and history(state) == ""


def test_an_event_outside_the_days_the_result_claims_is_not_that_results(tmp_path, record):
    """The second review: a result for November 11 to 17 that listed a December event was recorded."""
    state = tmp_path / "state"
    declare(state, desk={"plans_dirs": [], "travel_check": True})
    code, _, refusal = record(state, "--travel", result(tmp_path, dict(WHOLE, start="2026-12-25T19:00:00-05:00")))
    assert code != 0 and "travel" in refusal and history(state) == ""
    code, _, refusal = record(state, "--travel", result(tmp_path, {k: v for k, v in WHOLE.items() if k != "start"}))
    assert code != 0 and history(state) == ""
    under_way = dict(WHOLE, start="2026-11-10T23:00:00-05:00")  # one that began the evening before still belongs
    assert record(state, "--travel", result(tmp_path, under_way))[0] == 0


@pytest.mark.parametrize("start", ["2026-11-11nonsense", "2026-11-11T25:00:00", "2026-11-11 19:00 or so", "11 November 2026"])
def test_an_event_whose_start_is_no_date_and_time_is_not_the_checks_own_output(tmp_path, record, start):
    """The third review: only the first ten characters of a start were read, so `2026-11-11nonsense` was recorded."""
    state = tmp_path / "state"
    declare(state, desk={"plans_dirs": [], "travel_check": True})
    code, _, refusal = record(state, "--travel", result(tmp_path, dict(WHOLE, start=start)))
    assert code != 0 and "travel" in refusal and history(state) == ""


def test_an_event_over_before_the_results_days_is_not_that_results(tmp_path, record):
    """The fourth review: an event that started and ended years before the window was recorded, since only its
    start was held against the window's last day. One still under way when the window opens stays."""
    state = tmp_path / "state"
    declare(state, desk={"plans_dirs": [], "travel_check": True})
    past = dict(WHOLE, start="2020-01-01T19:00:00-05:00", end="2020-01-01T22:00:00-05:00")
    code, _, refusal = record(state, "--travel", result(tmp_path, past))
    assert code != 0 and "travel" in refusal and history(state) == ""
    code, _, refusal = record(state, "--travel", result(tmp_path, {k: v for k, v in WHOLE.items() if k != "end"}))
    assert code != 0 and history(state) == ""                                                # no end: not the check's own output
    under_way = dict(WHOLE, start="2026-11-09T09:00:00-05:00", end="2026-11-12T17:00:00-05:00")
    code, out, refusal = record(state, "--travel", result(tmp_path, under_way))
    assert code == 0 and "each with its travel" in out, refusal


def test_a_result_whose_event_ends_before_it_starts_is_not_what_the_check_printed(tmp_path, record):
    """The eighth review: an event starting at 22:00 and ending at 19:00 passed the gate."""
    state = tmp_path / "state"
    declare(state, desk={"plans_dirs": [], "travel_check": True})
    backwards = {**WHOLE, "start": "2026-11-11T22:00:00-05:00", "end": "2026-11-11T19:00:00-05:00"}
    code, _, refusal = record(state, "--travel", result(tmp_path, backwards))
    assert code != 0 and "does not agree with itself" in refusal and history(state) == ""
