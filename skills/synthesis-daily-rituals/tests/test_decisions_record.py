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


def test_a_recommendation_in_an_indented_code_block_is_an_example(tmp_path, record):
    shown = INVITATION + COSTS + "\nFor example:\n\n    Recommendation: **B**, decline\n"
    code, _, refusal = record(workspace(tmp_path, shown))
    assert code != 0 and "recommendation" in refusal


# --- the third review (2026-11-11) -------------------------------------------------------------------------
# Choices were read only under a third-level heading, so a plan that listed its decisions under a second-level
# heading recorded with none read; and a heading inside a fenced example was read as a real choice.

LISTED = ("1. Dinner with the board on Thursday\n   **Option A** - Accept\n   **Option B** - Decline\n"
          "2. The offsite in March\n   **Option A** - Go\n   **Option B** - Send a deputy\n")


def test_choices_listed_under_a_second_level_heading_are_read_each_by_itself(tmp_path, record):
    code, _, refusal = record(workspace(tmp_path, LISTED))
    assert code != 0 and "Dinner with the board" in refusal and "The offsite in March" in refusal
    viewed = LISTED.replace("2. The offsite", COSTS + VIEW + "2. The offsite")                    # the first has its view, the second none
    code, _, refusal = record(workspace(tmp_path, viewed))
    assert code != 0 and "The offsite in March" in refusal and "Dinner with the board" not in refusal
    code, out, refusal = record(workspace(tmp_path, viewed + COSTS + VIEW))
    assert code == 0 and "choices: 2 open" in out, refusal


def test_a_heading_inside_a_fenced_example_is_not_a_choice(tmp_path, record):
    example = "### How a choice is written\n\n```markdown\n### 9. An example\n**Option A:** Accept\n**Option B:** Decline\n```\n"
    code, out, refusal = record(workspace(tmp_path, example))
    assert code == 0 and "choices: 0 open" in out, refusal


def test_a_listed_choice_that_is_struck_or_ticked_is_closed(tmp_path, record):
    closed = "1. ~~Dinner with the board~~\n   **Option A** - Accept\n   **Option B** - Decline\n- [x] The offsite\n  **Option A** - Go\n  **Option B** - Stay\n"
    code, out, refusal = record(workspace(tmp_path, closed))
    assert code == 0 and "choices: 0 open" in out, refusal


def test_a_second_entry_whose_letters_go_on_is_still_its_own_choice(tmp_path, record):
    """The fourth review: a second entry lettered C and D was read as more options of the first, so its missing
    recommendation passed, and a first entry already decided hid it altogether."""
    listed = ("1. Dinner with the board on Thursday\n   **Option A** - Accept\n   **Option B** - Decline\n" + "   " + COSTS + "   " + VIEW
              + "2. The offsite in March\n   **Option C** - Go\n   **Option D** - Send a deputy\n")
    code, _, refusal = record(workspace(tmp_path, listed))
    assert code != 0 and "The offsite in March" in refusal and "Dinner with the board" not in refusal
    decided = listed.replace("   " + VIEW, "   " + VIEW + "   **Decided:** Option B\n")
    code, _, refusal = record(workspace(tmp_path, decided))
    assert code != 0 and "The offsite in March" in refusal
    notes = ("### 3. The launch\n**Option A:** Accept\n- it is three hours away\n- the fare is not expensable\n**Option B:** Decline\n" + COSTS + VIEW)
    code, out, refusal = record(workspace(tmp_path, notes))                                   # bullets under an option are not a new choice
    assert code == 0 and "choices: 1 open" in out, refusal


