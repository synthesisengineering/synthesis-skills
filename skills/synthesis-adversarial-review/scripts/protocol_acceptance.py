#!/usr/bin/env python3
"""Diagnose the structural adversarial-review and orchestration contract.

AGENT HEURISTIC: this is a diagnostic for section-scoped source structure. It
cannot establish that an agent followed the protocol; native behavioral smoke
checks remain a separate acceptance surface.
"""

from __future__ import annotations

import argparse
import pathlib
import re
import sys


HEADING = re.compile(r"^(#{2,3})\s+(.+?)\s*$", re.MULTILINE)


def read(path: pathlib.Path) -> str:
    if path.is_symlink() or not path.is_file():
        raise ValueError(f"unsafe or missing contract file: {path}")
    return path.read_text(encoding="utf-8")


def section_map(text: str) -> tuple[list[str], dict[str, str]]:
    matches = list(HEADING.finditer(text))
    order = [match.group(2) for match in matches]
    sections: dict[str, str] = {}
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        sections[match.group(2)] = text[match.end() : end]
    return order, sections


def require_order(order: list[str], expected: list[str], errors: list[str]) -> None:
    positions: list[int] = []
    for heading in expected:
        if heading not in order:
            errors.append(f"missing section: {heading}")
        else:
            positions.append(order.index(heading))
    if len(positions) == len(expected) and positions != sorted(positions):
        errors.append("protocol sections are out of order")


def require_terms(
    sections: dict[str, str], heading: str, terms: tuple[str, ...], errors: list[str]
) -> None:
    body = re.sub(r"\s+", " ", sections.get(heading, ""))
    for term in terms:
        if term not in body:
            errors.append(f"{heading!r} is missing {term!r}")


def review_errors(text: str) -> list[str]:
    errors: list[str] = []
    order, sections = section_map(text)
    expected = [
        "Purpose",
        "Before Round One: Proportionality Contract",
        "Roles and Blind-Spot Rotation",
        "Goal-Focused Round",
        "Sidecars, Evidence, and Handoff Topology",
        "Finding Ledger",
        "Bounded Control Depth",
        "Bounded Post-Publication Acceptance",
        "Agent-Principal Norms",
        "Completion Report",
    ]
    require_order(order, expected, errors)
    requirements = {
        "Purpose": ("principal's outcome", "Reviewer satisfaction"),
        "Before Round One: Proportionality Contract": (
            "Closed review universe",
            "Round-trip budget",
            "principal courier crossings",
            "Stop rule",
        ),
        "Roles and Blind-Spot Rotation": (
            "Executor",
            "Adversarial reviewer",
            "Concession is health",
        ),
        "Goal-Focused Round": (
            "Concept sweep",
            "Sufficiency",
            "ship-blocking",
            "ship-improving",
            "risk of shipping now",
            "principal's ruling terminates the loop",
        ),
        "Sidecars, Evidence, and Handoff Topology": (
            "Sidecars are claims",
            "production entry point",
            "enforcing boundary",
            "receipt consumer",
        ),
        "Finding Ledger": (
            "authority label",
            "enforcement outcome",
            "follow-up project",
        ),
        "Bounded Control Depth": (
            "generation N+1",
            "generation N+2",
            "explicit principal decision",
        ),
        "Bounded Post-Publication Acceptance": (
            "second agent",
            "per-artifact matrix",
            "fresh approval",
        ),
        "Agent-Principal Norms": ("known-false claim", "loosening", "Approval fatigue"),
        "Completion Report": ("unverified remainder", "principal outcome"),
    }
    for heading, terms in requirements.items():
        require_terms(sections, heading, terms, errors)
    goal = sections.get("Goal-Focused Round", "")
    for stage in ("1. **Contract.**", "2. **Attack.**", "3. **Disposition.**", "4. **Concept sweep.**", "5. **Sufficiency.**"):
        if stage not in goal:
            errors.append(f"goal-focused round is missing ordered stage {stage!r}")
    return errors


def autopilot_errors(text: str) -> list[str]:
    errors: list[str] = []
    _, sections = section_map(text)
    require_terms(
        sections,
        "Cross-Agent Orchestration",
        (
            "direct session-to-session dispatch",
            "principal courier crossings",
            "round-trip budget",
            "principal's outcome",
            "generation N+1",
            "generation N+2",
        ),
        errors,
    )
    return errors


def router_errors(text: str) -> list[str]:
    errors: list[str] = []
    _, sections = section_map(text)
    require_terms(
        sections,
        "Software engineering and review",
        ("adversarial review", "../synthesis-adversarial-review/SKILL.md"),
        errors,
    )
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(allow_abbrev=False)
    parser.add_argument("--review", required=True, type=pathlib.Path)
    parser.add_argument("--autopilot", required=True, type=pathlib.Path)
    parser.add_argument("--router", required=True, type=pathlib.Path)
    args = parser.parse_args()
    try:
        errors = [
            *review_errors(read(args.review)),
            *autopilot_errors(read(args.autopilot)),
            *router_errors(read(args.router)),
        ]
    except (OSError, ValueError) as exc:
        print(f"protocol diagnostic refused: {exc}", file=sys.stderr)
        return 1
    if errors:
        for error in errors:
            print(f"protocol diagnostic refused: {error}", file=sys.stderr)
        return 1
    print(
        "PASS protocol source structure; not verified: native agent behavior, "
        "review sufficiency, release state, or approval status"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
