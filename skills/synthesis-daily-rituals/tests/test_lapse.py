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
    done = lapse(env, "--id", "thanks", "--row-missing")                         # the mark stands and no row names it: said to be missing
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


def test_two_lapses_written_at_once_take_turns(seat, tmp_path):
    """The design asks for one lock around both writes: two helpers that each read the register before either wrote
    would both start a new table, and the second to reach a plan would replace what the first had written there."""
    import fcntl
    import time
    plan, register, env = seat
    with open(tmp_path / "state" / "lapse.lock", "a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        waiting = subprocess.Popen([sys.executable, str(SCRIPTS / "lapse.py"), "--workspace", "desk", "--as-of", DAY, "--id", "thanks", *WORDS],
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env)
        time.sleep(1.0)
        assert waiting.poll() is None and register.read_text(encoding="utf-8") == REGISTER    # it waits, and has written nothing
    out, err = waiting.communicate(timeout=30)
    assert waiting.returncode == 0, err
    assert f"{register}:13" in out and "`thanks` |" in register.read_text(encoding="utf-8")


def test_a_row_is_read_back_as_it_was_written():
    """The row is the register's permanent record, so the helper reads it back from the file before it says it is
    written: its day, and each of its seven cells."""
    sys.path.insert(0, str(SCRIPTS))
    import lapse
    cells = [DAY, "**Send it** `x`", "[p.md:5](../plans/p.md)", "a \\| b", "open", "the team", "ask again"]
    row = {"lapsed": DAY, "item": cells[1], "where": cells[2], "why": cells[3], "outcome": "open", "affected": cells[5], "still": cells[6], "line": 13}
    assert lapse.read_back([row], 13, cells)
    assert not lapse.read_back([row], 12, cells)                                 # another line
    assert not lapse.read_back([{**row, "still": "ask"}], 13, cells)             # a cell that reads back as something else
    assert not lapse.read_back([], 13, cells)


# --- the first review -------------------------------------------------------------------------------------------------

def in_process(seat, monkeypatch):
    """The helper as a module, with the seat's state, for a test that has to change what it meets while it runs."""
    sys.path.insert(0, str(SCRIPTS))
    import lapse as helper
    for key in ("RITUAL_STATE_DIR", "SYNTHESIS_HOME"):
        monkeypatch.setenv(key, seat[2][key])
    return helper, ["--workspace", "desk", "--as-of", DAY, *WORDS]


def test_a_tag_on_the_items_own_line_takes_its_mark_on_a_line_beneath_it(seat):
    """Finding 1: the mark's lead was everything before the tag, so a tag written on the item's own line got a copy
    of the item as its mark: a second item, which took the Decay ID with it and left the sweep blocked."""
    plan, register, env = seat
    plan.write_text("# Plan\n\n## Priority Tasks\n- Send the thanks **Decays:** 2026-11-10 (kudos)\n  **Decay ID:** inl\n\n"
                    "### Thank the host **Decays:** 2026-11-09 (after the dinner)\n**Decay ID:** host\n", encoding="utf-8")
    assert lapse(env, "--id", "inl").returncode == 0
    assert lapse(env, "--id", "host").returncode == 0
    lines = plan.read_text(encoding="utf-8").splitlines()
    assert lines[3:6] == ["- Send the thanks **Decays:** 2026-11-10 (kudos)", f"  **Lapsed:** {DAY} — no one was told the event had moved",
                          "  **Decay ID:** inl"]
    assert lines[7:10] == ["### Thank the host **Decays:** 2026-11-09 (after the dinner)", f"**Lapsed:** {DAY} — no one was told the event had moved",
                           "**Decay ID:** host"]
    assert "| Send the thanks `inl` |" in register.read_text(encoding="utf-8") and "| Thank the host `host` |" in register.read_text(encoding="utf-8")
    report = json.loads(lapse(env, "--json", words=(), script="decay_sweep.py").stdout)
    assert report["gaps"] == [] and {row["identity"]: row["unannounced"] for row in report["due"]} == {"id:inl": False, "id:host": False}


