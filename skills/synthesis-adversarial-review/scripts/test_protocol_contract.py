from __future__ import annotations

import pathlib
import subprocess
import sys

import yaml


SKILL_ROOT = pathlib.Path(__file__).resolve().parents[1]
REVIEW = SKILL_ROOT / "SKILL.md"
AUTOPILOT = SKILL_ROOT.parent / "synthesis-autopilot" / "SKILL.md"
ROUTER = SKILL_ROOT.parent / "synthesis-skill-router" / "SKILL.md"
CONTRACT = pathlib.Path(__file__).with_name("protocol_acceptance.py")
MANIFEST = SKILL_ROOT / "acceptance-suite.yaml"


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


def test_acceptance_manifest_classifies_control_authority() -> None:
    manifest = yaml.safe_load(MANIFEST.read_text(encoding="utf-8"))
    assert manifest["metadata_class"] == "acceptance-test"
    assert manifest["issues_authority_receipt"] is False
    allowed = {"diagnostic", "acceptance-test", "enforced-gate"}
    for case in manifest["cases"]:
        assert case["control_class"] in allowed
    assert all(
        case["control_class"] == "diagnostic"
        for case in manifest["cases"]
        if "test_protocol_contract.py" in case["fixture"]
    )


def test_protocol_acceptance_rejects_token_soup(tmp_path: pathlib.Path) -> None:
    valid = subprocess.run(
        [
            sys.executable,
            str(CONTRACT),
            "--review",
            str(REVIEW),
            "--autopilot",
            str(AUTOPILOT),
            "--router",
            str(ROUTER),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert valid.returncode == 0, valid.stderr

    token_soup = tmp_path / "tokens.md"
    token_soup.write_text(
        "principal's outcome goal-focused round ship-blocking ship-improving "
        "Concession is health per-artifact matrix production entry point "
        "enforcing boundary receipt consumer Sidecars are claims concept sweep "
        "established open risk of shipping now principal's ruling terminates "
        "the loop generation N+1 generation N+2 direct session-to-session "
        "dispatch principal courier crossings round-trip budget proportionality "
        "reviewer satisfaction ../synthesis-adversarial-review/SKILL.md",
        encoding="utf-8",
    )
    refused = subprocess.run(
        [
            sys.executable,
            str(CONTRACT),
            "--review",
            str(token_soup),
            "--autopilot",
            str(token_soup),
            "--router",
            str(token_soup),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert refused.returncode != 0
