"""The lapse register, read for the weekly and the longer reviews.

Each workspace keeps a register of what slipped: one row for each item that passed its date with no decision. The
Friday review reads its last fourteen days and the quarterly, six-month and annual reviews their whole window, and
until now no script read it: whichever session ran a review started from the file. Counted on 2026-11-13, the three
seats' registers held 64, 355 and 1 rows, one table each, five cells a row. This gives a review its section from
the register, counted: the rows of the window, and what repeats among them. Committed before the code.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "lapse_review.py"
DAY = "2026-11-13"  # a Friday
REGISTER = """# Lapse register

Permanent history: append rows, never remove or rewrite them.

| Lapsed | Item | Where it waited | Why it lapsed | Outcome |
|---|---|---|---|---|
| 2026-08-03 | An old acknowledgment | [plan](../daily-plans/2026-08-01.md) | no time | let go after its date |
| 2026-10-26 | Reply to the supplier `supplier-quote` | [plan](../daily-plans/2026-10-24.md) | travel | sent 10-28 |
| 2026-11-02 | Reply to the supplier `supplier-quote` | `daily-plans/2026-11-01.md:40` | no answer drafted | |
| 2026-11-02 | Thanks for the review `thanks-review` | [draft](../drafts/2026-10-30-thanks.md) | waited on a name | open |
| 2026-11-09 | The event decision | daily-plans/2026-11-07.md | the date passed over a weekend | pending |

- 2026-11-03: the row of 2026-08-03 was added late, from the August plans.

