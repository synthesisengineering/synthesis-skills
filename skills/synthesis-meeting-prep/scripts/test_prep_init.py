"""Tests for prep_init.py — meeting-prep configuration scaffolding."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from prep_init import add_reader, init_principal  # noqa: E402


def test_init_creates_principal_and_template(tmp_path: Path) -> None:
    root = tmp_path / "prep"
    result = init_principal(root, "Ada", "CTO", "Acme", ["ship v2"])
    principal = json.loads(Path(result["principal"]).read_text(encoding="utf-8"))
    assert principal["name"] == "Ada"
    assert principal["role"] == "CTO"
    assert principal["goals_professional"] == ["ship v2"]
    assert "authority" in principal
    assert Path(result["template"]).read_text(encoding="utf-8").startswith("# ")


def test_init_refuses_overwrite(tmp_path: Path) -> None:
    root = tmp_path / "prep"
    init_principal(root, "Ada", "CTO", "Acme", [])
    with pytest.raises(FileExistsError):
        init_principal(root, "Bob", "CFO", "Acme", [], force=False)
    init_principal(root, "Bob", "CFO", "Acme", [], force=True)
    principal = json.loads((root / "principal.json").read_text(encoding="utf-8"))
    assert principal["name"] == "Bob"


def test_add_reader_writes_profile(tmp_path: Path) -> None:
    root = tmp_path / "prep"
    result = add_reader(root, "rivera", "Dana Rivera", "peer")
    body = Path(result["reader"]).read_text(encoding="utf-8")
    assert body.startswith("# Dana Rivera")
    assert "relationship: peer" in body


def test_add_reader_rejects_bad_relationship(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="relationship must be"):
        add_reader(tmp_path / "prep", "x", "X", "nemesis")


def test_add_reader_rejects_bad_id(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="alphanumeric"):
        add_reader(tmp_path / "prep", "../evil", "X", "peer")


def test_add_reader_refuses_overwrite(tmp_path: Path) -> None:
    root = tmp_path / "prep"
    add_reader(root, "rivera", "Dana Rivera", "peer")
    with pytest.raises(FileExistsError):
        add_reader(root, "rivera", "Someone Else", "boss")


def test_cli_init_end_to_end(tmp_path: Path) -> None:
    script = Path(__file__).resolve().parent / "prep_init.py"
    root = tmp_path / "prep"
    first = subprocess.run(
        [sys.executable, str(script), "init", "--name", "Ada",
         "--role", "CTO", "--org", "Acme", "--goals", "a;b",
         "--dir", str(root)],
        capture_output=True, text=True,
    )
    assert first.returncode == 0, first.stderr
    assert (root / "principal.json").is_file()
    second = subprocess.run(
        [sys.executable, str(script), "init", "--name", "Ada",
         "--role", "CTO", "--org", "Acme", "--dir", str(root)],
        capture_output=True, text=True,
    )
    assert second.returncode == 2
