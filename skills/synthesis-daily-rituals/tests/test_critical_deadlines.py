"""A deadline whose miss cannot be undone is handled apart from ordinary dated work.

On 2026-11-06 an enrollment window closed with its item still open: first seen three weeks
ahead, it had been carried as one dated row among a hundred, written up as optional, never put
on the calendar and never escalated. These tests pin what replaced that: the `**Critical:**`
tag, its own view in the sweep from seven days out, alerts at three days and one day, no lapse,
closure only on evidence, and a ritual record that is refused while one is past due. The last
test replays that window day by day. Committed before the code it describes.
"""
from __future__ import annotations

import json
import os
import stat
import subprocess
import sys
from datetime import date, timedelta
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
import ritual_state  # noqa: E402

SWEEP = SCRIPTS / "decay_sweep.py"
DUE = date(2026, 11, 6)  # a Friday


def plan(root: Path, day, body: str) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    path = root / f"{day}.md"
    path.write_text(body, encoding="utf-8")
    return path


def critical(ident="enroll-2026", due=DUE, klass="benefits enrollment", calendar="event 4f2a", title="Open enrollment closes", extra=""):
    lines = [f"### {title}", f"**Critical:** {klass}", f"**Decays:** {due} (the window closes)"]
    lines += [f"**Decay ID:** {ident}"] if ident else []
    lines += [f"**Calendar:** {calendar}"] if calendar else []
    return "\n".join(lines + ([extra] if extra else [])) + "\n\n"


def sweep(*args, env=None):
    proc = subprocess.run([sys.executable, str(SWEEP), *map(str, args)], capture_output=True, text=True,
                          env={**os.environ, **(env or {})})
    return proc


def report(root: Path, as_of, *extra, env=None):
    proc = sweep("--as-of", as_of, "--plans-dir", root, "--json", *extra, env=env)
    assert proc.stdout, proc.stderr
    return proc.returncode, json.loads(proc.stdout)


def only(rows):
    assert len(rows) == 1, rows
    return rows[0]


# --- the critical view ---------------------------------------------------------------------------


def test_a_critical_item_is_listed_apart_and_never_in_the_dated_list(tmp_path):
    root = tmp_path / "plans"
    plan(root, "2026-10-16", critical() + "### Thank the team\n**Decay ID:** thanks\n**Decays:** 2026-10-20 (event date)\n")
    code, got = report(root, "2026-11-08")  # both dates have passed
    assert code == 0 and got["status"] == "REVIEW"
    assert [row["title"] for row in got["due"]] == ["Thank the team"]
    row = only(got["critical"]["open"])
    assert (row["title"], row["class"], row["due_date"]) == ("Open enrollment closes", "benefits enrollment", "2026-11-06")
    assert row["days_left"] == -2 and row["past_due"] is True and row["problems"] == []
    assert got["total_obligations"] == 2


@pytest.mark.parametrize("days_left, lead", [(8, False), (7, True), (1, True), (0, True)])
def test_it_leads_from_seven_days_before_its_date(tmp_path, days_left, lead):
    root = tmp_path / "plans"
    plan(root, "2026-10-16", critical())
    _, got = report(root, DUE - timedelta(days=days_left))
    row = only(got["critical"]["open"])
    assert (row["days_left"], row["lead"], row["past_due"]) == (days_left, lead, False)
    assert got["status"] == ("REVIEW" if lead else "CLEAR")


CLOSERS = [
    "**Resolved:** 2026-11-04 (nothing to change)",
    "**Released:** 2026-11-04 (not needed this year)",
    "**Sent:** 2026-11-04T10:00:00-05:00",
]


@pytest.mark.parametrize("closer", CLOSERS)
def test_a_closing_mark_without_evidence_leaves_it_open(tmp_path, closer):
    root = tmp_path / "plans"
    plan(root, "2026-10-16", critical())
    plan(root, "2026-11-04", critical(extra=closer))
    _, got = report(root, "2026-11-07")
    row = only(got["critical"]["open"])
    assert row["past_due"] is True
    assert any("Evidence" in problem for problem in row["problems"])
    assert got["critical"]["closed"] == []


