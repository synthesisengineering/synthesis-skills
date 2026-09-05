#!/usr/bin/env python3
"""Immutable bootstrap materialization tests."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest


SCRIPTS = Path(__file__).resolve().parent
REPO_ROOT = SCRIPTS.parents[2]
sys.path.insert(0, str(SCRIPTS))

import bootstrap  # noqa: E402
import system_contract  # noqa: E402
from test_system_contract import git, release_repo  # noqa: E402


def test_verified_cli_can_use_org_ssh_without_enabling_local_transports(tmp_path, monkeypatch):
    checkout = release_repo(tmp_path)
    calls = []
    monkeypatch.setenv("GIT_ALLOW_PROTOCOL", "https")
    monkeypatch.setenv("GIT_PROTOCOL_FROM_USER", "0")
    monkeypatch.setattr(bootstrap.subprocess, "call", lambda command, env=None: calls.append((command, env)) or 0)
    assert bootstrap.main([
        "--checkout", str(checkout), "--releases-dir", str(tmp_path / "releases"),
        "--launcher", str(tmp_path / "bin/synthesis"),
        "--active-descriptor", str(tmp_path / "state/active.json"),
        "--channel", "stable", "--ref", "stable",
        "--source-url", "https://example.test/synthesis-skills.git", "--", "update",
    ]) == 0
    environment = calls[0][1]
    assert environment["GIT_ALLOW_PROTOCOL"] == "https:ssh"
    assert environment["GIT_PROTOCOL_FROM_USER"] == "0"
    assert os.environ["GIT_ALLOW_PROTOCOL"] == "https"
    for forbidden in (checkout.as_uri(), "ext::git --version"):
        blocked = subprocess.run(["git", "ls-remote", forbidden], env=environment,
            capture_output=True, text=True)
        assert blocked.returncode != 0 and "not allowed" in blocked.stderr


def test_materialization_is_content_addressed_and_idempotent(tmp_path: Path) -> None:
    checkout = release_repo(tmp_path)
    releases = tmp_path / "cache" / "releases"
    first, descriptor = bootstrap.materialize_release(
        checkout,
        releases,
        channel="stable",
        ref="stable",
        source_url="https://example.test/synthesis-skills.git",
    )
    second, second_descriptor = bootstrap.materialize_release(
        checkout,
        releases,
        channel="stable",
        ref="stable",
        source_url="https://example.test/synthesis-skills.git",
    )
    assert first == second == releases / descriptor["content_digest"]
    assert second_descriptor["content_digest"] == descriptor["content_digest"]
    assert not (first / ".git").exists()
    assert len(list(releases.iterdir())) == 1


def test_materialized_generation_is_read_only(tmp_path: Path) -> None:
    checkout = release_repo(tmp_path)
    generation, _descriptor = bootstrap.materialize_release(
        checkout,
        tmp_path / "releases",
        channel="stable",
        ref="stable",
        source_url="https://example.test/synthesis-skills.git",
    )
    assert generation.stat().st_mode & 0o222 == 0
    assert all(path.stat().st_mode & 0o222 == 0 for path in generation.rglob("*"))


def test_existing_generation_permissions_are_reasserted(tmp_path: Path) -> None:
    checkout = release_repo(tmp_path)
    releases = tmp_path / "releases"
    generation, _descriptor = bootstrap.materialize_release(
        checkout,
        releases,
        channel="stable",
        ref="stable",
        source_url="https://example.test/synthesis-skills.git",
    )
    target = generation / ".codex-plugin" / "plugin.json"
    os.chmod(generation, 0o755)
    os.chmod(target, 0o644)
    same, _ = bootstrap.materialize_release(
        checkout,
        releases,
        channel="stable",
        ref="stable",
        source_url="https://example.test/synthesis-skills.git",
    )
    assert same == generation
    assert generation.stat().st_mode & 0o222 == 0
    assert target.stat().st_mode & 0o222 == 0


def test_floating_bootstrap_keeps_a_verified_newer_active_release(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    newer = release_repo(tmp_path / "newer", version="9.8.7")
    older = release_repo(tmp_path / "older", version="9.8.6")
    (newer / "onboard.sh").write_text("#!/bin/sh\n", encoding="utf-8")
    git(newer, "add", "onboard.sh")
    git(newer, "commit", "-q", "-m", "bootstrap")
    git(newer, "branch", "-f", "stable", "HEAD")
    git(newer, "tag", "-f", "v9.8.7")
    releases = tmp_path / "releases"
    generation, descriptor = bootstrap.materialize_release(
        newer,
        releases,
        channel="stable",
        ref="stable",
        source_url="https://example.test/synthesis-skills.git",
    )
    launcher = tmp_path / "bin" / "synthesis"
    active = tmp_path / "state" / "active.json"
    system_contract.activate_cli(generation, descriptor, launcher, active)
    calls = []
    monkeypatch.setattr(bootstrap.subprocess, "call", lambda command, env=None: calls.append((command, env)) or 0)
    assert bootstrap.main(
        [
            "--checkout", str(older),
            "--releases-dir", str(releases),
            "--launcher", str(launcher),
            "--active-descriptor", str(active),
            "--channel", "stable",
            "--ref", "stable",
            "--source-url", "https://example.test/synthesis-skills.git",
            "--", "update",
        ]
    ) == 0
    assert json.loads(active.read_text(encoding="utf-8"))["version"] == "9.8.7"
    assert str(generation) in calls[0][0][2]


def test_floating_bootstrap_honors_an_explicit_channel_change(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    stable = release_repo(tmp_path / "stable", version="9.8.7")
    edge = release_repo(tmp_path / "edge", version="9.8.6")
    git(edge, "branch", "main-edge", "HEAD")
    releases = tmp_path / "releases"
    stable_generation, stable_descriptor = bootstrap.materialize_release(
        stable,
        releases,
        channel="stable",
        ref="stable",
        source_url="https://example.test/synthesis-skills.git",
    )
    launcher = tmp_path / "bin" / "synthesis"
    active = tmp_path / "state" / "active.json"
    system_contract.activate_cli(stable_generation, stable_descriptor, launcher, active)
    monkeypatch.setattr(bootstrap.subprocess, "call", lambda _command, env=None: 0)
    assert bootstrap.main(
        [
            "--checkout", str(edge),
            "--releases-dir", str(releases),
            "--launcher", str(launcher),
            "--active-descriptor", str(active),
            "--channel", "edge",
            "--ref", "main",
            "--source-url", "https://example.test/synthesis-skills.git",
            "--", "setup",
        ]
    ) == 0
    selected = json.loads(active.read_text(encoding="utf-8"))
    assert selected["version"] == "9.8.6"
    assert selected["channel"] == "edge"
    assert selected["ref"] == "main"


def test_onboard_handoff_consumes_resolution_policy_before_update_cli(
    tmp_path: Path,
) -> None:
    checkout = release_repo(tmp_path / "source")
    fixture_scripts = checkout / "skills" / "synthesis-onboarding" / "scripts"
    shutil.copyfile(SCRIPTS / "bootstrap.py", fixture_scripts / "bootstrap.py")
    shutil.copyfile(SCRIPTS / "system_contract.py", fixture_scripts / "system_contract.py")
    marker = tmp_path / "cli-argv.json"
    (fixture_scripts / "synthesis_cli.py").write_text(
        "import argparse, json, os, sys\n"
        "from pathlib import Path\n\n\n"
        "def build_parser():\n"
        "    parser = argparse.ArgumentParser(prog='synthesis')\n"
        "    commands = parser.add_subparsers(dest='command', required=True)\n"
        "    for name in ('setup', 'update'):\n"
        "        commands.add_parser(name)\n"
        "    return parser\n\n\n"
        "if __name__ == '__main__':\n"
        "    if sys.argv[1:] != ['update']:\n"
        "        raise SystemExit(2)\n"
        "    Path(os.environ['SYNTHESIS_TEST_CLI_MARKER']).write_text("
        "json.dumps(sys.argv[1:]) + '\\n', encoding='utf-8')\n",
        encoding="utf-8",
    )
    git(checkout, "add", "-A")
    git(checkout, "commit", "-q", "-m", "handoff fixture")
    git(checkout, "branch", "-f", "stable", "HEAD")
    git(checkout, "tag", "-f", "v9.8.7")
    environment = dict(os.environ)
    environment.update(
        {
            "SYNTHESIS_ONBOARD_SOURCE_DIR": str(checkout),
            "SYNTHESIS_ONBOARD_CHANNEL": "stable",
            "SYNTHESIS_HOME": str(tmp_path / "home"),
            "SYNTHESIS_ONBOARD_CACHE_DIR": str(tmp_path / "cache"),
            "SYNTHESIS_INSTALL_BIN_DIR": str(tmp_path / "bin"),
            "XDG_STATE_HOME": str(tmp_path / "state"),
            "SYNTHESIS_TEST_CLI_MARKER": str(marker),
        }
    )
    completed = subprocess.run(
        ["sh", str(REPO_ROOT / "onboard.sh"), "update"],
        env=environment,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    assert json.loads(marker.read_text(encoding="utf-8")) == ["update"]


def test_existing_corrupt_generation_is_rejected(tmp_path: Path) -> None:
    checkout = release_repo(tmp_path)
    releases = tmp_path / "releases"
    generation, descriptor = bootstrap.materialize_release(
        checkout,
        releases,
        channel="stable",
        ref="stable",
        source_url="https://example.test/synthesis-skills.git",
    )
    target = generation / ".codex-plugin" / "plugin.json"
    target.chmod(0o644)
    target.write_text(json.dumps({"version": "0.0.0"}), encoding="utf-8")
    with pytest.raises(system_contract.ContractError):
        bootstrap.materialize_release(
            checkout,
            releases,
            channel="stable",
            ref="stable",
            source_url="https://example.test/synthesis-skills.git",
        )
    assert generation == releases / descriptor["content_digest"]


def test_ignored_build_artifacts_never_enter_materialized_release(tmp_path: Path) -> None:
    checkout = release_repo(tmp_path)
    ignored = checkout / "skills" / "synthesis-onboarding" / "scripts" / "__pycache__"
    ignored.mkdir()
    (ignored / "bootstrap.cpython-312.pyc").write_bytes(b"ignored test residue")
    (checkout / ".gitignore").write_text("__pycache__/\n", encoding="utf-8")
    git(checkout, "add", ".gitignore")
    git(checkout, "commit", "-q", "-m", "ignore build residue")
    git(checkout, "branch", "-f", "stable", "HEAD")
    git(checkout, "tag", "-f", "v9.8.7")

    generation, _descriptor = bootstrap.materialize_release(
        checkout,
        tmp_path / "releases",
        channel="stable",
        ref="stable",
        source_url="https://example.test/synthesis-skills.git",
    )
    assert not (generation / "skills" / "synthesis-onboarding" / "scripts" / "__pycache__").exists()
