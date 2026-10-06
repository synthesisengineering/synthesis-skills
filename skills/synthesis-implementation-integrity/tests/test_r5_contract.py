"""Facts other skills and this one must keep, read from where each lives in v5.

The scratchpad-sweep question moved with the autopilot rebuild (commit 5f535c4)
from its SKILL.md to references/delegation.md, the close step of its execution
loop. The acceptance-manifest and receipt wording was replaced when PR CI
became the only release gate; its v5 rules are checked below.
"""

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
    """The contract lives in one live reference of synthesis-context-lifecycle (its v5
    rewrite moved it out of SKILL.md); preserved and coverage files do not count."""
    heading = "Executable Working State — resources/scripts/"
    owner = REPO_ROOT / "skills/synthesis-context-lifecycle"
    homes = [p for p in sorted((owner / "references").glob("*.md"))
             if not p.name.startswith("preserved") and p.name != "coverage-map.md"
             and re.search(rf"^## {re.escape(heading)}\s*$", p.read_text(encoding="utf-8"), re.MULTILINE)]
    assert len(homes) == 1, homes
    # The 1.x SKILL.md section pointed at its operating protocol; in v5 a binding rule
    # states the duty and Contents links the reference that holds the section.
    entry = skill("synthesis-context-lifecycle")
    assert re.search(r"^\d+\. \*\*Preserve executable state\*\* under `resources/scripts/`", entry, re.MULTILINE)
    assert f"(references/{homes[0].name})" in entry
    contract = normalized(section(homes[0].read_text(encoding="utf-8"), heading))

    assert "If a script produces a number or conclusion cited in a durable record" in contract
    assert "preserve the script and every required input before recording the result" in contract
    assert "README.md" in contract
    assert "regeneration order" in contract
    assert "session-temporary" in contract
    assert "resources/scripts/" in contract
    # 1.x: "does not prove the script is correct"; v5: "existence never proves the script ... correct"
    assert re.search(r"(does not|never) proves? the script", contract)


def test_checkpoint_and_autopilot_ask_the_scratchpad_sweep_question() -> None:
    question = (
        "What executable state or required input data still exists only in this "
        "session's scratchpad?"
    )
    action = (
        "If a durable record cites its output, preserve the script and required "
        "inputs under resources/scripts/ before the checkpoint can close."
    )

    sources = {
        "synthesis-checkpoint": skill("synthesis-checkpoint"),
        "synthesis-autopilot": (REPO_ROOT / "skills/synthesis-autopilot/references/delegation.md").read_text(encoding="utf-8"),
    }
    for name, source in sources.items():
        text = normalized(source)
        assert question in text, name
        assert action in text, name


def test_integrity_requires_executable_acceptance_through_pr_ci() -> None:
    contract = normalized(section(skill("synthesis-implementation-integrity"), "Executable Acceptance"))

    for required in (
        "author-written claim ledger",
        "PR CI is the only release gate",
        "Every changed production surface names at least one test",
        "production entry point",
        "enforcing boundary",
        "unverified remainder",
        "fixture commit predates the green implementation",
        "a skip is not a pass",
    ):
        assert required in contract
    assert "acceptance_suite.py" not in contract


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
    assert "state-changing operation itself refuses" in contract
    assert "single-use approval code" in contract
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