def test_a_recommendation_on_the_title_line_counts_and_a_check_marked_title_is_closed(tmp_path, record):
    """The fifth review: `### Dinner — Recommendation: A` was read as having no recommendation, and a title marked
    with a plain check mark as still open."""
    titled = "### 4. Dinner with the board — Recommendation: B, decline\n**Option A:** Accept\n**Option B:** Decline\n" + COSTS
    code, out, refusal = record(workspace(tmp_path, titled))
    assert code == 0 and "choices: 1 open" in out, refusal
    for mark in ("✓", "✔"):
        done = f"### {mark} Dinner with the board\n**Option A:** Accept\n**Option B:** Decline\n"
        code, out, refusal = record(workspace(tmp_path, done))
        assert code == 0 and "choices: 0 open" in out, (mark, refusal)
    bare = "### 5. Dinner, no recommendation yet\n**Option A:** Accept\n**Option B:** Decline\n" + COSTS
    assert record(workspace(tmp_path, bare))[0] != 0                                          # the word in a title is not a view


# --- the seventh review (2026-11-11) ------------------------------------------------------------------------

def test_options_indented_under_a_list_entry_are_that_entrys_options(tmp_path, record):
    """The seventh review: options indented by four spaces under a numbered entry were read as an example, so an
    unfinished choice was recorded with none read. An example is a block indented four past the entry it stands in,
    after an empty line."""
    nested = "1. Dinner with the board on Thursday\n    - **Option A** - Accept\n    - **Option B** - Decline\n"
    code, _, refusal = record(workspace(tmp_path, nested))
    assert code != 0 and "Dinner with the board" in refusal and "recommendation" in refusal and "consequences" in refusal
    tenth = "10. The offsite in March\n    **Option A** - Go\n    **Option B** - Send a deputy\n"
    code, _, refusal = record(workspace(tmp_path, tenth))
    assert code != 0 and "The offsite in March" in refusal
    code, out, refusal = record(workspace(tmp_path, nested + "    - " + COSTS + "    - " + VIEW))
    assert code == 0 and "choices: 1 open" in out, refusal
    tabbed = "- Dinner with the board on Thursday\n\t- **Option A** - Accept\n\t- **Option B** - Decline\n"
    code, _, refusal = record(workspace(tmp_path, tabbed))
    assert code != 0 and "Dinner with the board" in refusal
    shown = nested + "\n   For example:\n\n       **Recommendation:** B, decline\n       " + COSTS
    code, _, refusal = record(workspace(tmp_path, shown))                                    # four past the entry's text is still an example
    assert code != 0 and "recommendation" in refusal and "consequences" in refusal
    apart = "### How a choice is written\n\nFor example:\n\n    1. An example\n       **Option A:** Accept\n       **Option B:** Decline\n"
    code, out, refusal = record(workspace(tmp_path, apart))                                  # and a whole example indented by four is none
    assert code == 0 and "choices: 0 open" in out, refusal


# --- the eighth review (2026-11-11) -------------------------------------------------------------------------

def test_an_example_inside_a_quote_is_still_an_example(tmp_path, record):
    """The eighth review: a recommendation inside a quoted fenced block, or quoted and indented as code, counted."""
    fenced = INVITATION + COSTS + "\n> For example:\n>\n> ```markdown\n> **Recommendation:** B, decline\n> ```\n"
    code, _, refusal = record(workspace(tmp_path, fenced))
    assert code != 0 and "recommendation" in refusal
    indented = INVITATION + COSTS + "\n> For example:\n>\n>     **Recommendation:** B, decline\n"
    code, _, refusal = record(workspace(tmp_path, indented))
    assert code != 0 and "recommendation" in refusal
    quoted = INVITATION + COSTS + "\n> **Recommendation:** B, decline: the trip outweighs the event.\n"
    code, out, refusal = record(workspace(tmp_path, quoted))                                  # a quoted line that is no example still counts
    assert code == 0 and "choices: 1 open" in out, refusal


# --- the ninth review (2026-11-11) --------------------------------------------------------------------------

