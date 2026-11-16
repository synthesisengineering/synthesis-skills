"""R6: the autopilot plan file, its turn-end check (synthesis/autopilot.py) and the commands an
agent runs by hand (skills/synthesis-autopilot/scripts/autopilot_cli.py).

Scenario numbers refer to section 3 of the v5 code evaluation for autopilot.
"""

import json
import os
import re
import shutil
import statistics
import subprocess
import sys
import time
from datetime import date, datetime, timedelta
from pathlib import Path

import pytest

from synthesis import autopilot, board, guards, install

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills" / "synthesis-autopilot"
TEMPLATE_DOC = SKILL / "references" / "plan-file.md"
CLI = SKILL / "scripts" / "autopilot_cli.py"
sys.path.insert(0, str(CLI.parent))
import autopilot_cli as cli  # noqa: E402

HEADER = {
    "Status": "running",
    "Owner session": "",
    "Engaged": "",
    "Horizon": "sitting",
    "Continuation": "none: this sitting only",
    "Backstop": "none (horizon is this sitting)",
}



def _check(payload, config):
    """The turn-end request the Stop hook would send, or None."""
    return autopilot.evaluate(payload, config)[0]

def ago(minutes: float) -> str:
    return (datetime.now().astimezone() - timedelta(minutes=minutes)).isoformat(timespec="minutes")


def write_plan(tmp_path, *, header=None, checklist=("- [x] 1. Migrate /users", "- [ ] 2. Migrate /orders",
                                                   "- [ ] 3. Update their tests"),
               criteria=("- [ ] Endpoint tests pass",), evidence=(), standing=(), blockers=(), questions=(),
               mission="Move the two remaining endpoints.", name="2026-10-05-endpoints-autopilot-plan.md"):
    project = tmp_path / "kb" / "projects" / "alpha"
    folder = project / "resources" / "artifacts"
    folder.mkdir(parents=True, exist_ok=True)
    fields = {**HEADER, **(header or {})}
    lines = ["# Autopilot plan: migrate endpoints", ""]
    lines += [f"{k}: {v}" for k, v in fields.items() if v is not None]
    for title, body in (("Mission", [mission]), ("Checklist", checklist), ("Completion criteria", criteria),
                        ("Required evidence", evidence), ("Standing checklist", standing), ("Blockers", blockers),
                        ("Questions for the principal", questions), ("Cycle ledger", [])):
        lines += ["", f"## {title}", ""] + list(body)
    path = folder / name
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def run(*argv) -> int:
    return cli.main([str(a) for a in argv])


def engage(session, path) -> None:
    assert run("--session", session, "engage", "--plan", path) == 0


def stop(session, **payload):
    return _check({"session_id": session, **payload}, {})


def edit(path, old, new):
    text = path.read_text(encoding="utf-8")
    assert old in text, old
    path.write_text(text.replace(old, new), encoding="utf-8")


def done_ready(tmp_path, **header):
    """A plan whose work is finished and evidenced, ready to close as done."""
    project = tmp_path / "kb" / "projects" / "alpha"
    (project / "resources" / "evidence").mkdir(parents=True, exist_ok=True)
    (project / "resources" / "evidence" / "test-run.md").write_text("42 passed\n", encoding="utf-8")
    standing = [f"- [x] {i}: {t} — done, see the session log" for i, t in cli.DEFAULT_STANDING]
    return write_plan(tmp_path, header=header, checklist=("- [x] 1. Migrate /users", "- [x] 2. Migrate /orders"),
                      criteria=("- [x] Endpoint tests pass — pytest tests/api: 42 passed",),
                      evidence=("- [test run](../evidence/test-run.md)",), standing=standing)


# ---- engagement and the plan-file convention ----------------------------------

def test_engage_fills_owner_status_and_standing_checklist_and_claims_the_plan(tmp_path, capsys):
    path = write_plan(tmp_path, header={"Status": ""})
    engage("S1", path)
    plan = autopilot.load(path)
    assert plan.field("owner session") == "S1" and plan.status == "running"
    assert autopilot._age_seconds(plan.field("engaged")) < 120
    ids = {re.split(r"[:\s]", t, maxsplit=1)[0] for _, t in plan.items("standing checklist")}
    assert ids == {i for i, _ in cli.DEFAULT_STANDING}
    assert str(path) in board.load("S1").claims
    assert "next item: 2. Migrate /orders" in capsys.readouterr().out


def test_engage_adds_the_principals_private_standing_items(tmp_path, write_config):
    write_config({"autopilot": {"standing_checklist": [{"id": "blog-seeds", "text": "Blog seeds captured."}]}})
    path = write_plan(tmp_path)
    engage("S1", path)
    assert any(t.startswith("blog-seeds:") for _, t in autopilot.load(path).items("standing checklist"))


def test_engage_adds_the_check_of_what_other_people_rely_on_and_only_the_items_a_plan_lacks(tmp_path):
    """A test two colleagues had come to rely on stopped, and two scheduled check-ins ran without looking at it.
    Every run now carries the check as a standing item, added like any other the plan lacks."""
    path = write_plan(tmp_path, standing=("- [ ] end-to-end: Complete the work, as this plan words it.",))
    engage("S1", path)
    standing = [text for _, text in autopilot.load(path).items("standing checklist")]
    assert sorted(re.split(r"[:\s]", text, maxsplit=1)[0] for text in standing) == sorted(i for i, _ in cli.DEFAULT_STANDING)
    assert "end-to-end: Complete the work, as this plan words it." in standing  # the plan's own wording stays
    check = next((text for text in standing if text.startswith("others-rely-on: ")), "")
    for words in ("At every wake", "everything a person other than the principal relies on", "relied_on.py --all",
                  "lead the reply with any failure"):
        assert words in check, words
    engage("S1", path)  # nothing is added twice
    assert [text for _, text in autopilot.load(path).items("standing checklist")] == standing


def test_the_check_of_what_other_people_rely_on_needs_its_own_evidence_at_close(tmp_path, capsys):
    """The item names the command it runs; `--all` in its text is not the dash that introduces evidence."""
    path = done_ready(tmp_path)
    engage("S1", path)
    item = "others-rely-on: " + dict(cli.DEFAULT_STANDING)["others-rely-on"]
    edit(path, f"- [x] {item} — done, see the session log", f"- [x] {item}")
    assert run("--session", "S1", "close", "--plan", path, "--done") == 1
    assert "standing item others-rely-on is checked without evidence after ' — '" in capsys.readouterr().err
    edit(path, f"- [x] {item}", f"- [x] {item} — every wake's result is in the cycle ledger; nothing was down")
    assert run("--session", "S1", "close", "--plan", path, "--done") == 0


