"""Every `query` view honors --workspace or refuses without it; none drops it.

The log is one append-only file shared by every workspace seat, so a view
that accepts --workspace and then answers for the whole log is the same
single-slot shape v2.28.0 removed for day-start and day-end: one seat's
record answers for every seat. On 2026-09-14 that shape was found again in
`query weekly-review` — `record --direction weekly-review` requires and stores
--workspace, but the query returned the newest review in the log regardless,
so one workspace's Friday review silenced every other workspace's owed-weekly
gate. `query open` dropped the argument the same way.

These tests pin, per view: `last`, `open`, `weekly-review` and `summary`
honor --workspace; `streak` and `weekly-review` refuse without it, naming the
accepted form — except that `weekly-review` uses the log's only workspace when
there is exactly one, and names it. An empty `--workspace ""` — the shape an
unset shell variable produces — is refused on every view and on `record`,
never read as omitted. Every run uses a scratch state directory.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "ritual_state.py"


def run(state: Path, *args: str) -> subprocess.CompletedProcess[str]:
    if "record" in args and not (state / "config.json").exists():
        # `record` reads the workspace's declared plan folders; these tests keep no plans, and say so.
        state.mkdir(parents=True, exist_ok=True)
        (state / "config.json").write_text(json.dumps({"defaults": {"plans_dirs": []}, "workspaces": {}}), encoding="utf-8")
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--state-dir", str(state), *args],
        capture_output=True, text=True, check=False,
    )


def record(state: Path, direction: str, workspace: str, day: str) -> None:
    done = run(state, "record", "--direction", direction, "--workspace", workspace, "--date", day)
    assert done.returncode == 0, done.stderr


def query_json(state: Path, *args: str) -> dict:
    done = run(state, "query", *args, "--json")
    assert done.returncode == 0, done.stderr
    return json.loads(done.stdout)


# --- weekly-review ---------------------------------------------------------------------------


def test_weekly_review_recorded_for_one_workspace_leaves_another_owed(tmp_path: Path) -> None:
    """The acceptance the reporting seat proposed: A's review must not answer for B."""
    record(tmp_path, "weekly-review", "alpha", "2026-09-11")

    beta = query_json(tmp_path, "weekly-review", "--workspace", "beta", "--today", "2026-09-14")
    alpha = query_json(tmp_path, "weekly-review", "--workspace", "alpha", "--today", "2026-09-14")
    assert beta == {"workspace": "beta", "last_weekly_review": None, "owed": True}
    assert alpha == {"workspace": "alpha", "last_weekly_review": "2026-09-11", "owed": False}


def test_weekly_review_returns_the_named_workspace_s_latest_not_the_log_s_latest(tmp_path: Path) -> None:
    record(tmp_path, "weekly-review", "alpha", "2026-09-04")
    record(tmp_path, "weekly-review", "alpha", "2026-09-11")
    record(tmp_path, "weekly-review", "beta", "2026-09-12")

    assert query_json(tmp_path, "weekly-review", "--workspace", "alpha")["last_weekly_review"] == "2026-09-11"
    assert query_json(tmp_path, "weekly-review", "--workspace", "beta")["last_weekly_review"] == "2026-09-12"


def test_weekly_review_without_workspace_is_refused_when_the_log_holds_several(tmp_path: Path) -> None:
    """Two seats in the log and no --workspace: nothing can be assumed, so the
    query refuses and names both the condition it tested and the accepted form."""
    record(tmp_path, "day-end", "alpha", "2026-09-11")
    record(tmp_path, "day-end", "beta", "2026-09-11")
    record(tmp_path, "weekly-review", "alpha", "2026-09-11")

    done = run(tmp_path, "query", "weekly-review", "--json")
    assert done.returncode != 0
    assert done.stdout == ""
    assert "query weekly-review needs --workspace" in done.stderr
    assert "2 workspaces (alpha, beta)" in done.stderr
    assert "query weekly-review --workspace <workspace>" in done.stderr


def test_weekly_review_without_workspace_on_an_empty_log_is_refused(tmp_path: Path) -> None:
    done = run(tmp_path, "query", "weekly-review", "--json")
    assert done.returncode != 0
    assert "query weekly-review needs --workspace" in done.stderr
    assert "0 workspaces" in done.stderr
    assert "query weekly-review --workspace <workspace>" in done.stderr


