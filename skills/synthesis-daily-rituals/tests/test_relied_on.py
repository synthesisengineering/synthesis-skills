"""What other people rely on has its health checked at every check-in.

A test set up on a principal's own laptop was given to two colleagues, who came to rely on it. It stopped when the
app that ran it restarted, two scheduled check-ins ran afterwards without looking at it, and it was found hours
later by accident. A workspace now declares what a person other than the principal relies on (`relied_on` in the
ritual config), each with the command that says whether it is healthy, and `relied_on.py` runs them all: whatever
is down prints first, and an entry that cannot be run as written counts as down. Committed before the script.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "relied_on.py"
HEALTHY = [sys.executable, "-c", "pass"]
NEEDS = 'could not be run (an entry needs "what" and "by")'
WORDS = 'could not be run ("check" must be a list of words: the program, then its arguments)'


def failing(said: str = "", code: int = 1) -> list:
    """A check that prints `said` on its error stream and exits `code`."""
    return [sys.executable, "-c", "import sys; sys.stderr.write(sys.argv[1]); sys.exit(int(sys.argv[2]))", said, str(code)]


def entry(what: str = "the intake form", by: str = "the sales team", check=HEALTHY) -> dict:
    return {"what": what, "by": by, "check": check}


def run(tmp_path: Path, *args: str, config=None, **workspaces):
    """Run the script over a ritual config, in a temporary synthesis home, that declares each workspace's `relied_on`."""
    home = tmp_path / "home"
    (home / "rituals").mkdir(parents=True, exist_ok=True)
    if config is None:
        config = json.dumps({"workspaces": {name: {"relied_on": found} for name, found in workspaces.items()}})
    (home / "rituals" / "config.json").write_text(config, encoding="utf-8")
    env = {**os.environ, "SYNTHESIS_HOME": str(home)}
    env.pop("RITUAL_STATE_DIR", None)
    proc = subprocess.run([sys.executable, str(SCRIPT), *args], capture_output=True, text=True, env=env)
    return proc.returncode, proc.stdout.splitlines(), proc.stderr


def stopped(pid: int) -> bool:
    """Gone, or ended and only waiting to be collected."""
    state = subprocess.run(["ps", "-o", "stat=", "-p", str(pid)], capture_output=True, text=True).stdout.strip()
    return not state or state.startswith("Z")


def test_a_healthy_check_is_ok_and_counted(tmp_path):
    code, lines, _ = run(tmp_path, "--workspace", "desk", desk=[entry()])
    assert (code, lines) == (0, ["ok the intake form", "1 relied on, 0 down"])


def test_a_failing_check_is_down_with_its_exit_code_and_the_first_line_it_printed(tmp_path):
    refused = failing("\n   \n  connection refused  \nand more after it\n", 3)
    code, lines, _ = run(tmp_path, "--workspace", "desk", desk=[entry(check=refused)])
    assert code == 1
    assert lines == ["DOWN the intake form (relied on by the sales team): exit 3: connection refused", "1 relied on, 1 down"]


def test_a_failing_check_that_printed_nothing_has_its_exit_code_alone_and_a_long_line_is_cut(tmp_path):
    code, lines, _ = run(tmp_path, "--workspace", "desk", desk=[
        entry(check=failing()), entry("the status page", check=failing("x" * 300)),
        entry("the wiki", check=failing("first line\n" + "y" * 20000))])   # however much it printed after
    assert code == 1
    assert lines == ["DOWN the intake form (relied on by the sales team): exit 1",
                     "DOWN the status page (relied on by the sales team): exit 1: " + "x" * 200,
                     "DOWN the wiki (relied on by the sales team): exit 1: first line",
                     "3 relied on, 3 down"]


def test_a_check_still_running_at_the_timeout_is_down_and_stopped_with_what_it_started(tmp_path):
    started = tmp_path / "started"
    hung = ["sh", "-c", 'sleep 60 & echo $! > "$0"; wait', str(started)]
    began = time.monotonic()
    code, lines, _ = run(tmp_path, "--workspace", "desk", "--timeout", "2", desk=[entry(check=hung)])
    assert code == 1
    assert lines == ["DOWN the intake form (relied on by the sales team): no answer in 2 s", "1 relied on, 1 down"]
    assert time.monotonic() - began < 30, "the script waited for the check instead of stopping it"
    pid, deadline = int(started.read_text(encoding="utf-8")), time.monotonic() + 10
    while not stopped(pid) and time.monotonic() < deadline:
        time.sleep(0.05)
    assert stopped(pid), "what the check started is still running"


def test_a_check_that_exits_0_is_healthy_whatever_it_left_running(tmp_path):
    """The check answered when its program ended; something it started that still holds its output is not waited for."""
    code, lines, _ = run(tmp_path, "--workspace", "desk", "--timeout", "2", desk=[entry(check=["sh", "-c", "sleep 4 & exit 0"])])
    assert (code, lines) == (0, ["ok the intake form", "1 relied on, 0 down"])