def test_a_wake_checks_what_other_people_rely_on_before_the_next_item_and_the_skill_says_how():
    """A standing item nobody is told how to run is not a control: the wake's own steps and the binding rules carry
    the command, by the path the install keeps in the runtime, and the plan-file page lists the item as engage adds it."""
    command = 'python3 -S "$HOME/.synthesis/v5/current/skills/synthesis-daily-rituals/scripts/relied_on.py" --all'
    reentry = (SKILL / "references" / "continuation.md").read_text(encoding="utf-8").split("\n## Re-entry protocol\n")[1].split("\n## ")[0]
    reentry = " ".join(reentry.split())  # the page wraps its lines
    places = [reentry.find(words) for words in ("Before the next open item, every wake checks what other people rely on",
                                                command, "A `DOWN` line leads the wake's reply")]
    assert -1 not in places and places == sorted(places), places
    rules = (SKILL / "SKILL.md").read_text(encoding="utf-8").split("## Binding rules")[1].split("## Contents")[0]
    rule = next((line for line in rules.splitlines() if command in line), "")
    assert "At every wake" in rule and "`DOWN`" in rule and "approval" in rule
    assert f"| `others-rely-on` | {dict(cli.DEFAULT_STANDING)['others-rely-on']} |" in TEMPLATE_DOC.read_text(encoding="utf-8")


def test_a_wake_takes_a_check_that_did_not_run_as_not_checked_and_never_as_healthy():
    """Review round 3, finding 24: a wake was told what a `DOWN` line and exit 2 ask for, and nothing of a checker that
    never started or printed none of the lines it documents. The standing item, the binding rule and the re-entry
    protocol each say such a run leads the reply as not checked."""
    reentry = (SKILL / "references" / "continuation.md").read_text(encoding="utf-8").split("\n## Re-entry protocol\n")[1].split("\n## ")[0]
    rules = (SKILL / "SKILL.md").read_text(encoding="utf-8").split("## Binding rules")[1].split("## Contents")[0]
    places = {"standing item": dict(cli.DEFAULT_STANDING)["others-rely-on"], "re-entry protocol": reentry,
              "binding rule": next((line for line in rules.splitlines() if "relied_on.py" in line), "")}
    for where, text in places.items():
        for words in ("never started", "printed none of the lines", "not checked", "never read as healthy"):
            assert words in " ".join(text.split()), (where, words)


def test_engage_refuses_a_plan_without_checklist_criteria_or_horizon(tmp_path, capsys):
    path = write_plan(tmp_path, checklist=(), criteria=(), header={"Horizon": None})
    assert run("--session", "S1", "engage", "--plan", path) == 1
    err = capsys.readouterr().err
    assert "Checklist" in err and "Completion criteria" in err and "Horizon" in err
    assert stop("S1") is None


def test_the_documented_template_engages_as_written(tmp_path):
    doc = TEMPLATE_DOC.read_text(encoding="utf-8")
    template = re.search(r"```markdown\n(.*?)\n```", doc, re.S).group(1)
    for item_id, _ in cli.DEFAULT_STANDING:
        assert item_id in doc
    for name in ("Status:", "Owner session:", "Engaged:", "Horizon:", "Continuation:", "First wake:",
                 "Backstop:", "Waiting on:", "Silent after:"):
        assert name in template
    folder = tmp_path / "kb" / "projects" / "alpha" / "resources" / "artifacts"
    folder.mkdir(parents=True)
    path = folder / "plan.md"
    path.write_text(template, encoding="utf-8")
    engage("S1", path)
    assert "Continue with the next one now" in stop("S1")


def test_binding_rule_14_stops_the_run_on_its_count_and_the_plan_file_page_says_how():
    """The convention is the skill's to state, and the count reads only what the plan file carries: each item's origin,
    the time an item was added after engagement and the time each item closed, one dated answer line, and the open
    principal items written day by day."""
    rules = (SKILL / "SKILL.md").read_text(encoding="utf-8").split("## Binding rules")[1].split("## Contents")[0]
    rule = " ".join(next((line for line in rules.splitlines() if line.startswith("14. ")), "").split())
    for words in ("`principal` or `self`", "close time", "over 24 hours", "two days running", "`cycle` refuses",
                  "start nothing new", "continue, narrow or stop"):
        assert words in rule, words
    doc = TEMPLATE_DOC.read_text(encoding="utf-8")
    assert "- [Origins and the count](#origins-and-the-count)" in doc
    template = re.search(r"```markdown\n(.*?)\n```", doc, re.S).group(1)
    for words in ("Principal answer:", "(origin: principal)", "## Backlog count"):
        assert words in template, words
    section = " ".join(doc.split("\n## Origins and the count\n")[1].split("\n## ")[0].split())
    for words in ("`origin: principal`", "`origin: self`", "`added <time>`", "`closed <time>`", "last 24 hours",
                  "two days running", "`Principal answer:`", "counts nothing", "says so once"):
        assert words in section, words


def test_the_procedures_six_steps_moved_word_for_word_to_their_own_page():
    """Rule 14 needed room under SKILL.md's 8,000 bytes, so the Procedure's six steps moved whole to references/procedure.md;
    the helper path stays where Contents points for it."""
    skill = (SKILL / "SKILL.md").read_text(encoding="utf-8")
    page = (SKILL / "references" / "procedure.md").read_text(encoding="utf-8")
    for step in ("1. **Engage.** Tell the user in one line: mode plus plan path.",
                 "2. **Plan.** Write the plan in the project from the template, then `engage --plan <path>`.",
                 "3. **Phase loop.** Re-read the plan and board; work with anti-shortcut discipline;",
                 "4. **Wait or block honestly.** Nothing ready: `Status: waiting` with `Waiting on:`.",
                 "5. **Verify.** Run synthesis-implementation-integrity or the domain's equivalent",
                 "6. **Close.** Delete every scheduled job and read the deletion back;"):
        assert step in page and step not in skill, step
    procedure = skill.split("\n## Procedure\n")[1]
    assert "[references/procedure.md](references/procedure.md)" in procedure and 'AP="$HOME/.synthesis/v5' in procedure


# ---- scenarios 1 to 5: when the turn-end check asks, and when it stays out ----