def test_no_lapse_is_written_over_a_sweep_that_did_not_take_every_source(seat):
    """Finding 2: with a later plan unreadable, the helper recorded as lapsed an item that plan closed; with a new
    date that gave no reason, it marked the old copy and recorded the old date. A row is permanent, so nothing is
    written from a reading that is not whole."""
    plan, register, env = seat
    (plan.parent / "2026-11-12.md").write_bytes(b"# Plan\n\n\xff\xfe not text\n")
    done = lapse(env, "--id", "thanks")
    assert done.returncode == 2 and "not taken in full" in done.stderr and "2026-11-12.md" in done.stderr, done.stderr
    assert plan.read_text(encoding="utf-8") == PLAN and register.read_text(encoding="utf-8") == REGISTER


def test_the_item_is_found_again_where_it_now_sits_before_anything_is_written(seat, monkeypatch):
    """Finding 3: a plan that changed while the sweep ran had its mark and its row land on another item, since the
    line the sweep gave was trusted. The item is found again by what it is, in the plan as it reads then."""
    helper, args = in_process(seat, monkeypatch)
    plan, register, _ = seat
    moved = PLAN.replace("## Priority Tasks\n", "## Priority Tasks\n0. **A new one**\n   **Decays:** 2026-11-01 (older)\n   **Decay ID:** newer\n")
    real = helper.decay_sweep.collect

    def changed_meanwhile(*given, **more):
        report = real(*given, **more)
        plan.write_text(moved, encoding="utf-8")  # another writer puts an item above it after the sweep has read the plan
        return report
    monkeypatch.setattr(helper.decay_sweep, "collect", changed_meanwhile)
    assert helper.main([*args, "--id", "thanks"]) == 0
    lines = plan.read_text(encoding="utf-8").splitlines()
    assert lines[7:9] == ["   **Decays:** 2026-11-11 (two days after the event)", f"   **Lapsed:** {DAY} — no one was told the event had moved"]
    assert "| [2026-11-10.md:8](../plans/2026-11-10.md) |" in register.read_text(encoding="utf-8")   # where it sits now


def test_an_item_with_no_id_that_is_no_longer_at_its_line_is_refused(seat, monkeypatch):
    helper, args = in_process(seat, monkeypatch)
    plan, register, _ = seat
    moved = PLAN.replace("## Priority Tasks\n", "## Priority Tasks\n0. **A new one**\n   **Decays:** 2026-11-01 (older)\n   **Decay ID:** newer\n")
    real = helper.decay_sweep.collect

    def changed_meanwhile(*given, **more):
        report = real(*given, **more)
        plan.write_text(moved, encoding="utf-8")
        return report
    monkeypatch.setattr(helper.decay_sweep, "collect", changed_meanwhile)
    assert helper.main([*args, "--at", f"{plan}:11"]) == 2                        # line 11 is another item's tag by then
    assert plan.read_text(encoding="utf-8") == moved and register.read_text(encoding="utf-8") == REGISTER


def test_an_item_already_marked_whose_row_cannot_be_matched_gets_no_second_row_unasked(seat):
    """Finding 4: a lapse recorded by hand, its row naming the item in words, got a second permanent row."""
    plan, register, env = seat
    plan.write_text(PLAN.replace("   **Decay ID:** thanks\n", "   **Decay ID:** thanks\n   **Lapsed:** 2026-11-12 — marked by hand\n"), encoding="utf-8")
    register.write_text(REGISTER + "| 2026-11-12 | Send the thanks | the plan of 11-10 | nobody was told | open |\n", encoding="utf-8")
    before = (plan.read_bytes(), register.read_bytes())
    done = lapse(env, "--id", "thanks")
    assert done.returncode == 2 and "--row-missing" in done.stderr and (plan.read_bytes(), register.read_bytes()) == before
    asked = lapse(env, "--id", "thanks", "--row-missing")
    assert asked.returncode == 0 and "already marked" in asked.stdout and "`thanks` |" in register.read_text(encoding="utf-8")