def test_a_program_that_does_not_exist_is_down_and_no_shell_reads_the_words(tmp_path):
    marker = tmp_path / "a-shell-ran-this"
    code, lines, _ = run(tmp_path, "--workspace", "desk", desk=[
        entry(check=["no-such-program-anywhere"]),
        entry("the status page", check=["sh-metachar;", "x"]),         # a program of that name, not a command line
        entry("the wiki", check=[f"touch {marker}"]),
        entry("the feed", check=["sh -c", f"touch {marker}"]),
        entry("the notes", check=["a word no program can be handed\x00"])])
    assert code == 1 and not marker.exists()
    assert lines[:4] == [f"DOWN {what} (relied on by the sales team): could not be run (No such file or directory)"
                         for what in ("the intake form", "the status page", "the wiki", "the feed")]
    assert lines[4].startswith("DOWN the notes (relied on by the sales team): could not be run (") and "null" in lines[4]
    assert lines[5:] == ["5 relied on, 5 down"]


def test_an_entry_that_cannot_be_run_as_written_is_down_and_never_skipped(tmp_path):
    code, lines, _ = run(tmp_path, "--workspace", "desk", desk=[
        entry(check="curl -fsS https://intake.example.com/health"),   # a command line, not a list of words
        entry("the status page", check=[]),                            # no program
        {"what": "the wiki", "by": "two colleagues"},                  # no check
        entry("the feed", check=["curl", "--max-time", 10]),           # a number is not a word
        {"by": "the sales team", "check": HEALTHY},                    # no what
        {"what": "the build cache", "check": HEALTHY},                 # no by
        {"what": " ", "by": "", "check": HEALTHY},                     # both empty
        "the intake form",                                             # not an entry
        entry("the calendar feed")])                                   # the healthy one after them still runs
    assert code == 1
    assert lines == [f"DOWN the intake form (relied on by the sales team): {WORDS}",
                     f"DOWN the status page (relied on by the sales team): {WORDS}",
                     f"DOWN the wiki (relied on by two colleagues): {WORDS}",
                     f"DOWN the feed (relied on by the sales team): {WORDS}",
                     f"DOWN entry 5 (relied on by the sales team): {NEEDS}",
                     f"DOWN the build cache (relied on by nobody named): {NEEDS}",
                     f"DOWN entry 7 (relied on by nobody named): {NEEDS}",
                     f"DOWN entry 8 (relied on by nobody named): {NEEDS}",
                     "ok the calendar feed",
                     "9 relied on, 8 down"]


def test_a_relied_on_that_is_not_a_list_is_read_as_one_entry(tmp_path):
    code, lines, _ = run(tmp_path, "--workspace", "desk", desk=entry())
    assert (code, lines) == (0, ["ok the intake form", "1 relied on, 0 down"])
    code, lines, _ = run(tmp_path, "--workspace", "desk", desk="the intake form")
    assert (code, lines) == (1, [f"DOWN entry 1 (relied on by nobody named): {NEEDS}", "1 relied on, 1 down"])


def test_nothing_declared_is_one_line_and_no_failure(tmp_path):
    for declared in ({}, {"relied_on": []}, {"relied_on": None}):
        code, lines, _ = run(tmp_path, "--workspace", "desk", config=json.dumps({"workspaces": {"desk": declared}}))
        assert (code, lines) == (0, ["nothing another person relies on is declared for desk"]), declared


def test_whatever_is_down_prints_first_whatever_its_place_in_the_config(tmp_path):
    found = [entry(name, check=HEALTHY if name in "ace" else failing()) for name in "abcde"]
    code, lines, _ = run(tmp_path, "--workspace", "desk", desk=found)
    assert code == 1
    assert [line.split(" (")[0] for line in lines] == ["DOWN b", "DOWN d", "ok a", "ok c", "ok e", "5 relied on, 2 down"]


def test_all_checks_every_workspace_and_names_it_on_each_line(tmp_path):
    code, lines, _ = run(tmp_path, "--all", desk=[entry(), entry("the status page", "two colleagues", failing("refused"))],
                         lab=[entry("the build cache", "the release team")], attic=[])
    assert code == 1
    assert lines == ["DOWN desk: the status page (relied on by two colleagues): exit 1: refused",
                     "ok desk: the intake form",
                     "ok lab: the build cache",
                     "nothing another person relies on is declared for attic",
                     "3 relied on, 1 down"]


def test_all_with_nothing_declared_anywhere_says_so_in_one_line(tmp_path):
    code, lines, _ = run(tmp_path, "--all", desk=None, lab=[])
    assert (code, lines) == (0, ["nothing another person relies on is declared for desk, lab"])
    code, lines, _ = run(tmp_path, "--all")
    assert (code, lines) == (0, ["nothing another person relies on is declared for any workspace"])


