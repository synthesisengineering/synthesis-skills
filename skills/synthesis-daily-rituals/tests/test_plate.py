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
    assert refused.returncode == 2 and refused.stdout == "" and "could not be read whole" in refused.stderr and "2026-11-09.md" in refused.stderr
    asked = plate(tmp_path, "--with-gaps")
    assert asked.returncode == 0 and "## Not read (1)" in asked.stdout and asked.stdout.index("## Not read (1)") < asked.stdout.index("## Critical deadlines")


def test_a_workspace_that_declares_no_folders_has_no_plate(tmp_path):
    env = seat(tmp_path)
    (tmp_path / "state" / "config.json").write_text(json.dumps({"workspaces": {"desk": {}}}), encoding="utf-8")
    done = subprocess.run([sys.executable, str(SCRIPTS / "plate.py"), "--workspace", "desk", "--as-of", DAY], capture_output=True, text=True, env=env)
    assert done.returncode == 2 and "declares no plan folders" in done.stderr