@pytest.mark.parametrize("title", ["~~Open enrollment closes~~ ✅", "[x] Open enrollment closes", "DONE Open enrollment closes"])
def test_a_done_title_without_evidence_leaves_it_open(tmp_path, title):
    root = tmp_path / "plans"
    plan(root, "2026-11-04", critical(title=title))
    _, got = report(root, "2026-11-07")
    assert only(got["critical"]["open"])["past_due"] is True


def test_a_struck_deadline_without_evidence_leaves_it_open(tmp_path):
    root = tmp_path / "plans"
    body = "### Open enrollment closes\n**Critical:** benefits enrollment\n**Decay ID:** enroll-2026\n**Calendar:** event 4f2a\n**Decays:** ~~2026-11-06~~ (released: nothing to change)\n"
    plan(root, "2026-11-04", body)
    _, got = report(root, "2026-11-07")
    assert only(got["critical"]["open"])["past_due"] is True


@pytest.mark.parametrize("closer", CLOSERS)
def test_evidence_closes_it_and_the_report_says_what_it_closed_on(tmp_path, closer):
    root = tmp_path / "plans"
    plan(root, "2026-10-16", critical())
    evidence = 'confirmation "Your elections are saved", received 2026-11-04 15:12'
    plan(root, "2026-11-04", critical(extra=f"{closer}\n**Evidence:** {evidence}"))
    code, got = report(root, "2026-11-07")
    assert code == 0 and got["status"] == "CLEAR" and got["critical"]["open"] == []
    closed = only(got["critical"]["closed"])
    assert closed["evidence"] == evidence and closed["closed_in"] == "2026-11-04"
    _, later = report(root, "2026-11-12")  # more than seven days after the plan that closed it
    assert later["critical"]["closed"] == []


def test_it_cannot_lapse(tmp_path):
    root = tmp_path / "plans"
    plan(root, "2026-10-16", critical())
    plan(root, "2026-11-07", critical(extra="**Lapsed:** 2026-11-07 — the window closed with no decision"))
    _, got = report(root, "2026-11-09")
    row = only(got["critical"]["open"])
    assert row["past_due"] is True and any("Lapsed" in problem for problem in row["problems"])


def test_a_missing_calendar_reference_or_id_is_named(tmp_path):
    root = tmp_path / "plans"
    plan(root, "2026-10-16", critical(ident=None, calendar=None))
    _, got = report(root, "2026-10-20")
    problems = " | ".join(only(got["critical"]["open"])["problems"])
    assert "Calendar" in problems and "Decay ID" in problems
    assert got["status"] == "REVIEW"  # a defect in a critical item is never CLEAR, however far its date


def test_a_later_copy_without_the_tag_stays_critical(tmp_path):
    root = tmp_path / "plans"
    plan(root, "2026-10-16", critical())
    plan(root, "2026-10-30", "### Open enrollment closes\n**Decay ID:** enroll-2026\n**Decays:** 2026-11-06 (the window closes)\n")
    _, got = report(root, "2026-11-07")
    row = only(got["critical"]["open"])
    assert row["class"] == "benefits enrollment" and row["calendar"] == "event 4f2a"
    assert got["due"] == []


def test_a_redated_critical_item_shows_the_date_it_had(tmp_path):
    root = tmp_path / "plans"
    plan(root, "2026-10-16", critical())
    plan(root, "2026-11-02", critical(due="2026-11-13").replace("(the window closes)", "(extended a week: notice of 2026-11-02)"))
    _, got = report(root, "2026-11-03")
    row = only(got["critical"]["open"])
    assert row["due_date"] == "2026-11-13" and row["redated_from"] == ["2026-11-06"]


def test_a_critical_item_without_a_date_blocks_the_sweep(tmp_path):
    root = tmp_path / "plans"
    plan(root, "2026-10-16", "### Renew the passport\n**Critical:** identity document\n**Decay ID:** passport\n")
    code, got = report(root, "2026-10-20")
    assert code == 2 and got["status"] == "BLOCKED"
    assert any("Critical" in gap["reason"] for gap in got["gaps"])


# --- items that read like a critical class but carry no tag ---------------------------------------