def test_json_carries_each_row_with_whatever_is_down_first(tmp_path):
    code, lines, _ = run(tmp_path, "--all", "--json", attic=[],
                         desk=[entry(), entry("the status page", "two colleagues", failing("refused", 7))])
    assert code == 1
    assert json.loads("\n".join(lines)) == {
        "relied_on": [{"workspace": "desk", "what": "the status page", "by": "two colleagues", "ok": False, "why": "exit 7: refused"},
                      {"workspace": "desk", "what": "the intake form", "by": "the sales team", "ok": True, "why": ""}],
        "down": 1, "nothing_declared": ["attic"]}


def test_a_config_that_cannot_be_read_or_a_workspace_not_in_it_is_never_a_pass(tmp_path):
    unreadable = ("{not json", json.dumps(["desk"]), json.dumps({"workspaces": {"desk": "the intake form"}}))
    for config in unreadable:
        code, lines, err = run(tmp_path, "--all", config=config)
        assert code == 2 and lines == [] and err.startswith("NOT CHECKED: ") and "config.json: " in err, (config, err)
    code, lines, err = run(tmp_path, "--workspace", "lab", desk=[entry()])
    assert code == 2 and lines == [] and err.startswith("NOT CHECKED: ") and err.rstrip().endswith("config.json: workspace lab is not in it"), err


# ---- the rituals run it ---------------------------------------------------------------------------------------

SKILL = SCRIPT.parents[1]
COMMAND = "python3 <rituals>/scripts/relied_on.py --workspace <W>"
LEADS = "**A `DOWN` line is the first thing in the plan and in the reply to the principal, before anything else,**"
INCIDENT = ("It is an incident, so the principal is told first, with who is affected and what the fix is, and the people "
            "affected are told only on the principal's approval.")


def reference(name: str) -> str:
    return (SKILL / "references" / name).read_text(encoding="utf-8")


def test_day_start_each_mid_day_sync_and_day_end_run_it_and_say_what_a_down_line_asks_for():
    """A mechanism nobody is told to run is not a control. Each ritual's own checklist carries the command, and the
    step that carries it says where a DOWN line goes and who is told."""
    for name in ("day-start.md", "mid-day-and-modes.md", "day-end.md", "procedure.md"):
        step = next((line for line in reference(name).splitlines() if COMMAND in line), "")
        assert step, f"{name} does not run the check"
        assert LEADS in step and INCIDENT in step, f"{name}: the step does not say what a DOWN line asks for"


def test_it_is_the_first_check_each_ritual_runs():
    """What is down is the first thing reported, so the check runs before the rest: after the date at day-start,
    before any surface at a sync, before the mode question at day-end."""
    step_1 = reference("day-start.md").split("\n## 1. ")[1].split("\n## ")[0]
    assert COMMAND in [line for line in step_1.splitlines() if line.startswith("- [ ]")][1]
    sync = reference("mid-day-and-modes.md").split("\n## Mid-Day Sync Protocol\n")[1].split("\n## ")[0]
    assert COMMAND in sync and sync.index(COMMAND) < sync.index("1. **Slack**")
    day_end = reference("day-end.md")
    assert COMMAND in day_end and day_end.index(COMMAND) < day_end.index("ask the user the one-letter mode question")


def test_a_ritual_in_observer_or_concurrent_seats_mode_keeps_the_check():
    modes = reference("mid-day-and-modes.md")
    for heading in ("### What Observer Mode Keeps (Non-Negotiable)", "### What Concurrent-Seats Mode Keeps (Non-Negotiable)"):
        assert "relied_on.py --workspace <W>" in modes.split(heading)[1].split("\n#")[0], heading


def test_the_plan_opens_with_what_is_down():
    plan = reference("plan-format.md")
    assert "## Down: needs your attention" in plan
    assert plan.index("## Down: needs your attention") < plan.index("## Critical deadlines: needs your attention")
    assert "`## Down: needs your attention`" in reference("day-start.md").split("\n## 6. ")[1].split("\n## ")[0]


def test_the_scripts_page_shows_the_command_and_the_key_and_the_example_config_declares_one():
    scripts = reference("scripts.md")
    assert "| `python3 <rituals>/scripts/relied_on.py --workspace <W>\\|--all [--timeout SECONDS] [--json]` |" in scripts
    assert '`"relied_on": [{"what": ' in scripts
    example = json.loads((SKILL / "assets" / "ritual-config.example.json").read_text(encoding="utf-8"))
    found = [declared for conf in example["workspaces"].values() for declared in conf.get("relied_on", [])]
    assert found, "the example config declares nothing another person relies on"
    for declared in found:  # the shape the script runs
        assert declared["what"].strip() and declared["by"].strip()
        assert declared["check"] and all(isinstance(word, str) for word in declared["check"])


def test_the_skill_binds_it():
    rules = (SKILL / "SKILL.md").read_text(encoding="utf-8").split("## Binding rules")[1].split("## Contents")[0]
    rule = next((line for line in rules.splitlines() if "`relied_on.py`" in line), "")
    assert rule and "`DOWN`" in rule and "approval" in rule
