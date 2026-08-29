"""Tests for the portfolio review surface.

Two properties matter more than the reporting itself, and both have a negative
case: the review must never fail a ritual (exit 0 under every degraded input),
and it must never surface a paused project (pausing something is how you get it
to stop asking).
"""

from __future__ import annotations

import datetime
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parent / "portfolio_review.py"


def run(*args: str, home: Path | None = None) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)
    if home is not None:
        env["SYNTHESIS_HOME"] = str(home)
    return subprocess.run([sys.executable, str(SCRIPT), *args],
                          capture_output=True, text=True, env=env)


def make_index(tmp_path: Path, projects: list[dict]) -> Path:
    import yaml
    root = tmp_path / "kb" / "projects"
    root.mkdir(parents=True)
    (root / "index.yaml").write_text(yaml.safe_dump({"projects": projects}))
    for p in projects:
        (root / p["id"]).mkdir(exist_ok=True)
    return root / "index.yaml"


def days_ago(n: int) -> str:
    return (datetime.date.today() - datetime.timedelta(days=n)).isoformat()


def test_stale_active_project_is_surfaced(tmp_path):
    idx = make_index(tmp_path, [{"id": "alpha", "status": "active",
                                 "last_session": days_ago(120)}])
    r = run("--index", str(idx))
    assert r.returncode == 0
    assert "alpha" in r.stdout


def test_paused_is_never_surfaced(tmp_path):
    """Pausing a project is how you get it to stop asking. If the review
    surfaced paused projects, pausing would buy nothing and the backlog would
    simply move."""
    idx = make_index(tmp_path, [{"id": "alpha", "status": "paused",
                                 "last_session": days_ago(900)}])
    r = run("--index", str(idx))
    assert r.returncode == 0
    assert "alpha" not in r.stdout
    assert "honest" in r.stdout


def test_fresh_active_project_is_not_surfaced(tmp_path):
    idx = make_index(tmp_path, [{"id": "alpha", "status": "active",
                                 "last_session": days_ago(3)}])
    r = run("--index", str(idx))
    assert "alpha" not in r.stdout


def test_output_is_capped_and_says_how_many_were_withheld(tmp_path):
    """An uncapped list gets skipped, and a skipped check protects nothing.
    The count of withheld items has to be visible or the cap becomes a silent
    truncation that reads as full coverage."""
    idx = make_index(tmp_path, [
        {"id": f"p{i}", "status": "active", "last_session": days_ago(100 + i)}
        for i in range(9)])
    r = run("--index", str(idx))
    shown = sum(1 for line in r.stdout.splitlines() if "stale " in line)
    assert shown == 3
    assert "and 6 more" in r.stdout


def test_all_flag_lifts_the_cap(tmp_path):
    idx = make_index(tmp_path, [
        {"id": f"p{i}", "status": "active", "last_session": days_ago(100 + i)}
        for i in range(9)])
    r = run("--index", str(idx), "--all")
    shown = sum(1 for line in r.stdout.splitlines() if "stale " in line)
    assert shown == 9


def test_undated_projects_sort_first(tmp_path):
    """No last_session is the most suspect state: nothing can even be
    checked about it."""
    idx = make_index(tmp_path, [
        {"id": "dated", "status": "active", "last_session": days_ago(400)},
        {"id": "undated", "status": "active"},
    ])
    r = run("--index", str(idx), "--all")
    assert r.stdout.index("undated") < r.stdout.index("dated")


def test_json_mode_is_machine_readable(tmp_path):
    idx = make_index(tmp_path, [{"id": "alpha", "status": "active",
                                 "last_session": days_ago(120)}])
    r = run("--index", str(idx), "--json")
    data = json.loads(r.stdout)
    assert data["stale_total"] == 1
    assert data["shown"][0]["id"] == "alpha"


# --- degraded inputs: a surface must never break the ritual that calls it ---

def test_missing_index_exits_zero(tmp_path):
    r = run("--index", str(tmp_path / "nope.yaml"))
    assert r.returncode == 0


def test_no_console_config_exits_zero(tmp_path):
    r = run(home=tmp_path / "empty-home")
    assert r.returncode == 0


def test_unparseable_index_exits_zero(tmp_path):
    bad = tmp_path / "projects"
    bad.mkdir()
    (bad / "index.yaml").write_text("{{{ not yaml")
    r = run("--index", str(bad / "index.yaml"))
    assert r.returncode == 0


def test_source_without_projects_dir_is_reported_not_skipped_silently(tmp_path):
    """Silently dropping a configured source is how a whole repo goes
    unreviewed while the run still prints a clean result."""
    home = tmp_path / "home"
    home.mkdir()
    (home / "console.yaml").write_text(
        "sources:\n  - root: /somewhere\n")
    r = run(home=home)
    assert r.returncode == 0
    assert "no projects_dir" in r.stderr
