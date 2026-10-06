"""okf_convert.py: backfill never overwrites, --dry-run writes nothing, and the result validates."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

yaml = pytest.importorskip("yaml")

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"


def _bundle(tmp_path: Path) -> Path:
    root = tmp_path / "source"
    (root / "runbooks").mkdir(parents=True)
    (root / "runbooks" / "deploy.md").write_text("# Deploy\n\nHow the site ships.\n", encoding="utf-8")
    (root / "runbooks" / "kept.md").write_text("---\ntitle: Hand title\ntype: Playbook\n---\n# Other\n\nBody.\n",
                                                 encoding="utf-8")
    (root / "README.md").write_text("# Knowledge\n\nWhat this bundle holds.\n", encoding="utf-8")
    return root


def _convert(root: Path, *extra):
    return subprocess.run([sys.executable, str(SCRIPTS / "okf_convert.py"), str(root),
                           "--type-map", "runbooks=Runbook", *extra], capture_output=True, text=True, timeout=60)


def _snapshot(root: Path) -> dict:
    return {p.relative_to(root): p.read_bytes() for p in sorted(root.rglob("*")) if p.is_file()}


def test_dry_run_changes_nothing(tmp_path):
    root = _bundle(tmp_path)
    before = _snapshot(root)
    result = _convert(root, "--dry-run")
    assert result.returncode == 0, result.stderr
    assert _snapshot(root) == before


def test_backfills_without_overwriting_and_the_bundle_validates(tmp_path):
    root = _bundle(tmp_path)
    result = _convert(root)
    assert result.returncode == 0, result.stderr
    deploy = (root / "runbooks" / "deploy.md").read_text(encoding="utf-8")
    meta = yaml.safe_load(deploy.split("---")[1])
    assert meta["type"] == "Runbook" and meta["title"] == "Deploy"
    kept = yaml.safe_load((root / "runbooks" / "kept.md").read_text(encoding="utf-8").split("---")[1])
    assert kept["title"] == "Hand title" and kept["type"] == "Playbook"  # existing fields never overwritten
    assert (root / "index.md").is_file() and not (root / "README.md").exists()
    check = subprocess.run([sys.executable, str(SCRIPTS / "okf_validate.py"), str(root)],
                           capture_output=True, text=True, timeout=60)
    assert check.returncode == 0, check.stdout
