"""stray_lessons.py: lessons added to project records since a date, outside a lessons folder, in a real git repo."""

import json
import os
import subprocess
import sys
from datetime import date
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import stray_lessons  # noqa: E402

OLD_LOG = "# Sessions\n\n## 2026-10-01\n\n### Lessons\n\nAn old lesson nobody moved.\n"


@pytest.fixture(autouse=True)
def git_identity(tmp_path, monkeypatch):
    config = tmp_path / "gitconfig"
    config.write_text("[user]\n\temail = test@example.com\n\tname = test\n[init]\n\tdefaultBranch = main\n")
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(config))
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")


def _repo(tmp_path):
    repo = tmp_path / "ai-knowledge-test"
    log = repo / "projects" / "p" / "sessions" / "2026-10.md"
    log.parent.mkdir(parents=True)
    log.write_text(OLD_LOG, encoding="utf-8")
    (repo / "lessons").mkdir()
    (repo / "lessons" / "2026-10-01-kept.md").write_text("# Lessons are kept here\n", encoding="utf-8")
    stamp = {"GIT_AUTHOR_DATE": "2026-10-01T12:00:00", "GIT_COMMITTER_DATE": "2026-10-01T12:00:00"}
    for args in (["init", "-q"], ["add", "."], ["commit", "-q", "-m", "records"]):
        subprocess.run(["git", "-C", str(repo), *args], check=True, env={**os.environ, **stamp})
    return repo, log


def test_a_lesson_added_since_the_date_without_a_link_is_listed(tmp_path):
    repo, log = _repo(tmp_path)
    log.write_text(OLD_LOG + "\n## 2026-11-02\n\n### Lessons learned\n\nA watcher carries an external wait.\n"
                   "\n### Notes\n\n**Lesson:** linked at [lessons/2026-11-02-watch.md](../../lessons/2026-11-02-watch.md).\n"
                   "\n- **Lessons:** one more, in a list\n- **Next:** see lessons/ for the rest\n"
                   "- **R10.6 Corrections become lessons.** A requirement that names lessons is not one.\n",
                   encoding="utf-8")
    (repo / "projects" / "p" / "resources").mkdir()
    (repo / "projects" / "p" / "resources" / "lessons.md").write_text("# Release lessons\n\n1. Verify.\n")
    found = stray_lessons.strays(repo, date(2026, 10, 30))
    assert [(f["path"], f["line"], f["text"]) for f in found] == [
        ("projects/p/resources/lessons.md", 1, "# Release lessons"),
        ("projects/p/sessions/2026-10.md", 11, "### Lessons learned"),
        ("projects/p/sessions/2026-10.md", 19, "- **Lessons:** one more, in a list"),
    ]


def test_nothing_new_lists_nothing_and_a_missing_repo_is_named(tmp_path, capsys):
    repo, _ = _repo(tmp_path)
    assert stray_lessons.strays(repo, date(2026, 10, 30)) == []
    assert stray_lessons.main(["--since", "2026-10-30", "--repo", str(repo), "--repo", str(tmp_path / "gone"),
                               "--json"]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["strays"] == [] and report["unread"] == [str(tmp_path / "gone")]


def test_every_record_counts_as_new_when_the_repo_is_younger_than_the_date(tmp_path, capsys):
    repo, _ = _repo(tmp_path)
    assert stray_lessons.main(["--since", "2026-09-01", "--repo", str(repo)]) == 0
    out = capsys.readouterr().out
    assert "since 2026-09-01: 1." in out and "ai-knowledge-test/projects/p/sessions/2026-10.md:5  ### Lessons" in out