def test_weekly_review_without_workspace_uses_the_only_workspace_and_names_it(tmp_path: Path) -> None:
    record(tmp_path, "day-end", "alpha", "2026-09-10")
    record(tmp_path, "weekly-review", "alpha", "2026-09-11")

    assert query_json(tmp_path, "weekly-review", "--today", "2026-09-14") == {
        "workspace": "alpha", "last_weekly_review": "2026-09-11", "owed": False, "workspace_inferred": True,
    }
    human = run(tmp_path, "query", "weekly-review")
    assert human.returncode == 0, human.stderr
    assert "alpha" in human.stdout
    assert "2026-09-11" in human.stdout
    assert "only workspace in the log" in human.stdout


def test_weekly_review_inference_ignores_unattributed_legacy_records(tmp_path: Path) -> None:
    """Migrated records carry workspace 'unknown'. They are neither a workspace
    the query can infer nor a review it may attribute to a named seat."""
    (tmp_path / "history.jsonl").write_text(
        json.dumps({"ts": "2026-09-12T00:00:00+00:00", "date": "2026-09-12",
                    "direction": "weekly-review", "workspace": "unknown",
                    "mode": "derived-from-legacy-state", "outcome": "clean"}) + "\n",
        encoding="utf-8",
    )
    record(tmp_path, "weekly-review", "alpha", "2026-09-04")

    assert query_json(tmp_path, "weekly-review", "--workspace", "alpha")["last_weekly_review"] == "2026-09-04"
    inferred = query_json(tmp_path, "weekly-review")
    assert inferred["workspace"] == "alpha"
    assert inferred["last_weekly_review"] == "2026-09-04"


# --- open ------------------------------------------------------------------------------------


def test_open_honors_workspace(tmp_path: Path) -> None:
    record(tmp_path, "day-start", "alpha", "2026-09-14")
    record(tmp_path, "day-start", "beta", "2026-09-14")
    record(tmp_path, "day-end", "beta", "2026-09-13")

    scoped = query_json(tmp_path, "open", "--workspace", "alpha", "--today", "2026-09-14")
    assert scoped["open_workdays"] == [{"workspace": "alpha", "date": "2026-09-14"}]

    unscoped = query_json(tmp_path, "open", "--today", "2026-09-14")
    assert unscoped["open_workdays"] == [
        {"workspace": "alpha", "date": "2026-09-14"},
        {"workspace": "beta", "date": "2026-09-14"},
    ]


# --- summary ---------------------------------------------------------------------------------


def test_summary_honors_workspace_in_every_section(tmp_path: Path) -> None:
    record(tmp_path, "day-start", "alpha", "2026-09-14")
    record(tmp_path, "day-start", "beta", "2026-09-14")
    record(tmp_path, "weekly-review", "beta", "2026-09-12")

    scoped = query_json(tmp_path, "summary", "--workspace", "alpha", "--today", "2026-09-14")
    assert set(scoped["workspaces"]) == {"alpha"}
    assert scoped["workspaces"]["alpha"]["last_weekly_review"] is None
    assert scoped["open_workdays"] == [{"workspace": "alpha", "date": "2026-09-14"}]
    assert "last_weekly_review" not in scoped, "a log-wide single slot answers for every seat"


def test_summary_without_workspace_reports_the_weekly_review_per_workspace(tmp_path: Path) -> None:
    record(tmp_path, "day-end", "alpha", "2026-09-11")
    record(tmp_path, "day-end", "beta", "2026-09-11")
    record(tmp_path, "weekly-review", "beta", "2026-09-12")

    out = query_json(tmp_path, "summary", "--today", "2026-09-14")
    assert out["workspaces"]["alpha"]["last_weekly_review"] is None
    assert out["workspaces"]["beta"]["last_weekly_review"] == "2026-09-12"
    assert "last_weekly_review" not in out
    human = run(tmp_path, "query", "summary", "--today", "2026-09-14")
    assert human.returncode == 0, human.stderr
    assert "weekly 2026-09-12" in human.stdout
    assert "weekly —" in human.stdout



