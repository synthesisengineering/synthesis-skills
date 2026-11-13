"""A seat's tasks, read by code where a rule asked an agent to remember (an audit of 2026-11-11, gaps 2, 3, 7, 8).

Counted on three seats' real plans on 2026-11-13 before anything here refused: the commitments with no deadline
tag and no park stood under the task and waiting headings (12, 0 and 9 in the newest plans) and no seat used task
boxes; every open dated item already carried a Decay ID; in a seat that runs its rituals no date ever showed as
passed, because each day's ritual re-dates what it carries, so a passed date exists only where no ritual ran; and
one seat kept a correspondence ledger, a table with a status and an owed-since column, 341 rows that nothing read.
Committed before the code.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import date
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
SWEEP = SCRIPTS / "decay_sweep.py"
sys.path.insert(0, str(SCRIPTS))
import ritual_state  # noqa: E402

DAY = "2026-11-13"
TAG = "\n   **Decays:** 2026-11-20 (chase it then)\n   **Decay ID:** {}\n"


def write(folder: Path, name: str, body: str) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / name
    path.write_text(body, encoding="utf-8")
    return path


def sweep(tmp_path: Path, *extra, as_of=DAY, json_out=True, env=None):
    roots = [word for flag, name in (("--plans-dir", "plans"), ("--artifacts-dir", "workers"), ("--records-dir", "drafts"))
             if (tmp_path / name).is_dir() for word in (flag, str(tmp_path / name))]
    proc = subprocess.run([sys.executable, str(SWEEP), "--as-of", as_of, *roots, *(["--json"] if json_out else []), *extra],
                          capture_output=True, text=True, env={**os.environ, "SYNTHESIS_HOME": str(tmp_path / "home"), **(env or {})})
    assert proc.stdout, proc.stderr
    return proc.returncode, json.loads(proc.stdout) if json_out else proc.stdout


PLAN = """# Daily Action Plan: tasks for Friday

1. A numbered line under the plan's own title is no commitment.

## Priority Tasks

### Do today: not negotiable
1. **File the return** before the window closes{filed}
2. **Call the landlord**
3. ~~**Renew the pass**~~ ✅ **DONE 09:10**

### Later, no date
- Sort the garage, parked (waits for spring)
- Sell the bike, parked
- Frame the print, parked ( )
- Fix the gate
  **Parked:** until the fence is done

## Waiting On Others
- The vendor's quote, asked on Monday
- [x] The bank's letter

## Carried Items
- Library books{carried}

## Things to Know
- The office is closed on Monday.

