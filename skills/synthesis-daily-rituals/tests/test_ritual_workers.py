"""The workers registry: `~`-rooted paths expand on every Mac, a malformed registry
is refused rather than read as "no workers", and the desk's coverage line names
every registered workspace as folded, pending or not scheduled."""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from datetime import date
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "ritual_workers.py"
SPEC = importlib.util.spec_from_file_location("ritual_workers", SCRIPT)
workers_mod = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(workers_mod)
DAY = date(2026, 9, 14)


def registry(tmp_path: Path, workers: str) -> Path:
    path = tmp_path / "workers.yaml"
    path.write_text("contract_version: 1\ndesk_seat: ops-desk\nworkers:\n" + workers, encoding="utf-8")
    return path


def test_tilde_and_home_paths_expand_on_this_mac(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    path = registry(tmp_path, "  alpha:\n    status: active\n    artifact_dir: ~/ws/alpha/ritual-workers\n"
                              "    seat: alpha-ops\n  beta:\n    status: on-demand\n    artifact_dir: $HOME/ws/beta\n")
    loaded = workers_mod.load_workers(path)
    assert loaded["alpha"]["artifact_dir"] == tmp_path / "ws" / "alpha" / "ritual-workers"
    assert loaded["beta"]["artifact_dir"] == tmp_path / "ws" / "beta"


def test_absolute_paths_keep_loading_and_relative_ones_are_refused(tmp_path: Path) -> None:
    ok = registry(tmp_path, f"  alpha:\n    status: active\n    artifact_dir: {tmp_path}/a\n")
    assert workers_mod.load_workers(ok)["alpha"]["artifact_dir"] == tmp_path / "a"
    bad = registry(tmp_path, "  alpha:\n    status: active\n    artifact_dir: relative/dir\n")
    with pytest.raises(ValueError, match="relative"):
        workers_mod.load_workers(bad)


def test_no_registry_is_the_single_session_ritual(tmp_path: Path) -> None:
    assert workers_mod.load_workers(tmp_path / "absent.yaml") == {}


@pytest.mark.parametrize("body", [
    "contract_version: 2\nworkers: {}\n",
    "contract_version: 1\nworkers: []\n",
    "contract_version: 1\nworkers:\n  alpha:\n    status: sometimes\n    artifact_dir: /x\n",
    "contract_version: 1\nworkers:\n  alpha:\n    status: active\n",
    "contract_version: 1\nworkers:\n  alpha: &a\n    status: active\n",
])
def test_a_malformed_registry_is_refused_not_read_as_empty(tmp_path: Path, body: str) -> None:
    path = tmp_path / "workers.yaml"
    path.write_text(body, encoding="utf-8")
    with pytest.raises(ValueError):
        workers_mod.load_workers(path)
    done = subprocess.run([sys.executable, str(SCRIPT), "coverage"], capture_output=True, text=True,
                          env={**os.environ, "RITUAL_WORKERS_FILE": str(path)})
    assert done.returncode == 2 and "refused" in done.stderr


def artifact(directory: Path, run_type: str, finished: str, outcome: str = "clean", name: str = "") -> None:
    """A worker's artifact for DAY, filed under its run type, or under `name` (a later mid-day run is `midday-N`)."""
    directory.mkdir(parents=True, exist_ok=True)
    (directory / f"{DAY}-{name or run_type}.md").write_text(
        f"---\ncontract_version: 1\nrun_type: {run_type}\ndate: {DAY}\nfinished: {finished}\n"
        f"outcome: {outcome}\ngaps: []\n---\n## Decisions needed\nnone\n", encoding="utf-8")


def test_coverage_folds_the_newest_run_and_names_absence(tmp_path: Path) -> None:
    path = registry(tmp_path, f"  alpha:\n    status: active\n    artifact_dir: {tmp_path}/alpha\n"
                              f"  beta:\n    status: active\n    artifact_dir: {tmp_path}/beta\n"
                              f"  gamma:\n    status: on-demand\n    artifact_dir: {tmp_path}/gamma\n"
                              f"  delta:\n    status: dormant\n    artifact_dir: {tmp_path}/delta\n")
    artifact(tmp_path / "alpha", "day-start", "2026-09-14T09:10:00-04:00")
    artifact(tmp_path / "alpha", "day-end", "2026-09-14T18:31:00-04:00", "partial")
    rows = workers_mod.coverage(workers_mod.load_workers(path), DAY)
    assert [(r["workspace"], r["state"]) for r in rows] == [
        ("alpha", "folded"), ("beta", "pending"), ("gamma", "not scheduled")]
    assert rows[0]["run_type"] == "day-end" and rows[0]["outcome"] == "partial"
    done = subprocess.run([sys.executable, str(SCRIPT), "coverage", "--date", str(DAY)], capture_output=True,
                          text=True, env={**os.environ, "RITUAL_WORKERS_FILE": str(path)})
    assert done.returncode == 0, done.stderr
    assert done.stdout.startswith("coverage: alpha day-end 2026-09-14T18:31:00-04:00 (partial)")
    assert "beta pending" in done.stdout and "gamma not scheduled" in done.stdout and "delta" not in done.stdout


def test_coverage_folds_the_newest_midday_run_of_the_day_as_the_sweep_orders_them(tmp_path: Path) -> None:
    """The contract files a later mid-day run that day as `midday-N`, and the deadline sweep reads it after the first
    (5.3.7). Coverage looked for `midday` alone, so with a second sync filed the desk's line gave the first one's time
    and outcome (5.25.1). It folds the newest, N read as a number and only where the sweep reads the name; a day-end
    still supersedes every sync."""
    path = registry(tmp_path, f"  alpha:\n    status: active\n    artifact_dir: {tmp_path}/alpha\n")
    folder = tmp_path / "alpha"
    artifact(folder, "midday", "2026-09-14T12:30:00-04:00", "partial")
    artifact(folder, "midday", "2026-09-14T16:10:00-04:00", "clean", name="midday-2")

    def folded() -> tuple:
        row = workers_mod.coverage(workers_mod.load_workers(path), DAY)[0]
        return row["run_type"], row["finished"], row["outcome"], Path(row["artifact"]).name

    assert folded() == ("midday", "2026-09-14T16:10:00-04:00", "clean", f"{DAY}-midday-2.md")
    done = subprocess.run([sys.executable, str(SCRIPT), "coverage", "--date", str(DAY)], capture_output=True,
                          text=True, env={**os.environ, "RITUAL_WORKERS_FILE": str(path)})
    assert done.returncode == 0 and done.stdout.startswith("coverage: alpha midday 2026-09-14T16:10:00-04:00 (clean)"), done.stderr
    artifact(folder, "midday", "2026-09-14T17:20:00-04:00", "partial", name="midday-9")
    artifact(folder, "midday", "2026-09-14T17:40:00-04:00", "clean", name="midday-10")
    artifact(folder, "midday", "2026-09-14T17:55:00-04:00", "failed", name="midday-02")   # a name the sweep does not read
    assert folded() == ("midday", "2026-09-14T17:40:00-04:00", "clean", f"{DAY}-midday-10.md")
    artifact(folder, "day-end", "2026-09-14T18:31:00-04:00", "partial")
    assert folded() == ("day-end", "2026-09-14T18:31:00-04:00", "partial", f"{DAY}-day-end.md")


def test_coverage_names_a_later_midday_run_with_the_sweeps_own_pattern() -> None:
    """The chief-of-staff collection carries this script without the rituals' records, which the sweep imports as it
    starts, so the script keeps its own copy of the sweep's pattern for a later mid-day run: the two name the same
    files (5.25.1)."""
    sys.path.insert(0, str(SCRIPT.parent))
    import decay_sweep
    assert workers_mod.MIDDAY_RUN.pattern == decay_sweep.MIDDAY_RUN.pattern


def test_list_reports_the_registry(tmp_path: Path) -> None:
    path = registry(tmp_path, f"  alpha:\n    status: active\n    artifact_dir: {tmp_path}/alpha\n    seat: alpha-ops\n")
    done = subprocess.run([sys.executable, str(SCRIPT), "list", "--json"], capture_output=True, text=True,
                          env={**os.environ, "RITUAL_WORKERS_FILE": str(path)})
    assert json.loads(done.stdout) == [{"workspace": "alpha", "status": "active", "seat": "alpha-ops",
                                        "artifact_dir": f"{tmp_path}/alpha"}]
