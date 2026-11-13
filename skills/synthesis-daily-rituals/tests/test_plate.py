"""Everything open for a seat, in one list built from the records.

An audit of 2026-11-11 found one task living as many copies: in nine plans, a ledger, five register rows and three
packets, tied only by its Decay ID. One seat had answered that with a script of its own that builds, from the
sweep, a single list of everything open, so that nothing depends on memory or on which plan an item was last
copied into. This is that list for every seat: the critical deadlines, the dated items due and ahead, the
commitments with no date, the ledger's open rows and the choices put to the principal. Committed before the code.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
DAY = "2026-11-13"

PLAN = """# Friday

## Critical deadlines: needs your attention
### Renew the visa
**Critical:** visa
**Decays:** 2026-11-20 (the window closes)
**Decay ID:** visa-2026
**Calendar:** on the calendar

## Decisions needed
### 1. Dinner on Thursday?
**Option A:** Accept
**Option B:** Decline
**Recommendation:** **B**, it is the night before the trip

### 2. Rebase or merge?
**Option A:** Rebase
**Option B:** Merge
**Decided:** Option A — 2026-11-13T09:00

## Priority Tasks
1. **File the return**
   **Decays:** 2026-11-13 (due today)
   **Decay ID:** return-2026
2. **Book the room**
   **Decays:** 2026-12-01 (the block opens)
   **Decay ID:** room
3. **Call the landlord**
4. ~~**Renew the pass**~~ ✅ **DONE 09:10**

## Waiting On Others
- The vendor's quote, parked (they answer in January)
"""
OLD = """# Tuesday

## Priority Tasks
1. **Send the thanks**
   **Decays:** 2026-11-11 (two days after the event)
   **Decay ID:** thanks