def test_summary_lists_each_declared_mailbox_left_unread(tmp_path: Path) -> None:
    home = tmp_path / "home"
    agents = home / "workspaces" / "alpha" / ".agents"
    agents.mkdir(parents=True)
    (agents / "mailboxes.yaml").write_text("workspace: alpha\naccounts:\n  - address: a@example.com\n"
                                           "    transport: gmail\n    role: work\n    sweep: every-ritual\n",
                                           encoding="utf-8")
    record(tmp_path, "day-end", "alpha", "2026-09-11")
    env = {**os.environ, "HOME": str(home), "SYNTHESIS_HOME": str(tmp_path / "synthesis")}
    args = [sys.executable, str(SCRIPT), "--state-dir", str(tmp_path), "query", "summary", "--today", "2026-09-14"]

    out = subprocess.run([*args, "--json"], env=env, capture_output=True, text=True, check=True)
    human = subprocess.run(args, env=env, capture_output=True, text=True, check=True)

    assert json.loads(out.stdout)["stale_mailboxes"] == [
        {"workspace": "alpha", "address": "a@example.com", "read_through": None}]
    assert "MAIL  alpha" in human.stdout and "a@example.com read through never" in human.stdout

# --- last ------------------------------------------------------------------------------------


def test_last_honors_workspace(tmp_path: Path) -> None:
    record(tmp_path, "day-end", "alpha", "2026-09-11")
    record(tmp_path, "day-end", "beta", "2026-09-12")

    scoped = query_json(tmp_path, "last", "--workspace", "alpha")
    assert set(scoped["workspaces"]) == {"alpha"}
    assert scoped["workspaces"]["alpha"]["last_day_end"]["date"] == "2026-09-11"
    assert set(query_json(tmp_path, "last")["workspaces"]) == {"alpha", "beta"}


# --- streak ----------------------------------------------------------------------------------


def test_streak_refuses_without_workspace_and_honors_it(tmp_path: Path) -> None:
    (tmp_path / "config.json").write_text(json.dumps({
        "defaults": {"streak": "none", "weekdays": [0, 1, 2, 3, 4], "non_working_dates": [], "plans_dirs": []},
        "workspaces": {"alpha": {"streak": "expected-days"}, "beta": {"streak": "expected-days"}},
    }), encoding="utf-8")
    for day in ("2026-09-08", "2026-09-09", "2026-09-10", "2026-09-11"):
        record(tmp_path, "day-end", "alpha", day)
    record(tmp_path, "day-end", "beta", "2026-09-11")

    refused = run(tmp_path, "query", "streak", "--json")
    assert refused.returncode != 0
    assert "query streak needs --workspace" in refused.stderr

    assert query_json(tmp_path, "streak", "--workspace", "alpha", "--today", "2026-09-11") == {
        "workspace": "alpha", "streak": 4,
    }
    assert query_json(tmp_path, "streak", "--workspace", "beta", "--today", "2026-09-11") == {
        "workspace": "beta", "streak": 1,
    }
    # A weekend without closes does not break the run; a missed weekday does.
    assert query_json(tmp_path, "streak", "--workspace", "alpha", "--today", "2026-09-14")["streak"] == 4
    assert query_json(tmp_path, "streak", "--workspace", "alpha", "--today", "2026-09-15")["streak"] == 0


def test_a_workspace_worked_occasionally_shows_quiet_days_and_owes_no_review(tmp_path: Path) -> None:
    (tmp_path / "config.json").write_text(json.dumps({
        "workspaces": {"advisory": {"streak": "none", "quiet_after_days": 21, "plans_dirs": []}},
    }), encoding="utf-8")
    record(tmp_path, "day-end", "advisory", "2026-09-01")
    view = query_json(tmp_path, "summary", "--today", "2026-09-25")["workspaces"]["advisory"]
    assert view["weekly_review_owed"] is False and view["quiet_days"] == 24
    assert query_json(tmp_path, "weekly-review", "--workspace", "advisory", "--today", "2026-09-25")["owed"] is False
    text = run(tmp_path, "query", "summary", "--today", "2026-09-25").stdout
    assert "QUIET 24 days (worked occasionally)" in text and "OWED" not in text


# --- an empty --workspace is refused, never read as omitted ----------------------------------

VIEWS = ("last", "open", "streak", "weekly-review", "summary")


def _one_workspace_log(state: Path) -> None:
    """A log naming exactly one workspace: the shape in which an empty value,
    read as omitted, lets `weekly-review` infer a seat and every other view
    answer for the whole log."""
    (state / "config.json").write_text(json.dumps({
        "defaults": {"streak": "expected-days", "weekdays": [0, 1, 2, 3, 4], "non_working_dates": [], "plans_dirs": []},
        "workspaces": {"alpha": {}},
    }), encoding="utf-8")
    record(state, "day-end", "alpha", "2026-09-11")
    record(state, "weekly-review", "alpha", "2026-09-11")
    record(state, "day-start", "alpha", "2026-09-14")


