"""Ritual workers registry: validation, statuses, and ~-expansion."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import ritual_workers as RW

HOME = str(Path.home())


def write_registry(path: Path, body: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")
    return path


def test_tilde_artifact_dir_expands_to_home(tmp_path):
    path = write_registry(
        tmp_path / "workers.yaml",
        "contract_version: 1\ndesk_seat: home\nworkers:\n"
        "  work:\n    status: active\n"
        '    artifact_dir: "~/workspaces/work/ritual-workers"\n'
        "    seat: work\n",
    )
    worker = RW.load_workers(path)["work"]
    assert worker.artifact_dir == f"{HOME}/workspaces/work/ritual-workers"
    assert worker.artifact_dir_raw == "~/workspaces/work/ritual-workers"
    assert worker.artifact_path("brief.md") == Path(
        f"{HOME}/workspaces/work/ritual-workers/brief.md"
    )


def test_dollar_home_artifact_dir_expands(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    path = write_registry(
        tmp_path / "workers.yaml",
        "contract_version: 1\ndesk_seat: home\nworkers:\n"
        "  work:\n    status: active\n"
        '    artifact_dir: "$HOME/workspaces/work/ritual-workers"\n'
        "    seat: work\n",
    )
    worker = RW.load_workers(path)["work"]
    assert worker.artifact_dir == str(tmp_path / "workspaces/work/ritual-workers")


def test_absolute_artifact_dir_keeps_loading(tmp_path):
    path = write_registry(
        tmp_path / "workers.yaml",
        "contract_version: 1\ndesk_seat: home\nworkers:\n"
        "  work:\n    status: active\n"
        f'    artifact_dir: "{tmp_path}/ritual-workers"\n'
        "    seat: work\n",
    )
    assert RW.load_workers(path)["work"].artifact_dir == str(
        tmp_path / "ritual-workers"
    )


def test_missing_registry_means_no_workers(tmp_path):
    assert RW.load_workers(tmp_path / "no-such.yaml") == {}


def test_statuses_filter_correctly(tmp_path):
    path = write_registry(
        tmp_path / "workers.yaml",
        "contract_version: 1\ndesk_seat: home\nworkers:\n"
        "  a:\n    status: active\n    artifact_dir: /tmp/a\n    seat: a\n"
        "  b:\n    status: on-demand\n    artifact_dir: /tmp/b\n    seat: b\n"
        "  c:\n    status: dormant\n    artifact_dir: /tmp/c\n    seat: c\n",
    )
    workers = RW.load_workers(path)
    assert set(RW.active_workers(workers)) == {"a"}
    assert set(workers) == {"a", "b", "c"}


@pytest.mark.parametrize(
    "body",
    [
        "contract_version: 2\nworkers: {}\n",
        "contract_version: 1\nworkers: []\n",
        "contract_version: 1\nworkers:\n  a:\n    status: sometimes\n    artifact_dir: /tmp/a\n    seat: a\n",
        "contract_version: 1\nworkers:\n  a:\n    status: active\n    artifact_dir: relative/path\n    seat: a\n",
        "contract_version: 1\nworkers:\n  a:\n    status: active\n    artifact_dir: /tmp/a\n",
        "- just\n- a\n- list\n",
        "contract_version: [unclosed\n",
    ],
)
def test_malformed_registry_fails_closed(tmp_path, body):
    path = write_registry(tmp_path / "workers.yaml", body)
    with pytest.raises(RW.RitualWorkersError):
        RW.load_workers(path)