def test_an_untagged_item_that_reads_like_a_critical_class_is_listed_until_classified(tmp_path):
    root = tmp_path / "plans"
    plan(root, "2026-10-16", "### Open enrollment for next year\n**Decay ID:** enroll\n**Decays:** 2026-11-06 (window closes)\n"
                             "### Thank the team\n**Decay ID:** thanks\n**Decays:** 2026-11-06 (event date)\n")
    _, got = report(root, "2026-10-20")
    assert [row["title"] for row in got["critical"]["unclassified"]] == ["Open enrollment for next year"]
    assert got["status"] == "REVIEW" and got["critical"]["open"] == []
    plan(root, "2026-10-21", "### Open enrollment for next year\n**Critical:** no (a newsletter about someone else's plan)\n"
                             "**Decay ID:** enroll\n**Decays:** 2026-11-06 (window closes)\n")
    _, after = report(root, "2026-10-21")
    assert after["critical"]["unclassified"] == [] and after["critical"]["open"] == [] and after["status"] == "CLEAR"


def test_the_words_that_flag_an_untagged_item_come_from_the_ritual_config_when_it_names_them(tmp_path):
    root, state = tmp_path / "plans", tmp_path / "state"
    plan(root, "2026-10-16", "### Renew the lease\n**Decay ID:** lease\n**Decays:** 2026-11-06 (notice period)\n"
                             "### Open enrollment for next year\n**Decay ID:** enroll\n**Decays:** 2026-11-06 (window closes)\n")
    state.mkdir()
    (state / "config.json").write_text(json.dumps({"critical_words": ["lease"], "workspaces": {}}), encoding="utf-8")
    _, got = report(root, "2026-10-20", env={"RITUAL_STATE_DIR": str(state)})
    assert [row["title"] for row in got["critical"]["unclassified"]] == ["Renew the lease"]


# --- alerts --------------------------------------------------------------------------------------


@pytest.mark.parametrize("days_left, alert", [(4, False), (3, True), (2, False), (1, True), (0, True), (-1, True), (-9, True)])
def test_alerts_fall_three_days_out_one_day_out_on_the_day_and_after(tmp_path, days_left, alert):
    root = tmp_path / "plans"
    plan(root, "2026-10-16", critical())
    _, got = report(root, DUE - timedelta(days=days_left))
    assert only(got["critical"]["open"])["alert"] is alert


def test_an_alert_day_off_moves_to_the_last_working_day_before_it(tmp_path):
    root = tmp_path / "plans"
    plan(root, "2026-10-16", critical(due="2026-11-17"))  # a Tuesday: three days out is a Saturday
    alerts = {day: only(report(root, f"2026-11-{day}")[1]["critical"]["open"])["alert"] for day in (12, 13, 14, 15, 16, 17)}
    assert alerts == {12: False, 13: True, 14: True, 15: False, 16: True, 17: True}


def stubs(tmp_path: Path) -> dict:
    """Stand-ins for the banner and speech commands that write what they were asked to show or say."""
    bin_dir, log = tmp_path / "bin", tmp_path / "alerts.log"
    bin_dir.mkdir()
    for name in ("osascript", "say"):
        tool = bin_dir / name
        tool.write_text(f'#!/bin/sh\necho "{name}: $*" >> "{log}"\n', encoding="utf-8")
        tool.chmod(tool.stat().st_mode | stat.S_IXUSR)
    home = tmp_path / "home"
    (home / ".synthesis").mkdir(parents=True)
    return {"PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}", "HOME": str(home), "LOG": str(log)}


def test_the_alert_carries_a_count_and_a_pointer_and_never_a_title(tmp_path):
    root, env = tmp_path / "plans", stubs(tmp_path)
    plan(root, "2026-10-16", critical() + critical(ident="passport", title="Renew the passport", klass="identity document"))
    _, got = report(root, DUE - timedelta(days=3), "--alert", env=env)
    assert got["critical"]["alert"] == {"count": 2, "banner": "posted", "audio": "played"}
    said = Path(env["LOG"]).read_text(encoding="utf-8")
    assert "osascript: " in said and "say: " in said and "2 critical deadlines" in said
    assert "enrollment" not in said.lower() and "passport" not in said.lower()