@pytest.mark.parametrize("empty", ["", "   "])
@pytest.mark.parametrize("view", VIEWS)
def test_an_empty_workspace_is_refused_on_every_view(tmp_path: Path, view: str, empty: str) -> None:
    """`--workspace ""` is the shape an unset shell variable produces. It is
    neither a seat nor an omission: read as omitted, a scoped call silently
    answers for the whole log. Refused, naming the accepted form."""
    _one_workspace_log(tmp_path)

    done = run(tmp_path, "query", view, "--workspace", empty, "--today", "2026-09-14", "--json")

    assert done.returncode != 0
    assert done.stdout == ""
    assert "empty" in done.stderr
    assert f"query {view} --workspace <workspace>" in done.stderr
    named = run(tmp_path, "query", view, "--workspace", "alpha", "--today", "2026-09-14", "--json")
    assert named.returncode == 0, named.stderr


def test_record_refuses_an_empty_workspace_before_appending(tmp_path: Path) -> None:
    """The same shape on the writer: an empty seat would append a record no
    per-workspace view can attribute. Refused, and nothing is written."""
    done = run(tmp_path, "record", "--direction", "day-end", "--workspace", "", "--date", "2026-09-14")

    assert done.returncode != 0
    assert "empty" in done.stderr
    assert "record --direction <direction> --workspace <workspace> --date YYYY-MM-DD" in done.stderr
    assert not (tmp_path / "history.jsonl").exists()


# --- two clocks, two workspaces, and the append itself (R5.1) --------------------------------


def test_two_workspaces_closing_the_same_evening_both_keep_their_close(tmp_path: Path) -> None:
    """2026-09-02: one seat's close overwrote another's single slot. Appends cannot."""
    record(tmp_path, "day-start", "alpha", "2026-09-14")
    record(tmp_path, "day-start", "beta", "2026-09-14")
    record(tmp_path, "day-end", "alpha", "2026-09-14")
    record(tmp_path, "day-end", "beta", "2026-09-14")

    out = query_json(tmp_path, "summary", "--today", "2026-09-14")
    assert out["workspaces"]["alpha"]["last_day_end"]["date"] == "2026-09-14"
    assert out["workspaces"]["beta"]["last_day_end"]["date"] == "2026-09-14"
    assert out["open_workdays"] == []
    alpha = query_json(tmp_path, "summary", "--workspace", "alpha", "--today", "2026-09-14")
    assert set(alpha["workspaces"]) == {"alpha"}


def test_a_close_written_after_midnight_counts_for_the_workday_it_names(tmp_path: Path) -> None:
    """A close written at 01:30 for the previous workday closes that workday; the
    wall-clock moment is kept as `ts` and never replaces the logical date."""
    record(tmp_path, "day-start", "alpha", "2026-09-14")
    record(tmp_path, "day-end", "alpha", "2026-09-14")  # written whenever the clock says

    line = json.loads((tmp_path / "history.jsonl").read_text(encoding="utf-8").splitlines()[-1])
    assert line["date"] == "2026-09-14" and "T" in line["ts"]
    assert query_json(tmp_path, "open", "--workspace", "alpha", "--today", "2026-09-15")["open_workdays"] == []