"""
LEDGER = """| Item | To | Status | Owed since |
|---|---|---|---|
| Reply to the supplier | Pat | NEEDS_DRAFT | 2026-10-20 |
| Thanks for the review | Lee | SENT | 2026-11-08 |
"""


def seat(tmp_path: Path) -> dict:
    for folder, name, body in (("plans", f"{DAY}.md", PLAN), ("plans", "2026-11-10.md", OLD), ("drafts", "_LEDGER.md", LEDGER)):
        (tmp_path / folder).mkdir(exist_ok=True)
        (tmp_path / folder / name).write_text(body, encoding="utf-8")
    state = tmp_path / "state"
    state.mkdir(exist_ok=True)
    (state / "config.json").write_text(json.dumps({"workspaces": {"desk": {
        "plans_dirs": [str(tmp_path / "plans")], "records_dirs": [str(tmp_path / "drafts")]}}}), encoding="utf-8")
    return {**os.environ, "RITUAL_STATE_DIR": str(state), "SYNTHESIS_HOME": str(tmp_path / "home")}


def plate(tmp_path: Path, *extra):
    return subprocess.run([sys.executable, str(SCRIPTS / "plate.py"), "--workspace", "desk", "--as-of", DAY, *extra],
                          capture_output=True, text=True, env=seat(tmp_path))


def test_the_sweep_lists_the_open_dated_items_that_are_not_yet_due(tmp_path):
    env = seat(tmp_path)
    out = subprocess.run([sys.executable, str(SCRIPTS / "decay_sweep.py"), "--workspace", "desk", "--as-of", DAY, "--json"],
                         capture_output=True, text=True, env=env)
    report = json.loads(out.stdout)
    assert [(row["identity"], row["due_date"]) for row in report["ahead"]] == [("id:room", "2026-12-01")]
    assert sorted(row["identity"] for row in report["due"]) == ["id:return-2026", "id:thanks"]


def test_the_plate_holds_everything_open_and_nothing_closed(tmp_path):
    done = plate(tmp_path)
    assert done.returncode == 0, done.stderr
    text = done.stdout
    assert text.startswith(f"# Everything open for desk, as of {DAY}\n")
    order = [text.index(part) for part in ("## Critical deadlines (1)", "## Due or past (2)", "## Dated ahead (1)",
                                           "## Commitments with no date and no park (1)", "## Owed in a ledger (1)",
                                           "## Choices with no decision (1)")]
    assert order == sorted(order)
    for kept in ("Renew the visa", "`visa-2026`", "**File the return**", "`return-2026`", "**Send the thanks**",
                 "passed with nothing written", "**Book the room**", "2026-12-01", "**Call the landlord**",
                 "Reply to the supplier", "NEEDS_DRAFT", "since 2026-10-20", "Dinner on Thursday?"):
        assert kept in text, kept
    for gone in ("Renew the pass", "Thanks for the review", "Rebase or merge?", "The vendor's quote"):
        assert gone not in text, gone
    assert f"({tmp_path / 'plans' / (DAY + '.md')}:" in text                    # each entry says where it sits


def test_written_to_a_file_its_links_lead_from_that_file(tmp_path):
    out = tmp_path / "artifacts" / "plate.md"
    out.parent.mkdir()
    done = plate(tmp_path, "--out", str(out))
    assert done.returncode == 0 and done.stdout.strip() == f"written {out}: 7 open"
    assert f"](../plans/{DAY}.md)" in out.read_text(encoding="utf-8") and "](../drafts/_LEDGER.md)" in out.read_text(encoding="utf-8")


def test_a_list_of_everything_is_not_built_over_records_that_could_not_be_read(tmp_path):
    seat(tmp_path)
    (tmp_path / "plans" / "2026-11-09.md").write_text("# Plan\n\n### A broken one\n**Decays:** someday (x)\n**Decay ID:** broken\n", encoding="utf-8")
    refused = plate(tmp_path)
    assert refused.returncode == 2 and refused.stdout == "" and "not taken in full" in refused.stderr and "2026-11-09.md" in refused.stderr
    asked = plate(tmp_path, "--with-gaps")
    assert asked.returncode == 0 and "## Not read (1)" in asked.stdout and asked.stdout.index("## Not read (1)") < asked.stdout.index("## Critical deadlines")


def test_a_workspace_that_declares_no_folders_has_no_plate(tmp_path):
    env = seat(tmp_path)
    (tmp_path / "state" / "config.json").write_text(json.dumps({"workspaces": {"desk": {}}}), encoding="utf-8")
    done = subprocess.run([sys.executable, str(SCRIPTS / "plate.py"), "--workspace", "desk", "--as-of", DAY], capture_output=True, text=True, env=env)
    assert done.returncode == 2 and "declares no plan folders" in done.stderr


# --- the first review -------------------------------------------------------------------------------------------------

def test_a_ledger_row_too_short_to_read_is_a_gap_for_a_list_of_everything(tmp_path):
    """Finding 8: the list left such a row out and said that nothing had gone unread."""
    seat(tmp_path)
    (tmp_path / "drafts" / "_LEDGER.md").write_text(LEDGER + "| A short one | Sam |\n", encoding="utf-8")
    refused = subprocess.run([sys.executable, str(SCRIPTS / "plate.py"), "--workspace", "desk", "--as-of", DAY], capture_output=True, text=True,
                             env={**os.environ, "RITUAL_STATE_DIR": str(tmp_path / "state"), "SYNTHESIS_HOME": str(tmp_path / "home")})
    assert refused.returncode == 2 and "1 row(s) of a ledger" in refused.stderr, refused.stderr
    asked = subprocess.run([sys.executable, str(SCRIPTS / "plate.py"), "--workspace", "desk", "--as-of", DAY, "--with-gaps"], capture_output=True, text=True,
                           env={**os.environ, "RITUAL_STATE_DIR": str(tmp_path / "state"), "SYNTHESIS_HOME": str(tmp_path / "home")})
    assert asked.returncode == 0 and "## Not read (1)" in asked.stdout and "1 row(s) of a ledger" in asked.stdout


def test_an_item_with_no_id_copied_into_two_plans_is_listed_once_and_said(tmp_path):
    """Finding 8: each copy of an item with no ID is another item to the sweep, and the list showed the task twice."""
    env = seat(tmp_path)
    for day in ("2026-11-08", "2026-11-09"):
        (tmp_path / "plans" / f"{day}.md").write_text("# Plan\n\n## Priority Tasks\n1. **Pay the invoice**\n   **Decays:** 2026-11-07 (net 30)\n", encoding="utf-8")
    done = subprocess.run([sys.executable, str(SCRIPTS / "plate.py"), "--workspace", "desk", "--as-of", DAY], capture_output=True, text=True, env=env)
    assert done.returncode == 0, done.stderr
    assert done.stdout.count("**Pay the invoice**") == 1 and "2 copies with no Decay ID" in done.stdout and "## Due or past (3)" in done.stdout


def test_what_reads_like_a_critical_deadline_and_is_not_classified_is_said(tmp_path):
    """Finding 8: the sweep flags an untagged deadline that reads like a critical class, and the list dropped the flag."""
    env = seat(tmp_path)
    (tmp_path / "plans" / "2026-11-12.md").write_text("# Plan\n\n## Priority Tasks\n1. **Renew the passport**\n   **Decays:** 2026-12-10 (it runs out)\n"
                                                    "   **Decay ID:** passport\n", encoding="utf-8")
    done = subprocess.run([sys.executable, str(SCRIPTS / "plate.py"), "--workspace", "desk", "--as-of", DAY], capture_output=True, text=True, env=env)
    assert done.returncode == 0 and "## Possibly critical, not classified (1)" in done.stdout and "**Renew the passport**" in done.stdout.split(
        "## Possibly critical, not classified (1)")[1].split("##")[0]


def test_the_list_is_never_written_over_a_plan_or_over_a_file_that_is_not_a_list(tmp_path):
    """Finding 9: `--out` replaced whatever it named, today's plan included."""
    seat(tmp_path)
    plan = tmp_path / "plans" / f"{DAY}.md"
    over_a_plan = plate(tmp_path, "--out", str(plan))
    assert over_a_plan.returncode == 2 and "a folder this workspace declares" in over_a_plan.stderr and plan.read_text(encoding="utf-8") == PLAN
    notes = tmp_path / "artifacts" / "notes.md"
    notes.parent.mkdir()
    notes.write_text("# My notes\n", encoding="utf-8")
    over_notes = plate(tmp_path, "--out", str(notes))
    assert over_notes.returncode == 2 and "is not a list this script wrote" in over_notes.stderr and notes.read_text(encoding="utf-8") == "# My notes\n"
    out = tmp_path / "artifacts" / "plate.md"
    assert plate(tmp_path, "--out", str(out)).returncode == 0 and plate(tmp_path, "--out", str(out)).returncode == 0   # its own list is written again