def test_a_quoted_example_under_a_list_entry_a_closed_title_in_bold_and_a_fence_left_open(tmp_path, record):
    """The ninth review: a recommendation quoted and indented as code under a numbered entry counted; a title struck
    or ticked inside bold was read as open; and options in a fenced example whose fence runs to the end of the file
    were read as a choice."""
    for entry in ("1. Dinner", "10. Dinner"):
        quoted = (f"{entry}\n    **Option A** - Accept\n    **Option B** - Decline\n    **Consequences:** Three hours and $30.\n\n"
                  "    > For example:\n    >\n    >     **Recommendation:** B, decline\n")
        code, _, refusal = record(workspace(tmp_path, quoted))
        assert code != 0 and "recommendation" in refusal, entry
    for title in ("### **~~Dinner~~**", "### **[x] Dinner**", "### __~~Dinner~~__"):
        code, out, refusal = record(workspace(tmp_path, title + "\n**Option A:** Accept\n**Option B:** Decline\n"))
        assert code == 0 and "choices: 0 open" in out, (title, refusal)
    code, _, refusal = record(workspace(tmp_path, "### **Dinner**\n**Option A:** Accept\n**Option B:** Decline\n"))
    assert code != 0 and "Dinner" in refusal                                                 # bold alone closes nothing
    left_open = "### How a choice is written\n\n```markdown\n### Dinner\n**Option A:** Accept\n**Option B:** Decline\n"
    assert list(ritual_state._items(left_open)) == []                                        # read as the plan's choices are read


def test_a_comment_is_not_shown_and_underscores_mark_emphasis_too(tmp_path, record):
    """Found by this project's own probe after the ninth review: a recommendation left as a placeholder inside an
    HTML comment counted, though Markdown shows none of it; and a line marked with underscores was not read."""
    hidden = INVITATION + COSTS + "<!-- **Recommendation:** say which you would take and why -->\n"
    code, _, refusal = record(workspace(tmp_path, hidden))
    assert code != 0 and "recommendation" in refusal
    spread = INVITATION + COSTS + "<!--\n**Recommendation:** B, decline\n-->\n"
    code, _, refusal = record(workspace(tmp_path, spread))
    assert code != 0 and "recommendation" in refusal
    template = "<!--\n### An example choice\n**Option A:** Accept\n**Option B:** Decline\n-->\n"
    code, out, refusal = record(workspace(tmp_path, template))                                # options inside a comment are no choice
    assert code == 0 and "choices: 0 open" in out, refusal
    shown = "### How a comment is written\n\n```html\n<!-- a note\n```\n\n" + INVITATION                # a comment opened inside an example hides nothing after it
    code, _, refusal = record(workspace(tmp_path, shown))
    assert code != 0 and "book launch" in refusal
    underscored = INVITATION + "__Consequences:__ Three hours and $30.\n_Recommendation:_ B, decline: the trip outweighs it.\n"
    code, out, refusal = record(workspace(tmp_path, underscored))
    assert code == 0 and "choices: 1 open" in out, refusal


# --- the tenth review (2026-11-12), each as a test that failed first ----------------------------------------

def test_underscores_mark_a_label_a_placeholder_and_a_field_of_the_title(tmp_path, record):
    """The tenth review: `__Option A__` was no option, `_TBD_` was a recommendation, and `__Recommendation:__ B`
    on a title line was none."""
    under = "### Dinner on Thursday\n__Option A__ - Accept\n__Option B__ - Decline\n"
    code, _, refusal = record(workspace(tmp_path, under))
    assert code != 0 and "Dinner on Thursday" in refusal and "recommendation" in refusal
    for empty in ("_TBD_", "__tbd__", "*TBD*", "_none_."):
        code, _, refusal = record(workspace(tmp_path, INVITATION + COSTS + f"**Recommendation:** {empty}\n"))
        assert code != 0 and "recommendation" in refusal, empty
    titled = "### Dinner with the board — __Recommendation:__ B, decline\n**Option A:** Accept\n**Option B:** Decline\n" + COSTS
    code, out, refusal = record(workspace(tmp_path, titled))
    assert code == 0 and "choices: 1 open" in out, refusal