def test_the_mute_flag_silences_the_audio_and_keeps_the_banner(tmp_path):
    root, env = tmp_path / "plans", stubs(tmp_path)
    plan(root, "2026-10-16", critical())
    (Path(env["HOME"]) / ".synthesis" / "quiet-audio").touch()
    _, got = report(root, DUE - timedelta(days=1), "--alert", env=env)
    assert got["critical"]["alert"] == {"count": 1, "banner": "posted", "audio": "suppressed (mute flag)"}
    said = Path(env["LOG"]).read_text(encoding="utf-8")
    assert "osascript: " in said and "say: " not in said and "1 critical deadline " in said


def test_no_alert_fires_on_a_day_none_is_due(tmp_path):
    root, env = tmp_path / "plans", stubs(tmp_path)
    plan(root, "2026-10-16", critical())
    _, got = report(root, DUE - timedelta(days=5), "--alert", env=env)
    assert got["critical"]["alert"] == {"count": 0}
    assert not Path(env["LOG"]).exists()


# --- declared plan folders ------------------------------------------------------------------------


def declare(state: Path, **workspaces) -> dict:
    state.mkdir(parents=True, exist_ok=True)
    (state / "config.json").write_text(json.dumps({"workspaces": workspaces}), encoding="utf-8")
    return {"RITUAL_STATE_DIR": str(state)}


def test_the_sweep_reads_the_folders_a_workspace_declares(tmp_path):
    plans, artifacts = tmp_path / "plans", tmp_path / "workers"
    plan(plans, "2026-10-16", critical())
    artifacts.mkdir()
    (artifacts / "2026-10-17-day-start.md").write_text(critical(ident="passport", title="Renew the passport", klass="identity document"), encoding="utf-8")
    env = declare(tmp_path / "state", desk={"plans_dirs": [str(plans)], "artifacts_dirs": [str(artifacts)]})
    proc = sweep("--as-of", "2026-11-01", "--workspace", "desk", "--json", env=env)
    got = json.loads(proc.stdout)
    assert sorted(row["title"] for row in got["critical"]["open"]) == ["Open enrollment closes", "Renew the passport"]
    undeclared = sweep("--as-of", "2026-11-01", "--workspace", "elsewhere", "--json", env=env)
    assert undeclared.returncode == 2 and json.loads(undeclared.stdout)["status"] == "BLOCKED"


def test_one_alert_counts_every_declared_workspace(tmp_path):
    first, second, env = tmp_path / "a", tmp_path / "b", stubs(tmp_path)
    plan(first, "2026-10-16", critical())
    plan(second, "2026-10-16", critical(ident="passport", title="Renew the passport", klass="identity document"))
    env.update(declare(tmp_path / "state", one={"plans_dirs": [str(first)]}, two={"plans_dirs": [str(second)]},
                       three={"plans_dirs": []}))
    proc = sweep("--as-of", DUE - timedelta(days=1), "--alert-declared", env=env)
    assert proc.returncode == 0, proc.stderr
    assert "2 due" in proc.stdout and "enrollment" not in proc.stdout.lower()
    said = Path(env["LOG"]).read_text(encoding="utf-8")
    assert said.count("osascript: ") == 1 and "2 critical deadlines" in said


def test_the_text_report_opens_with_the_critical_items(tmp_path):
    root = tmp_path / "plans"
    plan(root, "2026-10-16", critical() + "### Thank the team\n**Decay ID:** thanks\n**Decays:** 2026-10-20 (event date)\n")
    lines = sweep("--as-of", "2026-11-07", "--plans-dir", root).stdout.splitlines()
    assert lines[0].startswith("CRITICAL: 1 open (1 past due")
    assert "PAST DUE 2026-11-06" in lines[1] and "Open enrollment closes" in lines[1]
    assert any(line.startswith("Deadline sweep: REVIEW") for line in lines)


# --- the ritual record ----------------------------------------------------------------------------


@pytest.fixture
def record(monkeypatch, capsys):
    """Run `ritual_state.py record` in this process, on a named calendar day."""
    def run(state: Path, *extra, workspace="desk", day="2026-11-07", today="2026-11-07"):
        monkeypatch.setenv("RITUAL_STATE_DIR", str(state))
        monkeypatch.setattr(ritual_state, "today", lambda: date.fromisoformat(today), raising=False)
        try:
            code, refusal = ritual_state.main(["record", "--direction", "day-end", "--workspace", workspace,
                                               "--date", day, *extra]), ""
        except SystemExit as exc:
            code, refusal = 1, str(exc)
        return code, capsys.readouterr().out, refusal
    return run


