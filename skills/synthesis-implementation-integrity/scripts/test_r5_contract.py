from __future__ import annotations

import re
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]


def skill(name: str) -> str:
    return (REPO_ROOT / "skills" / name / "SKILL.md").read_text(encoding="utf-8")


def section(text: str, heading: str) -> str:
    match = re.search(rf"^## {re.escape(heading)}\s*$", text, re.MULTILINE)
    assert match, f"missing section: {heading}"
    following = re.search(r"^## ", text[match.end() :], re.MULTILINE)
    end = match.end() + following.start() if following else len(text)
    return text[match.end() : end]


def normalized(text: str) -> str:
    return " ".join(text.split())


def test_scripts_tier_contract_is_owned_by_context_lifecycle() -> None:
    contract = normalized(
        section(skill("synthesis-context-lifecycle"), "Executable Working State — resources/scripts/")
    )

    assert "If a script produces a number or conclusion cited in a durable record" in contract
    assert "preserve the script and every required input before recording the result" in contract
    assert "README.md" in contract
    assert "regeneration order" in contract
    assert "session-temporary" in contract
    assert "resources/scripts/" in contract
    assert "does not prove the script is correct" in contract


def test_checkpoint_and_autopilot_ask_the_scratchpad_sweep_question() -> None:
    question = (
        "What executable state or required input data still exists only in this "
        "session's scratchpad?"
    )
    action = (
        "If a durable record cites its output, preserve the script and required "
        "inputs under resources/scripts/ before the checkpoint can close."
    )

    for name in ("synthesis-checkpoint", "synthesis-autopilot"):
        text = normalized(skill(name))
        assert question in text, name
        assert action in text, name


def test_integrity_requires_executable_closed_acceptance_manifests() -> None:
    contract = normalized(
        section(skill("synthesis-implementation-integrity"), "Executable Acceptance Manifests")
    )

    for required in (
        "membership: closed",
        "production_entry_point",
        "enforcing_boundary",
        "receipt_consumer",
        "expected_status",
        "unverified_remainder",
        "acceptance_suite.py run",
    ):
        assert required in contract
    assert "Every changed production surface names at least one case" in contract
    assert "fixture commit predates the green implementation" in contract
    assert "author-written claim ledger" in contract


def test_integrity_requires_extract_dont_restate() -> None:
    contract = normalized(
        section(skill("synthesis-implementation-integrity"), "Extract, Do Not Restate")
    )

    assert "extract it from the authoritative source at verification time" in contract
    assert "second hand-maintained copy" in contract
    assert "shared author blind spot" in contract
    assert "unverifiable" in contract


def test_integrity_locates_authority_at_the_state_changing_boundary() -> None:
    contract = normalized(
        section(skill("synthesis-implementation-integrity"), "Authority Lives at the Boundary")
    )

    assert "standalone verifier is evidence, not enforcement" in contract
    assert "state-changing consumer" in contract
    assert "fresh, matching, transaction-bound receipt" in contract
    assert "metadata class" in contract
    assert "does not manufacture approval" in contract


def test_disclosure_categories_preserve_attention_for_real_approval_gates() -> None:
    contract = normalized(
        section(skill("synthesis-disclosure-policy"), "Category Allowlists Without Approval Fatigue")
    )

    assert "principal approves the category once" in contract
    assert "independent public evidence" in contract
    assert "positive or neutral" in contract
    assert "Class X is never category-allowlisted" in contract
    assert "ambiguity remains Class A" in contract
    assert "rubber-stamp" in contract
    assert "approval fatigue is a failure mode of fail-closed design" in contract
