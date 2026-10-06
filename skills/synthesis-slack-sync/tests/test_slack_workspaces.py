"""The workspace map and the visibility rule (E12): isolated mode reads the session workspace only."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "slack_workspaces.py"
MAP = {"mode": "unified", "workspaces": {"acme": {"domain": "acme.slack.com"},
                                         "personal": {"domain": "example-personal.slack.com"},
                                         "beta": {"domain": "beta-corp.slack.com"}}}


def run(tmp_path: Path, section, *argv: str) -> subprocess.CompletedProcess:
    home = tmp_path / "home"
    home.mkdir(exist_ok=True)
    (home / "config.json").write_text(json.dumps({"slack_workspaces": section} if section is not None else {}))
    env = {"SYNTHESIS_HOME": str(home), "PATH": "/usr/bin:/bin"}
    return subprocess.run([sys.executable, str(SCRIPT), *argv], capture_output=True, text=True, env=env, cwd=tmp_path)


def test_unified_mode_reads_the_focus_first_then_the_others(tmp_path):
    done = run(tmp_path, MAP, "--session-workspace", "acme", "--json")
    assert done.returncode == 0, done.stderr
    result = json.loads(done.stdout)
    assert [w["name"] for w in result["readable"]] == ["acme", "beta", "personal"]
    assert result["readable"][0]["domain"] == "acme.slack.com"


def test_e12_isolated_mode_never_reaches_another_workspace(tmp_path):
    done = run(tmp_path, {**MAP, "mode": "isolated"}, "--session-workspace", "acme", "--json")
    assert done.returncode == 0, done.stderr
    assert json.loads(done.stdout)["readable"] == [{"name": "acme", "domain": "acme.slack.com"}]
    text = run(tmp_path, {**MAP, "mode": "isolated"}, "--session-workspace", "acme").stdout
    assert "readable from here: acme\n" in text


def test_a_workspace_with_no_slack_of_its_own_reads_the_others(tmp_path):
    section = {"mode": "unified", "workspaces": {**MAP["workspaces"], "personal": {"domain": None}}}
    done = run(tmp_path, section, "--session-workspace", "personal", "--json")
    assert done.returncode == 0, done.stderr
    assert [w["name"] for w in json.loads(done.stdout)["readable"]] == ["acme", "beta"]
    assert "personal     (no Slack)  <-- focus" in run(tmp_path, section, "--session-workspace", "personal").stdout
    alone = run(tmp_path, {**section, "mode": "isolated"}, "--session-workspace", "personal", "--json")
    assert json.loads(alone.stdout)["readable"] == []
    assert run(tmp_path, {"workspaces": {"acme": {}}}, "--session-workspace", "acme").returncode == 2  # no domain key


def test_the_session_workspace_comes_from_the_workspaces_folder(tmp_path):
    folder = tmp_path / "workspaces" / "personal" / "some-repo"
    folder.mkdir(parents=True)
    home = tmp_path / "home"
    home.mkdir()
    (home / "config.json").write_text(json.dumps({"slack_workspaces": MAP}))
    done = subprocess.run([sys.executable, str(SCRIPT)], capture_output=True, text=True, cwd=folder,
                          env={"SYNTHESIS_HOME": str(home), "PATH": "/usr/bin:/bin"})
    assert done.returncode == 0 and "session workspace: personal" in done.stdout


@pytest.mark.parametrize("section,argv,reason", [
    (None, ["--session-workspace", "acme"], "slack_workspaces section"),
    ({**MAP, "mode": "open"}, ["--session-workspace", "acme"], "unknown mode"),
    ({"workspaces": {"acme": {"domain": "acme.example.com"}}}, ["--session-workspace", "acme"], "slack.com"),
    (MAP, ["--session-workspace", "unknown"], "not in the map"),
])
def test_a_missing_or_malformed_map_or_unknown_workspace_exits_two(tmp_path, section, argv, reason):
    done = run(tmp_path, section, *argv)
    assert done.returncode == 2 and reason in done.stderr
