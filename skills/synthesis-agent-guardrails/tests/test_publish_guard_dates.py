"""Fixtures for the publish guard's timeline invariants.

Origin (2026-08-29): a post frontmatter-dated the next afternoon was pushed
live the evening before — a future-dated page on the principal's site; the
first correction then re-dated the live post, which is visible date-editing.
Both moves are now blocked at the publish boundary, above the approval
ledger.
"""
from __future__ import annotations

import importlib.util
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parent.parent / "guards" / "publish_guard.py"
SPEC = importlib.util.spec_from_file_location("publish_guard", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)

NOW = datetime(2026, 8, 29, 19, 30)


def _post(repo: Path, rel: str, stamp: str) -> Path:
    p = repo / "content" / "posts" / rel / "index.md"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        f"---\ntitle: \"T\"\ndate: '{stamp}'\n---\n\nBody.\n", encoding="utf-8"
    )
    return p


def _git(repo: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-C", str(repo), *args], check=True, capture_output=True
    )


def _repo_with_origin(tmp_path: Path) -> Path:
    repo = tmp_path / "site"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main", str(repo)], check=True)
    for k, v in (("user.name", "T"), ("user.email", "t@example.com"),
                 ("core.hooksPath", "/dev/null")):
        _git(repo, "config", k, v)
    return repo


def test_future_dated_file_is_flagged(tmp_path: Path) -> None:
    repo = tmp_path / "site"
    _post(repo, "2026/08/30-future", "2026-08-30T16:47:00")
    _post(repo, "2026/08/29-past", "2026-08-29T19:14:00")

    offenders = MODULE.future_dated_files(str(repo), now=NOW)

    assert [p for p, _ in offenders] == [
        "content/posts/2026/08/30-future/index.md"
    ]


def test_skew_window_tolerates_minutes_not_hours(tmp_path: Path) -> None:
    repo = tmp_path / "site"
    _post(repo, "2026/08/29-soon", "2026-08-29T19:40:00")   # +10m: skew
    _post(repo, "2026/08/29-later", "2026-08-29T21:40:00")  # +2h10m: future

    offenders = MODULE.future_dated_files(str(repo), now=NOW)

    assert [p for p, _ in offenders] == [
        "content/posts/2026/08/29-later/index.md"
    ]


def test_date_mutation_of_published_post_is_flagged(tmp_path: Path) -> None:
    repo = _repo_with_origin(tmp_path)
    post = _post(repo, "2026/08/28-live", "2026-08-28T10:00:00")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "publish")
    origin = tmp_path / "origin.git"
    subprocess.run(["git", "init", "-q", "--bare", str(origin)], check=True)
    _git(repo, "remote", "add", "origin", str(origin))
    _git(repo, "push", "-q", "origin", "main")

    post.write_text(
        post.read_text(encoding="utf-8").replace(
            "2026-08-28T10:00:00", "2026-08-27T10:00:00"
        ),
        encoding="utf-8",
    )
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "re-date")

    mutations = MODULE.published_date_mutations(str(repo))

    assert mutations == [
        ("content/posts/2026/08/28-live/index.md",
         "2026-08-28 10:00", "2026-08-27 10:00")
    ]


def test_unreachable_published_base_returns_none(tmp_path: Path) -> None:
    repo = _repo_with_origin(tmp_path)
    _post(repo, "2026/08/28-live", "2026-08-28T10:00:00")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "publish")

    assert MODULE.published_date_mutations(str(repo)) is None


def test_unchanged_dates_pass(tmp_path: Path) -> None:
    repo = _repo_with_origin(tmp_path)
    post = _post(repo, "2026/08/28-live", "2026-08-28T10:00:00")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "publish")
    origin = tmp_path / "origin.git"
    subprocess.run(["git", "init", "-q", "--bare", str(origin)], check=True)
    _git(repo, "remote", "add", "origin", str(origin))
    _git(repo, "push", "-q", "origin", "main")

    post.write_text(
        post.read_text(encoding="utf-8") + "\nA body edit, date untouched.\n",
        encoding="utf-8",
    )
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "body edit")

    assert MODULE.published_date_mutations(str(repo)) == []
    assert MODULE.future_dated_files(str(repo), now=NOW) == []


def test_push_regex_matches_subcommand_not_message_text() -> None:
    """`git commit -m "site push"` is not a push (2026-08-29 false positive);
    `git push`, `git --no-pager push`, and flagged pushes are."""
    rx = MODULE.GIT_PUSH_RX
    assert rx.search("git push origin main")
    assert rx.search("cd /x && git --no-pager push origin main")
    assert not rx.search('git commit -m "site push or deploy invariants"')
    assert not rx.search("git commit -m pushover-notes")


if __name__ == "__main__":
    # Without this, `python3 test_publish_guard_dates.py` exited 0 having run nothing —
    # a silent false pass in a verification path.
    import pytest

    raise SystemExit(pytest.main([__file__, "-q"]))


# --- the flat article layout ------------------------------------------------
# Found 2026-08-31 during the project completion audit: both timeline
# invariants globbed content/posts/**/index.md only, so the flat-layout
# site — whose articles live at astro-site/src/content/articles/*.md and
# whose URLs carry dates exactly like the others — was silently exempt from
# both. The guard reported healthy the whole time, which is the failure
# mode that matters.

def _flat_post(repo: Path, name: str, stamp: str) -> Path:
    p = repo / "astro-site" / "src" / "content" / "articles" / f"{name}.md"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        f'---\ntitle: "T"\nslug: "{name}"\ndate: "{stamp}"\n---\n\nBody.\n',
        encoding="utf-8",
    )
    return p


def test_flat_layout_future_dated_file_is_flagged(tmp_path: Path) -> None:
    repo = tmp_path / "site"
    _flat_post(repo, "future-post", "2026-08-30T16:47:00")
    _flat_post(repo, "past-post", "2026-08-29T19:14:00")

    offenders = MODULE.future_dated_files(str(repo), now=NOW)

    assert [p for p, _ in offenders] == [
        "astro-site/src/content/articles/future-post.md"
    ]


def test_flat_layout_date_mutation_of_published_post_is_flagged(
    tmp_path: Path,
) -> None:
    repo = _repo_with_origin(tmp_path)
    _flat_post(repo, "shipped", "2026-05-15T20:00:00")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "publish")
    _git(repo, "update-ref", "refs/remotes/origin/main", "HEAD")

    _flat_post(repo, "shipped", "2026-05-16T09:00:00")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "re-date")

    mutations = MODULE.published_date_mutations(str(repo))

    assert [rel for rel, _, _ in mutations] == [
        "astro-site/src/content/articles/shipped.md"
    ]


def test_both_layouts_coexist_in_one_scan(tmp_path: Path) -> None:
    """A repo carrying both shapes must have both scanned, not the first found."""
    repo = tmp_path / "site"
    _post(repo, "2026/08/30-nested-future", "2026-08-30T16:47:00")
    _flat_post(repo, "flat-future", "2026-08-30T18:00:00")

    offenders = sorted(p for p, _ in MODULE.future_dated_files(str(repo), now=NOW))

    assert offenders == [
        "astro-site/src/content/articles/flat-future.md",
        "content/posts/2026/08/30-nested-future/index.md",
    ]