def test_1_running_plan_asks_once_for_the_next_open_item(tmp_path):
    path = write_plan(tmp_path)
    engage("S1", path)
    reason = stop("S1")
    assert "Continue with the next one now: 2. Migrate /orders (1 more open after it)" in reason
    assert "Status: blocked" in reason and "close" not in reason.split("Migrate /orders")[0]


def test_1_all_items_checked_asks_for_an_honest_close(tmp_path):
    path = write_plan(tmp_path, checklist=("- [x] 1. Migrate /users",))
    engage("S1", path)
    assert "close it honestly" in stop("S1")


def test_2_at_most_three_continuations_in_a_row_then_a_note(tmp_path):
    path = write_plan(tmp_path)
    engage("S1", path)
    assert stop("S1") is not None
    assert stop("S1", stop_hook_active=True) is not None
    assert stop("S1", stop_hook_active=True) is not None
    reason, note = autopilot.evaluate({"session_id": "S1", "stop_hook_active": True}, {})
    assert reason is None and "3 times in a row" in note and str(path) in note
    assert autopilot.evaluate({"session_id": "S1", "stop_hook_active": True}, {}) == (None, None)
    edit(path, "- [ ] 2. Migrate /orders", "- [x] 2. Migrate /orders")  # progress, then a fresh turn
    assert "3. Update their tests" in stop("S1", stop_hook_active=False)


def test_2_an_unchanged_plan_counts_as_a_repeat_when_the_harness_sends_no_flag(tmp_path):
    path = write_plan(tmp_path)
    engage("S1", path)
    assert [stop("S1") is not None for _ in range(3)] == [True, True, True]
    assert stop("S1") is None


def test_2_the_limit_is_configurable(tmp_path):
    engage("S1", write_plan(tmp_path))
    config = {"autopilot": {"max_continuations": 1}}
    assert _check({"session_id": "S1"}, config) is not None
    assert _check({"session_id": "S1", "stop_hook_active": True}, config) is None


def test_3_any_error_lets_the_turn_end(tmp_path, monkeypatch):
    path = write_plan(tmp_path)
    engage("S1", path)
    with monkeypatch.context() as patched:  # scoped, so the isolated home stays in place
        patched.setattr(autopilot, "turn_end_reason", lambda *a: 1 / 0)
        assert stop("S1") is None
    autopilot._pointer_file("S1").write_text("{not json", encoding="utf-8")
    assert stop("S1") is None
    engage("S1", path)
    path.unlink()
    assert stop("S1") is None
    assert _check(None, None) is None and _check({"session_id": 7}, {}) is None


def test_4_no_session_no_plan_or_an_unknown_client_is_silent():
    assert _check({}, {}) is None
    assert _check({"session_id": "nobody-engaged"}, {}) is None
    assert _check({"hook_event_name": "Stop", "cwd": "/"}, {}) is None


def test_5_another_sessions_plan_never_blocks_this_session(tmp_path):
    path = write_plan(tmp_path)
    engage("S1", path)
    assert stop("S2") is None
    autopilot._write_pointer("S2", {"plan": str(path)})  # S2 pointed at a plan S1 owns
    assert stop("S2") is None
    garbage = tmp_path / "garbage.md"
    garbage.write_bytes(b"\xff\xfe\x00 not a plan")
    autopilot._write_pointer("S3", {"plan": str(garbage)})
    assert stop("S3") is None


def test_a_running_background_task_or_a_principal_pause_lets_the_turn_end(tmp_path):
    path = write_plan(tmp_path)
    engage("S1", path)
    assert stop("S1", background_tasks=[{"id": "b1", "command": "pytest"}]) is None
    edit(path, "Status: running", "Status: paused — the principal asked to pause at 14:02")
    assert stop("S1") is None


# ---- scenarios 6 and 7: continuation must be real and must outlive the session ----

def test_6_a_scheduled_continuation_counts_only_once_its_first_wake_is_seen(tmp_path):
    waiting = {"Status": "waiting", "Waiting on": "CI run 812 (about 40 minutes)",
               "Continuation": "Codex scheduled task 'wake-alpha', hourly, this thread", "First wake": "not yet"}
    path = write_plan(tmp_path, header={**waiting, "Engaged": ago(120)})
    engage("S1", path)
    assert "no observed first wake 60 minutes after engagement" in stop("S1")
    edit(path, f"Engaged: {autopilot.load(path).field('engaged')}", f"Engaged: {ago(10)}")
    assert stop("S1") is None
    edit(path, "First wake: not yet", f"First wake: {ago(5)}")
    edit(path, f"Engaged: {autopilot.load(path).field('engaged')}", f"Engaged: {ago(300)}")
    assert stop("S1") is None


def test_6_waiting_needs_a_named_wait_and_something_that_will_wake_the_session(tmp_path):
    path = write_plan(tmp_path, header={"Status": "waiting", "Continuation": None, "Backstop": None})
    engage("S1", path)
    reason = stop("S1")
    assert "Waiting on:" in reason and "nothing is recorded that will wake" in reason
    edit(path, "Status: waiting", "Status: waiting\nWaiting on: the nightly export")
    assert stop("S1", session_crons=[{"id": "c1", "cron": "*/20 * * * *"}]) is None


def test_7_an_overnight_run_needs_a_backstop_that_outlives_the_session(tmp_path):
    header = {"Status": "waiting", "Waiting on": "CI", "Horizon": "overnight (until 08:00)",
              "Continuation": None, "Backstop": "none"}
    path = write_plan(tmp_path, header=header)
    engage("S1", path)
    crons = [{"id": "c1", "cron": "*/30 * * * *"}]
    assert "record a backstop that survives this session" in stop("S1", session_crons=crons)
    edit(path, "Backstop: none", "Backstop: Claude desktop scheduled task alpha-backstop, hourly")
    assert "how to stop it" in stop("S1", session_crons=crons)
    edit(path, "hourly", "hourly — stop: delete it under Scheduled in the desktop app")
    assert stop("S1", session_crons=crons) is None


def test_7_running_overnight_without_continuation_names_both_gaps(tmp_path):
    path = write_plan(tmp_path, header={"Horizon": "overnight", "Continuation": None, "Backstop": None})
    engage("S1", path)
    reason = stop("S1")
    assert "Migrate /orders" in reason and "no continuation is recorded" in reason and "backstop" in reason


# ---- scenario 8: closing deletes every scheduled job; late wakes do nothing ----

