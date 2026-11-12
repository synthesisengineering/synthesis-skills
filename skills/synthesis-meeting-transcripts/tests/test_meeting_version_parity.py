"""The skill's executable components must report the skill's own version.

An external review of 4.56.0 found three skills shipping frontmatter behind
their body versions; this repository's transcripts checker already enforces
script-to-frontmatter parity at CI, and this pytest fixture keeps the
same contract in CI. The skill and its scripts move together (1.0.0 in M3).
"""
from __future__ import annotations

import re
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]


def _frontmatter_version() -> str:
    text = (HERE / "SKILL.md").read_text(encoding="utf-8")
    match = re.search(r'^\s*version:\s*"([^"]+)"', text, re.M)
    assert match, "SKILL.md frontmatter version not found"
    return match.group(1)


def _script_version(name: str) -> str:
    text = (HERE / name).read_text(encoding="utf-8")
    match = re.search(r'^SCRIPT_VERSION = "([^"]+)"$', text, re.M)
    assert match, f"{name} SCRIPT_VERSION not found"
    return match.group(1)


def test_executable_components_match_the_skill_version() -> None:
    skill = _frontmatter_version()
    assert _script_version("verify_transcripts.py") == skill
    assert _script_version("extract_commitments.py") == skill


def _releases() -> list:
    """The release each section of release-notes.md is for, newest first, as its heading writes it."""
    notes = (HERE / "references" / "release-notes.md").read_text(encoding="utf-8")
    return [heading.split(" — ")[0] for heading in re.findall(r"^## (.+)$", notes, re.M)]


def test_the_contents_line_names_the_range_of_releases_the_notes_cover() -> None:
    """It said the notes ran to 1.0.1 after two later releases had their notes there."""
    releases = _releases()
    assert len(releases) >= 10 and releases[-1] == "v0.2.0"
    contents = (HERE / "SKILL.md").read_text(encoding="utf-8").split("## Contents", 1)[1].split("\n## ", 1)[0]
    line = next(row for row in contents.splitlines() if "references/release-notes.md" in row)
    assert f"release notes from {releases[-1]} to {releases[0]}." in line, line
    assert len((HERE / "SKILL.md").read_bytes()) <= 8000


def test_the_release_notes_own_heading_and_contents_name_every_release_they_hold() -> None:
    notes = (HERE / "references" / "release-notes.md").read_text(encoding="utf-8")
    title, listed = notes.splitlines()[0], notes.split("\nContents:\n", 1)[1].split("\n\n", 1)[0]
    for release in _releases():
        assert f"- {release}" in listed, release
    assert all(part.lstrip("v") in title for part in _releases()[0].split(" and ")), title
