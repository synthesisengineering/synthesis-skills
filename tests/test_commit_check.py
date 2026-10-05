"""R2.1 and R3.3: the commit check refuses secrets, disclosures and other sessions' files."""

import os
import subprocess
import sys
from pathlib import Path

import pytest

from synthesis import board

CHECK = Path(__file__).resolve().parents[1] / "synthesis" / "commit_check.py"
FAKE_AWS = "AKIA" + "ABCDEFGHIJKLMNOP"  # split so this file never trips the scanner itself


@pytest.fixture
def repo(tmp_path):
    root = tmp_path / "repo"
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    hooks = root / ".git" / "hooks"
    hooks.mkdir(exist_ok=True)
    hook = hooks / "pre-commit"
    hook.write_text(f"#!/bin/sh\nexec {sys.executable} -S {CHECK}\n")
    hook.chmod(0o755)
    return root


def _commit(repo, name, text, env_extra=None):
    (repo / name).parent.mkdir(parents=True, exist_ok=True)
    (repo / name).write_text(text)
    subprocess.run(["git", "-C", str(repo), "add", name], check=True)
    env = {**os.environ, **(env_extra or {})}
    return subprocess.run(["git", "-C", str(repo), "commit", "-qm", "test"], capture_output=True, text=True, env=env)


def test_credentials_are_refused(repo):
    result = _commit(repo, "config.txt", f"key = {FAKE_AWS}\n")
    assert result.returncode != 0 and "AWS access key" in result.stderr


def test_ordinary_commit_passes(repo):
    assert _commit(repo, "notes.md", "nothing secret here\n").returncode == 0


def test_file_inside_another_sessions_claim_is_refused(repo):
    board.claim("OTHER", [f"{repo}/projects/alpha/**"], project="alpha", goal="drafting")
    result = _commit(repo, "projects/alpha/CONTEXT.md", "x\n", {"SYNTHESIS_SESSION": "ME"})
    assert result.returncode != 0 and "held by OTHER" in result.stderr
    subprocess.run(["git", "-C", str(repo), "reset", "-q"], check=True)
    board.claim("ME", [f"{repo}/projects/beta/**"])
    assert _commit(repo, "projects/beta/CONTEXT.md", "x\n", {"SYNTHESIS_SESSION": "ME"}).returncode == 0


def test_own_claim_does_not_block_own_commit(repo):
    board.claim("ME", [f"{repo}/projects/alpha/**"])
    assert _commit(repo, "projects/alpha/a.md", "x\n", {"SYNTHESIS_SESSION": "ME"}).returncode == 0


def test_disclosure_patterns_apply_only_to_strict_remotes(repo, write_config):
    write_config({"disclosure": {"strict_remotes": ["github.com/public-org/"],
                                 "patterns": [{"name": "client codename", "pattern": r"\bBluebird\b"}]}})
    assert _commit(repo, "a.md", "Bluebird launch\n").returncode == 0
    subprocess.run(["git", "-C", str(repo), "remote", "add", "origin", "https://github.com/public-org/site.git"], check=True)
    result = _commit(repo, "b.md", "Bluebird again\n")
    assert result.returncode != 0 and "client codename" in result.stderr
