"""Fleet ~-normalization: expansion, account-routing, and the doctor gate."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import fleet_paths as FP

HOME = str(Path.home())


def test_expand_home_covers_tilde_and_dollar_home():
    assert FP.expand_home("~/x") == HOME + "/x"
    assert FP.expand_home("$HOME/x") == HOME + "/x"
    assert FP.expand_home("${HOME}/x") == HOME + "/x"
    assert FP.expand_home("/tmp/x") == "/tmp/x"


def test_is_unexpanded_home_path_flags_literal_home_absolutes():
    assert FP.is_unexpanded_home_path(f"{HOME}/workspaces/work")
    assert FP.is_unexpanded_home_path("/Users/rajiv/.synthesis/coordination/active-sessions.md")
    assert FP.is_unexpanded_home_path("/Users/other/x")
    assert FP.is_unexpanded_home_path("/home/other/x")


def test_is_unexpanded_home_path_passes_portable_values():
    assert not FP.is_unexpanded_home_path("~/.synthesis/coordination/active-sessions.md")
    assert not FP.is_unexpanded_home_path("~/workspaces/work")
    assert not FP.is_unexpanded_home_path("$HOME/workspaces/work")
    assert not FP.is_unexpanded_home_path("${HOME}/workspaces/work")
    assert not FP.is_unexpanded_home_path("relative/path")
    assert not FP.is_unexpanded_home_path("/tmp/outside-home")
    assert not FP.is_unexpanded_home_path("")
    assert not FP.is_unexpanded_home_path(None)
    assert not FP.is_unexpanded_home_path(42)


def test_route_matches_tilde_key_against_absolute_candidate():
    workspaces = {"~/workspaces/work": {"account": "work"}}
    match = FP.route_account_workspace(workspaces, f"{HOME}/workspaces/work")
    assert match == ("~/workspaces/work", {"account": "work"})


def test_route_matches_absolute_key_against_tilde_candidate():
    # Legacy absolute keys keep routing after the other side normalizes.
    workspaces = {f"{HOME}/workspaces/work": {"account": "work"}}
    match = FP.route_account_workspace(workspaces, "~/workspaces/work")
    assert match is not None and match[1] == {"account": "work"}


def test_route_expands_before_compare_regression():
    # Exact-match on unexpanded strings would silently stop routing: the
    # persisted key and the runtime candidate differ textually but name the
    # same directory.
    workspaces = {"~/workspaces/work": {"account": "work"}}
    candidate = f"{HOME}/workspaces/work"
    assert candidate not in workspaces
    assert FP.route_account_workspace(workspaces, candidate) is not None


def test_route_prefers_longest_prefix_and_subpaths():
    workspaces = {
        "~/workspaces": {"account": "default"},
        "~/workspaces/work": {"account": "work"},
    }
    key, record = FP.route_account_workspace(
        workspaces, f"{HOME}/workspaces/work/tribune"
    )
    assert record == {"account": "work"}
    assert FP.route_account_workspace(workspaces, f"{HOME}/elsewhere") is None
    assert FP.route_account_workspace({}, "~/workspaces/x") is None


def _write(root: Path, name: str, content: str) -> Path:
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def _offending_fixtures(root: Path) -> None:
    _write(
        root,
        "git-hook-config.yaml",
        f'config_version: 2\ncoordination_board: "{HOME}/.synthesis/coordination/active-sessions.md"\n',
    )
    _write(
        root,
        "ritual/workers.yaml",
        f'workers:\n  - id: work\n    artifact_dir: "{HOME}/workspaces/work/ritual-workers"\n',
    )
    _write(
        root,
        "account-routing/workspaces.json",
        json.dumps({f"{HOME}/workspaces/work": {"account": "work"}}),
    )
    _write(
        root,
        "checkpoint/active-campaign.json",
        json.dumps(
            {
                "schema_version": 1,
                "id": "drive",
                "recipient": "x sessions",
                "checks": ["recovery"],
                "minimum_plugin_version": "4.0.0",
                "recipient_index": f"{HOME}/projects/index.yaml",
            }
        ),
    )


def test_doctor_gate_fails_naming_all_four_files(tmp_path):
    _offending_fixtures(tmp_path)
    hits = FP.check_synced_root(tmp_path)
    assert {Path(hit.path).name for hit in hits} == {
        "git-hook-config.yaml",
        "workers.yaml",
        "workspaces.json",
        "active-campaign.json",
    }
    assert all(hit.line >= 1 and hit.value for hit in hits)
    report = FP.format_gate_report(hits)
    assert report.startswith("FAIL fleet-paths")
    assert "git-hook-config.yaml" in report
    assert "workers.yaml" in report


def test_doctor_gate_passes_after_normalization(tmp_path):
    _write(
        tmp_path,
        "git-hook-config.yaml",
        'config_version: 2\ncoordination_board: "~/.synthesis/coordination/active-sessions.md"\n',
    )
    _write(
        tmp_path,
        "ritual/workers.yaml",
        "workers:\n  - id: work\n"
        '    artifact_dir: "~/workspaces/work/ritual-workers"\n',
    )
    _write(
        tmp_path,
        "account-routing/workspaces.json",
        json.dumps({"~/workspaces/work": {"account": "work"}}),
    )
    _write(
        tmp_path,
        "checkpoint/active-campaign.json",
        json.dumps(
            {
                "schema_version": 1,
                "id": "drive",
                "recipient": "x sessions",
                "checks": ["recovery"],
                "minimum_plugin_version": "4.0.0",
                "recipient_index": "~/projects/index.yaml",
            }
        ),
    )
    hits = FP.check_synced_root(tmp_path)
    assert hits == []
    assert FP.format_gate_report(hits).startswith("PASS fleet-paths")


def test_doctor_gate_skips_missing_files(tmp_path):
    assert FP.check_synced_root(tmp_path) == []


def test_doctor_gate_ignores_comments_and_non_home_absolutes(tmp_path):
    _write(
        tmp_path,
        "git-hook-config.yaml",
        "# was: /Users/rajiv/old/path\nconfig_version: 2\nlog: /tmp/hooks.log\n",
    )
    assert FP.check_synced_root(tmp_path) == []


def test_doctor_gate_reports_line_numbers(tmp_path):
    path = _write(
        tmp_path,
        "git-hook-config.yaml",
        "config_version: 2\n"
        'coordination_board: "~/.synthesis/ok.md"\n'
        f'secondary: "{HOME}/second.md"\n',
    )
    hits = FP.check_synced_root(tmp_path)
    assert [(hit.line, hit.value) for hit in hits] == [
        (3, f"{HOME}/second.md")
    ]
    assert str(hits[0]).startswith(f"{path}:3:")


def test_fleet_doctor_command_fails_and_passes(tmp_path, capsys):
    import coordination as ENGINE

    failing = tmp_path / "synthesis"
    _write(
        failing,
        "git-hook-config.yaml",
        f'config_version: 2\ncoordination_board: "{HOME}/board.md"\n',
    )
    shell = type("Args", (), {"board": failing / "board.md", "synthesis_root": failing})()
    assert ENGINE.command_fleet_doctor(shell) == 1
    err = capsys.readouterr().err
    assert "FAIL fleet-paths" in err
    assert "git-hook-config.yaml" in err
    passing = tmp_path / "clean"
    _write(
        passing,
        "git-hook-config.yaml",
        'config_version: 2\ncoordination_board: "~/.synthesis/board.md"\n',
    )
    shell = type("Args", (), {"board": passing / "board.md", "synthesis_root": passing})()
    assert ENGINE.command_fleet_doctor(shell) == 0
    assert "PASS fleet-paths" in capsys.readouterr().out
