"""Hermetic tests for the one-command fleet sync."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))
PM_SCRIPTS = SCRIPTS_DIR.parents[2] / "skills" / "synthesis-project-management" / "scripts"
if str(PM_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(PM_SCRIPTS))

import fleet_sync
import fleet_identity as FI
import fleet_bootstrap
import synthesis_cli


MACHINE_ID = "11111111-2222-4333-8444-555555555555"


def _git(*args, cwd):
    out = subprocess.run(
        ["git", *args], cwd=str(cwd),
        capture_output=True, text=True, check=True,
    )
    return out.stdout.strip()


def _make_remote(path: Path, files: dict[str, str]) -> None:
    work = path.parent / (path.name + "-work")
    work.mkdir(parents=True)
    _git("init", "-b", "main", cwd=work)
    _git("config", "user.email", "t@t", cwd=work)
    _git("config", "user.name", "t", cwd=work)
    _git("config", "core.hooksPath", "/dev/null", cwd=work)
    for name, content in files.items():
        target = work / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    _git("add", ".", cwd=work)
    _git("commit", "-m", "seed", cwd=work)
    path.mkdir(parents=True)
    _git("init", "--bare", "-b", "main", cwd=path)
    _git("remote", "add", "origin", str(path), cwd=work)
    _git("push", "origin", "main", cwd=work)


def _commit_on_remote(remote: Path, name: str, content: str) -> None:
    work = remote.parent / (remote.name + "-work")
    assert work.is_dir()
    (work / name).write_text(content, encoding="utf-8")
    _git("add", ".", cwd=work)
    _git("commit", "-m", "advance", cwd=work)
    _git("push", "origin", "main", cwd=work)


@pytest.fixture
def enrolled_home(tmp_path: Path) -> Path:
    home = tmp_path / "home"
    fleet = home / ".synthesis" / "fleet"
    fleet.mkdir(parents=True)
    (fleet / "machine-id").write_text(MACHINE_ID + "\n", encoding="utf-8")
    registry = FI.empty_registry()
    registry["machines"]["11111111-1111-4111-8111-111111111111"] = {
        "label": "primary-test-mac",
        "enrolled_at": "2026-09-20T00:00:00+00:00",
        "last_seen": "2026-09-20T00:00:00+00:00",
        "role": "primary",
        "environments": ["default"],
        "retired_at": None,
    }
    registry["machines"][MACHINE_ID] = {
        "label": "test-mac",
        "enrolled_at": "2026-09-20T00:00:00+00:00",
        "last_seen": "2026-09-20T00:00:00+00:00",
        "role": "secondary",
        "environments": ["default"],
        "retired_at": None,
    }
    (fleet / "machines.json").write_text(
        json.dumps(registry), encoding="utf-8"
    )
    return home


@pytest.fixture
def kb_checkout(enrolled_home: Path, tmp_path: Path) -> Path:
    home = enrolled_home
    remote = tmp_path / "remotes" / "kb.git"
    _make_remote(remote, {"fleet/machines.json": json.dumps({
        "schema_version": 1,
        "machines": {
            "11111111-1111-4111-8111-111111111111": {
                "label": "primary-test-mac",
                "enrolled_at": "2026-09-20T00:00:00+00:00",
                "last_seen": "2026-09-20T00:00:00+00:00",
                "role": "primary",
                "environments": ["default"],
                "retired_at": None,
            },
            MACHINE_ID: {
                "label": "test-mac",
                "enrolled_at": "2026-09-20T00:00:00+00:00",
                "last_seen": "2026-09-20T00:00:00+00:00",
                "role": "secondary",
                "environments": ["default"],
                "retired_at": None,
            },
        },
    })})
    kb = home / "workspaces" / "work" / "ai-knowledge-kb"
    kb.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["git", "clone", str(remote), str(kb)],
        capture_output=True, text=True, check=True,
    )
    _git("config", "user.email", "t@t", cwd=kb)
    _git("config", "user.name", "t", cwd=kb)
    _git("config", "core.hooksPath", "/dev/null", cwd=kb)
    return kb


def _write_manifest(kb: Path, repos: list[dict]) -> None:
    (kb / "fleet").mkdir(parents=True, exist_ok=True)
    (kb / "fleet" / "repos.w.json").write_text(
        json.dumps({"schema_version": 1, "repos": repos}),
        encoding="utf-8",
    )


def _sync_args(**overrides):
    base = {"kb": None, "workspace": None, "json": False}
    base.update(overrides)
    return SimpleNamespace(**base)


def test_sync_full_run_current(enrolled_home, kb_checkout, tmp_path):
    home = enrolled_home
    remote = tmp_path / "remotes" / "notes.git"
    _make_remote(remote, {"note.md": "hi"})
    _write_manifest(kb_checkout, [{
        "remote": str(remote), "path": "~/workspaces/work/notes",
        "branch": "main",
    }])
    notes = home / "workspaces" / "work" / "notes"
    subprocess.run(
        ["git", "clone", str(remote), str(notes)],
        capture_output=True, text=True, check=True,
    )
    lines: list[str] = []
    code = fleet_sync.sync(
        _sync_args(), release_root=Path("/nonexistent"),
        home=home, bootstrap=fleet_bootstrap,
        run_update=lambda: 0, run_doctor=lambda: 0,
        run_repair=lambda: 0, progress=lines.append,
    )
    assert code == 0
    assert any("this Mac is current" in line for line in lines)
    assert any("notes: ok" in line for line in lines)


def test_sync_pulls_behind_repo(enrolled_home, kb_checkout, tmp_path):
    home = enrolled_home
    remote = tmp_path / "remotes" / "notes.git"
    _make_remote(remote, {"note.md": "hi"})
    notes = home / "workspaces" / "work" / "notes"
    notes.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["git", "clone", str(remote), str(notes)],
        capture_output=True, text=True, check=True,
    )
    _commit_on_remote(remote, "note2.md", "new")
    _write_manifest(kb_checkout, [{
        "remote": str(remote), "path": "~/workspaces/work/notes",
        "branch": "main",
    }])
    lines: list[str] = []
    code = fleet_sync.sync(
        _sync_args(), release_root=Path("/nonexistent"),
        home=home, bootstrap=fleet_bootstrap,
        run_update=lambda: 0, run_doctor=lambda: 0,
        run_repair=lambda: 0, progress=lines.append,
    )
    assert code == 0
    assert (notes / "note2.md").is_file()
    assert any("fast-forwarded" in line for line in lines)


def test_sync_skips_dirty_repo(enrolled_home, kb_checkout, tmp_path):
    home = enrolled_home
    remote = tmp_path / "remotes" / "notes.git"
    _make_remote(remote, {"note.md": "hi"})
    notes = home / "workspaces" / "work" / "notes"
    notes.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["git", "clone", str(remote), str(notes)],
        capture_output=True, text=True, check=True,
    )
    (notes / "draft.md").write_text("uncommitted", encoding="utf-8")
    _write_manifest(kb_checkout, [{
        "remote": str(remote), "path": "~/workspaces/work/notes",
        "branch": "main",
    }])
    lines: list[str] = []
    code = fleet_sync.sync(
        _sync_args(), release_root=Path("/nonexistent"),
        home=home, bootstrap=fleet_bootstrap,
        run_update=lambda: 0, run_doctor=lambda: 0,
        run_repair=lambda: 0, progress=lines.append,
    )
    assert code == 0
    assert (notes / "draft.md").is_file()
    assert any("dirty working tree" in line for line in lines)


def test_sync_clones_missing_repo(enrolled_home, kb_checkout, tmp_path):
    home = enrolled_home
    remote = tmp_path / "remotes" / "notes.git"
    _make_remote(remote, {"note.md": "hi"})
    _write_manifest(kb_checkout, [{
        "remote": str(remote), "path": "~/workspaces/work/notes",
        "branch": "main",
    }])
    lines: list[str] = []
    code = fleet_sync.sync(
        _sync_args(), release_root=Path("/nonexistent"),
        home=home, bootstrap=fleet_bootstrap,
        run_update=lambda: 0, run_doctor=lambda: 0,
        run_repair=lambda: 0, progress=lines.append,
    )
    assert code == 0
    assert (home / "workspaces" / "work" / "notes" / "note.md").is_file()


def test_sync_repairs_when_doctor_fails(enrolled_home, kb_checkout):
    calls: list[str] = []
    lines: list[str] = []
    code = fleet_sync.sync(
        _sync_args(), release_root=Path("/nonexistent"),
        home=enrolled_home, bootstrap=fleet_bootstrap,
        run_update=lambda: 0,
        run_doctor=lambda: calls.append("doctor") or 1,
        run_repair=lambda: calls.append("repair") or 0,
        progress=lines.append,
    )
    assert code == 0
    assert calls == ["doctor", "repair"]
    assert any("repair: done" in line for line in lines)


def test_sync_reports_update_failure(enrolled_home, kb_checkout):
    lines: list[str] = []
    code = fleet_sync.sync(
        _sync_args(), release_root=Path("/nonexistent"),
        home=enrolled_home, bootstrap=fleet_bootstrap,
        run_update=lambda: 3, run_doctor=lambda: 0,
        run_repair=lambda: 0, progress=lines.append,
    )
    assert code == 1
    assert any("update" in line and "problem" in line for line in lines)


def test_sync_refuses_unenrolled(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    with pytest.raises(fleet_sync.FleetSyncError, match="not enrolled"):
        fleet_sync.sync(
            _sync_args(), release_root=Path("/nonexistent"),
            home=home, bootstrap=fleet_bootstrap,
            run_update=lambda: 0, run_doctor=lambda: 0,
            run_repair=lambda: 0,
        )


def test_discover_kb_checkout_ambiguous(enrolled_home, tmp_path):
    home = enrolled_home
    doc = {"schema_version": 1, "machines": {MACHINE_ID: {"label": "x"}}}
    for kb_name in ("ai-knowledge-a", "ai-knowledge-b"):
        kb = home / "workspaces" / "work" / kb_name
        (kb / "fleet").mkdir(parents=True)
        (kb / "fleet" / "machines.json").write_text(
            json.dumps(doc), encoding="utf-8"
        )
    with pytest.raises(fleet_sync.FleetSyncError, match="--kb"):
        fleet_sync.discover_kb_checkout(home, MACHINE_ID)


def test_cli_registers_sync():
    assert "sync" in synthesis_cli.CLI_COMMANDS
    parser = synthesis_cli.build_parser()
    parsed = parser.parse_args(["sync", "--workspace", "w"])
    assert parsed.command == "sync"
    assert parsed.workspace == "w"
