from __future__ import annotations

import pathlib


SKILL_ROOT = pathlib.Path(__file__).resolve().parents[1]
REVIEW = SKILL_ROOT / "SKILL.md"
AUTOPILOT = SKILL_ROOT.parent / "synthesis-autopilot" / "SKILL.md"
ROUTER = SKILL_ROOT.parent / "synthesis-skill-router" / "SKILL.md"


def review_text() -> str:
    return REVIEW.read_text(encoding="utf-8")


def autopilot_text() -> str:
    return AUTOPILOT.read_text(encoding="utf-8")


def router_text() -> str:
    return ROUTER.read_text(encoding="utf-8")


def test_review_protocol_is_principal_outcome_focused() -> None:
    text = review_text()
    for required in (
        "principal's outcome",
        "goal-focused round",
        "ship-blocking",
        "ship-improving",
        "Concession is health",
        "per-artifact matrix",
    ):
        assert required in text


def test_handoff_contract_names_the_production_topology() -> None:
    text = review_text()
    for required in (
        "production entry point",
        "enforcing boundary",
        "receipt consumer",
        "Sidecars are claims",
        "concept sweep",
    ):
        assert required in text


def test_control_depth_and_sufficiency_are_bounded() -> None:
    text = review_text()
    for required in (
        "established",
        "open",
        "risk of shipping now",
        "principal's ruling terminates the loop",
        "generation N+1",
        "generation N+2",
    ):
        assert required in text


def test_autopilot_tracks_direct_dispatch_and_courier_cost() -> None:
    text = autopilot_text()
    for required in (
        "direct session-to-session dispatch",
        "principal courier crossings",
        "round-trip budget",
        "proportionality",
        "reviewer satisfaction",
    ):
        assert required in text


def test_hidden_specialist_is_reachable_through_the_router() -> None:
    text = router_text()
    assert "../synthesis-adversarial-review/SKILL.md" in text
    assert "adversarial review" in text.lower()
