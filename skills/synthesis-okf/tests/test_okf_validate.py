"""okf_validate.py: OKF v0.1 conformance (E92). Every non-reserved file needs frontmatter
with a non-empty `type`; broken links are reported only with --check-links, as info."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

pytest.importorskip("yaml")

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "okf_validate.py"


def _bundle(tmp_path: Path, files: dict) -> Path:
    root = tmp_path / "bundle"
    for rel, text in files.items():
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_text(text, encoding="utf-8")
    return root


def _run(*args):
    return subprocess.run([sys.executable, str(SCRIPT), *map(str, args)], capture_output=True, text=True, timeout=30)


CONCEPT = "---\ntype: Reference\ntitle: A\ndescription: d\ntimestamp: 2026-07-29\n---\n# A\n\nSee [missing](nowhere.md).\n"


def test_conformant_bundle_passes_and_broken_links_are_silent_by_default(tmp_path):
    root = _bundle(tmp_path, {"index.md": "# Bundle\n", "a.md": CONCEPT})
    result = _run(root)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "nowhere.md" not in result.stdout


def test_broken_links_are_info_under_check_links_never_errors(tmp_path):
    root = _bundle(tmp_path, {"index.md": "# Bundle\n", "a.md": CONCEPT})
    result = _run(root, "--check-links")
    assert result.returncode == 0
    assert "info" in result.stdout and "nowhere.md" in result.stdout


@pytest.mark.parametrize("text", ["# No frontmatter\n", "---\ntitle: A\n---\n# A\n", "---\ntype: ''\n---\n# A\n"])
def test_missing_frontmatter_or_type_is_an_error(tmp_path, text):
    root = _bundle(tmp_path, {"index.md": "# Bundle\n", "nested/b.md": text})
    result = _run(root)
    assert result.returncode == 1 and "ERROR" in result.stdout


def test_reserved_files_need_no_frontmatter_and_a_missing_bundle_is_a_usage_error(tmp_path):
    root = _bundle(tmp_path, {"index.md": "# Bundle\n", "log.md": "# Log\n"})
    assert _run(root).returncode == 0
    assert _run(tmp_path / "missing").returncode == 2