def test_8_close_requires_every_scheduled_job_deleted_and_read_back(tmp_path, capsys):
    backstop = "Codex scheduled task alpha-backstop — stop: delete it in the app"
    path = done_ready(tmp_path, Backstop=backstop, Continuation="/loop every 30m, job c1")
    engage("S1", path)
    assert run("--session", "S1", "close", "--plan", path, "--done") == 1
    err = capsys.readouterr().err
    assert "Continuation: job is not recorded as deleted" in err and "Backstop: job" in err
    edit(path, "job c1", "job c1, deleted 2026-10-06T07:10 (CronList no longer shows it)")
    edit(path, backstop, backstop + "; deleted 2026-10-06T07:11, read back from the app")
    assert run("--session", "S1", "close", "--plan", path, "--done") == 0
    assert autopilot.load(path).status == "done"
    assert stop("S1") is None and not autopilot._pointer_file("S1").exists()
    assert str(path) not in board.load("S1").claims


def test_8_a_hand_written_close_with_a_live_job_is_caught_at_turn_end(tmp_path):
    path = done_ready(tmp_path, Backstop="desktop task nightly — stop: delete in app")
    engage("S1", path)
    edit(path, "Status: running", "Status: done")
    assert "Backstop: job is not recorded as deleted" in stop("S1")


def test_8_every_scheduled_wake_reads_the_plan_first_and_stops_on_a_closed_one(tmp_path, capsys):
    path = write_plan(tmp_path)
    assert run("wake-prompt", "--plan", path) == 0
    prompt = capsys.readouterr().out
    assert str(path) in prompt and "Read that plan before anything else" in prompt
    assert "do no work: delete this scheduled job, read the deletion back" in prompt


# ---- scenario 9: no bare spins -------------------------------------------------

def test_9_a_cycle_that_advanced_nothing_must_name_its_wait(tmp_path, capsys):
    path = write_plan(tmp_path)
    engage("S1", path)
    before = path.read_text(encoding="utf-8")
    assert run("--session", "S1", "cycle", "--plan", path) == 1
    assert "bare spin" in capsys.readouterr().err and path.read_text(encoding="utf-8") == before
    assert run("--session", "S1", "cycle", "--plan", path, "--waiting-on", "CI run 812") == 0
    assert run("--session", "S1", "cycle", "--plan", path, "--advanced", "migrated /orders") == 0
    ledger = [l for l in autopilot.load(path).sections["cycle ledger"] if l.strip()]
    assert "waiting on: CI run 812" in ledger[0] and "advanced: migrated /orders" in ledger[1]


# ---- the run's own work against the principal's: the count, its stop and the principal's answer ----
# The principal's rulings of 2026-11-16. A principal item delivers the principal's request, their backlog or a build
# their ruling ordered; a self-generated item only fixes, reviews or re-reviews what the run itself produced. When,
# over a day, the run adds more of its own items than it closes of the principal's, or the principal's open items
# rise two days running, it starts nothing new and asks the principal one line: continue, narrow, or stop.

def tagged(tmp_path, *, closed=(), added=(), still_open=1, answer=None, days=(), header=None):
    """A plan whose items carry their origin: the principal's items closed `closed` minutes ago, the run's own items
    added `added` minutes ago and still open, `still_open` of the principal's items open, and the open principal items
    counted on the days before today, oldest first, as `days`."""
    items = [f"- [x] {n}. Ship part {n} (origin: principal, closed {ago(m)}) — its tests pass" for n, m in enumerate(closed, 1)]
    items += [f"- [ ] {len(items) + n}. Close what review round {n} found (origin: self, added {ago(m)})"
              for n, m in enumerate(added, 1)]
    items += [f"- [ ] {len(items) + n}. Ship part {len(items) + n} (origin: principal)" for n in range(1, still_open + 1)]
    path = write_plan(tmp_path, checklist=items, header={**(header or {}), **({"Principal answer": answer} if answer else {})})
    if days:
        lines = [f"- {(date.today() - timedelta(days=len(days) - i)).isoformat()}: {n} open principal item(s)"
                 for i, n in enumerate(days)]
        with path.open("a", encoding="utf-8") as handle:
            handle.write("\n## Backlog count\n\n" + "\n".join(lines) + "\n")
    return path


def advance(path, what="closed the next part") -> int:
    return run("--session", "S1", "cycle", "--plan", path, "--advanced", what)


def test_cycle_refuses_an_advance_once_the_runs_own_items_outnumber_the_principals_closed_over_24_hours(tmp_path, capsys):
    """The advance is not recorded, and cycle prints the one line to bring the principal. A wait is still recorded,
    with the line still to ask."""
    path = tagged(tmp_path, closed=(90,), added=(60, 30))
    engage("S1", path)
    capsys.readouterr()
    assert advance(path, "re-reviewed the fix") == 1
    err = capsys.readouterr().err
    assert ("migrate endpoints: in the last 24 hours this run added 2 item(s) of its own and closed 1 of yours. "
            "Continue, narrow, or stop?") in err
    assert "Start nothing new" in err and "Principal answer:" in err and "## Blockers" in err
    assert "re-reviewed the fix" not in path.read_text(encoding="utf-8")
    assert run("--session", "S1", "cycle", "--plan", path, "--waiting-on", "the principal's answer") == 0
    assert "Continue, narrow, or stop?" in capsys.readouterr().out
    assert "waiting on: the principal's answer" in path.read_text(encoding="utf-8")


def test_a_continue_or_narrow_answer_dated_inside_the_window_lets_the_run_go_on_and_nothing_else_does(tmp_path):
    """The principal's answer is one dated line the template names. Continue lets the run go on; so does narrow, once
    the plan is narrowed as they said. An answer older than the window's start, a stop, or one with no time does not."""
    cases = ((f"continue {ago(30)}", 0), (f"narrow {ago(30)}", 0), (f"continue {ago(25 * 60)}", 1),
             (f"stop {ago(30)}", 1), ("continue", 1))
    for i, (answer, refused) in enumerate(cases):
        path = tagged(tmp_path / str(i), closed=(90,), added=(60, 30), answer=answer)
        engage("S1", path)
        assert advance(path) == refused, answer
        assert ("advanced: closed the next part" in path.read_text(encoding="utf-8")) == (not refused), answer


