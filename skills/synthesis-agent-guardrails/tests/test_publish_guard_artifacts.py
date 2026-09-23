"""Exact artifact approval: no live state, credentials, or deployment runner."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

import pytest

SPEC = importlib.util.spec_from_file_location("publish_guard_artifact_test", Path(__file__).resolve().parent.parent / "guards" / "publish_guard.py")
pg = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(pg)



@pytest.fixture
def candidate(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    repo.mkdir()
    env = dict(os.environ, GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull,
               GIT_AUTHOR_NAME="Fixture", GIT_AUTHOR_EMAIL="fixture@example.com",
               GIT_COMMITTER_NAME="Fixture", GIT_COMMITTER_EMAIL="fixture@example.com")
    def git(*args, data=None):
        return subprocess.run(["git", "-C", str(repo), *args], input=data, env=env,
                              check=True, text=True, capture_output=True).stdout.strip()
    git("init", "-q")
    tree = git("mktree", data="")
    head = git("commit-tree", tree, data="Fixture\n")
    git("update-ref", "HEAD", head)
    git("update-ref", "refs/remotes/origin/main", head)
    config = tmp_path / "config.json"
    config.write_text(json.dumps({"auto_deploy_repos": [str(repo)]}))
    monkeypatch.setenv("PUBLISH_GUARD_CONFIG", str(config))
    monkeypatch.setenv("PUBLISH_GUARD_STATE_DIR", str(tmp_path / "state"))
    consumer = tmp_path / "consumer.mjs"
    consumer.write_text("// Hermetic non-executable fixture.\n")
    artifact = tmp_path / "artifact.js"
    artifact.write_text("export default {};\n")
    digest = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
    bound_files = [{"path": str(p), "sha256": digest(p)} for p in (consumer, artifact)]
    binding = {"schema": 1, "transaction_id": str(uuid4()), "surface": "worker",
               "repo": str(repo), "head_sha": head, "tree_sha": tree,
               "consumer_path": str(consumer), "consumer_sha256": digest(consumer),
               "bound_files": bound_files,
               "artifact_manifest_sha256": digest(artifact),
               "plan": {"surface": "worker", "target": "fixture-only"}}
    path = tmp_path / "binding.json"
    path.write_text(json.dumps(binding))
    return path, binding, artifact


def approve(path):
    return pg.approve_deployment(str(path), "Approved fixture only", "Yes, approve this exact fixture.")


def test_approval_consumes_once_and_cannot_be_reissued(candidate):
    path, _, _ = candidate
    assert approve(path) == 0
    assert pg.consume_deployment(str(path)) == 0
    assert pg.consume_deployment(str(path)) == 2
    assert approve(path) == 2


def test_missing_approval_refuses_without_consumption(candidate):
    path, _, _ = candidate
    assert pg.consume_deployment(str(path)) == 2


@pytest.mark.parametrize("field", ["transaction_id", "surface", "head_sha", "tree_sha", "plan", "artifact_manifest_sha256"])
def test_binding_change_refuses(candidate, field):
    path, binding, _ = candidate
    assert approve(path) == 0
    binding[field] = "changed"
    path.write_text(json.dumps(binding))
    assert pg.consume_deployment(str(path)) == 2


def test_bound_artifact_change_refuses(candidate):
    path, _, artifact = candidate
    assert approve(path) == 0
    artifact.write_text("changed\n")
    assert pg.consume_deployment(str(path)) == 2


def test_consumer_change_refuses(candidate):
    path, binding, _ = candidate
    assert approve(path) == 0
    Path(binding["consumer_path"]).write_text("changed\n")
    assert pg.consume_deployment(str(path)) == 2


def test_concurrent_consumers_have_one_winner(candidate):
    path, _, _ = candidate
    assert approve(path) == 0
    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda _: pg.consume_deployment(str(path)), range(2)))
    assert sorted(results) == [0, 2]


def test_expired_approval_refuses(candidate):
    path, _, _ = candidate
    assert approve(path) == 0
    approvals = list(Path(pg.state_dir()).glob("deployments/*/approval.json"))
    assert len(approvals) == 1
    value = json.loads(approvals[0].read_text())
    value["created_at"] = (datetime.now(timezone.utc) - timedelta(minutes=16)).isoformat()
    approvals[0].write_text(json.dumps(value))
    assert pg.consume_deployment(str(path)) == 2


def test_no_quote_or_summary_is_not_approval(candidate):
    path, _, _ = candidate
    assert pg.approve_deployment(str(path), "", "yes") == 2
    assert pg.approve_deployment(str(path), "fixture", "") == 2


def test_state_symlink_refuses(candidate, monkeypatch, tmp_path):
    path, _, _ = candidate
    target = tmp_path / "elsewhere"
    target.mkdir()
    link = tmp_path / "link"
    link.symlink_to(target, target_is_directory=True)
    monkeypatch.setenv("PUBLISH_GUARD_STATE_DIR", str(link))
    assert approve(path) == 2
    assert list(target.iterdir()) == []


def test_builtin_controls_do_not_depend_on_operator_default_branch(tmp_path):
    config = tmp_path / "gitconfig"
    config.write_text("[init]\n\tdefaultBranch = fixture-default\n")
    env = dict(os.environ, GIT_CONFIG_GLOBAL=str(config), GIT_CONFIG_NOSYSTEM="1")
    result = subprocess.run([sys.executable, str(Path(pg.__file__)), "--test"], env=env,
                            capture_output=True, text=True, timeout=300)
    assert result.returncode == 0, result.stdout + result.stderr


def test_database_candidate_has_separate_exact_single_use_approval(candidate):
    path, binding, _ = candidate
    binding["surface"] = "database"
    path.write_text(json.dumps(binding))
    assert approve(path) == 0
    assert pg.consume_deployment(str(path), peek=True) == 0
    assert pg.consume_deployment(str(path)) == 0
    assert pg.consume_deployment(str(path)) == 2
