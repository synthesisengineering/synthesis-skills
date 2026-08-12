"""Tests for resolve_scope.py — the workspace-scope contract.

Subprocess-level, so exit codes (0 resolved / 1 config defects / 2 unverifiable)
are pinned as the contract rituals depend on. The dangerous failure this guards:
a typo'd workspace resolving to zero accounts and reading as a clean sweep.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

RESOLVER = Path(__file__).parent.parent / "scripts" / "resolve_scope.py"

CONFIG = {
    "version": 1,
    "all_scope_workspaces": ["personal"],
    "accounts": [
        {"address": "me@example.com", "workspace": "personal", "stack": "icloud-imap"},
        {"address": "me@work-a.example.com", "workspace": "acme", "stack": "gmail"},
        {"address": "me@work-a2.example.com", "workspace": "acme", "stack": "gmail"},
        {"address": "me@advisory.example.com", "workspace": "advisory", "stack": "m365-applescript"},
    ],
}


def run(config: dict | None, *args: str, config_path: Path | None = None):
    cmd = [sys.executable, str(RESOLVER), *args]
    if config_path is not None:
        cmd += ["--config", str(config_path)]
    return subprocess.run(cmd, capture_output=True, text=True, timeout=30)


@pytest.fixture()
def config_file(tmp_path: Path) -> Path:
    p = tmp_path / "scopes.yaml"
    p.write_text(yaml.safe_dump(CONFIG))
    return p


def test_workspace_scope_selects_only_its_accounts(config_file):
    r = run(CONFIG, "--workspace", "acme", "--json", config_path=config_file)
    assert r.returncode == 0, r.stderr
    out = json.loads(r.stdout)
    assert {a["address"] for a in out["accounts"]} == {
        "me@work-a.example.com", "me@work-a2.example.com"
    }
    assert out["scope"] == "workspace"


def test_all_scope_workspace_gets_everything(config_file):
    r = run(CONFIG, "--workspace", "personal", "--json", config_path=config_file)
    assert r.returncode == 0
    out = json.loads(r.stdout)
    assert len(out["accounts"]) == 4
    assert out["scope"] == "all"


def test_explicit_all_overrides_workspace_scope(config_file):
    r = run(CONFIG, "--workspace", "acme", "--all", "--json", config_path=config_file)
    assert r.returncode == 0
    assert len(json.loads(r.stdout)["accounts"]) == 4


def test_unknown_workspace_is_unverifiable_not_empty(config_file):
    """The load-bearing test: a typo must never look like a clean sweep."""
    r = run(CONFIG, "--workspace", "acmee", config_path=config_file)
    assert r.returncode == 2
    assert "UNVERIFIED" in r.stderr
    assert "acmee" in r.stderr


def test_missing_config_exits_2(tmp_path):
    r = run(None, "--workspace", "acme", config_path=tmp_path / "absent.yaml")
    assert r.returncode == 2
    assert "UNVERIFIED" in r.stderr


def test_malformed_account_is_a_defect(tmp_path):
    bad = {"version": 1, "accounts": [{"address": "x@example.com"}]}  # no workspace
    p = tmp_path / "scopes.yaml"
    p.write_text(yaml.safe_dump(bad))
    r = run(bad, "--workspace", "acme", config_path=p)
    assert r.returncode == 1
    assert "DEFECT" in r.stderr


def test_empty_accounts_is_a_defect(tmp_path):
    p = tmp_path / "scopes.yaml"
    p.write_text(yaml.safe_dump({"version": 1, "accounts": []}))
    r = run(None, "--workspace", "personal", config_path=p)
    assert r.returncode == 1
