"""Facts the review protocol depends on, read from where each now lives.

Replaces scripts/test_protocol_contract.py, whose checks went through the
retired protocol_acceptance.py diagnostic. Source-structure checks only: they
cannot establish native agent behavior or the sufficiency of a real review.
"""

from __future__ import annotations

import re
from pathlib import Path

SKILL = Path(__file__).resolve().parents[1]
SKILLS = SKILL.parent
PROTOCOL = SKILL / "references" / "protocol.md"
DOMAIN = SKILL / "references" / "domain-review-contract.md"


def text(path: Path) -> str:
    return " ".join(path.read_text(encoding="utf-8").split())


def section(path: Path, heading: str) -> str:
    """The text under one `## ` heading, up to the next one outside a code fence."""
    lines, found, fenced = [], False, False
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("```"):
            fenced = not fenced
        if not fenced and line.startswith("## "):
            if found:
                break
            found = line[3:].strip() == heading
            continue
        if found:
            lines.append(line)
    assert found, f"missing section {heading} in {path.name}"
    return " ".join(" ".join(lines).split())


def test_protocol_sections_are_present_in_order():
    body = PROTOCOL.read_text(encoding="utf-8")
    order = ["Purpose", "Before Round One: Proportionality Contract", "Roles and Blind-Spot Rotation",
             "Adjudication and Separation of Duties", "Goal-Focused Round",
             "Sidecars, Evidence, and Handoff Topology", "Finding Ledger", "Bounded Control Depth",
             "Bounded Post-Publication Acceptance", "Agent-Principal Norms", "Completion Report"]
    positions = [body.index(f"\n## {heading}\n") for heading in order]
    assert positions == sorted(positions)


def test_review_protocol_is_principal_outcome_focused():
    protocol = text(PROTOCOL)
    for required in ("principal's outcome", "goal-focused round", "ship-blocking", "ship-improving",
                     "Concession is health", "per-artifact matrix"):
        assert required in protocol
    goal = section(PROTOCOL, "Goal-Focused Round")
    for stage in ("1. **Contract.**", "2. **Attack.**", "3. **Disposition.**", "4. **Concept sweep.**",
                  "5. **Sufficiency.**"):
        assert stage in goal


def test_handoff_contract_names_the_production_topology():
    handoff = section(PROTOCOL, "Sidecars, Evidence, and Handoff Topology")
    for required in ("production entry point", "enforcing boundary", "receipt consumer",
                     "Sidecars are claims", "concept sweep"):
        assert required in handoff


def test_control_depth_and_sufficiency_are_bounded():
    protocol = text(PROTOCOL)
    for required in ("established", "open", "risk of shipping now", "principal's ruling terminates the loop",
                     "generation N+1", "generation N+2", "principal courier crossings", "Round-trip budget"):
        assert required in protocol


def test_findings_table_keeps_every_ledger_field_and_rule():
    ledger = section(PROTOCOL, "Finding Ledger")
    for state in ("open", "challenged", "repaired-prose", "repaired-source", "repaired-verified", "conceded",
                  "awaiting-principal"):
        assert f"{state}" in ledger
    for required in ("ship-blocking | ship-improving", "principal-rule | agent-heuristic", "enforcement outcome",
                     "follow-up project", "append-only", "compare-before-write", "| ID | Finding | State | Class |",
                     "only a fail-closed caller at the state-changing boundary can claim an enforced gate"):
        assert required in ledger
    assert "finding_ledger.py" not in ledger


def test_domain_contract_keeps_the_ten_replay_shapes_as_checks():
    checks = section(DOMAIN, "Checks the reviewer applies")
    for shape in ("uniform failure of 60 cases", "durable versus disposable paths",
                  "exact-session readiness with aggregate open work",
                  "delivered board message with incomplete continuity", "a 455-item corpus changed by 30 publications",
                  "mixed automatic and manual destination outcomes", "approval versus actual bytes",
                  "independently derived reviewer inputs", "destination-relative handoff links",
                  "exact saved output with prior custody"):
        assert shape in checks
    assert "review_contract" not in DOMAIN.read_text(encoding="utf-8")


def test_hidden_specialist_is_reachable_through_the_router():
    router = (SKILLS / "synthesis-skill-router" / "SKILL.md").read_text(encoding="utf-8")
    assert "../synthesis-adversarial-review/SKILL.md" in router
    assert "adversarial review" in router.lower()


def test_autopilot_routes_review_to_this_skill():
    """The facts the old autopilot SKILL.md carried, where the rebuilt autopilot keeps them."""
    autopilot = SKILLS / "synthesis-autopilot"
    front = (autopilot / "SKILL.md").read_text(encoding="utf-8").split("---", 2)[1]
    depends = re.search(r"^depends_on:\s*\[(.*?)\]\s*$", front, re.M)
    assert depends and "synthesis-adversarial-review" in re.findall(r"[\"']([^\"']+)[\"']", depends.group(1))
    doctrine = text(autopilot / "references" / "execution-doctrine.md")
    assert "one complete adversarial review per declared package" in doctrine
    assert "substantiated findings" in doctrine
    link = "../../synthesis-thinking-framework/references/decision-ownership.md"
    assert link in doctrine
    assert (autopilot / "references" / link).resolve().is_file()
    delegation = text(autopilot / "references" / "delegation.md")
    assert "synthesis msg" in delegation and "courier crossings" in delegation
    assert "Use synthesis-adversarial-review for the complete round and ledger protocol." in delegation
