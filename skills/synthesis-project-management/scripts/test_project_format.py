"""Tests for project_format.py — versioned project formats."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))

from project_format import detect, migrate, validate_state  # noqa: E402


@pytest.fixture()
def v1_project(tmp_path: Path) -> Path:
    project = tmp_path / "demo"
    sessions = project / "sessions"
    sessions.mkdir(parents=True)
    (project / "CONTEXT.md").write_text("# context\n", encoding="utf-8")
    (project / "REFERENCE.md").write_text("# reference\n", encoding="utf-8")
    (sessions / "2026-08.md").write_text(
        "## 2026-08-10 session\n\nDid things.\n", encoding="utf-8"
    )
    (sessions / "2026-09.md").write_text(
        "## 2026-09-19 session\n\nTODO: ship the thing\n", encoding="utf-8"
    )
    return project


def test_detect_v1(v1_project: Path) -> None:
    assert detect(v1_project) == "v1"


def test_detect_missing(tmp_path: Path) -> None:
    assert detect(tmp_path / "nope") == "missing"


def test_detect_partial(tmp_path: Path) -> None:
    project = tmp_path / "demo"
    project.mkdir()
    (project / "CONTEXT.md").write_text("# c\n", encoding="utf-8")
    assert detect(project) == "partial"


def test_detect_unknown_version(v1_project: Path) -> None:
    (v1_project / ".synthesis-project.yaml").write_text(
        "format_version: 99\n", encoding="utf-8"
    )
    assert detect(v1_project) == "unknown"


def test_migrate_check_writes_nothing(v1_project: Path) -> None:
    report = migrate(v1_project)
    assert report["from"] == 1 and report["to"] == 2
    assert not report["verified"]
    assert not (v1_project / ".synthesis-project.yaml").exists()
    assert not (v1_project / "CURRENT_STATE.json").exists()


def test_migrate_apply_adds_and_verifies(v1_project: Path) -> None:
    report = migrate(v1_project, goal="Prove v2.", status="active", apply=True)
    assert report["verified"] is True
    assert report["added"] == [
        ".synthesis-project.yaml",
        "CURRENT_STATE.json",
        "sessions/INDEX.md",
    ]
    assert detect(v1_project) == "v2"
    marker = yaml.safe_load(
        (v1_project / ".synthesis-project.yaml").read_text(encoding="utf-8")
    )
    assert marker["format_version"] == 2
    assert marker["migrated_from"] == 1
    state = json.loads((v1_project / "CURRENT_STATE.json").read_text(encoding="utf-8"))
    assert state["goal"] == "Prove v2."
    assert state["status"] == "active"
    assert state["skeleton"] is True
    assert state["last_session"] == "2026-09"
    assert len(state["open_loops"]) == 1
    assert state["open_loops"][0]["unverified"] is True
    index = (v1_project / "sessions" / "INDEX.md").read_text(encoding="utf-8")
    assert "2026-09-19 session" in index


def test_migrate_leaves_existing_bytes_untouched(v1_project: Path) -> None:
    before = {
        name: (v1_project / name).read_bytes()
        for name in ("CONTEXT.md", "REFERENCE.md")
    }
    migrate(v1_project, apply=True)
    for name, content in before.items():
        assert (v1_project / name).read_bytes() == content


def test_migrate_keeps_existing_valid_state(v1_project: Path) -> None:
    kept = {
        "schema": 1, "goal": "hand-written", "status": "active",
        "open_loops": [], "last_session": None,
    }
    state_path = v1_project / "CURRENT_STATE.json"
    state_path.write_text(json.dumps(kept), encoding="utf-8")
    report = migrate(v1_project, apply=True)
    assert report["verified"] is True
    assert report["kept"] == ["CURRENT_STATE.json"]
    assert json.loads(state_path.read_text(encoding="utf-8")) == kept


def test_migrate_fails_closed_on_invalid_kept_state(v1_project: Path) -> None:
    state_path = v1_project / "CURRENT_STATE.json"
    state_path.write_text('{"schema": 99}', encoding="utf-8")
    report = migrate(v1_project, apply=True)
    assert report["verified"] is False
    assert report["errors"]
    # The invalid file is preserved untouched for a human to fix.
    assert state_path.read_text(encoding="utf-8") == '{"schema": 99}'
    # The failed migration rolls the version claim back to v1.
    assert detect(v1_project) == "v1"


def test_migrate_is_idempotent(v1_project: Path) -> None:
    migrate(v1_project, apply=True)
    report = migrate(v1_project, apply=True)
    assert report["noop"] is True and report["verified"] is True


def test_migrate_refuses_non_v1(tmp_path: Path) -> None:
    project = tmp_path / "demo"
    project.mkdir()
    with pytest.raises(ValueError):
        migrate(project, apply=True)
    with pytest.raises(FileNotFoundError):
        migrate(tmp_path / "nope", apply=True)


def test_validate_state_accepts_skeleton(v1_project: Path) -> None:
    migrate(v1_project, apply=True)
    state = json.loads((v1_project / "CURRENT_STATE.json").read_text(encoding="utf-8"))
    assert validate_state(state) == []


def test_validate_state_rejects_garbage() -> None:
    assert validate_state([]) != []
    assert validate_state({}) != []
    assert validate_state({"schema": 1, "goal": 1, "status": "x"}) != []


def test_cli_detect_and_migrate(v1_project: Path) -> None:
    script = Path(__file__).resolve().parent / "project_format.py"
    out = subprocess.run(
        [sys.executable, str(script), "detect", str(v1_project)],
        capture_output=True, text=True, check=True,
    )
    assert json.loads(out.stdout)["format"] == "v1"
    check = subprocess.run(
        [sys.executable, str(script), "migrate", "--check", str(v1_project)],
        capture_output=True, text=True, check=True,
    )
    assert json.loads(check.stdout)["verified"] is False
    apply = subprocess.run(
        [sys.executable, str(script), "migrate", "--goal", "g", str(v1_project)],
        capture_output=True, text=True, check=True,
    )
    assert json.loads(apply.stdout)["verified"] is True
    assert detect(v1_project) == "v2"