def test_only_the_last_24_hours_are_counted(tmp_path):
    cases = (((), (25 * 60, 26 * 60), 0),    # the run's own items were added more than a day ago
             ((25 * 60,), (30,), 1),          # the principal's item closed more than a day ago: one of its own against none
             ((23 * 60, 22 * 60), (30,), 0),  # two of the principal's against one of its own
             ((60,), (30,), 0))               # level is not outnumbered
    for i, (closed, added, refused) in enumerate(cases):
        path = tagged(tmp_path / str(i), closed=closed, added=added)
        engage("S1", path)
        assert advance(path) == refused, (closed, added)


def test_cycle_records_each_wake_with_the_days_count_of_both(tmp_path, capsys):
    path = tagged(tmp_path, closed=(90, 80), added=(30,), still_open=3)
    engage("S1", path)
    capsys.readouterr()
    assert advance(path) == 0
    assert ("last 24 hours: 2 principal item(s) closed, 1 self-generated item(s) added; 3 principal item(s) open"
            in capsys.readouterr().out)
    ledger = [line for line in autopilot.load(path).sections["cycle ledger"] if line.strip()]
    assert ledger[-1].endswith("advanced: closed the next part; last 24 h: 2 principal closed, 1 self added")


def test_the_open_principal_items_are_written_at_each_days_first_wake_and_two_rises_running_stop_the_run(tmp_path, capsys):
    path = tagged(tmp_path, still_open=4, days=(2, 3))
    engage("S1", path)
    capsys.readouterr()
    assert advance(path) == 1
    assert ("migrate endpoints: your open items in this run rose two days running (2, 3, 4). Continue, narrow, or stop?"
            in capsys.readouterr().err)
    today = f"- {date.today().isoformat()}: 4 open principal item(s)"
    assert autopilot.load(path).sections["backlog count"].count(today) == 1  # written at the day's first wake, refused or not
    edit(path, "Status: running", f"Status: running\nPrincipal answer: continue {ago(1)}")
    assert advance(path) == 0 and advance(path, "closed another part") == 0
    assert autopilot.load(path).sections["backlog count"].count(today) == 1  # once a day
    for i, (days, still_open) in enumerate((((3, 2), 4), ((2, 3), 3), ((2,), 3))):  # a fall, a level day, one day only
        path = tagged(tmp_path / str(i), still_open=still_open, days=days)
        engage("S1", path)
        assert advance(path) == 0, days


def test_both_reasons_go_in_the_one_line(tmp_path, capsys):
    path = tagged(tmp_path, closed=(90,), added=(60, 30), still_open=4, days=(2, 3))
    engage("S1", path)
    capsys.readouterr()
    assert advance(path) == 1
    assert ("in the last 24 hours this run added 2 item(s) of its own and closed 1 of yours, and your open items in "
            "this run rose two days running (2, 3, 4). Continue, narrow, or stop?") in capsys.readouterr().err


def test_a_plan_without_origins_counts_nothing_and_says_so_once(tmp_path, capsys):
    """A plan written before origins: every item is unknown, nothing is counted, nothing stops the run, and cycle says
    so once, and again only when more such items appear."""
    path = write_plan(tmp_path)
    engage("S1", path)
    capsys.readouterr()
    assert advance(path, "migrated /orders") == 0
    out = capsys.readouterr().out
    assert out.count("the count leaves out 3 checklist item(s)") == 1 and "last 24 hours" not in out
    assert advance(path, "updated their tests") == 0
    assert "leaves out" not in capsys.readouterr().out
    plan = autopilot.load(path)
    assert "backlog count" not in plan.sections
    assert [line for line in plan.sections["cycle ledger"] if "the count leaves out 3 item(s)" in line] != []
    assert "Continue with the next one now: 2. Migrate /orders (1 more open after it)" in stop("S1")
    edit(path, "- [ ] 3. Update their tests", "- [ ] 3. Update their tests\n- [ ] 4. Tidy the fixtures")
    assert advance(path, "tidied") == 0
    assert "the count leaves out 4 checklist item(s)" in capsys.readouterr().out


def test_an_item_the_count_cannot_place_is_left_out_and_said(tmp_path, capsys):
    """An item of the principal's checked with no close time, or one of the run's own with no added time, is left
    out like an item with no origin."""
    path = tagged(tmp_path, closed=(90,), added=(60,))
    edit(path, "(origin: self, added", "(origin: self, found")
    edit(path, "- [ ] 3. Ship part 3 (origin: principal)", "- [x] 3. Ship part 3 (origin: principal) — shipped")
    engage("S1", path)
    capsys.readouterr()
    assert advance(path) == 0
    assert "the count leaves out 2 checklist item(s)" in capsys.readouterr().out


def test_the_documented_cycle_output_is_what_cycle_prints(tmp_path, capsys):
    """The helper page says its output is real: its three cycle examples are run here, times aside."""
    doc = (SKILL / "references" / "turn-end-check.md").read_text(encoding="utf-8").split("**Cycle**")[1].split("**Close**")[0]
    blocks = [[line for line in block.splitlines() if not line.startswith("$ ")]
              for block in re.findall(r"```text\n(.*?)\n```", doc, re.S)]
    older = write_plan(tmp_path / "older", checklist=("- [ ] 1. Migrate /orders and its tests", "- [ ] 2. Retire the v1 route"))
    engage("S1", older)
    capsys.readouterr()
    assert advance(older, "migrated /orders; 12 tests pass") == 0
    assert capsys.readouterr().out.splitlines() == blocks[0][:2]
    path = tagged(tmp_path / "counted", closed=(90,), added=(60, 30))
    engage("S1", path)
    capsys.readouterr()
    assert advance(path, "re-reviewed the guard fix") == 1
    stamp = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}[+-]\d{2}:\d{2}")
    assert stamp.sub("<time>", capsys.readouterr().err).splitlines() == [stamp.sub("<time>", line) for line in blocks[1]]
    edit(path, "Status: running", f"Status: running\nPrincipal answer: continue {ago(1)}")
    assert advance(path, "re-reviewed the guard fix") == 0
    assert capsys.readouterr().out.splitlines() == blocks[2]


def test_the_turn_end_check_asks_the_run_to_stop_and_bring_the_one_line_rather_than_the_next_item(tmp_path):
    path = tagged(tmp_path, closed=(90,), added=(60, 30))
    engage("S1", path)
    reason = stop("S1")
    assert "start nothing new" in reason and "Continue, narrow, or stop?" in reason and "Principal answer:" in reason
    assert "Continue with the next one now" not in reason
    edit(path, "Status: running", f"Status: running\nPrincipal answer: continue {ago(1)}")
    assert "Continue with the next one now: 2. Close what review round 1 found" in stop("S1")
    blocked = tagged(tmp_path / "blocked", closed=(90,), added=(60, 30), header={"Status": "blocked"})
    edit(blocked, "## Blockers\n", "## Blockers\n\n- [ ] Continue, narrow, or stop? — alerted 2026-11-16T10:00 (banner posted)\n")
    engage("S2", blocked)
    assert stop("S2") is None
    rising = tagged(tmp_path / "rising", still_open=4, days=(2, 3))
    engage("S3", rising)
    assert "rose two days running (2, 3, 4)" in stop("S3")