## Sync state
1. Mail read to 09:00.
"""


def titles(report):
    return [row["title"] for row in report["untagged"]]


# --- gap 2: a commitment with no date and no park ---------------------------------------------------------------------

def test_an_open_entry_under_a_task_waiting_or_carried_heading_needs_a_date_or_a_park(tmp_path):
    plan = write(tmp_path / "plans", f"{DAY}.md", PLAN.format(filed=TAG.format("return-2026"), carried=""))
    code, report = sweep(tmp_path)
    assert code == 0 and report["status"] == "REVIEW"
    assert titles(report) == ["**Call the landlord**", "Sell the bike, parked", "Frame the print, parked ( )",
                              "The vendor's quote, asked on Monday", "Library books"]
    first = report["untagged"][0]
    assert first["path"] == str(plan) and first["line"] == 12 and first["section"] == "Do today: not negotiable"


def test_every_commitment_dated_or_parked_leaves_nothing_to_review(tmp_path):
    body = PLAN.format(filed=TAG.format("return-2026"), carried=TAG.format("photos"))
    for old, new in (("2. **Call the landlord**", "2. **Call the landlord**" + TAG.format("landlord")),
                     ("- Sell the bike, parked\n", "- Sell the bike, parked (no buyer before spring)\n"),
                     ("- Frame the print, parked ( )\n", "- Frame the print\n  **Critical:** no\n  **Decays:** 2026-12-01 (the framer closes)\n  **Decay ID:** print\n"),
                     ("- The vendor's quote, asked on Monday\n", "- The vendor's quote, asked on Monday" + TAG.format("quote").replace("\n   ", "\n  "))):
        assert old in body
        body = body.replace(old, new)
    write(tmp_path / "plans", f"{DAY}.md", body)
    code, report = sweep(tmp_path)
    assert report["untagged"] == [] and report["no_id"] == [] and report["status"] == "CLEAR", report["untagged"]


def test_the_newest_plan_is_the_one_read_for_commitments(tmp_path):
    """A seat's commitments stand in its newest plan until a newer one is written: on a day with no ritual they are
    still open (counted 2026-11-13: one seat's newest plan was a day old and held nine). An older plan was held to
    the rule on its own day, and a plan dated ahead is not read."""
    write(tmp_path / "plans", "2026-11-12.md", "# Plan\n\n## Priority Tasks\n1. **An old line**\n")
    write(tmp_path / "plans", f"{DAY}.md", "# Plan\n\n## Priority Tasks\n1. **Today's line**\n")
    assert titles(sweep(tmp_path)[1]) == ["**Today's line**"]
    assert titles(sweep(tmp_path, as_of="2026-11-16")[1]) == ["**Today's line**"]   # no plan since: it is still the seat's plan
    assert titles(sweep(tmp_path, as_of="2026-11-12")[1]) == ["**An old line**"]


def test_a_seat_that_keeps_a_dated_plan_is_read_there_and_not_in_its_rituals_artifacts(tmp_path):
    write(tmp_path / "plans", "2026-11-12.md", "# Plan\n\n## Priority Tasks\n1. **The plan's line**\n")
    write(tmp_path / "workers", f"{DAY}-day-start.md", "# Start\n\n## Carried Items\n- A worker's line\n")
    assert titles(sweep(tmp_path)[1]) == ["**The plan's line**"]


def test_a_seat_whose_plan_is_a_rituals_artifact_is_read_at_its_newest_of_the_day(tmp_path):
    write(tmp_path / "workers", f"{DAY}-day-start.md", "# Start\n\n## Carried Items\n- Morning's line\n")
    write(tmp_path / "workers", f"{DAY}-day-end.md", "# End\n\n## Carried Items\n- Evening's line\n")
    assert titles(sweep(tmp_path)[1]) == ["Evening's line"]
    write(tmp_path / "workers", f"{DAY}-midday-2.md", "# Mid\n\n## Waiting On Others\n- Noon's line\n")
    assert titles(sweep(tmp_path)[1]) == ["Evening's line"]                      # the day-end is the day's last word


def test_the_text_report_counts_the_commitments_and_names_each(tmp_path):
    write(tmp_path / "plans", f"{DAY}.md", PLAN.format(filed="", carried=""))
    _, out = sweep(tmp_path, json_out=False)
    assert "Commitments with no date and no park: 6 in the newest plan" in out
    assert f"  **File the return** before the window closes ({tmp_path / 'plans' / (DAY + '.md')}:8)" in out


# --- gap 7: a dated item with no Decay ID ----------------------------------------------------------------------------

def test_an_open_dated_item_with_no_decay_id_is_listed(tmp_path):
    write(tmp_path / "plans", "2026-11-12.md", "# Plan\n\n### Pay the invoice\n**Decays:** 2026-11-30 (net 30)\n\n"
          "### Closed one\n**Decays:** 2026-11-30 (x)\n**Resolved:** 2026-11-12 (paid)\n\n"
          "### With its ID\n**Decays:** 2026-11-30 (x)\n**Decay ID:** kept\n")
    _, report = sweep(tmp_path)
    assert [(row["title"], row["due_date"]) for row in report["no_id"]] == [("Pay the invoice", "2026-11-30")]
    assert report["status"] == "REVIEW"
    assert "1 open dated item has no Decay ID" in sweep(tmp_path, json_out=False)[1]


# --- gap 3: a date that passed with nothing written --------------------------------------------------------------------

def dated(ident, due, extra=""):
    return f"### Item {ident}\n**Decays:** {due} (why)\n**Decay ID:** {ident}\n{extra}\n"


def test_a_due_item_whose_date_passed_with_no_lapsed_mark_is_unannounced(tmp_path):
    write(tmp_path / "plans", "2026-11-10.md", "# Plan\n\n" + dated("passed", "2026-11-11") + dated("today", DAY)
          + dated("marked", "2026-11-11", "**Lapsed:** 2026-11-12 (no answer came; it waited in this plan)\n"))
    _, report = sweep(tmp_path)
    assert {row["identity"]: row["unannounced"] for row in report["due"]} == {"id:passed": True, "id:today": False, "id:marked": False}
    _, out = sweep(tmp_path, json_out=False)
    assert "1 of them passed its date with nothing written" in out


def test_a_lapsed_mark_on_an_earlier_copy_still_announces_it(tmp_path):
    write(tmp_path / "plans", "2026-11-10.md", "# Plan\n\n" + dated("carried", "2026-11-11", "**Lapsed:** 2026-11-11 (waited)\n"))
    write(tmp_path / "plans", "2026-11-12.md", "# Plan\n\n" + dated("carried", "2026-11-12").replace("(why)", "(carried a day)"))
    _, report = sweep(tmp_path)
    assert [row["unannounced"] for row in report["due"]] == [False]


def test_the_evening_job_counts_the_dates_that_passed_unannounced_in_every_declared_workspace(tmp_path):
    for name in ("alpha", "beta"):
        write(tmp_path / name, "2026-11-10.md", "# Plan\n\n" + dated(f"{name}-passed", "2026-11-11") + dated(f"{name}-today", DAY))
    state, tools, log = tmp_path / "state", tmp_path / "tools", tmp_path / "banners"
    write(state, "config.json", json.dumps({"workspaces": {n: {"plans_dirs": [str(tmp_path / n)]} for n in ("alpha", "beta")}}))
    for tool in ("osascript", "say"):
        write(tools, tool, f'#!/bin/sh\necho "{tool}: $*" >> "{log}"\n').chmod(0o755)
    env = {**os.environ, "RITUAL_STATE_DIR": str(state), "SYNTHESIS_HOME": str(tmp_path / "home"), "HOME": str(tmp_path),
           "PATH": f"{tools}{os.pathsep}{os.environ['PATH']}"}
    proc = subprocess.run([sys.executable, str(SWEEP), "--as-of", DAY, "--alert-declared"], capture_output=True, text=True, env=env)
    assert proc.returncode == 0, proc.stderr
    assert "passed dates: 2 with nothing written across 2 declared set(s) of plan folders" in proc.stdout
    said = log.read_text(encoding="utf-8")
    assert said.count("osascript: ") == 1 and "2 dated items passed their date with nothing written" in said and "say: " not in said
    assert "alpha" not in said and "Item" not in said                            # a count and a pointer, never a title


# --- gap 8: a ledger's rows -------------------------------------------------------------------------------------------

LEDGER = """# Correspondence

| Status | Meaning |
|---|---|
| `SENT` | gone |

## Active

| Item | To | Status | Owed since | Last verified |
|---|---|---|---|---|
| Reply to the supplier | Pat | NEEDS_DRAFT | 2026-10-20 | 2026-11-12 |
| Thanks for the review | Lee | ✅ SENT 2026-11-10 | 2026-11-08 | 2026-11-10 |
| The renewal | Sam | **DRAFTED_HELD** | 2026-11-12 (asked twice) | 2026-11-12 |
| An older ask | Kim | SUPERSEDED by the renewal | 2026-09-01 | 2026-11-01 |
| No status yet | Ana | | 2026-11-01 | |
| No date yet | Ola | OWED | soon | |
| **A divider row** |
"""


def test_a_ledgers_open_rows_are_reported_in_a_view_of_their_own(tmp_path):
    ledger = write(tmp_path / "drafts", "_LEDGER.md", LEDGER)
    write(tmp_path / "plans", "2026-11-12.md", "# Plan\n\nNothing dated.\n")
    code, report = sweep(tmp_path)
    owed = report["owed"]
    assert code == 0 and report["status"] == "REVIEW" and report["due"] == []
    assert (owed["open"], owed["oldest"], owed["over_14_days"], owed["undated"], owed["unread"]) == (4, "2026-10-20", 1, 1, 1)
    assert [(row["item"], row["status"], row["owed_since"], row["days"]) for row in owed["rows"]] == [
        ("No date yet", "OWED", None, None), ("Reply to the supplier", "NEEDS_DRAFT", "2026-10-20", 24),
        ("No status yet", "", "2026-11-01", 12), ("The renewal", "DRAFTED_HELD", "2026-11-12", 1)]
    assert owed["rows"][1]["path"] == str(ledger) and owed["rows"][1]["line"] == 11


def test_the_text_report_gives_the_ledgers_count_and_its_oldest_rows(tmp_path):
    write(tmp_path / "drafts", "_LEDGER.md", LEDGER)
    write(tmp_path / "plans", "2026-11-12.md", "# Plan\n\nNothing dated.\n")
    _, out = sweep(tmp_path, json_out=False)
    assert "Owed: 4 open ledger rows (oldest 2026-10-20, 1 owed over 14 days, 1 with no date, 1 row not read)" in out
    assert "  2026-10-20 Reply to the supplier [NEEDS_DRAFT]" in out and "Thanks for the review" not in out


def test_a_table_with_no_status_or_no_owed_since_column_is_no_ledger(tmp_path):
    write(tmp_path / "drafts", "notes.md", "| Item | Status |\n|---|---|\n| A | OWED |\n\n| Item | Owed since |\n|---|---|\n| B | 2026-11-01 |\n")
    write(tmp_path / "plans", "2026-11-12.md", "# Plan\n\nNothing dated.\n")
    _, report = sweep(tmp_path)
    assert report["owed"]["open"] == 0 and report["owed"]["rows"] == [] and report["status"] == "CLEAR"


# --- the day's record -------------------------------------------------------------------------------------------------

def workspace(tmp_path: Path, plan: str, check=None, older: str = "") -> Path:
    plans, state = tmp_path / "plans", tmp_path / "state"
    write(plans, f"{DAY}.md", plan)
    if older:
        write(plans, "2026-11-12.md", older)
    settings = {"plans_dirs": [str(plans)], **({} if check is None else {"commitment_check": check})}
    write(state, "config.json", json.dumps({"workspaces": {"desk": settings}}))
    return state


@pytest.fixture
def record(monkeypatch, capsys):
    def run(state: Path, outcome: str = "clean"):
        monkeypatch.setenv("RITUAL_STATE_DIR", str(state))
        monkeypatch.setattr(ritual_state, "today", lambda: date.fromisoformat(DAY), raising=False)
        try:
            code, refusal = ritual_state.main(["record", "--direction", "day-end", "--workspace", "desk", "--date", DAY,
                                               "--outcome", outcome]), ""
        except SystemExit as exc:
            code, refusal = 1, str(exc)
        return code, capsys.readouterr().out, refusal
    return run


BARE = "# Friday\n\n## Priority Tasks\n\n1. **Call the landlord**\n\n## Waiting On Others\n- The vendor's quote\n"


def test_a_clean_record_is_refused_while_a_commitment_has_no_date_and_no_park(tmp_path, record):
    code, _, refusal = record(workspace(tmp_path, BARE, check=True))
    assert code != 0 and not (tmp_path / "state" / "history.jsonl").exists()
    assert "2 commitment(s) in the newest plan carry no date and no park" in refusal
    assert "Call the landlord" in refusal and "The vendor's quote" in refusal and f"{DAY}.md:5" in refusal
    assert "**Decays:** YYYY-MM-DD" in refusal and "parked (" in refusal


def test_a_partial_record_goes_through_and_says_how_many(tmp_path, record):
    code, out, refusal = record(workspace(tmp_path, BARE, check=True), outcome="partial")
    assert code == 0, refusal
    assert "commitments: 2 in the newest plan carry no date and no park" in out


def test_with_each_dated_or_parked_the_record_says_so(tmp_path, record):
    plan = BARE.replace("**Call the landlord**", "**Call the landlord**" + TAG.format("landlord")).replace(
        "- The vendor's quote", "- The vendor's quote, parked (they answer in January)")
    code, out, refusal = record(workspace(tmp_path, plan, check={}))
    assert code == 0, refusal
    assert "commitments: 2 open in the newest plan, each with a date or a park" in out


def test_a_clean_record_is_refused_over_an_open_dated_item_with_no_decay_id(tmp_path, record):
    plan = "# Friday\n\n## Priority Tasks\n\n1. **Pay the invoice**\n   **Decays:** 2026-11-30 (net 30)\n"
    code, _, refusal = record(workspace(tmp_path, plan, check=True))
    assert code != 0 and "1 open dated item(s) carry no Decay ID" in refusal and "Pay the invoice" in refusal
    assert "**Decay ID:**" in refusal


def test_the_check_is_off_unless_the_workspace_turns_it_on_and_starts_on_its_first_day(tmp_path, record):
    for check in (None, False, {"from": "2026-11-16"}):
        code, out, refusal = record(workspace(tmp_path, BARE, check=check))
        assert code == 0, (check, refusal)
        assert ("commitments: checked from 2026-11-16" in out) == isinstance(check, dict)
        (tmp_path / "state" / "history.jsonl").unlink()
    assert record(workspace(tmp_path, BARE, check={"from": DAY}))[0] != 0


@pytest.mark.parametrize("check", [None, 0, "yes", [], {"from": "Monday"}, {"from": 20261116}])
def test_a_setting_that_is_neither_on_nor_off_is_refused(tmp_path, record, check):
    state = workspace(tmp_path, BARE, check=True)
    config = json.loads((state / "config.json").read_text(encoding="utf-8"))
    config["workspaces"]["desk"]["commitment_check"] = check
    (state / "config.json").write_text(json.dumps(config), encoding="utf-8")
    code, _, refusal = record(state)
    assert code != 0 and "commitment_check" in refusal and "this ritual is not recorded" in refusal