def test_what_came_of_a_lapse_is_appended_as_a_row_of_its_own(seat):
    """Finding 6: once a lapse was recorded there was no way to say what came of it: a row is never rewritten, and a
    second run was refused. `--came` appends a row for the same lapse, on its day, with what came of it, and the
    review reads a lapse by its last row. It needs no open item: by then the item may be closed."""
    plan, register, env = seat
    assert lapse(env, "--id", "thanks").returncode == 0
    marked, once = plan.read_text(encoding="utf-8"), register.read_text(encoding="utf-8")
    plan.write_text(marked.replace("   **Decay ID:** thanks\n", "   **Decay ID:** thanks\n   **Released:** 2026-11-13 (his decision)\n"), encoding="utf-8")
    done = lapse(env, "--id", "thanks", "--came", "let go after its date", words=())
    assert done.returncode == 0, done.stderr
    text = register.read_text(encoding="utf-8")
    assert text.startswith(once) and text[len(once):] == (
        f"| {DAY} | **Send the thanks** to the review team `thanks` | [2026-11-10.md:5](../plans/2026-11-10.md) | "
        "no one was told the event had moved | let go after its date | the review team | send it with an apology |\n")
    review = json.loads(lapse(env, "--json", words=(), script="lapse_review.py").stdout)
    assert [(row["item"], row["outcome"]) for row in review["rows"]] == [("**Send the thanks** to the review team `thanks`", "let go after its date")]
    assert review["patterns"]["item"] == {} and review["patterns"]["open"] == 0
    kept = register.read_bytes()
    for args in (("--id", "nobody", "--came", "sent late"), ("--id", "thanks", "--came", " "), ("--id", "thanks", "--came", "x", "--why", "y")):
        assert lapse(env, *args, words=()).returncode == 2 and register.read_bytes() == kept, args


def test_a_register_that_cannot_be_written_is_a_refusal_and_not_a_traceback(seat):
    """Finding 10: it ended in a traceback with exit 1, the code that says a row was written."""
    plan, register, env = seat
    register.chmod(0o444)
    done = lapse(env, "--id", "thanks")
    register.chmod(0o644)
    assert done.returncode == 2 and "Traceback" not in done.stderr and "nothing was written" in done.stderr, done.stderr
    assert plan.read_text(encoding="utf-8") == PLAN and register.read_text(encoding="utf-8") == REGISTER


def test_a_plan_that_may_only_be_read_is_not_rewritten(seat):
    """Finding 11: replacing a file needs only its folder, so a plan marked read-only took the mark."""
    plan, register, env = seat
    plan.chmod(0o444)
    done = lapse(env, "--id", "thanks")
    plan.chmod(0o644)
    assert done.returncode == 2 and "may not be written" in done.stderr, done.stderr
    assert plan.read_text(encoding="utf-8") == PLAN and register.read_text(encoding="utf-8") == REGISTER


def test_a_folder_with_spaces_in_its_name_still_makes_a_link(tmp_path):
    """Finding 12: `[..](../My  plans/..)` is no link in Markdown, and the two spaces had been made one."""
    plan, register, state = tmp_path / "My  plans" / "2026-11-10.md", tmp_path / "records" / "lapse-register.md", tmp_path / "state"
    for path, text in ((plan, PLAN), (register, REGISTER)):
        path.parent.mkdir()
        path.write_text(text, encoding="utf-8")
    state.mkdir()
    (state / "config.json").write_text(json.dumps({"workspaces": {"desk": {
        "plans_dirs": [str(plan.parent)], "lapse_register": str(register)}}}), encoding="utf-8")
    env = {**os.environ, "RITUAL_STATE_DIR": str(state), "SYNTHESIS_HOME": str(tmp_path / "home")}
    assert lapse(env, "--id", "thanks").returncode == 0
    assert "| [2026-11-10.md:5](<../My  plans/2026-11-10.md>) |" in register.read_text(encoding="utf-8")
    review = json.loads(lapse(env, "--json", words=(), script="lapse_review.py").stdout)
    assert len(review["rows"]) == 1


def test_a_seven_cell_table_with_no_line_end_takes_the_next_row_and_a_registers_line_ends_are_kept(seat):
    """Finding 13: a table that ended the file with no line end got a second header, and a register written with
    CRLF got LF lines."""
    plan, register, env = seat
    assert lapse(env, "--id", "thanks").returncode == 0
    register.write_bytes(register.read_text(encoding="utf-8").rstrip("\n").replace("\n", "\r\n").encode("utf-8"))
    assert lapse(env, "--id", "older").returncode == 0
    after = register.read_bytes().decode("utf-8")
    assert after.count("| Lapsed | Item |") == 2 and after.endswith("|\r\n") and "\n" not in after.replace("\r\n", "")