| Lapsed | Item | Where it waited | Why it lapsed | Outcome | Who it affected | What can still be done |
|---|---|---|---|---|---|---|
| 2026-11-09 | Reply to the supplier `supplier-quote` | [plan](../daily-plans/2026-11-08.md) | third time | open | the supplier | call them |
| 2026-11-10 | A registration | [ledger](../drafts/_LEDGER.md) | the window closed | let go after its date | nobody | nothing |
"""


def review(tmp_path: Path, *extra, register: str | None = REGISTER, declare: bool = True):
    state, file = tmp_path / "state", tmp_path / "records" / "lapse-register.md"
    state.mkdir(exist_ok=True)
    file.parent.mkdir(exist_ok=True)
    if register is not None:
        file.write_text(register, encoding="utf-8")
    elif file.exists():
        file.unlink()
    (state / "config.json").write_text(json.dumps({"workspaces": {"desk": {"lapse_register": str(file)} if declare else {}}}), encoding="utf-8")
    return subprocess.run([sys.executable, str(SCRIPT), "--workspace", "desk", "--as-of", DAY, *extra], capture_output=True, text=True,
                          env={**os.environ, "RITUAL_STATE_DIR": str(state), "SYNTHESIS_HOME": str(tmp_path / "home")})


def test_the_weekly_window_is_the_last_fourteen_days_from_both_tables(tmp_path):
    done = review(tmp_path)
    assert done.returncode == 0, done.stderr
    lines = done.stdout.splitlines()
    assert lines[0] == f"Slipped through: 5 lapses from 2026-10-31 to {DAY} (7 rows in the register)"
    rows = [line for line in lines if line.startswith("  | ")]
    assert [row.split("|")[1].strip() for row in rows] == ["2026-11-10", "2026-11-09", "2026-11-09", "2026-11-02", "2026-11-02"]   # newest first
    assert "An old acknowledgment" not in done.stdout and "sent 10-28" not in done.stdout


def test_it_names_what_repeats_and_counts_it(tmp_path):
    out = review(tmp_path).stdout
    assert "  the same item more than once: `supplier-quote` (2)" in out
    assert "  the weekday it was recorded on: Monday (4)" in out
    assert "  where it waited: daily-plans (3)" in out
    assert "  outcome still open: 4 of 5" in out
    assert "Tuesday" not in out and "drafts (" not in out                        # once or twice is no pattern


def test_a_longer_window_reads_further_back(tmp_path):
    quarter = review(tmp_path, "--window", "quarter").stdout
    assert quarter.splitlines()[0] == f"Slipped through: 6 lapses from 2026-08-14 to {DAY} (7 rows in the register)"
    assert "`supplier-quote` (3)" in quarter and "the weekday it was recorded on: Monday (5)" in quarter
    assert review(tmp_path, "--window", "year").stdout.splitlines()[0].startswith("Slipped through: 7 lapses from 2025-11-13")
    between = review(tmp_path, "--since", "2026-08-01", "--until", "2026-10-31").stdout
    assert between.splitlines()[0] == "Slipped through: 2 lapses from 2026-08-01 to 2026-10-31 (7 rows in the register)"
    assert "Patterns: none repeats" in between


def test_a_window_with_no_row_says_so(tmp_path):
    out = review(tmp_path, "--since", "2026-09-01", "--until", "2026-09-30").stdout
    assert out.splitlines() == ["Slipped through: 0 lapses from 2026-09-01 to 2026-09-30 (7 rows in the register)"]


def test_the_same_as_json(tmp_path):
    data = json.loads(review(tmp_path, "--json").stdout)
    assert (data["since"], data["until"], data["total"], len(data["rows"])) == ("2026-10-31", DAY, 7, 5)
    assert data["patterns"] == {"item": {"supplier-quote": 2}, "weekday": {"Monday": 4}, "place": {"daily-plans": 3}, "open": 4}
    assert data["rows"][0] == {"lapsed": "2026-11-10", "item": "A registration", "where": "[ledger](../drafts/_LEDGER.md)",
                               "why": "the window closed", "outcome": "let go after its date", "affected": "nobody", "still": "nothing",
                               "line": 18}


def test_it_writes_nothing(tmp_path):
    review(tmp_path)
    before = {p: p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}
    review(tmp_path, "--window", "year", "--json")
    assert {p: p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()} == before


def test_a_register_it_cannot_read_is_said_and_never_read_as_empty(tmp_path):
    undeclared = review(tmp_path, declare=False)
    assert undeclared.returncode == 2 and "lapse_register" in undeclared.stderr and undeclared.stdout == ""
    missing = review(tmp_path, register=None)
    assert missing.returncode == 2 and "is no file" in missing.stderr
    tableless = review(tmp_path, register="# Lapse register\n\nNothing yet.\n")
    assert tableless.returncode == 2 and "holds no register table" in tableless.stderr
    backwards = review(tmp_path, "--since", "2026-11-10", "--until", "2026-11-01")
    assert backwards.returncode == 2 and "before" in backwards.stderr


def test_rows_appended_beneath_a_note_are_still_the_registers_rows(tmp_path):
    """Run on a real register on 2026-11-13, the first form read 14 of its 64 rows: rows had been appended beneath
    the notes under the table, where Markdown no longer shows them as its rows. A register is append-only, so a row
    is wherever a line opens with a pipe and a day, after the register's header."""
    register = ("# Lapse register\n\n| Lapsed | Item | Where it waited | Why it lapsed | Outcome |\n|---|---|---|---|---|\n"
                "| 2026-11-02 | First | daily-plans/2026-11-01.md | a | open |\n\n- 2026-11-03: a note about the first row.\n\n"
                "| 2026-11-09 | Second | daily-plans/2026-11-08.md | b | open |\n| 2026-11-10 | Third | daily-plans/2026-11-09.md | c | open |\n\n"
                "Another paragraph.\n| 2026-11-11 | Fourth | daily-plans/2026-11-10.md | d | open |\n\n"
                "| Day | Count |\n|---|---|\n| 2026-11-12 | 3 |\n")
    data = json.loads(review(tmp_path, "--json", register=register).stdout)
    assert [row["item"] for row in data["rows"]] == ["Fourth", "Third", "Second", "First"] and data["total"] == 4


# --- the first review -------------------------------------------------------------------------------------------------

HEAD = "# Lapse register\n\n| Lapsed | Item | Where it waited | Why it lapsed | Outcome |\n|---|---|---|---|---|\n"


def test_the_item_that_repeats_is_named_by_its_id_and_not_by_code_in_its_title(tmp_path):
    """Finding 5: a title that holds inline code was grouped by that code, and neither real ID was counted."""
    register = HEAD + ("| 2026-11-03 | Fix the `config.json` loader `load-fix` | daily-plans/2026-11-02.md | a | open |\n"
                       "| 2026-11-04 | Document the `config.json` keys `doc-keys` | daily-plans/2026-11-03.md | b | open |\n"
                       "| 2026-11-06 | Fix the `config.json` loader `load-fix` | daily-plans/2026-11-05.md | c | open |\n")
    data = json.loads(review(tmp_path, "--json", register=register).stdout)
    assert data["patterns"]["item"] == {"load-fix": 2}