def test_a_quote_inside_a_list_entry_and_an_explanation_above_the_options(tmp_path, record):
    """The tenth review: options quoted inside a list entry (`- > **Option A:**`) were not read, and a closed list
    entry with a sentence between its title and its options became an open choice titled by the section."""
    quoted = "### Dinner on Thursday\n- > **Option A:** Accept\n- > **Option B:** Decline\n"
    code, _, refusal = record(workspace(tmp_path, quoted))
    assert code != 0 and "Dinner on Thursday" in refusal
    closed = ("1. **[x] Dinner with the board**\n   It was answered last week; the options stay for the record.\n"
              "   **Option A:** Accept\n   **Option B:** Decline\n")
    code, out, refusal = record(workspace(tmp_path, closed))
    assert code == 0 and "choices: 0 open" in out, refusal
    code, _, refusal = record(workspace(tmp_path, closed.replace("[x] ", "")))
    assert code != 0 and "Dinner with the board" in refusal and "Decisions needed" not in refusal   # named by its entry, not by the section
    spaced = closed.replace("record.\n", "record.\n\n   A second paragraph of it.\n\n")
    code, out, refusal = record(workspace(tmp_path, spaced))
    assert code == 0 and "choices: 0 open" in out, refusal


def test_a_longer_fence_holds_a_shorter_one(tmp_path, record):
    """The tenth review: three backticks inside a four-backtick fence closed it, and the options of the example
    after them were read as a choice."""
    for mark in ("`", "~"):
        shown = (f"### How a choice is written\n\n{mark * 4}markdown\n{mark * 3}markdown\n**Option A:** Accept\n**Option B:** Decline\n"
                 f"{mark * 3}\n{mark * 4}\n")
        code, out, refusal = record(workspace(tmp_path, shown))
        assert code == 0 and "choices: 0 open" in out, (mark, refusal)
        code, _, refusal = record(workspace(tmp_path, shown + "\n" + INVITATION))             # after the closed fence the plan goes on
        assert code != 0 and "book launch" in refusal, mark
    opened = "### How a fence is opened\n\n```markdown\n```python\n**Option A:** Accept\n**Option B:** Decline\n```\n\n" + INVITATION
    code, _, refusal = record(workspace(tmp_path, opened))                                    # a fence line with a word after it opens, never closes
    assert code != 0 and "book launch" in refusal and "How a fence" not in refusal


# --- this project's own probe after the tenth review (2026-11-12), each as a test that failed first --------
# Thirty-six ordinary shapes of a plan were put to the reader. It refused a closed choice under a fourth-level
# heading or a bold title, read a sentence that begins "Option A was fine" as an option, did not read options
# written as headings or table rows, and did not take a recommendation written with a dash, as "Recommended:", as
# "My recommendation:" or on the option itself.

OPTIONS = "**Option A:** Accept\n**Option B:** Decline\n"


def test_a_choice_under_a_deeper_heading_or_a_bold_title_is_read_by_its_own_title(tmp_path, record):
    for title in ("#### ~~2. Dinner with the board~~", "##### [x] Dinner with the board", "**~~3. Dinner with the board~~**",
                  "**[x] 3. Dinner with the board**\n"):
        code, out, refusal = record(workspace(tmp_path, title + "\n" + OPTIONS))
        assert code == 0 and "choices: 0 open" in out, (title, refusal)
    code, _, refusal = record(workspace(tmp_path, "#### ~~1. Lunch~~\n" + OPTIONS + "\n#### 2. Dinner on Friday\n" + OPTIONS))
    assert code != 0 and "Dinner on Friday" in refusal and "Lunch" not in refusal
    code, _, refusal = record(workspace(tmp_path, "**3. Dinner with the board**\n" + OPTIONS))
    assert code != 0 and "Dinner with the board" in refusal and "Decisions needed" not in refusal
    parted = "### ~~2. Dinner with the board~~\nIt was answered on Tuesday.\n\n#### Options\n" + OPTIONS
    code, out, refusal = record(workspace(tmp_path, parted))                                  # a heading that only says "Options" is no title
    assert code == 0 and "choices: 0 open" in out, refusal