def test_a_folder_that_is_not_there_is_a_refusal_and_not_a_traceback(tmp_path):
    """Finding 10."""
    done = plate(tmp_path, "--out", str(tmp_path / "nowhere" / "plate.md"))
    assert done.returncode == 2 and "Traceback" not in done.stderr and "could not be written" in done.stderr


def test_a_workspace_that_keeps_no_dated_plans_is_told_so(tmp_path):
    """Finding 16: it was refused over a gap with no path, and `--with-gaps` built a list over nothing."""
    env = seat(tmp_path)
    (tmp_path / "state" / "config.json").write_text(json.dumps({"workspaces": {"desk": {"plans_dirs": []}}}), encoding="utf-8")
    for extra in ((), ("--with-gaps",)):
        done = subprocess.run([sys.executable, str(SCRIPTS / "plate.py"), "--workspace", "desk", "--as-of", DAY, *extra], capture_output=True, text=True, env=env)
        assert done.returncode == 2 and "keeps no dated plans" in done.stderr and done.stdout == "", extra


def test_a_choice_is_listed_with_the_line_it_stands_on_and_a_path_with_spaces_is_a_link(tmp_path):
    """The list says each entry with where it sits; a choice had its file and no line. Finding 12: a folder with a
    space in its name made no link."""
    done = plate(tmp_path)
    assert f"Dinner on Thursday? ({tmp_path / 'plans' / (DAY + '.md')}:11)" in done.stdout
    out = tmp_path / "my artifacts" / "plate.md"
    out.parent.mkdir()
    assert plate(tmp_path, "--out", str(out)).returncode == 0
    assert f"]({'../plans/' + DAY + '.md'})" in out.read_text(encoding="utf-8")
    spaced = tmp_path / "artifacts"
    spaced.mkdir()
    (tmp_path / "plans").rename(tmp_path / "my plans")
    (tmp_path / "state").mkdir(exist_ok=True)
    (tmp_path / "state" / "config.json").write_text(json.dumps({"workspaces": {"desk": {"plans_dirs": [str(tmp_path / "my plans")]}}}), encoding="utf-8")
    done = subprocess.run([sys.executable, str(SCRIPTS / "plate.py"), "--workspace", "desk", "--as-of", DAY, "--out", str(spaced / "plate.md")],
                          capture_output=True, text=True, env={**os.environ, "RITUAL_STATE_DIR": str(tmp_path / "state"), "SYNTHESIS_HOME": str(tmp_path / "home")})
    assert done.returncode == 0, done.stderr
    assert f"](<../my plans/{DAY}.md>)" in (spaced / "plate.md").read_text(encoding="utf-8")


