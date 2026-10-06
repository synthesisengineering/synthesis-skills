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
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "ritual_state.py"


def run(state: Path, *args: str) -> subprocess.CompletedProcess[str]:
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
        "defaults": {"streak": "none", "weekdays": [0, 1, 2, 3, 4], "non_working_dates": []},
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


# --- an empty --workspace is refused, never read as omitted ----------------------------------

VIEWS = ("last", "open", "streak", "weekly-review", "summary")


def _one_workspace_log(state: Path) -> None:
    """A log naming exactly one workspace: the shape in which an empty value,
    read as omitted, lets `weekly-review` infer a seat and every other view
    answer for the whole log."""
    (state / "config.json").write_text(json.dumps({
        "defaults": {"streak": "expected-days", "weekdays": [0, 1, 2, 3, 4], "non_working_dates": []},
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


def test_a_record_needs_its_logical_date(tmp_path: Path) -> None:
    done = run(tmp_path, "record", "--direction", "day-end", "--workspace", "alpha", "--date", "yesterday")
    assert done.returncode != 0 and "never inferred" in done.stderr
    missing = run(tmp_path, "record", "--direction", "day-end", "--workspace", "alpha")
    assert missing.returncode != 0
    assert not (tmp_path / "history.jsonl").exists()


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
    procs = [subprocess.Popen([sys.executable, str(SCRIPT), "--state-dir", str(tmp_path), "record",
                               "--direction", "day-end", "--workspace", f"ws{i}", "--date", "2026-09-14"],
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE) for i in range(12)]
    assert all(p.wait() == 0 for p in procs)
    lines = (tmp_path / "history.jsonl").read_text(encoding="utf-8").splitlines()
    assert sorted(json.loads(line)["workspace"] for line in lines) == sorted(f"ws{i}" for i in range(12))
