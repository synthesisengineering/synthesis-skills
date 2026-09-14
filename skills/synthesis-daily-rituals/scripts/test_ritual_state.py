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

SCRIPT = Path(__file__).resolve().parent / "ritual_state.py"


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

    assert query_json(tmp_path, "weekly-review", "--workspace", "beta") == {
        "workspace": "beta", "last_weekly_review": None,
    }
    assert query_json(tmp_path, "weekly-review", "--workspace", "alpha") == {
        "workspace": "alpha", "last_weekly_review": "2026-09-11",
    }


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

    assert query_json(tmp_path, "weekly-review") == {
        "workspace": "alpha", "last_weekly_review": "2026-09-11", "workspace_inferred": True,
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


# --- the script's own suite ------------------------------------------------------------------


def test_script_self_test_suite_passes() -> None:
    """The installed copy ships without pytest; its `test` subcommand is the
    suite a seat can run from the runtime directory, and it stays green."""
    done = subprocess.run([sys.executable, str(SCRIPT), "test"], capture_output=True, text=True, check=False)
    assert done.returncode == 0, done.stdout + done.stderr
    assert "all tests pass" in done.stdout