def history(state: Path) -> str:
    log = state / "history.jsonl"
    return log.read_text(encoding="utf-8") if log.exists() else ""


def test_a_workspace_that_declares_no_plan_folders_cannot_record(tmp_path, record):
    state = tmp_path / "state"
    declare(state, other={"plans_dirs": []})
    code, _, refusal = record(state)
    assert code != 0 and "plans_dirs" in refusal and "desk" in refusal
    assert history(state) == ""


def test_a_workspace_that_declares_it_keeps_no_plans_records(tmp_path, record):
    state = tmp_path / "state"
    declare(state, desk={"plans_dirs": []})
    code, out, refusal = record(state)
    assert code == 0, refusal
    assert "no dated plans" in out and '"workspace":"desk"' in history(state)


def test_a_past_due_critical_item_refuses_the_record_and_is_named(tmp_path, record):
    state, root = tmp_path / "state", tmp_path / "plans"
    path = plan(root, "2026-10-16", critical())
    declare(state, desk={"plans_dirs": [str(root)]})
    code, _, refusal = record(state)
    assert code != 0 and history(state) == ""
    assert "Open enrollment closes" in refusal and "2026-11-06" in refusal and str(path) in refusal
    assert "Evidence" in refusal


def test_an_open_critical_item_that_is_not_past_due_lets_the_record_through(tmp_path, record):
    state, root = tmp_path / "state", tmp_path / "plans"
    plan(root, "2026-10-16", critical())
    declare(state, desk={"plans_dirs": [str(root)]})
    code, out, refusal = record(state, day="2026-11-05", today="2026-11-05")
    assert code == 0, refusal
    assert "critical deadlines: 1 open" in out


def test_incomplete_plan_coverage_cannot_be_recorded_as_clean(tmp_path, record):
    state, root = tmp_path / "state", tmp_path / "plans"
    plan(root, "2026-10-16", "### Broken\n**Decay ID:** broken\n**Decays:** not-a-date\n")
    declare(state, desk={"plans_dirs": [str(root)]})
    code, _, refusal = record(state)
    assert code != 0 and "partial" in refusal and history(state) == ""
    code, _, refusal = record(state, "--outcome", "partial")
    assert code == 0, refusal


# --- the window of 2026-11-06, replayed -----------------------------------------------------------


def test_replay_a_window_first_seen_three_weeks_ahead(tmp_path, record):
    state, root, env = tmp_path / "state", tmp_path / "plans", stubs(tmp_path)
    plan(root, "2026-10-16", critical())  # the day the announcement is first seen
    declare(state, desk={"plans_dirs": [str(root)]})

    def day(as_of):
        return only(report(root, as_of)[1]["critical"]["open"])

    assert day("2026-10-29")["lead"] is False                 # eight days out: tracked, not yet leading
    assert day("2026-10-30")["lead"] is True                  # seven days out: it leads every plan from here
    assert [day(f"2026-11-0{n}")["alert"] for n in (2, 3, 4, 5, 6)] == [False, True, False, True, True]
    assert record(state, day="2026-11-06", today="2026-11-06")[0] == 0   # the closing day itself

    code, _, refusal = record(state)                          # the morning after
    assert code != 0 and "Open enrollment closes" in refusal

    plan(root, "2026-11-07", critical(extra="**Resolved:** 2026-11-07 (no change needed)"))
    assert record(state)[0] != 0                              # an agent's inference closes nothing
    plan(root, "2026-11-07", critical(extra="**Lapsed:** 2026-11-07 — the window closed with no decision"))
    assert record(state)[0] != 0                              # and it cannot be written off as lapsed

    words = 'the principal, 2026-11-07 09:40: "I checked on the 5th, nothing to change this year"'
    plan(root, "2026-11-07", critical(extra=f"**Resolved:** 2026-11-07 (his answer)\n**Evidence:** {words}"))
    code, _, refusal = record(state)
    assert code == 0, refusal
    _, got = report(root, "2026-11-07", "--alert", env=env)
    assert got["critical"]["open"] == [] and only(got["critical"]["closed"])["evidence"] == words
    assert got["critical"]["alert"] == {"count": 0}