# ---- scenarios 10 to 14: an honest close ----------------------------------------

def test_10_done_is_refused_while_required_evidence_sits_in_scratch(tmp_path, capsys):
    scratch = tmp_path / "scratchpad"
    scratch.mkdir()
    (scratch / "findings.md").write_text("findings\n", encoding="utf-8")
    path = done_ready(tmp_path)
    edit(path, "## Required evidence\n", f"## Required evidence\n\n- `{scratch / 'findings.md'}`\n"
                                         "- [labels](../evidence/labels.md)\n")
    engage("S1", path)
    assert run("--session", "S1", "close", "--plan", path, "--done") == 1
    err = capsys.readouterr().err
    assert "findings.md sits in a scratch or temp folder" in err and "labels.md does not exist" in err
    assert "Closing as incomplete with the reason stays available" in err
    assert autopilot.load(path).status == "running"
    assert run("--session", "S1", "close", "--plan", path, "--incomplete", "labels research lost; redo") == 0
    assert autopilot.load(path).status == "incomplete"


def test_11_scratch_paths_in_prose_examples_and_comments_do_not_block(tmp_path):
    path = done_ready(tmp_path)
    edit(path, "Move the two remaining endpoints.",
         "Move the two remaining endpoints. Earlier drafts lived in /tmp/old-notes.md.")
    edit(path, "## Required evidence\n", "## Required evidence\n\n<!-- e.g. - `/tmp/example.md` -->\n"
                                         "```\n- /private/tmp/fenced-example.md\n```\n")
    engage("S1", path)
    assert run("--session", "S1", "close", "--plan", path, "--done") == 0


def test_12_done_is_refused_for_a_missing_plan_or_one_without_criteria(tmp_path, capsys):
    assert run("--session", "S1", "close", "--plan", tmp_path / "missing.md", "--done") == 1
    assert "no plan file" in capsys.readouterr().err
    path = done_ready(tmp_path)
    engage("S1", path)
    edit(path, "- [x] Endpoint tests pass — pytest tests/api: 42 passed", "")
    edit(path, "Status: running", "Status: done")
    assert "no completion criteria" in stop("S1")


def test_12_a_criterion_checked_without_evidence_is_not_met(tmp_path):
    path = done_ready(tmp_path)
    engage("S1", path)
    edit(path, " — pytest tests/api: 42 passed", "")
    edit(path, "Status: running", "Status: done")
    assert "criterion checked without evidence" in stop("S1")


def test_13_a_blocker_stays_open_until_it_is_resolved(tmp_path, capsys):
    path = done_ready(tmp_path)
    edit(path, "## Blockers\n", "## Blockers\n\n- [ ] Staging credentials expired; alerted 2026-10-05T22:10 "
                                "(banner posted; audio played)\n")
    engage("S1", path)
    edit(path, "- [x] 2. Migrate /orders", "- [ ] 2. Migrate /orders")
    assert "Continue with the next one now" in stop("S1")  # an old blocker is not a way out of work
    edit(path, "- [ ] 2. Migrate /orders", "- [x] 2. Migrate /orders")
    assert run("--session", "S1", "close", "--plan", path, "--done") == 1
    assert "blocker still open: Staging credentials expired" in capsys.readouterr().err
    edit(path, "- [ ] Staging credentials", "- [x] Staging credentials")
    assert run("--session", "S1", "close", "--plan", path, "--done") == 0


def test_14_a_standing_item_added_mid_run_needs_a_disposition(tmp_path, capsys):
    path = done_ready(tmp_path)
    engage("S1", path)
    edit(path, "## Blockers", "- [ ] blog-seeds: Blog material captured as work proceeds.\n\n## Blockers")
    assert run("--session", "S1", "close", "--plan", path, "--done") == 1
    assert "standing item blog-seeds has no disposition (evidence, or WAIVED: reason)" in capsys.readouterr().err
    edit(path, "as work proceeds.\n", "as work proceeds. — WAIVED: no public angle in an endpoint move\n")
    assert run("--session", "S1", "close", "--plan", path, "--done") == 0


# ---- scenarios 15 and 16: one owner; silent owners can be replaced -------------

def test_15_a_second_session_cannot_engage_or_write_a_plan_another_holds(tmp_path, capsys):
    path = write_plan(tmp_path)
    engage("S1", path)
    assert run("--session", "S2", "engage", "--plan", path) == 1
    assert "owned by session S1" in capsys.readouterr().err
    board.load("S1")  # the claim is the board's, so commits by S2 are refused there too (R2.1)
    with pytest.raises(board.ClaimConflict, match="held by S1"):
        board.claim("S2", [str(path)])
    assert run("--session", "S2", "cycle", "--plan", path, "--advanced", "x") == 1
    assert run("--session", "S2", "close", "--plan", path, "--incomplete", "x") == 1


def test_16_a_plan_silent_for_eight_hours_can_be_taken_over_with_its_items(tmp_path, capsys):
    path = write_plan(tmp_path)
    engage("S1", path)
    assert run("--session", "S2", "takeover", "--plan", path) == 1
    assert "message it with `synthesis msg S1" in capsys.readouterr().err
    old = time.time() - 9 * 3600
    os.utime(path, (old, old))
    holder = board.load("S1")
    holder.seen = old
    board.save(holder)
    assert run("--session", "S2", "takeover", "--plan", path) == 0
    plan = autopilot.load(path)
    assert plan.field("owner session") == "S2" and plan.open_items() == ["2. Migrate /orders", "3. Update their tests"]
    assert "Took over autopilot plan" in board.inbox("S1")[0]["text"]
    assert stop("S1") is None and "Migrate /orders" in stop("S2")


def test_16_an_overnight_plan_can_shorten_the_silence_limit_for_its_backstop(tmp_path):
    path = write_plan(tmp_path, header={"Silent after": "90 minutes"})
    engage("S1", path)
    old = time.time() - 2 * 3600
    os.utime(path, (old, old))
    holder = board.load("S1")
    holder.seen = old
    board.save(holder)
    assert run("--session", "S2", "takeover", "--plan", path) == 0