def test_a_five_cell_table_that_ends_the_file_is_not_written_under(seat):
    """A row of seven cells under the old header of five would be a row of another table: a new header is written."""
    plan, register, env = seat
    register.write_text(REGISTER.split("\n- 2026-10-27")[0], encoding="utf-8")       # the five-cell table ends the file
    assert lapse(env, "--id", "thanks").returncode == 0
    lines = register.read_text(encoding="utf-8").splitlines()
    assert lines[-3].startswith("| Lapsed | Item |") and lines[-3].count("|") == 8 and lines[-4] == ""


def test_an_item_that_lapsed_was_given_a_new_date_and_lapsed_again_gets_a_second_row(seat):
    """A row for an earlier date is no row for this one."""
    plan, register, env = seat
    register.write_text(REGISTER + "\n| 2026-11-05 | **Send the thanks** `thanks` | old | first time | open |\n", encoding="utf-8")
    assert lapse(env, "--id", "thanks").returncode == 0
    assert register.read_text(encoding="utf-8").count("`thanks` |") == 2


def test_a_row_that_does_not_read_back_stops_the_helper_before_the_mark(seat, monkeypatch):
    helper, args = in_process(seat, monkeypatch)
    plan, register, _ = seat
    monkeypatch.setattr(helper, "read_back", lambda *given: False)
    assert helper.main([*args, "--id", "thanks"]) == 1
    assert plan.read_text(encoding="utf-8") == PLAN and "`thanks` |" in register.read_text(encoding="utf-8")


def test_a_plan_that_changes_after_the_row_is_written_takes_its_mark_on_the_next_run(seat, monkeypatch, capsys):
    """The row stands, the helper says to run it again, and the second run writes the mark alone."""
    helper, args = in_process(seat, monkeypatch)
    plan, register, _ = seat
    real = helper.append_row

    def then_the_plan_changes(*given):
        line = real(*given)
        plan.write_text(PLAN + "\n- a note written meanwhile\n", encoding="utf-8")
        return line
    monkeypatch.setattr(helper, "append_row", then_the_plan_changes)
    assert helper.main([*args, "--id", "thanks"]) == 1
    assert "run this again" in capsys.readouterr().err and "**Lapsed:**" not in plan.read_text(encoding="utf-8")
    once = register.read_bytes()
    monkeypatch.setattr(helper, "append_row", real)
    assert helper.main([*args, "--id", "thanks"]) == 0
    said = capsys.readouterr().out
    assert "row: already there" in said and f"mark: {plan}:6" in said and register.read_bytes() == once
    assert f"   **Lapsed:** {DAY} — no one was told the event had moved" in plan.read_text(encoding="utf-8").splitlines()


def test_an_item_with_no_id_is_found_by_a_path_from_here_and_through_a_link(seat, tmp_path):
    plan, register, env = seat
    (tmp_path / "linked").symlink_to(plan.parent)
    done = subprocess.run([sys.executable, str(SCRIPTS / "lapse.py"), "--workspace", "desk", "--as-of", DAY, "--at", "linked/2026-11-10.md:11", *WORDS],
                          capture_output=True, text=True, env=env, cwd=tmp_path)
    assert done.returncode == 0, done.stderr
    assert "| **Pay the invoice** | [2026-11-10.md:11](../plans/2026-11-10.md) |" in register.read_text(encoding="utf-8")


def test_two_helpers_started_together_write_one_table_and_both_marks(seat):
    """Two real helpers, for two items: without the lock each reads a register with no seven-cell table and starts
    one, and the second to replace the plan writes over the first one's mark."""
    plan, register, env = seat
    both = [subprocess.Popen([sys.executable, str(SCRIPTS / "lapse.py"), "--workspace", "desk", "--as-of", DAY, "--id", which, *WORDS],
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env) for which in ("thanks", "older")]
    for helper in both:
        assert helper.wait(60) == 0, helper.stderr.read()
    text = register.read_text(encoding="utf-8")
    assert text.count("| Lapsed | Item |") == 2 and "`thanks` |" in text and "`older` |" in text
    assert plan.read_text(encoding="utf-8").count("**Lapsed:**") == 2
