#!/usr/bin/env python3
"""Organization enrollment boundary tests."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest


SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS))

import organization  # noqa: E402
import system_contract  # noqa: E402


@pytest.mark.parametrize(
    ("url", "slug"),
    [
        ("https://example.test/group/config.git", "config"),
        ("ssh://git@example.test/group/team-config.git", "team-config"),
        ("git@example.test:group/team-config.git", "team-config"),
    ],
)
def test_repository_slug_is_safe(url: str, slug: str) -> None:
    assert organization.repository_slug(url) == slug


def test_repository_slug_rejects_destination_escape() -> None:
    with pytest.raises(system_contract.ContractError):
        organization.repository_slug("https://example.test/group/..git")


def test_existing_clone_with_wrong_remote_is_rejected(tmp_path: Path, monkeypatch) -> None:
    destination = tmp_path / "organizations" / "config"
    (destination / ".git").mkdir(parents=True)
    monkeypatch.setattr(
        organization,
        "_git",
        lambda *args, **kwargs: "https://example.test/wrong.git"
        if args[:3] == ("remote", "get-url", "origin")
        else "",
    )
    with pytest.raises(system_contract.ContractError, match="wrong remote"):
        organization.acquire_repository(
            "https://example.test/group/config.git", tmp_path
        )


def test_verify_only_never_fetches_or_clones(tmp_path: Path, monkeypatch) -> None:
    destination = tmp_path / "organizations" / "config"
    (destination / ".git").mkdir(parents=True)
    (destination / ".agents").mkdir()
    (destination / organization.MANIFEST_RELATIVE).write_text("version: 2\n")
    calls = []

    def fake_git(*args, **kwargs):
        calls.append(args)
        if args[:3] == ("remote", "get-url", "origin"):
            return "https://example.test/group/config.git"
        if args[:2] == ("status", "--porcelain"):
            return ""
        if args[:2] == ("rev-parse", "HEAD^{commit}"):
            return "a" * 40
        if args[:3] == ("branch", "-r", "--contains"):
            return "origin/main"
        return ""

    monkeypatch.setattr(organization, "_git", fake_git)
    monkeypatch.setattr(organization.subprocess, "run", lambda *args, **kwargs: type("P", (), {"returncode": 0})())
    _, commit = organization.acquire_repository(
        "https://example.test/group/config.git",
        tmp_path,
        expected_commit="a" * 40,
        refresh=False,
    )
    assert commit == "a" * 40
    assert not any(call and call[0] in {"fetch", "clone", "checkout"} for call in calls)


def test_existing_clone_rejects_symlinked_git_directory(tmp_path: Path) -> None:
    url = "https://example.test/team/onboarding.git"
    data_root = tmp_path / "data"
    root = data_root / "organizations" / "onboarding"
    root.mkdir(parents=True)
    outside = tmp_path / "outside-git"
    outside.mkdir()
    (root / ".git").symlink_to(outside, target_is_directory=True)
    with pytest.raises(system_contract.ContractError, match="real Git clone"):
        organization.acquire_repository(url, data_root)


def test_repository_parent_rejects_symlink_boundary(tmp_path: Path) -> None:
    url = "https://example.test/team/onboarding.git"
    data_root = tmp_path / "data"
    data_root.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    (data_root / "organizations").symlink_to(outside, target_is_directory=True)
    with pytest.raises(system_contract.ContractError, match="parent"):
        organization.acquire_repository(url, data_root)


def test_clone_rejects_ambient_https_to_file_transport_rewrite(
    tmp_path: Path, monkeypatch
) -> None:
    source = tmp_path / "source" / "team" / "config.git"
    work = tmp_path / "work"
    work.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main", str(work)], check=True)
    (work / ".agents").mkdir()
    (work / organization.MANIFEST_RELATIVE).write_text("version: 2\n", encoding="utf-8")
    env = dict(os.environ)
    env.update(
        {
            "GIT_AUTHOR_NAME": "Fixture",
            "GIT_AUTHOR_EMAIL": "fixture@example.test",
            "GIT_COMMITTER_NAME": "Fixture",
            "GIT_COMMITTER_EMAIL": "fixture@example.test",
        }
    )
    subprocess.run(["git", "-C", str(work), "add", "-A"], env=env, check=True)
    subprocess.run(
        [
            "git",
            "-c",
            "core.hooksPath=/dev/null",
            "-C",
            str(work),
            "commit",
            "-q",
            "-m",
            "fixture",
        ],
        env=env,
        check=True,
    )
    source.parent.mkdir(parents=True)
    subprocess.run(["git", "clone", "-q", "--bare", str(work), str(source)], check=True)
    global_config = tmp_path / "gitconfig"
    global_config.write_text(
        '[url "file://%s/"]\n\tinsteadOf = https://example.test/\n'
        % (tmp_path / "source"),
        encoding="utf-8",
    )
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(global_config))
    with pytest.raises(system_contract.ContractError, match="operation failed"):
        organization.acquire_repository(
            "https://example.test/team/config.git", tmp_path / "data"
        )
    assert not (tmp_path / "data" / "organizations" / "config").exists()