# ---- scenario 17: authority never comes from a file --------------------------

def test_17_a_deploy_grant_written_in_the_plan_grants_nothing(tmp_path):
    path = write_plan(tmp_path, mission="Deploy authority this run: production deploy approved by the principal.")
    engage("S1", path)
    assert guards.check("Bash", {"command": "wrangler pages deploy dist --project-name=site"}, {}) is not None


# ---- scenarios 23 and 25: blocked runs alert, and capability claims carry a probe ----

def test_23_25_each_open_blocker_needs_its_own_alert_and_absence_claims_need_a_probe(tmp_path):
    blockers = ("- [ ] Need the principal's pick between two vendors; alerted 2026-10-05T22:12 (banner posted)",
                "- [ ] Muse cannot run unattended overnight on this Mac")
    path = write_plan(tmp_path, header={"Status": "blocked"}, blockers=blockers)
    engage("S1", path)
    reason = stop("S1")
    assert "no alert recorded for: Muse cannot run unattended" in reason
    assert "no probe recorded for the capability claim" in reason and "two vendors" not in reason
    edit(path, "overnight on this Mac", "overnight on this Mac; probe: `muse --help | grep -i schedule` -> no "
                                        "out-of-session scheduler; alerted 2026-10-05T22:14 (audio suppressed (mute flag))")
    assert stop("S1") is None


def test_23_alerts_carry_counts_only_and_a_muted_alert_is_suppressed_not_delivered(tmp_path):
    calls = []

    class Done:
        returncode = 0

    def fake(command, **kwargs):
        calls.append(command)
        return Done()

    which = lambda name: f"/usr/bin/{name}"
    mute = tmp_path / "quiet-audio"
    mute.touch()
    outcomes = cli.alert("blocked", 2, mute_flag=mute, run=fake, which=which)
    assert outcomes == [("banner", "posted"), ("audio", "suppressed (mute flag)")]
    assert len(calls) == 1 and "2 question(s)" in calls[0][-1] and "alpha" not in calls[0][-1]
    mute.unlink()
    assert dict(cli.alert("done", 1, mute_flag=mute, run=fake, which=which))["audio"] == "played"

    def broken(command, **kwargs):
        raise OSError("no display")

    assert dict(cli.alert("budget", 3, mute_flag=mute, run=broken, which=which))["banner"] == "failed (OSError)"
    assert dict(cli.alert("done", 1, mute_flag=mute, run=fake, which=lambda n: None)) == {
        "banner": "unavailable (no osascript)", "audio": "unavailable (no say)"}


# ---- scenario 24: the person sees open questions without the harness pane ------

def test_24_status_shows_every_runs_next_item_blockers_and_open_questions(tmp_path, capsys):
    questions = ("- [ ] Keep the v1 endpoints alive for a week?", "- [x] Use the staging DB? — yes, 10-05")
    path = write_plan(tmp_path, questions=questions, blockers=("- [ ] Waiting on the vendor's API key; alerted x",))
    engage("S1", path)
    capsys.readouterr()
    assert run("--session", "S9", "status", "--all") == 0
    out = capsys.readouterr().out
    assert str(path) in out and "next: 2. Migrate /orders  (2 of 3 items open)" in out
    assert "question: Keep the v1 endpoints alive for a week?" in out and "staging DB" not in out
    assert "blocker: Waiting on the vendor's API key" in out
    assert run("--session", "S1", "status", "--json") == 0
    [row] = json.loads(capsys.readouterr().out)
    assert row["plan"] == str(path) and row["this_session"] and (row["open"], row["total"]) == (2, 3)
    assert row["next"] == "2. Migrate /orders" and row["questions"] == ["Keep the v1 endpoints alive for a week?"]
    assert row["blockers"] == ["Waiting on the vendor's API key; alerted x"]
    assert run("--session", "S9", "status", "--json") == 0 and json.loads(capsys.readouterr().out) == []


# ---- scenario 30 and R6.3: nothing old is read; compaction brings the run back ----

