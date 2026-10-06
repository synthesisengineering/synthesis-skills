"""Tests for resume_probe.py — machine-readable resume status."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from resume_probe import probe  # noqa: E402

INDEX_YAML = """\
projects:
  - id: demo-project
    name: Demo Project
    status: active
    description: Prove the resume probe works.
    last_session: 2026-09-19
  - id: no-dir-project
    name: No Dir
    status: paused
    description: Index entry without a directory.
"""


@pytest.fixture()
def source_root(tmp_path: Path) -> Path:
    projects = tmp_path / "projects"
    projects.mkdir()
    (projects / "index.yaml").write_text(INDEX_YAML, encoding="utf-8")
    demo = projects / "demo-project"
    (demo / "sessions").mkdir(parents=True)
    (demo / "CONTEXT.md").write_text("# context\n", encoding="utf-8")
    (demo / "REFERENCE.md").write_text("# reference\n", encoding="utf-8")
    (demo / "sessions" / "2026-08.md").write_text("# august\n", encoding="utf-8")
    (demo / "sessions" / "2026-09.md").write_text("# september\n", encoding="utf-8")
    return tmp_path


def test_probe_reports_identity_and_goal(source_root: Path) -> None:
    doc = probe(source_root, "demo-project")
    assert doc["id"] == "demo-project"
    assert doc["name"] == "Demo Project"
    assert doc["goal"] == "Prove the resume probe works."
    assert doc["status"] == "active"


def test_probe_reports_newest_session(source_root: Path) -> None:
    doc = probe(source_root, "demo-project")
    assert doc["newest_session"] == "2026-09"
    assert doc["session_mtime"] is not None


def test_probe_ignores_generated_index(source_root: Path) -> None:
    index = source_root / "projects" / "demo-project" / "sessions" / "INDEX.md"
    index.write_text("# index\n", encoding="utf-8")
    doc = probe(source_root, "demo-project")
    assert doc["newest_session"] == "2026-09"


def test_probe_reports_a_project_without_a_directory(source_root: Path) -> None:
    doc = probe(source_root, "no-dir-project")
    assert doc["newest_session"] is None
    assert "format_version" not in doc  # v5 has one plain-markdown format


def test_index_folded_descriptions_nested_lists_and_bare_lists_parse_without_yaml(tmp_path: Path) -> None:
    projects = tmp_path / "projects"
    projects.mkdir()
    (projects / "index.yaml").write_text(
        "# comment\ninitiatives:\n- id: not-a-project\nprojects:\n- id: folded\n  status: active\n"
        "  tags:\n    - nested\n  description: >\n    Two lines\n    folded into one.\n  last_session: '2026-10-01'\n"
        "- id: second\n  name: \"Second # not a comment\"\n",
        encoding="utf-8",
    )
    doc = probe(tmp_path, "folded")
    assert doc["goal"] == "Two lines folded into one." and doc["updated"] == "2026-10-01"
    assert probe(tmp_path, "second")["name"] == "Second # not a comment"
    with pytest.raises(LookupError):
        probe(tmp_path, "not-a-project")
    (projects / "index.yaml").write_text("- id: bare\n  status: paused\n", encoding="utf-8")
    assert probe(tmp_path, "bare")["status"] == "paused"


def test_unknown_project_raises_lookup(source_root: Path) -> None:
    with pytest.raises(LookupError):
        probe(source_root, "nope")


def test_missing_index_raises_oserror(tmp_path: Path) -> None:
    with pytest.raises(OSError):
        probe(tmp_path, "demo-project")


def test_git_changes_reported_when_repo(tmp_path: Path, source_root: Path) -> None:
    del tmp_path
    git = ["git", "-c", "core.hooksPath=/dev/null"]
    subprocess.run([*git, "init", "-q"], cwd=source_root, check=True)
    subprocess.run([*git, "add", "."], cwd=source_root, check=True)
    subprocess.run(
        [*git, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "seed"],
        cwd=source_root,
        check=True,
    )
    doc = probe(source_root, "demo-project")
    assert len(doc["recent_changes"]) == 1
    assert doc["recent_changes"][0]["subject"] == "seed"


def test_non_repo_degrades_to_empty_changes(source_root: Path) -> None:
    assert probe(source_root, "demo-project")["recent_changes"] == []


def test_cli_exit_codes(source_root: Path) -> None:
    script = Path(__file__).resolve().parents[1] / "scripts" / "resume_probe.py"
    ok = subprocess.run(
        [sys.executable, str(script), str(source_root), "demo-project"],
        capture_output=True,
        text=True,
    )
    assert ok.returncode == 0, ok.stderr
    assert json.loads(ok.stdout)["id"] == "demo-project"
    unknown = subprocess.run(
        [sys.executable, str(script), str(source_root), "nope"],
        capture_output=True,
        text=True,
    )
    assert unknown.returncode == 3
