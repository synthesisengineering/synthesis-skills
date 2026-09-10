"""The version record covers every version the skill document names.

SKILL.md labels each checklist step with the version that introduced it
("(vX.Y.Z)") and carries the current version in its frontmatter;
references/version-history.md is the release-by-release record those labels
send a reader to. On 2026-09-10 the record's newest entry was v2.34.0 while
the frontmatter said 2.34.2 and the weekly review's PR-queue step was labeled
v2.35.0, so a reader following a label found no entry. These tests fail when a
labeled or declared version has no heading in the record, when the record's
newest entry and the frontmatter disagree, and when a label runs ahead of the
declared version.
"""

from __future__ import annotations

import re
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parents[1]
SKILL = SKILL_DIR / "SKILL.md"
HISTORY = SKILL_DIR / "references" / "version-history.md"

LABEL = re.compile(r"\(v(\d+\.\d+\.\d+)\)")
HEADING = re.compile(r"^## v(\d+\.\d+\.\d+)\b", re.MULTILINE)
FRONTMATTER_VERSION = re.compile(r'^\s+version:\s*"(\d+\.\d+\.\d+)"\s*$', re.MULTILINE)


def _version_key(version: str) -> tuple[int, ...]:
    return tuple(int(part) for part in version.split("."))


def _frontmatter(text: str) -> str:
    assert text.startswith("---\n"), "SKILL.md must open with a YAML frontmatter block"
    return text[4:].split("\n---\n", 1)[0]


def declared_version() -> str:
    match = FRONTMATTER_VERSION.search(_frontmatter(SKILL.read_text(encoding="utf-8")))
    assert match, "SKILL.md frontmatter carries no quoted metadata.version"
    return match.group(1)


def labeled_versions() -> set[str]:
    return set(LABEL.findall(SKILL.read_text(encoding="utf-8")))


def recorded_versions() -> list[str]:
    """Headings in file order; the record is newest first."""
    return HEADING.findall(HISTORY.read_text(encoding="utf-8"))


def test_every_labeled_version_has_a_record_entry() -> None:
    missing = sorted(labeled_versions() - set(recorded_versions()), key=_version_key)
    assert not missing, (
        f"SKILL.md labels versions that have no '## vX.Y.Z' heading in "
        f"references/version-history.md: {missing}"
    )


def test_declared_version_has_a_record_entry() -> None:
    version = declared_version()
    assert version in recorded_versions(), (
        f"metadata.version {version} has no '## v{version}' heading in references/version-history.md"
    )


def test_record_newest_entry_is_the_declared_version() -> None:
    recorded = recorded_versions()
    assert recorded, "references/version-history.md has no '## vX.Y.Z' headings"
    assert recorded[0] == declared_version(), (
        f"the record's newest entry is v{recorded[0]} but metadata.version is {declared_version()}; "
        "the record is newest first and every release adds its entry"
    )


def test_no_label_runs_ahead_of_the_declared_version() -> None:
    declared = _version_key(declared_version())
    ahead = sorted((v for v in labeled_versions() if _version_key(v) > declared), key=_version_key)
    assert not ahead, (
        f"SKILL.md labels versions newer than metadata.version {declared_version()}: {ahead}; "
        "a label names a released version, so the frontmatter bumps in the same change"
    )
