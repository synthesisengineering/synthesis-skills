"""A ritual is not recorded while the day's plan puts a choice to the principal with no recommendation.

On 2026-10-30 a daily plan put an invitation to its principal as "Option A: Accept / Option B: Decline": no
recommendation, no trip, no cost, no time home. He said yes to an evening that turned out to be three hours of
travel away, home near midnight before an early morning. A choice put with no view is not neutral: it defaults to
yes. `ritual_state.py record` now reads the day's plan in each plan folder a workspace declares, and refuses while an
open item that offers options has no recommendation, or, when it would commit the principal's time, no word on
what it costs. Committed before the change to the script.
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
INVITATION = "### 2. The book launch on Wednesday, 7 to 10 PM, in Harbor Town\n**Option A:** Accept\n**Option B:** Decline\n"
COSTS = ("**Consequences:** 1 h 25 min each way by train, $32 round trip and not expensable, home at 23:48 before a "
         "07:30 session on Thursday; it is also the night a guest arrives.\n")
VIEW = "**Recommendation:** **B**, decline: three hours of travel and a midnight return for a two-hour event.\n"


def workspace(tmp_path: Path, *items: str) -> Path:
    plans, state = tmp_path / "plans", tmp_path / "state"
    plans.mkdir(exist_ok=True)
    state.mkdir(exist_ok=True)
    (plans / f"{DAY}.md").write_text("# Wednesday\n\n## Decisions needed\n\n" + "\n".join(items) + "\n## Priority Tasks\n\n1. **Ship** it\n",
                                     encoding="utf-8")
    (state / "config.json").write_text(json.dumps({"workspaces": {"desk": {"plans_dirs": [str(plans)]}}}), encoding="utf-8")
    return state


@pytest.fixture
def record(monkeypatch, capsys):
    def run(state: Path):
        monkeypatch.setenv("RITUAL_STATE_DIR", str(state))
        monkeypatch.setattr(ritual_state, "today", lambda: date.fromisoformat(DAY), raising=False)
        try:
            code, refusal = ritual_state.main(["record", "--direction", "day-start", "--workspace", "desk", "--date", DAY]), ""
        except SystemExit as exc:
            code, refusal = 1, str(exc)
        return code, capsys.readouterr().out, refusal
    return run


def test_a_bare_accept_or_decline_keeps_the_ritual_from_being_recorded(tmp_path, record):
    code, _, refusal = record(workspace(tmp_path, INVITATION))
    assert code != 0 and not (tmp_path / "state" / "history.jsonl").exists()
    assert "The book launch on Wednesday" in refusal and "recommendation" in refusal and "consequences" in refusal
    assert "defaults to yes" in refusal and "**Recommendation:**" in refusal and "**Consequences:**" in refusal


def test_a_recommendation_alone_is_not_enough_for_a_choice_that_commits_time(tmp_path, record):
    code, _, refusal = record(workspace(tmp_path, INVITATION + VIEW))
    assert code != 0 and "consequences" in refusal and "lacks its recommendation" not in refusal


def test_with_what_it_costs_and_a_view_the_ritual_is_recorded_and_says_so(tmp_path, record):
    code, out, refusal = record(workspace(tmp_path, INVITATION + COSTS + VIEW))
    assert code == 0, refusal
    assert "choices: 1 open in today's plan, each with a recommendation" in out


def test_a_choice_that_commits_no_time_needs_only_a_recommendation(tmp_path, record):
    branch = "### 1. Rebase or merge the feature branch?\n**Option A:** Rebase onto main\n**Option B:** Merge main into it\n"
    code, _, refusal = record(workspace(tmp_path, branch))
    assert code != 0 and "Rebase or merge" in refusal and "consequences" not in refusal.split("Under each")[0]
    code, out, refusal = record(workspace(tmp_path, branch + "Recommendation: **A**, the history stays linear\n"))
    assert code == 0, refusal


@pytest.mark.parametrize("empty", ["**Recommendation:** TBD", "**Recommendation:** none", "Recommendation:", "**Recommendation:** your call"])
def test_a_recommendation_that_recommends_nothing_is_none(tmp_path, record, empty):
    code, _, refusal = record(workspace(tmp_path, INVITATION + COSTS + empty + "\n"))
    assert code != 0 and "recommendation" in refusal


def test_a_choice_already_made_or_withdrawn_is_not_asked_again(tmp_path, record):
    made = INVITATION + "**Decided:** Option B — 2026-11-11T09:12:00-05:00\n"
    struck = "### ~~3. Dinner on Friday~~\n**Option A:** Accept\n**Option B:** Decline\n"
    code, out, refusal = record(workspace(tmp_path, made, struck))
    assert code == 0, refusal
    assert "choices: 0 open" in out


def test_an_item_marked_as_committing_time_needs_its_costs_whatever_its_options_say(tmp_path, record):
    hosted = ("### 4. A friend asks to stay the week of the 16th\n**Commits:** the living room, Monday to Saturday\n"
              "**Option A:** Offer the week\n**Option B:** Offer two nights\n" + VIEW)
    code, _, refusal = record(workspace(tmp_path, hosted))
    assert code != 0 and "A friend asks to stay" in refusal and "consequences" in refusal


# --- the second review round (2026-11-11) ---------------------------------------------------------------------

@pytest.mark.parametrize("options", ["1. **Option A**: Accept\n2. **Option B**: Decline\n", "+ **Option A**: Accept\n+ **Option B**: Decline\n",
                                     "* Option A: Accept\n* Option B: Decline\n"])
def test_options_written_as_any_list_are_options(tmp_path, record, options):
    code, _, refusal = record(workspace(tmp_path, "### 5. The dinner on Friday\n" + options))
    assert code != 0 and "The dinner on Friday" in refusal


def test_a_recommendation_inside_a_code_fence_is_an_example_not_a_recommendation(tmp_path, record):
    fenced = INVITATION + COSTS + "```text\nRecommendation: **B**, decline\n```\n"
    code, _, refusal = record(workspace(tmp_path, fenced))
    assert code != 0 and "recommendation" in refusal


@pytest.mark.parametrize("view", ["+ **Recommendation:** **B**, decline\n", "1. Recommendation: B, decline\n", "* **Recommendation**: B, decline\n"])
def test_a_recommendation_written_as_any_list_item_counts(tmp_path, record, view):
    code, out, refusal = record(workspace(tmp_path, INVITATION + COSTS + view))
    assert code == 0, refusal


def test_options_in_a_quote_are_options_and_a_ticked_title_is_closed(tmp_path, record):
    quoted = "### 6. The panel in March\n> **Option A:** Accept\n> **Option B:** Decline\n"
    code, _, refusal = record(workspace(tmp_path, quoted))
    assert code != 0 and "The panel in March" in refusal
    ticked = "### [x] 7. The dinner on Friday\n**Option A:** Accept\n**Option B:** Decline\n"
    code, out, refusal = record(workspace(tmp_path, ticked))
    assert code == 0, refusal