def test_options_written_as_headings_or_as_rows_of_a_table_are_options(tmp_path, record):
    headed = "### 2. Dinner on Friday\n#### Option A: Accept\nGo.\n#### Option B: Decline\nStay.\n"
    code, _, refusal = record(workspace(tmp_path, headed))
    assert code != 0 and "Dinner on Friday" in refusal
    code, out, refusal = record(workspace(tmp_path, headed + COSTS + VIEW))
    assert code == 0 and "choices: 1 open" in out, refusal
    table = "### Dinner on Friday\n| Option | What |\n|---|---|\n| **Option A** | Accept |\n| **Option B** | Decline |\n"
    code, _, refusal = record(workspace(tmp_path, table))
    assert code != 0 and "Dinner on Friday" in refusal


def test_a_sentence_that_begins_with_the_word_is_no_option(tmp_path, record):
    notes = "### Notes from yesterday\nOption A was fine last time, so there is nothing to decide.\nOption B never came up.\n"
    code, out, refusal = record(workspace(tmp_path, notes))
    assert code == 0 and "choices: 0 open" in out, refusal
    for written in ("Option A: Accept\nOption B: Decline\n", "**Option A** Accept the invitation\n**Option B** Decline it\n",
                    "Option A) Accept\nOption B) Decline\n", "- Option A - Accept\n- Option B - Decline\n"):
        code, _, refusal = record(workspace(tmp_path, "### Dinner on Friday\n" + written))
        assert code != 0 and "Dinner on Friday" in refusal, written


@pytest.mark.parametrize("view", ["**Recommendation** - B, decline.\n", "**Recommended:** B, decline.\n", "**My recommendation:** B, decline.\n",
                                  "**Recommendation —** B, decline.\n", "#### Recommendation: B, decline\n"])
def test_a_recommendation_is_read_as_it_is_commonly_written(tmp_path, record, view):
    code, out, refusal = record(workspace(tmp_path, INVITATION + COSTS + view))
    assert code == 0 and "choices: 1 open" in out, refusal


def test_one_consequence_and_an_option_marked_as_the_recommended_one(tmp_path, record):
    code, out, refusal = record(workspace(tmp_path, INVITATION + COSTS.replace("Consequences", "Consequence") + VIEW))
    assert code == 0 and "choices: 1 open" in out, refusal
    marked = "### Dinner on Friday\n**Option A:** Accept\n**Option B (recommended):** Decline\n" + COSTS
    code, out, refusal = record(workspace(tmp_path, marked))
    assert code == 0 and "choices: 1 open" in out, refusal
    code, _, refusal = record(workspace(tmp_path, marked.replace(" (recommended)", " (not recommended)").replace(COSTS, "")))
    assert code != 0 and "consequences" in refusal                                            # a mark on an option is a view, never the costs


def test_a_closing_line_closes_only_when_it_says_what_was_decided(tmp_path, record):
    code, out, refusal = record(workspace(tmp_path, INVITATION + "**Decision:** B, declined on Wednesday\n"))
    assert code == 0 and "choices: 0 open" in out, refusal
    for blank in ("**Decided:**\n", "**Decision:** pending\n", "**Decided:** TBD\n", "**Decision needed:** by Friday\n"):
        code, _, refusal = record(workspace(tmp_path, INVITATION + blank))
        assert code != 0 and "book launch" in refusal, blank


# --- the eleventh review round (2026-11-12) -------------------------------------------------------------------
# Two choices under deeper headings, the first closed and the second lettered on from it (C and D after A and B),
# were read as one closed choice; a sentence between a closed title and its options hid the title; and
# "Recommendation: pending" counted as a recommendation, "Decision: undecided" as a decision.

def test_each_deeper_heading_is_its_own_choice_whatever_its_options_are_lettered(tmp_path, record):
    dinner = "#### Dinner with the board\n**Option A:** Accept\n**Option B:** Decline\n**Decision:** B, declined on Tuesday\n"
    lunch = "#### Lunch on Friday\n**Option C:** Accept\n**Option D:** Decline\n"
    code, _, refusal = record(workspace(tmp_path, dinner + "\n" + lunch))
    assert code != 0 and "Lunch on Friday" in refusal and "Dinner with the board" not in refusal, refusal
    code, out, refusal = record(workspace(tmp_path, dinner + "\n" + lunch + COSTS + VIEW))
    assert code == 0 and "choices: 1 open" in out, refusal
    bold = ("**Dinner with the board**\n**Option A:** Accept\n**Option B:** Decline\n**Decision:** B, declined\n\n"
            "**Lunch on Friday**\n**Option C:** Accept\n**Option D:** Decline\n")
    code, _, refusal = record(workspace(tmp_path, bold))
    assert code != 0 and "Lunch on Friday" in refusal and "Dinner with the board" not in refusal, refusal


