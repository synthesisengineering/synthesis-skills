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
