"""R5.1 and R1.2: the SessionStart ritual line and the nudge's owed-today answer.

The line reads the append-only ritual log, names no workspace (this session's is
"this workspace", others are counts plus a pointer), and says when no day-start
has been recorded today. The nudge question fails toward nudging.
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
from datetime import date, timedelta
from pathlib import Path

from synthesis import rituals

ROOT = Path(__file__).resolve().parents[1]
MONDAY = date(2026, 9, 14)


def log(home: Path, *records: dict, config: dict | None = None) -> None:
    folder = home / "rituals"
    folder.mkdir(parents=True, exist_ok=True)
    with (folder / "history.jsonl").open("a", encoding="utf-8") as handle:
        for r in records:
            handle.write(json.dumps({"ts": "2026-09-14T09:00:00-04:00", **r}) + "\n")
    if config is not None:
        (folder / "config.json").write_text(json.dumps(config), encoding="utf-8")


def rec(direction: str, workspace: str, day: date, **extra) -> dict:
    return {"direction": direction, "workspace": workspace, "date": day.isoformat(), **extra}


def here(tmp_path: Path, monkeypatch, workspace: str = "alpha") -> str:
    monkeypatch.setenv("HOME", str(tmp_path))
    cwd = tmp_path / "workspaces" / workspace / "some-repo"
    cwd.mkdir(parents=True)
    return str(cwd)


def test_no_ritual_ever_recorded_means_no_line(isolated_home, tmp_path, monkeypatch):
    assert rituals.session_line(here(tmp_path, monkeypatch), MONDAY) == ""


def test_the_line_describes_this_workspace_without_naming_any(isolated_home, tmp_path, monkeypatch):
    log(isolated_home,
        rec("day-start", "alpha", MONDAY - timedelta(days=3)),  # Friday, never closed
        rec("day-end", "alpha", MONDAY - timedelta(days=4)),
        rec("day-start", "client-secret-name", MONDAY - timedelta(days=1)),
        rec("weekly-review", "client-secret-name", MONDAY - timedelta(days=3)),
        config={"workspaces": {"alpha": {"streak": "expected-days"}}})
    line = rituals.session_line(here(tmp_path, monkeypatch), MONDAY)

    assert line.startswith("Rituals (today Mon 2026-09-14): this workspace: last day-end 2026-09-10; streak 0")
    assert "no day-start recorded today" in line
    assert "1 workday(s) started and never closed (2026-09-11)" in line
    assert "weekly review owed (Friday 2026-09-11)" in line
    assert "1 other workspace(s): 1 with workdays never closed, 0 owing a weekly review" in line
    assert "alpha" not in line and "client-secret-name" not in line
    assert "ritual_state.py query summary" in line


def test_a_day_start_recorded_today_is_not_reported_missing(isolated_home, tmp_path, monkeypatch):
    log(isolated_home, rec("day-start", "alpha", MONDAY), rec("weekly-review", "alpha", MONDAY - timedelta(days=3)))
    line = rituals.session_line(here(tmp_path, monkeypatch), MONDAY)
    assert "no day-start recorded today" not in line
    assert "never closed" not in line  # today's open day is not yet a missed close
    assert "weekly review owed" not in line


def test_outside_a_workspace_the_line_is_counts_only(isolated_home, tmp_path, monkeypatch):
    log(isolated_home, rec("day-start", "alpha", MONDAY - timedelta(days=1)))
    monkeypatch.setenv("HOME", str(tmp_path))
    line = rituals.session_line(str(tmp_path), MONDAY)
    assert "this workspace" not in line and "1 other workspace(s): 1 with workdays never closed" in line


def test_an_unreadable_config_is_said_and_never_guessed_around(isolated_home, tmp_path, monkeypatch):
    log(isolated_home, rec("day-end", "alpha", MONDAY))
    cwd = here(tmp_path, monkeypatch)
    for broken in ("not json", "[]", '{"defaults": {}}'):
        (isolated_home / "rituals" / "config.json").write_text(broken, encoding="utf-8")
        assert "state unreadable" in rituals.session_line(cwd, MONDAY)


def test_migration_markers_and_unnamed_records_open_nothing(isolated_home):
    log(isolated_home, rec("day-start", "alpha", MONDAY, mode="migration"), rec("day-start", "", MONDAY),
        rec("day-start", "unknown", MONDAY))
    records, bad = rituals.read()
    assert rituals.open_days(records, MONDAY) == [] and bad == 0


def test_a_malformed_line_costs_only_that_line(isolated_home):
    log(isolated_home, rec("day-end", "alpha", MONDAY))
    with (isolated_home / "rituals" / "history.jsonl").open("a", encoding="utf-8") as handle:
        handle.write("{broken\n")
    records, bad = rituals.read()
    assert len(records) == 1 and bad == 1


def test_weekly_review_is_anchored_to_the_most_recent_friday(isolated_home):
    friday = date(2026, 9, 11)
    assert rituals.friday(friday) == friday and rituals.friday(MONDAY) == friday
    assert rituals.weekly_owed([], "alpha", MONDAY)
    review = [rec("weekly-review", "alpha", friday)]  # done Thursday, recorded for the Friday it satisfies
    assert not rituals.weekly_owed(review, "alpha", friday) and rituals.weekly_owed(review, "alpha", friday + timedelta(7))
    assert rituals.weekly_owed([rec("weekly-review", "beta", friday)], "alpha", friday)  # one seat never answers for another


def test_owed_today_needs_every_expected_workspace_closed(isolated_home):
    cfg = {"defaults": {"weekdays": [0, 1, 2, 3, 4]}, "workspaces": {"alpha": {"streak": "expected-days"},
                                                                     "beta": {"streak": "expected-days"}}}
    log(isolated_home, rec("day-end", "alpha", MONDAY), config=cfg)
    assert rituals.owed_today(MONDAY)  # beta has not closed: one close never silences another
    log(isolated_home, rec("day-end", "beta", MONDAY))
    assert not rituals.owed_today(MONDAY)
    assert not rituals.owed_today(date(2026, 9, 13))  # Sunday is not expected
    log(isolated_home, rec("day-start", "gamma", MONDAY))
    assert rituals.owed_today(MONDAY)  # opened today and not closed


def test_the_nudge_entry_point_fails_toward_nudging(isolated_home, tmp_path):
    def owed(env_home):
        return subprocess.run([sys.executable, "-S", str(ROOT / "synthesis" / "rituals.py"), "--owed-today"],
                              env={"SYNTHESIS_HOME": str(env_home), "PATH": "/usr/bin:/bin"}, capture_output=True).returncode
    assert owed(tmp_path / "empty") == 0
    log(isolated_home, rec("day-start", "alpha", date.today()))
    assert owed(isolated_home) == 1
    (isolated_home / "rituals" / "config.json").write_text("{", encoding="utf-8")
    assert owed(isolated_home) != 0


def test_the_line_is_fast_on_a_year_of_records(isolated_home, tmp_path, monkeypatch):
    start = MONDAY - timedelta(days=400)
    log(isolated_home, *[rec(d, w, start + timedelta(days=i)) for i in range(400)
                         for w in ("alpha", "beta", "gamma") for d in ("day-start", "day-end")],
        config={"workspaces": {"alpha": {"streak": "expected-days"}}})
    cwd = here(tmp_path, monkeypatch)
    began = time.perf_counter()
    line = rituals.session_line(cwd, MONDAY)
    assert time.perf_counter() - began < 0.1 and "streak" in line


def test_session_start_carries_the_ritual_line(isolated_home, tmp_path, monkeypatch):
    import io
    from synthesis import hook
    log(isolated_home, rec("day-end", "alpha", date.today() - timedelta(days=1)))
    out = io.StringIO()
    monkeypatch.setattr(sys, "stdout", out)
    hook.session_start({"session_id": "s-1", "cwd": here(tmp_path, monkeypatch)})
    context = json.loads(out.getvalue())["hookSpecificOutput"]["additionalContext"]
    assert "Rituals (today" in context and "alpha" not in context