def test_a_close_corrected_within_the_same_second_reads_as_corrected(tmp_path: Path, monkeypatch, capsys) -> None:
    """day-end.md: when a gate fails after a clean close, a corrected record for the same day is appended, and the
    later record wins. A record's time is kept to the second, so a correction recorded within that second tied with
    the close, and the close was read: clean (5.25.1). The record runs in this process, its clock held to one second."""
    from datetime import datetime, timedelta, timezone
    sys.path.insert(0, str(SCRIPT.parent))
    import ritual_state

    class OneSecond(datetime):
        @classmethod
        def now(cls, tz=None):
            return datetime(2026, 9, 14, 18, 30, 5, tzinfo=timezone(timedelta(hours=-4)))
    (tmp_path / "config.json").write_text(json.dumps({"defaults": {"plans_dirs": []}, "workspaces": {}}), encoding="utf-8")
    monkeypatch.setenv("RITUAL_STATE_DIR", str(tmp_path))
    monkeypatch.setattr(ritual_state, "datetime", OneSecond)
    for outcome in ("clean", "blocked"):
        assert ritual_state.main(["record", "--direction", "day-end", "--workspace", "alpha", "--date", "2026-09-14",
                                  "--outcome", outcome]) == 0
    capsys.readouterr()

    close, correction = log_lines(tmp_path)
    assert close["ts"] == correction["ts"] and (close["outcome"], correction["outcome"]) == ("clean", "blocked")
    assert ritual_state.main(["query", "last", "--workspace", "alpha", "--today", "2026-09-14", "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["workspaces"]["alpha"]["last_day_end"]["outcome"] == "blocked"


def test_a_record_needs_its_logical_date(tmp_path: Path) -> None:
    done = run(tmp_path, "record", "--direction", "day-end", "--workspace", "alpha", "--date", "yesterday")
    assert done.returncode != 0 and "never inferred" in done.stderr
    missing = run(tmp_path, "record", "--direction", "day-end", "--workspace", "alpha")
    assert missing.returncode != 0
    assert not (tmp_path / "history.jsonl").exists()


@pytest.mark.parametrize("day", ["20260914", "2026-W38-1", "2026-W38", "2026-09-14T09:00", "2026-9-14", "14/09/2026", " 2026-09-14"])
def test_a_day_written_any_other_way_is_refused_on_every_python(tmp_path: Path, day: str) -> None:
    """Python 3.11 and later read `20260914` and `2026-W38-1` as dates, so a record was appended under a date no
    view matches: the command said the day was recorded, and every view went on showing it open."""
    done = run(tmp_path, "record", "--direction", "day-end", "--workspace", "alpha", "--date", day)
    assert done.returncode != 0 and "is not YYYY-MM-DD" in done.stderr
    assert not (tmp_path / "history.jsonl").exists()


def test_a_record_dated_after_the_macs_own_today_is_refused_and_todays_is_kept(tmp_path: Path) -> None:
    """The record takes the day from the Mac's clock. Two days ahead has not come at any hour of this run; today has,
    and if the run crosses midnight it is yesterday, which is recorded too."""
    from datetime import date, timedelta
    today, ahead = date.today().isoformat(), (date.today() + timedelta(days=2)).isoformat()
    for direction in ("day-start", "day-end"):
        done = run(tmp_path, "record", "--direction", direction, "--workspace", "alpha", "--date", ahead)
        assert done.returncode != 0 and f"--date {ahead} has not come" in done.stderr and "today is 20" in done.stderr
    assert not (tmp_path / "history.jsonl").exists()
    record(tmp_path, "day-end", "alpha", today)
    assert query_json(tmp_path, "last", "--workspace", "alpha")["workspaces"]["alpha"]["last_day_end"]["date"] == today


def test_an_early_weekly_review_recorded_for_its_friday_is_not_owed_on_friday(tmp_path: Path) -> None:
    """2026-08-27 lesson: a review pulled forward to Thursday is recorded with the
    date of the Friday it satisfies, so Friday's obligation reads as met."""
    record(tmp_path, "weekly-review", "alpha", "2026-09-11")  # done Thursday 09-10, for Friday 09-11

    assert query_json(tmp_path, "weekly-review", "--workspace", "alpha", "--today", "2026-09-11")["owed"] is False
    assert query_json(tmp_path, "weekly-review", "--workspace", "alpha", "--today", "2026-09-17")["owed"] is False
    assert query_json(tmp_path, "weekly-review", "--workspace", "alpha", "--today", "2026-09-18")["owed"] is True


def test_a_review_dated_the_day_it_was_done_leaves_friday_owed(tmp_path: Path) -> None:
    """The failure the lesson records: dated Thursday, Friday still reads owed."""
    record(tmp_path, "weekly-review", "alpha", "2026-09-10")
    assert query_json(tmp_path, "weekly-review", "--workspace", "alpha", "--today", "2026-09-11")["owed"] is True


def test_record_refuses_unknown_outcomes_migration_mode_and_oversized_records(tmp_path: Path) -> None:
    bad = run(tmp_path, "record", "--direction", "day-end", "--workspace", "alpha", "--date", "2026-09-14",
              "--outcome", "done-ish")
    assert bad.returncode != 0
    migration = run(tmp_path, "record", "--direction", "day-end", "--workspace", "alpha", "--date", "2026-09-14",
                    "--mode", "migration")
    assert migration.returncode != 0 and "migration" in migration.stderr
    big = run(tmp_path, "record", "--direction", "day-end", "--workspace", "alpha", "--date", "2026-09-14",
              "--note", "x" * 3000)
    assert big.returncode != 0 and "--pointer" in big.stderr
    assert not (tmp_path / "history.jsonl").exists()


def test_an_interrupted_tail_is_left_as_found(tmp_path: Path) -> None:
    (tmp_path / "history.jsonl").write_text('{"date": "2026-09-14", "direction": "day-st', encoding="utf-8")
    done = run(tmp_path, "record", "--direction", "day-end", "--workspace", "alpha", "--date", "2026-09-14")
    assert done.returncode != 0 and "interrupted" in done.stderr
    assert (tmp_path / "history.jsonl").read_text(encoding="utf-8").endswith("day-st")


def test_a_malformed_line_costs_only_that_line(tmp_path: Path) -> None:
    (tmp_path / "history.jsonl").write_text("not json\n", encoding="utf-8")
    record(tmp_path, "day-end", "alpha", "2026-09-14")
    out = query_json(tmp_path, "last", "--workspace", "alpha")
    assert out["workspaces"]["alpha"]["last_day_end"]["date"] == "2026-09-14"
    assert out["malformed_lines"] == 1


def test_concurrent_writers_keep_whole_records(tmp_path: Path) -> None:
    (tmp_path / "config.json").write_text(json.dumps({"defaults": {"plans_dirs": []}, "workspaces": {}}), encoding="utf-8")
    procs = [subprocess.Popen([sys.executable, str(SCRIPT), "--state-dir", str(tmp_path), "record",
                               "--direction", "day-end", "--workspace", f"ws{i}", "--date", "2026-09-14"],
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE) for i in range(12)]
    said = [p.communicate() for p in procs]  # reads each to its end and closes its pipes
    assert all(p.returncode == 0 for p in procs), said
    lines = (tmp_path / "history.jsonl").read_text(encoding="utf-8").splitlines()
    assert sorted(json.loads(line)["workspace"] for line in lines) == sorted(f"ws{i}" for i in range(12))


def test_no_test_reads_the_ritual_history_this_mac_has_synced() -> None:
    """5.20.1: once this Mac's hourly sync had written its ritual history into its sessions repos (5.20.0), these tests
    read it through the person's own synthesis config, and seven of them failed on this Mac alone. No test reads this
    Mac's own state: every test's synthesis home is a folder of its own."""
    from synthesis import rituals
    assert rituals.hosts_folders() == []


# --- a mid-day sync (5.25.1) -----------------------------------------------------------------
# 2026-11-18: an operations seat could not record its mid-day sync. The worker contract names `midday` among the run
# types and records a run with `--direction <run type>`, the skill says to record every ritual, and `record` took only
# day-start, day-end and weekly-review. A sync opens no workday and closes none, so each view of starts, closes,
# streaks and reviews reads as it did without one; the row of `last` lists the newest. Committed before the change to
# the script. Each test reads a home of its own, so the summary's mail lines read no manifest of this Mac's.


def midday(state: Path, workspace: str, day: str, *extra: str) -> str:
    done = run(state, "record", "--direction", "midday", "--workspace", workspace, "--date", day, *extra)
    assert done.returncode == 0, done.stderr
    return done.stdout


def log_lines(state: Path) -> list[dict]:
    return [json.loads(line) for line in (state / "history.jsonl").read_text(encoding="utf-8").splitlines()]


def test_a_midday_sync_is_recorded_and_listed(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    said = midday(tmp_path, "alpha", "2026-09-14", "--outcome", "partial", "--pointer", "/w/ritual-workers/2026-09-14-midday.md")

    assert said.startswith("recorded midday alpha 2026-09-14 (partial)\n")
    line = log_lines(tmp_path)[-1]
    assert (line["direction"], line["date"], line["outcome"], line["pointer"]) == (
        "midday", "2026-09-14", "partial", "/w/ritual-workers/2026-09-14-midday.md")
    view = query_json(tmp_path, "last", "--workspace", "alpha", "--today", "2026-09-14")
    alpha = view["workspaces"]["alpha"]
    assert alpha["last_midday"] == {"date": "2026-09-14", "mode": "full", "outcome": "partial", "ts": line["ts"]}
    assert alpha["last_day_start"] is None and alpha["last_day_end"] is None   # a sync opens and closes nothing
    assert "malformed_lines" not in view
    assert query_json(tmp_path, "open", "--workspace", "alpha", "--today", "2026-09-14")["open_workdays"] == []


# A week of one workspace's rituals, and another's close, with a sync on a day left open, after a close, on a day with
# no day-start, twice in one day and in the other workspace.
WEEK = [("day-start", "alpha", "2026-09-08"), ("day-end", "alpha", "2026-09-08"),
        ("day-start", "alpha", "2026-09-09"), ("midday", "alpha", "2026-09-09"),
        ("day-start", "alpha", "2026-09-10"), ("day-end", "alpha", "2026-09-10"), ("midday", "alpha", "2026-09-10"),
        ("midday", "alpha", "2026-09-11"), ("weekly-review", "alpha", "2026-09-11"), ("day-end", "beta", "2026-09-11"),
        ("day-start", "alpha", "2026-09-14"), ("midday", "alpha", "2026-09-14"), ("midday", "alpha", "2026-09-14"),
        ("midday", "beta", "2026-09-14")]


def test_midday_syncs_change_no_view_of_starts_closes_streaks_or_reviews(tmp_path: Path, monkeypatch) -> None:
    """The same week in two logs, the second with its syncs: the summary reads the same in words and in JSON, apart
    from the newest sync each row lists."""
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    config = {"defaults": {"streak": "expected-days", "weekdays": [0, 1, 2, 3, 4], "non_working_dates": [], "plans_dirs": []},
              "workspaces": {"alpha": {}, "beta": {}}}
    hours: dict = {}
    lines = []
    for direction, workspace, day in WEEK:  # each step as `record` appends it, an hour after the one before it that day
        hours[day] = hours.get(day, 8) + 1
        lines.append(json.dumps({"ts": f"{day}T{hours[day]:02d}:00:00-04:00", "date": day, "direction": direction,
                                 "workspace": workspace, "mode": "full", "outcome": "clean"}, separators=(",", ":"), sort_keys=True))
    for name, kept in (("plain", [line for line, step in zip(lines, WEEK) if step[0] != "midday"]), ("synced", lines)):
        (tmp_path / name).mkdir()
        (tmp_path / name / "config.json").write_text(json.dumps(config), encoding="utf-8")
        (tmp_path / name / "history.jsonl").write_text("".join(line + "\n" for line in kept), encoding="utf-8")

    for today in ("2026-09-14", "2026-09-15"):
        words = [run(tmp_path / name, "query", "summary", "--today", today) for name in ("plain", "synced")]
        assert words[0].returncode == words[1].returncode == 0 and words[0].stdout == words[1].stdout, today
        plain, synced = (query_json(tmp_path / name, "summary", "--today", today) for name in ("plain", "synced"))
        assert [row.pop("last_midday") for row in plain["workspaces"].values()] == [None, None]
        newest = {name: row.pop("last_midday")["date"] for name, row in synced["workspaces"].items()}
        assert newest == {"alpha": "2026-09-14", "beta": "2026-09-14"} and synced == plain, today
    assert synced["open_workdays"] == [{"workspace": "alpha", "date": "2026-09-09"}, {"workspace": "alpha", "date": "2026-09-14"}]
    monday = query_json(tmp_path / "synced", "summary", "--today", "2026-09-14")["workspaces"]
    assert (monday["alpha"]["streak"], monday["beta"]["streak"], monday["alpha"]["last_day_end"]["date"]) == (0, 1, "2026-09-10")
    assert (monday["alpha"]["weekly_review_owed"], monday["beta"]["weekly_review_owed"]) == (False, True)


def test_a_midday_sync_after_the_days_close_leaves_it_closed(tmp_path: Path, monkeypatch) -> None:
    """A sync asked for after the close, partial, leaves the close clean and the streak as it was."""
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    (tmp_path / "config.json").write_text(json.dumps({
        "defaults": {"weekdays": [0, 1, 2, 3, 4], "non_working_dates": [], "plans_dirs": []},
        "workspaces": {"alpha": {"streak": "expected-days"}}}), encoding="utf-8")
    record(tmp_path, "day-start", "alpha", "2026-09-14")
    record(tmp_path, "day-end", "alpha", "2026-09-14")
    before = query_json(tmp_path, "summary", "--today", "2026-09-14")

    midday(tmp_path, "alpha", "2026-09-14", "--outcome", "partial")

    after = query_json(tmp_path, "summary", "--today", "2026-09-14")
    assert before["workspaces"]["alpha"].pop("last_midday") is None
    synced = after["workspaces"]["alpha"].pop("last_midday")
    assert (synced["date"], synced["outcome"]) == ("2026-09-14", "partial") and after == before
    assert after["workspaces"]["alpha"]["last_day_end"] == {"date": "2026-09-14", "mode": "full", "outcome": "clean"}
    assert (after["workspaces"]["alpha"]["streak"], after["open_workdays"]) == (1, [])


def test_two_midday_syncs_in_one_day_each_keep_their_own_record(tmp_path: Path, monkeypatch) -> None:
    """The contract writes a later mid-day run's artifact as `midday-N`. Its record is `midday` too, one per run, each
    pointing at its own artifact: the N belongs to the artifact's name, and no direction carries it."""
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    record(tmp_path, "day-start", "alpha", "2026-09-14")
    for name, outcome in (("midday", "clean"), ("midday-2", "partial")):
        midday(tmp_path, "alpha", "2026-09-14", "--outcome", outcome, "--pointer", f"/w/ritual-workers/2026-09-14-{name}.md")
    refused = run(tmp_path, "record", "--direction", "midday-2", "--workspace", "alpha", "--date", "2026-09-14")
    assert refused.returncode == 2 and "midday-2" in refused.stderr

    syncs = [line for line in log_lines(tmp_path) if line["direction"] == "midday"]
    assert [(s["date"], s["outcome"], s["pointer"].rsplit("/", 1)[1]) for s in syncs] == [
        ("2026-09-14", "clean", "2026-09-14-midday.md"), ("2026-09-14", "partial", "2026-09-14-midday-2.md")]
    alpha = query_json(tmp_path, "last", "--workspace", "alpha", "--today", "2026-09-14")["workspaces"]["alpha"]
    assert alpha["last_midday"]["ts"] == syncs[-1]["ts"] and alpha["last_day_end"] is None
    assert query_json(tmp_path, "open", "--workspace", "alpha", "--today", "2026-09-15")["open_workdays"] == [
        {"workspace": "alpha", "date": "2026-09-14"}]                         # two syncs, and the day is still open


def test_the_summary_counts_each_macs_close_and_names_the_one_it_runs_on(tmp_path: Path, monkeypatch) -> None:
    """BACKLOG D5 (2026-11-18): two Macs that close one workspace on one day read the same in a summary that names only
    the newest close, so whether the other Mac's record had arrived could not be seen. Each Mac's newest close of the
    workspace is listed by host, this Mac's own marked; with no other Mac's close read, the words are as they were."""
    monkeypatch.setenv("SYNTHESIS_HOST", "Mac A")
    home, repo, state = Path(os.environ["SYNTHESIS_HOME"]), tmp_path / "sessions-alpha", tmp_path / "state"
    (repo / "rituals").mkdir(parents=True)
    home.mkdir(parents=True, exist_ok=True)
    (home / "config.json").write_text(json.dumps({"sessions_repos": {"alpha": str(repo)}}), encoding="utf-8")
    record(state, "day-end", "alpha", "2026-09-14")
    alone = run(state, "query", "summary", "--today", "2026-09-14").stdout
    view = query_json(state, "summary", "--today", "2026-09-14")
    here = view["host"]
    assert here.startswith("Mac-A-") and view["workspaces"]["alpha"]["last_day_end_by_host"] == {here: "2026-09-14"}
    assert "closes by host" not in alone, alone
    (repo / "rituals" / "Mac-B-0123abcd.jsonl").write_text(json.dumps({"date": "2026-09-11", "direction": "day-end", "workspace": "alpha",
                                                                       "ts": "2026-09-11T18:00:00-04:00"}) + "\n", encoding="utf-8")
    view = query_json(state, "summary", "--today", "2026-09-14")
    assert view["workspaces"]["alpha"]["last_day_end_by_host"] == {here: "2026-09-14", "Mac-B-0123abcd": "2026-09-11"}
    assert view["workspaces"]["alpha"]["last_day_end"]["date"] == "2026-09-14"
    shown = run(state, "query", "summary", "--today", "2026-09-14").stdout
    assert f"closes by host: {here} 2026-09-14 (this Mac), Mac-B-0123abcd 2026-09-11" in shown, shown
    assert [line for line in shown.splitlines() if "closes by host" not in line] == alone.splitlines()