def test_what_came_of_a_lapse_is_read_from_its_last_row(tmp_path):
    """A row is never rewritten, so what came of a lapse is a later row for the same item and the same day: the
    lapse is one, and its outcome is the last one written."""
    register = HEAD + ("| 2026-11-03 | Reply to the supplier `quote` | daily-plans/2026-11-02.md | a | open |\n"
                       "| 2026-11-06 | Thanks for the review `thanks` | daily-plans/2026-11-05.md | b | open |\n"
                       "| 2026-11-03 | Reply to the supplier `quote` | daily-plans/2026-11-02.md | a | sent late on 11-07 |\n")
    data = json.loads(review(tmp_path, "--json", register=register).stdout)
    assert [(row["item"], row["outcome"]) for row in data["rows"]] == [("Thanks for the review `thanks`", "open"),
                                                                       ("Reply to the supplier `quote`", "sent late on 11-07")]
    assert data["patterns"]["item"] == {} and data["patterns"]["open"] == 1 and data["total"] == 3
    text = review(tmp_path, register=register).stdout
    assert text.splitlines()[0] == f"Slipped through: 2 lapses from 2026-10-31 to {DAY} (3 rows in the register)"


def test_a_day_written_with_emphasis_is_read_and_a_row_whose_day_cannot_be_read_is_said(tmp_path):
    """Finding 7: rows whose day stood in bold, in a link or in code were dropped without a word, and so was a day
    that does not exist; a table of two columns beneath a note was counted as lapses."""
    register = HEAD + ("| **2026-11-03** | Bold day | daily-plans/a.md | a | open |\n| [2026-11-04](../daily-plans/2026-11-04.md) | Linked day | b.md | b | open |\n"
                       "| `2026-11-05` | Code day | c.md | c | open |\n| 2026-11-31 | No such day | d.md | d | open |\n| soon | No day | e.md | e | open |\n\n"
                       "- 2026-11-10: totals, kept by hand.\n\n| 2026-11-09 | 4 lapses |\n| 2026-11-10 | 2 lapses |\n")
    done = review(tmp_path, register=register)
    assert done.returncode == 0, done.stderr
    assert "Slipped through: 3 lapses" in done.stdout and "2 row(s) of the register could not be read" in done.stdout and "lines 8, 9" in done.stdout
    data = json.loads(review(tmp_path, "--json", register=register).stdout)
    assert [row["item"] for row in data["rows"]] == ["Code day", "Linked day", "Bold day"] and data["unread"] == [8, 9] and data["total"] == 3


def test_the_place_is_the_folder_that_says_what_kind_of_record_it_was_not_a_month(tmp_path):
    """Finding 14: plans kept in month folders gave every row of a month the place `2026-11`. Finding 12: a link
    written between angle brackets, as a path with spaces has to be, gave `..`."""
    register = HEAD + "".join(f"| 2026-11-0{n} | Item {n} | [plan](../daily-plans/2026-11/2026-11-0{n}.md) | a | open |\n" for n in (3, 4, 5)) + (
        "".join(f"| 2026-11-06 | Item 6{which} | [plan](<../My  drafts/2026-11-06.md>) | a | open |\n" for which in "abc"))  # three items: one row thrice is one lapse
    data = json.loads(review(tmp_path, "--json", register=register).stdout)
    assert data["patterns"]["place"] == {"daily-plans": 3, "My  drafts": 3}


def test_a_window_and_a_first_day_together_are_refused_and_a_bad_day_names_its_flag(tmp_path):
    """Finding 16."""
    both = review(tmp_path, "--window", "year", "--since", "2026-11-01")
    assert both.returncode == 2 and "--window" in both.stderr and "--since" in both.stderr
    bad = review(tmp_path, "--since", "2026-13-01")
    assert bad.returncode == 2 and "--since" in bad.stderr
    late = review(tmp_path, "--until", "tomorrow")
    assert late.returncode == 2 and "--until" in late.stderr


def test_the_weekday_is_said_to_be_the_day_a_lapse_was_recorded(tmp_path):
    """Finding 16: the day in a row is the day the lapse was written down, so a weekend's slips show as Monday."""
    register = HEAD + "".join(f"| 2026-11-{day} | Item {day} | daily-plans/x.md | a | sent |\n" for day in ("02", "09")) + (
        "| 2026-10-26 | Item 26 | daily-plans/y.md | a | sent |\n")
    text = review(tmp_path, "--window", "quarter", register=register).stdout
    assert "the weekday it was recorded on: Monday (3)" in text
