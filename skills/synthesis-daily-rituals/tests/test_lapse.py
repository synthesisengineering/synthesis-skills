"""A lapse is written where it belongs in one step: the mark at the item, and the row in the register.

When an item passes its date with no decision it lapsed, and the day-end asks for two things by hand: a
`**Lapsed:**` mark where the item sits, and an appended row in the workspace's lapse register. An audit of
2026-11-11 found no script that writes either, nothing that checks one against the other, and no place in a row for
whom the lapse affected or what can still be done. This helper takes the item's Decay ID and the agent's words,
and writes both: the row first, in a table with those two columns, appended and never rewritten. On every refusal it
leaves both files as they were. Committed before the code.
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
PLAN = """# Tuesday

## Priority Tasks
1. **Send the thanks** to the review team
   **Decays:** 2026-11-11 (two days after the event)
   **Decay ID:** thanks
2. **File the return**
   **Decays:** 2026-11-13 (due today)
   **Decay ID:** return-2026
3. **Pay the invoice**
   **Decays:** 2026-11-09 (net 30)
4. **Reply to the supplier**
   **Decays:** 2026-11-05 (their quote expires)
   **Decay ID:** supplier
   **Resolved:** 2026-11-06 (answered)
- An older one
  - **Decays:** 2026-11-08 (it was promised)
  - **Decay ID:** older

### Renew the visa
**Critical:** visa
**Decays:** 2026-11-12 (the window closed)
**Decay ID:** visa-2026
**Calendar:** on the calendar
"""
REGISTER = """# Lapse register

Permanent history: append rows, never remove or rewrite them.

| Lapsed | Item | Where it waited | Why it lapsed | Outcome |
|---|---|---|---|---|
| 2026-10-26 | An old acknowledgment | [plan](../plans/2026-10-24.md) | travel | let go after its date |

