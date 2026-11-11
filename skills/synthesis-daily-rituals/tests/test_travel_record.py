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
WHOLE = {"summary": "Book launch at the Grand Theatre", "start": "2026-11-11T19:00:00-05:00",
         "location": "The Grand Theatre, 149 Main St, Harbor Town", "lacks": [], "leave": "17:05", "home": "23:20"}
BARE = {"summary": "Book launch at the Grand Theatre", "start": "2026-11-11T19:00:00-05:00",
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
