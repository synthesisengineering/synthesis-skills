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


def test_disclosure_patterns_apply_only_where_outsiders_read(repo, tmp_path, write_config):
    policy = tmp_path / "policy.yaml"
    policy.write_text("config_version: 2\npersonal_remote_patterns:\n  - '[:/]example-person/'\n"
                      "tier_0_always:\n  keys:\n    - 'sk-ant-api[a-z0-9-]+'\n"
                      "tier_1_strict_only:\n  confidential_names:\n    - '\\bBluebird\\b'\n", encoding="utf-8")
    write_config({"commit_policy": str(policy)})
    subprocess.run(["git", "-C", str(repo), "remote", "add", "origin", "git@github.com:example-person/notes.git"], check=True)
    assert _commit(repo, "a.md", "Bluebird launch\n").returncode == 0
    subprocess.run(["git", "-C", str(repo), "remote", "set-url", "origin", "https://github.com/public-org/site.git"], check=True)
    result = _commit(repo, "b.md", "Bluebird again\n")
    assert result.returncode != 0 and "unapproved disclosure" in result.stderr


def test_no_board_on_the_machine_advises_and_an_unreadable_board_blocks(repo, isolated_home):
    result = _commit(repo, "a.md", "x\n")
    assert result.returncode == 0 and "claims were not checked" in result.stderr
    sessions = isolated_home / "state" / "sessions"
    sessions.mkdir(parents=True)
    (sessions / "broken.json").write_text("{not json", encoding="utf-8")
    result = _commit(repo, "b.md", "x\n")
    assert result.returncode != 0 and "coordination board can't be read" in result.stderr


def test_a_rename_out_of_another_sessions_claim_is_refused(repo):
    assert _commit(repo, "projects/alpha/notes.md", "x\n").returncode == 0
    board.claim("OTHER", [f"{repo}/projects/alpha/**"], project="alpha", goal="drafting")
    subprocess.run(["git", "-C", str(repo), "mv", "projects/alpha/notes.md", "elsewhere.md"], check=True)
    env = {**os.environ, "SYNTHESIS_SESSION": "ME"}
    result = subprocess.run(["git", "-C", str(repo), "commit", "-qm", "move"], capture_output=True, text=True, env=env)
    assert result.returncode != 0 and "projects/alpha/notes.md: inside a claim held by OTHER" in result.stderr


def test_a_committer_with_no_session_identity_is_told_how_to_identify(repo):
    board.claim("OTHER", [f"{repo}/projects/alpha/**"], project="alpha", goal="drafting")
    result = _commit(repo, "projects/alpha/a.md", "x\n")
    assert result.returncode != 0 and "SYNTHESIS_SESSION=<your session id>" in result.stderr
    subprocess.run(["git", "-C", str(repo), "reset", "-q"], check=True)
    assert _commit(repo, "projects/beta/a.md", "x\n").returncode == 0  # unclaimed paths need no identity


def test_an_unreadable_config_blocks_the_commit(repo, isolated_home):
    isolated_home.mkdir(parents=True, exist_ok=True)
    (isolated_home / "config.json").write_text("{broken", encoding="utf-8")
    result = _commit(repo, "a.md", "x\n")
    assert result.returncode != 0 and "commit blocked" in result.stderr


def test_a_rename_into_another_sessions_claim_is_refused(repo):
    assert _commit(repo, "notes.md", "x\n").returncode == 0
    board.claim("OTHER", [f"{repo}/projects/alpha/**"], project="alpha", goal="drafting")
    (repo / "projects" / "alpha").mkdir(parents=True)
    subprocess.run(["git", "-C", str(repo), "mv", "notes.md", "projects/alpha/notes.md"], check=True)
    env = {**os.environ, "SYNTHESIS_SESSION": "ME"}
    result = subprocess.run(["git", "-C", str(repo), "commit", "-qm", "move"], capture_output=True, text=True, env=env)
    assert result.returncode != 0 and "projects/alpha/notes.md: inside a claim held by OTHER" in result.stderr


def test_a_deletion_inside_another_sessions_claim_is_refused(repo):
    assert _commit(repo, "projects/alpha/old.md", "x\n").returncode == 0
    board.claim("OTHER", [f"{repo}/projects/alpha/**"], project="alpha", goal="drafting")
    subprocess.run(["git", "-C", str(repo), "rm", "-q", "projects/alpha/old.md"], check=True)
    env = {**os.environ, "SYNTHESIS_SESSION": "ME"}
    result = subprocess.run(["git", "-C", str(repo), "commit", "-qm", "delete"], capture_output=True, text=True, env=env)
    assert result.returncode != 0 and "projects/alpha/old.md: inside a claim held by OTHER" in result.stderr
