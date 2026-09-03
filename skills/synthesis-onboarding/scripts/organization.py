#!/usr/bin/env python3
"""Acquire and verify declarative organization configuration repositories."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from urllib.parse import urlsplit

from system_contract import ContractError, safe_identifier, validate_repository_url


MANIFEST_RELATIVE = ".agents/onboarding.yaml"


def _git_environment() -> dict[str, str]:
    """Keep credentials available while forbidding ambient transport expansion."""
    environment = dict(os.environ)
    for key in list(environment):
        if key == "GIT_CONFIG_COUNT" or key == "GIT_CONFIG_PARAMETERS" or re.fullmatch(
            r"GIT_CONFIG_(KEY|VALUE)_[0-9]+", key
        ):
            environment.pop(key, None)
    environment["GIT_ALLOW_PROTOCOL"] = "https:ssh"
    environment["GIT_PROTOCOL_FROM_USER"] = "0"
    return environment


def repository_slug(url: str) -> str:
    validate_repository_url(url)
    if re.match(r"^[^@]+@[^:]+:", url):
        path = url.split(":", 1)[1]
    else:
        path = urlsplit(url).path
    name = path.rstrip("/").rsplit("/", 1)[-1]
    if name.endswith(".git"):
        name = name[:-4]
    return safe_identifier(name, "organization repository name")


def _git(*args: str, cwd: Path | None = None, timeout: int = 600) -> str:
    proc = subprocess.run(
        ["git", "-c", "protocol.file.allow=never", "-c", "protocol.ext.allow=never", *args],
        cwd=str(cwd) if cwd else None,
        env=_git_environment(),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout,
        check=False,
    )
    if proc.returncode:
        raise ContractError(
            "organization repository operation failed: %s"
            % ((proc.stderr or proc.stdout).strip().splitlines()[-1] if (proc.stderr or proc.stdout).strip() else "git failed")
        )
    return proc.stdout.strip()


def canonical_remote(url: str) -> str:
    return url[:-4] if url.endswith(".git") else url.rstrip("/")


def acquire_repository(
    url: str,
    data_root: Path,
    expected_commit: str | None = None,
    refresh: bool = True,
) -> tuple[Path, str]:
    """Clone or fast-forward a data-only org repository and return its commit."""
    validate_repository_url(url)
    slug = repository_slug(url)
    data_root = Path(data_root)
    data_root.mkdir(parents=True, exist_ok=True)
    if data_root.is_symlink() or not data_root.is_dir():
        raise ContractError("organization data root must be a real directory")
    organization_root = data_root / "organizations"
    organization_root.mkdir(exist_ok=True)
    if organization_root.is_symlink() or not organization_root.is_dir():
        raise ContractError("organization repository parent must be a real directory")
    root = organization_root / slug
    if root.exists():
        git_directory = root / ".git"
        if (
            not root.is_dir()
            or root.is_symlink()
            or not git_directory.is_dir()
            or git_directory.is_symlink()
        ):
            raise ContractError("organization repository destination is not a real Git clone")
        origin = _git("remote", "get-url", "origin", cwd=root)
        if canonical_remote(origin) != canonical_remote(url):
            raise ContractError("existing organization clone has the wrong remote")
        if _git("status", "--porcelain", cwd=root):
            raise ContractError("existing organization clone has local changes")
        if refresh:
            _git("fetch", "--prune", "origin", cwd=root)
            if expected_commit:
                _git("checkout", "--detach", expected_commit, cwd=root)
            else:
                branch = _git("symbolic-ref", "--short", "refs/remotes/origin/HEAD", cwd=root)
                _git("checkout", "--detach", branch, cwd=root)
    else:
        if not refresh:
            raise ContractError("organization repository is not installed")
        staging = Path(tempfile.mkdtemp(prefix=".%s-stage-" % slug, dir=organization_root))
        staging.rmdir()
        try:
            _git("clone", "--origin", "origin", url, str(staging))
            if expected_commit:
                _git("checkout", "--detach", expected_commit, cwd=staging)
            staged_origin = _git("remote", "get-url", "origin", cwd=staging)
            if canonical_remote(staged_origin) != canonical_remote(url):
                raise ContractError(
                    "organization clone transport does not match the declared remote"
                )
            staged_manifest = staging / MANIFEST_RELATIVE
            if not staged_manifest.is_file() or staged_manifest.is_symlink():
                raise ContractError(
                    "organization repository has no regular .agents/onboarding.yaml"
                )
            _git("ls-files", "--error-unmatch", "--", MANIFEST_RELATIVE, cwd=staging)
            os.replace(staging, root)
        finally:
            if staging.exists():
                shutil.rmtree(staging)
    origin = _git("remote", "get-url", "origin", cwd=root)
    if canonical_remote(origin) != canonical_remote(url):
        raise ContractError("organization clone transport does not match the declared remote")
    commit = _git("rev-parse", "HEAD^{commit}", cwd=root)
    if expected_commit and commit != expected_commit:
        raise ContractError("organization repository did not resolve to the invited commit")
    if not _git("branch", "-r", "--contains", commit, cwd=root):
        raise ContractError(
            "organization commit is not reachable from a fetched origin branch"
        )
    manifest = root / MANIFEST_RELATIVE
    if not manifest.is_file() or manifest.is_symlink():
        raise ContractError("organization repository has no regular .agents/onboarding.yaml")
    tracked = subprocess.run(
        [
            "git",
            "-c",
            "protocol.file.allow=never",
            "-c",
            "protocol.ext.allow=never",
            "-C",
            str(root),
            "ls-files",
            "--error-unmatch",
            "--",
            MANIFEST_RELATIVE,
        ],
        env=_git_environment(),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if tracked.returncode:
        raise ContractError("organization manifest is not Git-tracked")
    return root, commit


def default_data_root(home: Path) -> Path:
    return Path(os.environ.get("XDG_DATA_HOME", str(Path(home) / ".local" / "share"))) / "synthesis"
