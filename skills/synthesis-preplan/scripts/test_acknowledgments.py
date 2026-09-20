"""Pin the preplan proposal credit — it must survive future edits."""

from __future__ import annotations

from pathlib import Path


def test_acknowledgments_credit_the_proposer() -> None:
    body = (
        Path(__file__).resolve().parent.parent / "SKILL.md"
    ).read_text(encoding="utf-8")
    assert "## Acknowledgments" in body
    assert "Emil Peñalo" in body
    assert "https://github.com/EPenaloColon" in body
    assert "synthesis-skills/issues/4" in body