def test_30_old_engagement_records_are_never_read(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    legacy = tmp_path / ".synthesis" / "autopilot" / "engagements"
    legacy.mkdir(parents=True)
    (legacy / "overnight-abc.json").write_text(json.dumps({"status": "active", "session_id": "S1",
                                                           "plan": str(tmp_path / "p.md")}), encoding="utf-8")
    (legacy / "broken.json").write_text("{", encoding="utf-8")
    assert stop("S1") is None and stop("anyone") is None


def test_session_start_brief_brings_the_run_back_after_compaction(tmp_path):
    path = write_plan(tmp_path)
    engage("S1", path)
    note = autopilot.brief({"session_id": "S1", "source": "compact"})
    assert str(path) in note and "Next open item: 2. Migrate /orders" in note
    assert autopilot.brief({"session_id": "S2"}) == ""


def test_session_start_brief_says_a_run_its_count_stopped_waits_for_the_principals_answer(tmp_path):
    """When the count has stopped the run, what comes back at session start and after compaction says so, with the
    one line, and names no next item to start; once the principal's answer is written, the next item comes back."""
    path = tagged(tmp_path, closed=(90,), added=(60, 30))
    engage("S1", path)
    note = autopilot.brief({"session_id": "S1", "source": "compact"})
    assert note.startswith(f"Autopilot run stopped by its count, waiting for the principal's answer: {path} ")
    assert ("The one line: migrate endpoints: in the last 24 hours this run added 2 item(s) of its own and closed 1 of "
            "yours. Continue, narrow, or stop?") in note
    assert "start nothing new" in note and "Principal answer:" in note and "Next open item" not in note
    edit(path, "Status: running", "Status: blocked")
    assert "waiting for the principal's answer" in autopilot.brief({"session_id": "S1"})  # asked, not yet answered
    edit(path, "Status: blocked", f"Status: running\nPrincipal answer: continue {ago(1)}")
    assert "Next open item: 2. Close what review round 1 found" in autopilot.brief({"session_id": "S1"})


def test_the_fan_out_rules_and_binding_rule_11_name_the_three_agent_cap():
    """The principal's caps of 2026-11-16 bound every fan-out, a review's or not: at most three agents at once."""
    fan_out = (SKILL / "references" / "delegation.md").read_text(encoding="utf-8").split(
        "\n## Sub-Agent Fan-Out Hygiene\n")[1].split("\n## ")[0]
    assert "**At most three agents at once.**" in fan_out and "references/review-caps.md" in fan_out
    rules = (SKILL / "SKILL.md").read_text(encoding="utf-8").split("## Binding rules")[1].split("## Contents")[0]
    assert "At most three agents run at once." in next(line for line in rules.splitlines() if line.startswith("11. "))


# ---- R6.4 and R8.1: fast enough for every turn end ------------------------------

def test_the_check_takes_well_under_50_ms(tmp_path, pace):
    path = write_plan(tmp_path, checklist=[f"- [x] {i}. step" for i in range(200)] + ["- [ ] 200. last step"])
    edit(path, "## Cycle ledger\n", "## Cycle ledger\n\n" + "".join(f"- 2026-10-05T{i % 24:02}:00 advanced: x\n"
                                                                    for i in range(2000)))
    engage("S1", path)
    times = []
    for _ in range(15):
        start = time.perf_counter()
        _check({"session_id": "S1", "stop_hook_active": False}, {})
        times.append(time.perf_counter() - start)
    assert statistics.median(times) < 0.05 * pace


def test_the_count_keeps_the_check_well_under_50_ms(tmp_path, pace):
    """The check counts from the plan it already read: every item's origin and times, the answer line and the days."""
    items = [f"- [x] {i}. step (origin: principal, closed {ago(i)}) — done" for i in range(100)]
    items += [f"- [ ] {i}. fix (origin: self, added {ago(i)})" for i in range(100, 200)] + ["- [ ] 200. last (origin: principal)"]
    path = tagged(tmp_path, days=tuple(range(60, 0, -1)))
    edit(path, "## Checklist\n", "## Checklist\n\n" + "\n".join(items) + "\n")
    edit(path, "## Cycle ledger\n", "## Cycle ledger\n\n" + "".join(f"- 2026-10-05T{i % 24:02}:00 advanced: x\n"
                                                                    for i in range(2000)))
    engage("S1", path)
    assert "Continue with the next one now: 100. fix" in stop("S1")  # 100 of each in the window: level, so it goes on
    times = []
    for _ in range(15):
        start = time.perf_counter()
        _check({"session_id": "S1", "stop_hook_active": False}, {})
        times.append(time.perf_counter() - start)
    assert statistics.median(times) < 0.05 * pace


# What the modules the turn-end check loads import as they load, by the module that asks.
CHECK_NEEDS = ("json", "sys",                                                       # the caller
               "__future__", "datetime", "hashlib", "os", "pathlib", "re", "time",  # autopilot.py
               "unicodedata")                                                       # paths.py


def test_a_cold_hook_process_stays_inside_the_hook_budget(tmp_path, compiled_runtime, hook_budget):
    """The check as a session meets it: a new process, the installed runtime, compiled as the installer leaves it."""
    path = write_plan(tmp_path)
    engage("S1", path)
    call = ["-c", "import json, sys; sys.path.insert(0, sys.argv[1]); from synthesis import autopilot; "
                  "print(autopilot.evaluate(json.load(sys.stdin), {})[0] or '')", str(compiled_runtime)]
    said = hook_budget(call, CHECK_NEEDS, input=json.dumps({"session_id": "S1"}))
    assert "Migrate /orders" in said  # the first run; later ones meet the repeat cap, which does the same work


def test_the_helpers_run_as_a_script_without_site_packages(tmp_path, isolated_home):
    path = write_plan(tmp_path)
    env = {**os.environ, "SYNTHESIS_HOME": str(isolated_home)}
    out = subprocess.run([sys.executable, "-S", str(CLI), "--session", "S1", "engage", "--plan", str(path)],
                         capture_output=True, text=True, env=env)
    assert out.returncode == 0, out.stderr
    out = subprocess.run([sys.executable, "-S", str(CLI), "--session", "S1", "status"],
                         capture_output=True, text=True, env=env)
    assert "status: running" in out.stdout


def test_the_documented_helper_path_is_the_copy_the_install_makes_and_it_runs(tmp_path, isolated_home):
    """Every `$HOME/.synthesis/v5/current/...` path the skill documents is a file the install puts in
    the runtime, and the helpers run from there with only the runtime on the path."""
    docs = [SKILL / "SKILL.md"] + sorted((SKILL / "references").glob("*.md"))
    documented = {m.group(1) for doc in docs if not doc.name.startswith("preserved")
                  for m in re.finditer(r"\$HOME/\.synthesis/v5/current/([\w./-]+\.py)", doc.read_text(encoding="utf-8"))}
    assert documented == {"skills/synthesis-autopilot/scripts/autopilot_cli.py",
                          "skills/synthesis-daily-rituals/scripts/relied_on.py"}  # the check every wake runs
    assert cli.wake_prompt("<plan>") in (SKILL / "references" / "turn-end-check.md").read_text(encoding="utf-8")
    assert {"synthesis-autopilot", "synthesis-daily-rituals"} <= set(install.STABLE_SKILL_SCRIPTS)
    plugin = tmp_path / "plugin"
    shutil.copytree(ROOT / "synthesis", plugin / "synthesis", ignore=shutil.ignore_patterns("__pycache__"))
    for skill in ("synthesis-autopilot", "synthesis-daily-rituals"):
        shutil.copytree(ROOT / "skills" / skill / "scripts", plugin / "skills" / skill / "scripts",
                        ignore=shutil.ignore_patterns("__pycache__"))
    install.install(plugin)
    shutil.rmtree(plugin)  # the runtime copy must stand alone
    helper = isolated_home / "current" / "skills" / "synthesis-autopilot" / "scripts" / "autopilot_cli.py"
    path = write_plan(tmp_path)
    env = {**os.environ, "SYNTHESIS_HOME": str(isolated_home), "HOME": str(tmp_path)}
    env.pop("RITUAL_STATE_DIR", None)
    out = subprocess.run([sys.executable, "-S", str(helper), "--session", "S1", "engage", "--plan", str(path)],
                         capture_output=True, text=True, env=env, cwd=str(tmp_path))
    assert out.returncode == 0, out.stderr
    assert "Continue with the next one now" in stop("S1")
    check = isolated_home / "current" / "skills" / "synthesis-daily-rituals" / "scripts" / "relied_on.py"
    out = subprocess.run([sys.executable, "-S", str(check), "--all"], capture_output=True, text=True, env=env, cwd=str(tmp_path))
    assert (out.returncode, out.stdout) == (0, "nothing another person relies on is declared for any workspace\n"), out.stderr
