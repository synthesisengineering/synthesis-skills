"""A mid-day sync is recorded, and its record is checked as a day-start's is.

On 2026-11-18 an operations seat could not record its mid-day sync: the worker contract names `midday` among the run
types and records a run with `--direction <run type>`, the skill's rule 6 says to record every ritual, and
`ritual_state.py record` took only day-start, day-end and weekly-review. The seat kept its artifact and said that no
record could be made, rather than call the sync a day-start, which would have opened a workday.

Which checks hold a mid-day record follows from what each one catches and from what a sync does
(references/mid-day-and-modes.md): it sounds the critical alert, runs the travel check over the days ahead and puts
what it finds in the day's plan. So a critical deadline past due and open, an in-person event without its travel, a
choice put with no recommendation and a commitment the sweep cannot see refuse it, as they refuse a day-start. The
prompts the principal typed are reconciled over the whole day, at its close: a sync, like a day-start, lists none.
Committed before the change to the script.
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

DAY = "2026-11-11"  # a Wednesday


def declare(tmp_path: Path, plan: str = "# Wednesday\n\nNothing is open.\n", **settings) -> Path:
    """The workspace `desk`, its plan for the day (a folder with no dated plan is a gap in the sweep) and its config."""
    plans, state = tmp_path / "plans", tmp_path / "state"
    plans.mkdir(exist_ok=True)
    state.mkdir(exist_ok=True)
    (plans / f"{DAY}.md").write_text(plan, encoding="utf-8")
    (state / "config.json").write_text(json.dumps({"workspaces": {"desk": {"plans_dirs": [str(plans)], **settings}}}),
                                       encoding="utf-8")
    return state


@pytest.fixture
def record(monkeypatch, capsys):
    """Run `ritual_state.py record` in this process, for a mid-day sync unless told otherwise, on the calendar day `today`."""
    def run(state: Path, *extra, direction="midday", day=DAY, today=None):
        monkeypatch.setenv("RITUAL_STATE_DIR", str(state))
        monkeypatch.setattr(ritual_state, "today", lambda: date.fromisoformat(today or day), raising=False)
        try:
            code, refusal = ritual_state.main(["record", "--direction", direction, "--workspace", "desk", "--date", day, *extra]), ""
        except SystemExit as exc:
            code, refusal = 1, str(exc)
        return code, capsys.readouterr().out, refusal
    return run


def history(state: Path) -> str:
    log = state / "history.jsonl"
    return log.read_text(encoding="utf-8") if log.exists() else ""


def test_a_midday_sync_is_recorded_for_its_workday_and_never_for_a_day_ahead(tmp_path, record):
    state = declare(tmp_path)
    code, _, refusal = record(state, day="2026-11-12", today=DAY)
    assert code != 0 and "--date 2026-11-12 has not come" in refusal and history(state) == ""
    code, out, refusal = record(state)
    assert code == 0, refusal
    assert out.startswith(f"recorded midday desk {DAY} (clean)\ncritical deadlines: 0 open")
    assert json.loads(history(state))["direction"] == "midday"


CRITICAL = ("### Open enrollment closes\n**Critical:** benefits enrollment\n**Decays:** 2026-11-06 (the window closes)\n"
            "**Decay ID:** enroll-2026\n**Calendar:** event 4f2a\n\n")


def test_a_critical_deadline_past_due_refuses_a_midday_sync(tmp_path, record):
    state = declare(tmp_path)
    (tmp_path / "plans" / "2026-11-02.md").write_text("# Monday\n\n" + CRITICAL, encoding="utf-8")
    code, _, refusal = record(state)
    assert code != 0 and history(state) == ""
    assert "1 critical deadline(s) past due and open" in refusal and "Open enrollment closes" in refusal and "Evidence" in refusal
    code, out, refusal = record(state, day="2026-11-05")                             # the day before it falls due
    assert code == 0 and "critical deadlines: 1 open" in out, refusal


EVENT = {"summary": "Book launch at the Grand Theatre", "start": "2026-11-11T19:00:00-05:00", "end": "2026-11-11T22:00:00-05:00",
         "location": "The Grand Theatre, 149 Main St, Harbor Town", "lacks": [], "leave": "17:05", "home": "23:20"}


def travel(tmp_path: Path, *lacks: str) -> str:
    """What `travel_check.py --json` prints for today and the six days after, over the one event."""
    event = {**EVENT, "lacks": list(lacks)}
    saved = tmp_path / "travel.json"
    saved.write_text(json.dumps({"window": {"from": DAY, "through": "2026-11-17"}, "in_person": 1, "flagged": int(bool(lacks)),
                                 "verdict": "REFUSE" if lacks else "OK", "events": [event]}), encoding="utf-8")
    return str(saved)


def test_a_midday_sync_is_held_to_the_travel_check(tmp_path, record):
    state = declare(tmp_path, travel_check=True)
    code, _, refusal = record(state)
    assert code != 0 and "--travel" in refusal and history(state) == ""
    code, _, refusal = record(state, "--travel", travel(tmp_path, "no travel block before it (leave, route, arrive)"))
    assert code != 0 and "1 in-person event(s)" in refusal and "Book launch" in refusal and history(state) == ""
    code, out, refusal = record(state, "--travel", travel(tmp_path))
    assert code == 0 and "travel: 1 in-person event through 2026-11-17, each with its travel" in out, refusal


INVITATION = "### 2. The book launch on Wednesday, 7 to 10 PM, in Harbor Town\n**Option A:** Accept\n**Option B:** Decline\n"
COSTS = "**Consequences:** 1 h 25 min each way by train, $32 round trip, home at 23:48 before a 07:30 session.\n"
VIEW = "**Recommendation:** **B**, decline: three hours of travel and a midnight return for a two-hour event.\n"


def test_a_choice_a_midday_sync_puts_in_the_plan_needs_its_recommendation_and_costs(tmp_path, record):
    state = declare(tmp_path, "# Wednesday\n\n## Decisions needed\n\n" + INVITATION)
    code, _, refusal = record(state)
    assert code != 0 and "The book launch on Wednesday" in refusal and "defaults to yes" in refusal and history(state) == ""
    declare(tmp_path, "# Wednesday\n\n## Decisions needed\n\n" + INVITATION + COSTS + VIEW)
    code, out, refusal = record(state)
    assert code == 0 and "choices: 1 open in today's plan, each with a recommendation" in out, refusal


BARE = "# Wednesday\n\n## Priority Tasks\n\n1. **Call the landlord**\n\n## Waiting On Others\n- The vendor's quote\n"


def test_a_midday_sync_is_held_to_the_commitments_check(tmp_path, record):
    state = declare(tmp_path, BARE, commitment_check=True)
    code, _, refusal = record(state)
    assert code != 0 and "2 commitment(s) in the newest plan carry no date and no park" in refusal and history(state) == ""
    code, out, refusal = record(state, "--outcome", "partial")
    assert code == 0 and "commitments: 2 in the newest plan carry no date and no park" in out, refusal


def test_a_midday_sync_lists_no_prompts_and_the_close_still_does(tmp_path, record, monkeypatch):
    """With the prompt check on and no `synthesis` command to list the day's prompts, the close is refused and the
    sync is recorded: it does not ask for them."""
    state = declare(tmp_path, prompt_reconcile={"records": [str(tmp_path / "kb")]})
    monkeypatch.setenv("PATH", "/usr/bin:/bin")
    code, out, refusal = record(state)
    assert code == 0 and "prompts" not in out, refusal
    code, _, refusal = record(state, direction="day-end")
    assert code != 0 and "the `synthesis` command is not on the PATH" in refusal
    assert [json.loads(line)["direction"] for line in history(state).splitlines()] == ["midday"]
