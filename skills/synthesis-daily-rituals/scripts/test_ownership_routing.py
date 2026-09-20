"""Ownership-vs-visibility (§3) wiring stays pinned in the rituals documents.

SKILL.md carries the checklist bullets; references/ownership-routing.md
carries the routing rules, the seat publish procedure, and the overlap
call. These tests pin the anchors both sides need, the link between them,
and the layer-path contract the overlap script resolves — so a rename on
either side fails here instead of stranding a seat.
"""

from __future__ import annotations

from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parents[1]
SKILL = SKILL_DIR / "SKILL.md"
REFERENCE = SKILL_DIR / "references" / "ownership-routing.md"
CHIEF_OF_STAFF = SKILL_DIR.parent / "synthesis-chief-of-staff"
OVERLAP = CHIEF_OF_STAFF / "scripts" / "overlap.py"


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
    ):
        assert anchor in text, f"ownership-routing.md lost its anchor: {anchor}"


def test_reference_documents_publish_and_overlap() -> None:
    text = REFERENCE.read_text(encoding="utf-8")
    for anchor in (
        "time-blocks.json",
        "overlap.py",
        "real titles",
        "by hand",
        "movable:",
        "never writes to a calendar",
    ):
        assert anchor in text, f"ownership-routing.md lost its anchor: {anchor}"


def test_skill_checklist_links_and_labels_the_wiring() -> None:
    text = SKILL.read_text(encoding="utf-8")
    assert "ownership-routing.md" in text
    assert "routing rules" in text
    assert "ownership-v-visibility" in text or "ownership-vs-visibility" in text or "Ownership vs visibility" in text


def test_layer_path_contract_matches_overlap_script() -> None:
    reference = REFERENCE.read_text(encoding="utf-8")
    script = OVERLAP.read_text(encoding="utf-8")
    assert "coordination/time-blocks.json" in reference
    assert "SYNTHESIS_TIME_BLOCKS" in reference
    assert "SYNTHESIS_TIME_BLOCKS" in script
    assert "synthesis-time-blocks/v1" in reference
    assert "synthesis-time-blocks/v1" in script