# --- the second review ------------------------------------------------------------------------------------------------

def swept(tmp_path: Path, env: dict, *extra):
    return subprocess.run([sys.executable, str(SCRIPTS / "plate.py"), "--workspace", "desk", "--as-of", DAY, *extra],
                          capture_output=True, text=True, env=env)


def test_out_is_refused_in_a_declared_folder_written_from_the_home_folder_and_as_that_folder_itself(tmp_path):
    """A folder the config writes with `~` was compared unexpanded, so the list was written into a folder it is read
    from; and the folder itself, named as `--out`, was not taken to be inside it."""
    env = seat(tmp_path)
    home = tmp_path / "house"
    (home / "records").mkdir(parents=True)
    (tmp_path / "state" / "config.json").write_text(json.dumps({"workspaces": {"desk": {
        "plans_dirs": [str(tmp_path / "plans")], "records_dirs": ["~/records"]}}}), encoding="utf-8")
    for named in ("~/records/plate.md", "~/records"):
        done = swept(tmp_path, {**env, "HOME": str(home)}, "--out", named)
        assert done.returncode == 2 and "a folder this workspace declares" in done.stderr, (named, done.returncode, done.stderr)
    assert list((home / "records").iterdir()) == []


def test_two_items_of_one_title_and_date_in_one_plan_are_two_entries_each_merged_across_plans(tmp_path):
    """Copies of an item with no Decay ID were merged by title and date alone, so two different calls in one plan were
    one entry said as copies. The first of a title and date in one plan pairs with the first in another plan, the
    second with the second, and each entry names its own place."""
    env = seat(tmp_path)
    twice = ("# Plan\n\n## Priority Tasks\n1. **Call the bank**\n   **Decays:** 2026-11-10 (about the card)\n"
             "2. **Call the bank**\n   **Decays:** 2026-11-10 (about the loan)\n")
    for day in ("2026-11-11", "2026-11-12"):
        (tmp_path / "plans" / f"{day}.md").write_text(twice, encoding="utf-8")
    done = swept(tmp_path, env)
    assert done.returncode == 0, done.stderr
    due = done.stdout.split("## Due or past")[1].split("\n## ")[0]
    assert due.count("**Call the bank**") == 2 and due.count("2 copies with no Decay ID") == 2, due
    newest = tmp_path / "plans" / "2026-11-12.md"
    assert f"({newest}:5)" in due and f"({newest}:7)" in due, due                  # each at its own Decays line


def test_a_merged_entry_is_passed_only_where_no_copy_carries_a_mark_and_stands_at_its_newest_copy(tmp_path):
    """The second review: the merged entry took the oldest copy's flag and place. The third: said passed wherever any
    copy was, it named a lapse already marked on the newest copy as one nobody was told of. An item is read as the sweep
    reads one with an ID: announced where any copy carries a mark for its date, and placed at its newest copy."""
    env = seat(tmp_path)
    plans = tmp_path / "plans"
    bare = "# Plan\n\n## Priority Tasks\n1. **Pay the invoice**\n   **Decays:** 2026-11-05 (net 30)\n"
    marked = bare + "   **Lapsed:** 2026-11-06 (passed with no decision)\n"

    def line_for(*plan_texts):
        for day, body in zip(("2026-11-06", "2026-11-07", "2026-11-08"), plan_texts):
            (plans / f"{day}.md").write_text(body, encoding="utf-8")
        done = swept(tmp_path, env)
        assert done.returncode == 0, done.stderr
        return next(line for line in done.stdout.splitlines() if "**Pay the invoice**" in line)

    assert line_for("# Plan\n", marked, bare) == f"- 2026-11-05 **Pay the invoice**, 2 copies with no Decay ID ({plans / '2026-11-08.md'}:5)"
    assert line_for(bare, bare, marked) == f"- 2026-11-05 **Pay the invoice**, 3 copies with no Decay ID ({plans / '2026-11-08.md'}:5)"
    assert line_for(marked, marked, marked) == f"- 2026-11-05 **Pay the invoice**, 3 copies with no Decay ID ({plans / '2026-11-08.md'}:5)"
    assert line_for(bare, bare, bare) == (
        f"- 2026-11-05 **Pay the invoice**, passed with nothing written, 3 copies with no Decay ID ({plans / '2026-11-08.md'}:5)")


