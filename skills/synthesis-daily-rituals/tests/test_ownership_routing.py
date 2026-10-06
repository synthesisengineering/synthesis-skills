"""Ownership-vs-visibility (§3) wiring stays pinned in the rituals documents.

references/ownership-routing.md carries the routing rules and the movable-side
rule; the day-start checklist carries the bullets that apply them. The shared
time-block layer and its overlap script were retired with the chief-of-staff
skill's v5 change; the rule that survived (a window nobody read is not free)
is pinned here too.
"""

from __future__ import annotations

from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parents[1]
REFERENCE = SKILL_DIR / "references" / "ownership-routing.md"
DAY_START = SKILL_DIR / "references" / "day-start.md"


def test_reference_exists_and_names_routing_rules() -> None:
    text = REFERENCE.read_text(encoding="utf-8")
    for anchor in (
        "Rule 1",
        "Rule 2",
        "Rule 3",
        "owner:",
        "owner_rule:",
        "candidate-confirmed",
        "never double-recorded",
        "movable:",
    ):
        assert anchor in text, f"ownership-routing.md lost its anchor: {anchor}"


def test_an_unread_window_is_never_free() -> None:
    text = REFERENCE.read_text(encoding="utf-8")
    assert "not a free window" in text
    assert "time-blocks.json" not in text and "overlap.py" not in text


def test_checklist_links_and_labels_the_wiring() -> None:
    text = DAY_START.read_text(encoding="utf-8")
    assert "ownership-routing.md" in text
    assert "routing rules" in text
    assert "Ownership vs visibility" in text
    assert "not a free window" in text
    assert (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8").count("ownership-routing.md") >= 1