def test_a_sentence_between_a_closed_title_and_its_options_leaves_it_closed(tmp_path, record):
    for title in ("#### ~~Dinner with the board~~", "#### [x] Dinner with the board", "**~~Dinner with the board~~**"):
        text = title + "\nIt was answered on Tuesday, by phone.\n\n" + OPTIONS
        code, out, refusal = record(workspace(tmp_path, text))
        assert code == 0 and "choices: 0 open" in out, (title, refusal)
    code, _, refusal = record(workspace(tmp_path, "#### Dinner with the board\nThe invitation came on Monday.\n\n" + OPTIONS))
    assert code != 0 and "Dinner with the board" in refusal and "Decisions needed" not in refusal, refusal   # and an open one is named by its own title


@pytest.mark.parametrize("blank", ["pending", "undecided", "Pending his answer", "to be decided", "not yet", "unknown", "?",
                                   "awaiting the venue's reply", "open"])
def test_a_recommendation_or_a_decision_that_says_nothing_yet_is_none(tmp_path, record, blank):
    code, _, refusal = record(workspace(tmp_path, INVITATION + COSTS + f"**Recommendation:** {blank}\n"))
    assert code != 0 and "recommendation" in refusal, blank
    code, _, refusal = record(workspace(tmp_path, INVITATION + f"**Decision:** {blank}\n"))
    assert code != 0 and "book launch" in refusal, blank


@pytest.mark.parametrize("view", ["Waiting costs nothing here, so B: decline.", "Open with a no: B, decline.", "B. Pending the venue, nothing else changes it."])
def test_a_recommendation_that_begins_with_such_a_word_and_says_more_is_one(tmp_path, record, view):
    code, out, refusal = record(workspace(tmp_path, INVITATION + COSTS + f"**Recommendation:** {view}\n"))
    assert code == 0 and "choices: 1 open" in out, (view, refusal)


def test_a_line_led_by_a_pictograph_is_still_its_line(tmp_path, record):
    """This project's probe: plans mark these lines with a pin, a pointing hand or a tick, and the mark hid the word."""
    code, out, refusal = record(workspace(tmp_path, INVITATION + "📌 " + COSTS + "👉 " + VIEW))
    assert code == 0 and "choices: 1 open" in out, refusal
    code, out, refusal = record(workspace(tmp_path, INVITATION + "✅ **Decision:** B, declined on Wednesday\n"))
    assert code == 0 and "choices: 0 open" in out, refusal
    code, _, refusal = record(workspace(tmp_path, INVITATION + "📌 " + COSTS + "👉 **Recommendation:** pending\n"))
    assert code != 0 and "recommendation" in refusal


# --- the twelfth review round (2026-11-12) --------------------------------------------------------------------

def test_a_fenced_example_that_begins_a_list_entry_is_an_example(tmp_path, record):
    """The fence opened on the line of the list mark (`- ```md`), so it was not seen as a fence and its options
    were read as a choice."""
    for mark in ("- ", "* ", "1. ", "- > "):
        text = "### How a choice is written\n" + mark + "```md\n  Option A: Accept\n  Option B: Decline\n  ```\n"
        code, out, refusal = record(workspace(tmp_path, text))
        assert code == 0 and "choices: 0 open" in out, (mark, refusal)
    code, _, refusal = record(workspace(tmp_path, "### Dinner\n- ```md\n  Option A: Accept\n  ```\n- **Option A:** Accept\n- **Option B:** Decline\n"))
    assert code != 0 and "Dinner" in refusal                                                    # what follows the example is still read