def test_a_choice_is_placed_at_the_line_it_opens_on_and_not_at_an_earlier_line_that_reads_the_same(tmp_path):
    """The line came from the first place the plan's text held the choice's first line: a summary near the top that
    repeats it. A fenced example above the choice must not move the line either."""
    env = seat(tmp_path)
    plan = tmp_path / "plans" / f"{DAY}.md"
    text = PLAN.replace("# Friday\n\n", "# Friday\n\n## Summary\n- 1. Dinner on Thursday? (one choice is open)\n\n"
                        "```text\n### 1. An example heading\n**Option A:** kept as written\n```\n\n", 1)
    plan.write_text(text, encoding="utf-8")
    line = text.splitlines().index("### 1. Dinner on Thursday?") + 1
    done = swept(tmp_path, env)
    assert done.returncode == 0, done.stderr
    assert f"Dinner on Thursday? ({plan}:{line})" in done.stdout, done.stdout.split("## Choices with no decision")[-1]


def test_a_gap_names_its_ledger_and_its_line(tmp_path):
    """The second review: a row too short to read was said of `a ledger`, and a seat with several could not tell
    which to mend; a gap on a line of a plan was said without its line."""
    env = seat(tmp_path)
    ledger = tmp_path / "drafts" / "_LEDGER.md"
    ledger.write_text(LEDGER + "| A short one | Sam |\n", encoding="utf-8")
    broken = tmp_path / "plans" / "2026-11-09.md"
    broken.write_text("# Plan\n\n### A broken one\n**Decays:** someday (x)\n**Decay ID:** broken\n", encoding="utf-8")
    refused = subprocess.run([sys.executable, str(SCRIPTS / "plate.py"), "--workspace", "desk", "--as-of", DAY],
                             capture_output=True, text=True, env=env)                # `plate` would write the seat's ledger again
    assert refused.returncode == 2 and f"  {ledger}: 1 row(s) of a ledger" in refused.stderr, refused.stderr
    assert f"  {broken}: invalid Decays date (line 4)" in refused.stderr, refused.stderr


def test_an_item_with_no_id_dated_ahead_is_listed_once_with_its_copies(tmp_path):
    """The third review: each plan's copy was its own entry under Dated ahead, and the count of what is open grew with
    every plan that carried it."""
    env = seat(tmp_path)
    for day in ("2026-11-10", "2026-11-11", "2026-11-12"):
        (tmp_path / "plans" / f"{day}.md").write_text("# Plan\n\n## Priority Tasks\n1. **Renew the lease**\n   **Decays:** 2026-12-01 (a month out)\n",
                                                       encoding="utf-8")
    done = swept(tmp_path, env)
    assert done.returncode == 0, done.stderr
    ahead = done.stdout.split("## Dated ahead")[1].split("\n## ")[0]
    assert ahead.count("**Renew the lease**") == 1 and "3 copies with no Decay ID" in ahead, ahead
    assert f"({tmp_path / 'plans' / '2026-11-12.md'}:5)" in ahead, ahead


@pytest.mark.skipif(sys.platform != "darwin", reason="a folder named in another case is the same folder only where names are compared so")
def test_out_in_a_declared_folder_named_in_another_case_is_refused(tmp_path):
    """The third review: on a volume that compares names without case, `PLANS/` is `plans/`, and the list was written
    among the plans, where the next sweep read it as a plan dated ahead."""
    env = seat(tmp_path)
    if not (tmp_path / "PLANS").exists():
        pytest.skip("this volume compares names with case")
    out = tmp_path / "PLANS" / "2026-11-14.md"
    done = swept(tmp_path, env, "--out", str(out))
    assert done.returncode == 2 and "a folder this workspace declares" in done.stderr, done.stderr
    assert sorted(path.name for path in (tmp_path / "plans").iterdir()) == sorted(["2026-11-10.md", f"{DAY}.md"])