- 2026-10-27: a note beneath the table.
"""
WORDS = ("--why", "no one was told the event had moved", "--affected", "the review team", "--still", "send it with an apology")


@pytest.fixture
def seat(tmp_path):
    plan, register, state = tmp_path / "plans" / "2026-11-10.md", tmp_path / "records" / "lapse-register.md", tmp_path / "state"
    for path, text in ((plan, PLAN), (register, REGISTER)):
        path.parent.mkdir()
        path.write_text(text, encoding="utf-8")
    state.mkdir()
    (state / "config.json").write_text(json.dumps({"workspaces": {"desk": {
        "plans_dirs": [str(plan.parent)], "lapse_register": str(register)}}}), encoding="utf-8")
    return plan, register, {**os.environ, "RITUAL_STATE_DIR": str(state), "SYNTHESIS_HOME": str(tmp_path / "home")}


def lapse(env, *args, words=WORDS, script="lapse.py", as_of=DAY):
    return subprocess.run([sys.executable, str(SCRIPTS / script), "--workspace", "desk", "--as-of", as_of, *args, *words],
                          capture_output=True, text=True, env=env)


def test_a_lapse_is_marked_at_the_item_and_appended_to_the_register(seat):
    plan, register, env = seat
    done = lapse(env, "--id", "thanks")
    assert done.returncode == 0, done.stderr
    text = register.read_text(encoding="utf-8")
    assert text.startswith(REGISTER)                                             # nothing that was there is rewritten
    added = text[len(REGISTER):].splitlines()
    assert added == ["", "| Lapsed | Item | Where it waited | Why it lapsed | Outcome | Who it affected | What can still be done |",
                     "|---|---|---|---|---|---|---|",
                     f"| {DAY} | **Send the thanks** to the review team `thanks` | [2026-11-10.md:5](../plans/2026-11-10.md) | "
                     "no one was told the event had moved | open | the review team | send it with an apology |"]
    marked = plan.read_text(encoding="utf-8").splitlines()
    assert marked[4:7] == ["   **Decays:** 2026-11-11 (two days after the event)",
                           f"   **Lapsed:** {DAY} — no one was told the event had moved", "   **Decay ID:** thanks"]
    assert len(marked) == len(PLAN.splitlines()) + 1
    assert f"{register}:13" in done.stdout and f"{plan}:6" in done.stdout
    report = json.loads(lapse(env, "--json", words=(), script="decay_sweep.py").stdout)
    assert {row["identity"]: row["unannounced"] for row in report["due"]}["id:thanks"] is False
    review = lapse(env, "--json", words=(), script="lapse_review.py")
    assert [row["item"] for row in json.loads(review.stdout)["rows"]] == ["**Send the thanks** to the review team `thanks`"]


def test_the_next_lapse_goes_under_the_same_table(seat):
    plan, register, env = seat
    assert lapse(env, "--id", "thanks").returncode == 0
    once = register.read_text(encoding="utf-8")
    done = lapse(env, "--id", "older", "--outcome", "let go after its date", "--lapsed", "2026-11-12")
    assert done.returncode == 0, done.stderr
    text = register.read_text(encoding="utf-8")
    assert text.startswith(once) and text.count("| Lapsed | Item |") == 2        # the old header and the new one, once each
    assert text[len(once):] == ("| 2026-11-12 | An older one `older` | [2026-11-10.md:18](../plans/2026-11-10.md) | "
                                "no one was told the event had moved | let go after its date | the review team | send it with an apology |\n")
    assert "  - **Lapsed:** 2026-11-12 — no one was told the event had moved" in plan.read_text(encoding="utf-8").splitlines()


def test_an_item_with_no_id_is_named_by_where_it_sits(seat):
    plan, register, env = seat
    done = lapse(env, "--at", f"{plan}:11")
    assert done.returncode == 0, done.stderr
    assert "| **Pay the invoice** | [2026-11-10.md:11](../plans/2026-11-10.md) |" in register.read_text(encoding="utf-8")
    assert plan.read_text(encoding="utf-8").splitlines()[11] == f"   **Lapsed:** {DAY} — no one was told the event had moved"


def test_a_mark_that_already_stands_is_not_written_twice_and_a_row_already_there_is_refused(seat):
    plan, register, env = seat
    plan.write_text(PLAN.replace("   **Decay ID:** thanks\n", "   **Decay ID:** thanks\n   **Lapsed:** 2026-11-12 — marked by hand\n"), encoding="utf-8")
    before = plan.read_bytes()
    done = lapse(env, "--id", "thanks")
    assert done.returncode == 0 and plan.read_bytes() == before and "already marked" in done.stdout
    assert "`thanks` |" in register.read_text(encoding="utf-8")
    kept = register.read_bytes()
    again = lapse(env, "--id", "thanks")
    assert again.returncode == 2 and "already has a row" in again.stderr and register.read_bytes() == kept and plan.read_bytes() == before


@pytest.mark.parametrize("args, words, said", [
    (("--id", "visa-2026"), WORDS, "never lapses"),
    (("--id", "supplier"), WORDS, "no open item"),
    (("--id", "nobody"), WORDS, "no open item"),
    (("--id", "return-2026"), WORDS, "has not passed"),
    (("--id", "thanks", "--lapsed", "2026-11-14"), WORDS, "ahead"),
    (("--id", "thanks", "--lapsed", "2026-11-10"), WORDS, "before its date"),
    (("--id", "thanks"), ("--why", " ", "--affected", "them", "--still", "something"), "--why"),
    (("--id", "thanks"), ("--why", "x", "--affected", "", "--still", "something"), "--affected"),
    (("--at", "nowhere.md:3"), WORDS, "no open item"),
])
def test_what_it_refuses_leaves_both_files_as_they_were(seat, args, words, said):
    plan, register, env = seat
    done = lapse(env, *args, words=words)
    assert done.returncode == 2 and said in done.stderr, done.stderr
    assert plan.read_text(encoding="utf-8") == PLAN and register.read_text(encoding="utf-8") == REGISTER


def test_a_register_that_is_not_declared_or_not_there_is_refused(seat, tmp_path):
    plan, register, env = seat
    config = tmp_path / "state" / "config.json"
    config.write_text(json.dumps({"workspaces": {"desk": {"plans_dirs": [str(plan.parent)]}}}), encoding="utf-8")
    assert lapse(env, "--id", "thanks").returncode == 2 and plan.read_text(encoding="utf-8") == PLAN
    config.write_text(json.dumps({"workspaces": {"desk": {"plans_dirs": [str(plan.parent)], "lapse_register": str(register)}}}), encoding="utf-8")
    register.write_text("# Lapse register\n\nNo table yet.\n", encoding="utf-8")
    done = lapse(env, "--id", "thanks")
    assert done.returncode == 2 and "holds no register table" in done.stderr and plan.read_text(encoding="utf-8") == PLAN


def test_words_cannot_break_the_row(seat):
    plan, register, env = seat
    done = lapse(env, "--id", "thanks", words=("--why", "a | b\nsecond line", "--affected", "the team", "--still", "ask | again"))
    assert done.returncode == 0, done.stderr
    row = register.read_text(encoding="utf-8").splitlines()[-1]
    assert "| a \\| b second line |" in row and "| ask \\| again |" in row and row.count(" | ") == 6


def test_a_register_that_ends_without_a_line_end_still_gets_its_row_on_a_line_of_its_own(seat):
    plan, register, env = seat
    register.write_text(REGISTER.rstrip("\n"), encoding="utf-8")
    assert lapse(env, "--id", "thanks").returncode == 0
    lines = register.read_text(encoding="utf-8").splitlines()
    assert lines[8] == "- 2026-10-27: a note beneath the table." and lines[9] == "" and lines[10].startswith("| Lapsed | Item |")


def test_a_plans_own_line_ends_and_mode_are_kept(seat):
    """Written with the code: the plan is replaced whole to take its one new line, so what it had is kept."""
    plan, register, env = seat
    plan.write_bytes(PLAN.replace("\n", "\r\n").encode("utf-8"))
    plan.chmod(0o640)
    assert lapse(env, "--id", "thanks").returncode == 0
    after = plan.read_bytes()
    assert after.count(b"\r\n") == PLAN.count("\n") + 1 and b"\n" not in after.replace(b"\r\n", b"")
    assert f"   **Lapsed:** {DAY} — no one was told the event had moved\r\n".encode("utf-8") in after
    assert plan.stat().st_mode & 0o777 == 0o640


def test_a_tag_that_ends_the_file_with_no_line_end_takes_its_mark_on_a_line_of_its_own(seat):
    plan, register, env = seat
    plan.write_text("# Plan\n\n## Priority Tasks\n- Send it\n  **Decay ID:** last\n  **Decays:** 2026-11-09 (promised)", encoding="utf-8")
    assert lapse(env, "--id", "last").returncode == 0
    assert plan.read_text(encoding="utf-8").endswith(f"  **Decays:** 2026-11-09 (promised)\n  **Lapsed:** {DAY} — no one was told the event had moved")
