"""Tests for prep_init.py — meeting-prep configuration scaffolding."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from prep_init import add_reader, init_principal  # noqa: E402


def context(tmp_path):
    root = tmp_path / "private-context"
    root.mkdir()
    subprocess.run(["git", "init", "-q", str(root)], check=True, timeout=10)
    return root


def test_init_creates_principal_and_template(tmp_path: Path) -> None:
    root = context(tmp_path)
    result = init_principal(root, "Ada", "CTO", "Acme", ["ship v2"], workspace="synthetic")
    principal = json.loads(Path(result["principal"]).read_text(encoding="utf-8"))
    assert principal["name"] == "Ada"
    assert principal["role"] == "CTO"
    assert principal["goals_professional"] == ["ship v2"]
    assert "authority" in principal
    assert Path(result["template"]).read_text(encoding="utf-8").startswith("# ")


def test_init_refuses_overwrite(tmp_path: Path) -> None:
    root = context(tmp_path)
    init_principal(root, "Ada", "CTO", "Acme", [], workspace="synthetic")
    with pytest.raises(FileExistsError):
        init_principal(root, "Bob", "CFO", "Acme", [], workspace="synthetic")
    principal = json.loads((root / "profiles/meeting-prep/principal.json").read_text(encoding="utf-8"))
    assert principal["name"] == "Ada"


def test_add_reader_writes_profile(tmp_path: Path) -> None:
    root = context(tmp_path)
    result = add_reader(root, "rivera", "Dana Rivera", "peer", workspace="synthetic")
    body = Path(result["reader"]).read_text(encoding="utf-8")
    assert body.startswith("# Dana Rivera")
    assert "relationship: peer" in body


def test_add_reader_rejects_bad_relationship(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="relationship must be"):
        add_reader(tmp_path / "prep", "x", "X", "nemesis", workspace="synthetic")


def test_add_reader_rejects_bad_id(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="alphanumeric"):
        add_reader(tmp_path / "prep", "../evil", "X", "peer", workspace="synthetic")


def test_add_reader_refuses_overwrite(tmp_path: Path) -> None:
    root = context(tmp_path)
    add_reader(root, "rivera", "Dana Rivera", "peer", workspace="synthetic")
    with pytest.raises(FileExistsError):
        add_reader(root, "rivera", "Someone Else", "boss", workspace="synthetic")


def test_cli_init_end_to_end(tmp_path: Path) -> None:
    script = Path(__file__).resolve().parent / "prep_init.py"
    root = context(tmp_path)
    first = subprocess.run(
        [sys.executable, str(script), "init", "--name", "Ada",
         "--role", "CTO", "--org", "Acme", "--goals", "a;b",
         "--context-repo", str(root), "--workspace", "synthetic"],
        capture_output=True, text=True,
    )
    assert first.returncode == 0, first.stderr
    assert (root / "profiles/meeting-prep/principal.json").is_file()
    second = subprocess.run(
        [sys.executable, str(script), "init", "--name", "Ada",
         "--role", "CTO", "--org", "Acme", "--context-repo", str(root), "--workspace", "synthetic"],
        capture_output=True, text=True,
    )
    assert second.returncode == 2
