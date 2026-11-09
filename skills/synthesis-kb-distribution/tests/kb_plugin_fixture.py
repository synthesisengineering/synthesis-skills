"""A knowledge-base repository for the build and publish tests: the fixture, committed at a fixed time."""

import os
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCRIPTS = HERE.parent / "scripts"
FIXTURE = HERE / "fixtures" / "knowledge-base"
WHEN = "2026-11-01T09:30:00+00:00"
VERSION = "1.20261101.930"  # 1.{date}.{time} of WHEN
PUBLISHED = ["datasets/active/pricing-decision.md", "datasets/active/roadmap.md", "datasets/reference/company.md",
             "datasets/reference/glossary.md", "notes/onboarding.md"]


def git(repo: Path, *args: str, when: str = WHEN) -> str:
    env = {**os.environ, "GIT_AUTHOR_DATE": when, "GIT_COMMITTER_DATE": when}
    return subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True,
                          env=env).stdout.strip()


def commit(repo: Path, message: str = "Edit", when: str = WHEN) -> str:
    git(repo, "add", "-A")
    git(repo, "commit", "--quiet", "-m", message, when=when)
    return git(repo, "rev-parse", "HEAD")


def make_repo(tmp_path: Path) -> Path:
    """The fixture copied to tmp_path/knowledge-base as a git repository with one commit."""
    repo = tmp_path / "knowledge-base"
    shutil.copytree(FIXTURE, repo)
    git(repo, "init", "--quiet")
    commit(repo, "Knowledge base")
    return repo


def build(repo: Path, out: Path, *extra: str, config: Path = None, env: dict = None):
    """Run build_plugin.py as CI would, from another folder."""
    command = [sys.executable, str(SCRIPTS / "build_plugin.py"), "--config",
               str(config or repo / "distribution" / "kb-plugin.json"), "--source", str(repo / "source"),
               "--out", str(out), *extra]
    return subprocess.run(command, capture_output=True, text=True, cwd=repo.parent, env={**os.environ, **(env or {})})


def files_under(root: Path) -> list:
    return sorted(p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file())
