"""Fixtures for the intake-routing coverage check.

Origin: a principal directive (evaluate the A2A protocol) was captured in an
intake artifact on 2026-08-25, endorsed in prose, and never routed to
numbered work; nothing warned for four days. The intake itself predicted
this: "not evaluating is the only bad outcome, and it is the one that
happens by default."
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

MODULE_PATH = Path(__file__).with_name("context_doctor.py")
SPEC = importlib.util.spec_from_file_location("context_doctor", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def _project(tmp_path: Path, context: str) -> Path:
    project = tmp_path / "projects" / "alpha"
    (project / "resources" / "artifacts").mkdir(parents=True)
    (project / "CONTEXT.md").write_text(context, encoding="utf-8")
    return project


def _artifact(project: Path, name: str, body: str) -> None:
    (project / "resources" / "artifacts" / name).write_text(
        body, encoding="utf-8"
    )


def test_endorsed_but_unrouted_intake_warns(tmp_path: Path) -> None:
    """The A2A failure shape: captured, endorsed, routed nowhere."""
    project = _project(tmp_path, "**Last session:** 2026-08-29\n\n## Open\n")
    _artifact(
        project,
        "2026-08-25-intake-open-standards.md",
        "# Intake\n\nThe principal directed an evaluation. Strongly agreed.\n",
    )

    assert MODULE.unrouted_intake_findings(project) == [
        "2026-08-25-intake-open-standards.md"
    ]


def test_context_reference_covers_an_intake(tmp_path: Path) -> None:
    project = _project(
        tmp_path,
        "**Last session:** 2026-08-29\n\n"
        "20. [ ] Evaluate per "
        "[the intake](resources/artifacts/2026-08-25-intake-open-standards.md).\n",
    )
    _artifact(
        project,
        "2026-08-25-intake-open-standards.md",
        "# Intake\n\nThe principal directed an evaluation.\n",
    )

    assert MODULE.unrouted_intake_findings(project) == []


def test_terminal_routing_marker_covers_an_intake(tmp_path: Path) -> None:
    project = _project(tmp_path, "**Last session:** 2026-08-29\n")
    _artifact(
        project,
        "2026-08-28-extraction-brief.md",
        "# Brief\n\n**Routed:** CONTEXT item 18, 2026-08-29.\n\nDetail...\n",
    )
    _artifact(
        project,
        "2026-08-25-defect-catalogue.md",
        "# Catalogue\n\n**Declined:** superseded by the shipped review skill.\n",
    )

    assert MODULE.unrouted_intake_findings(project) == []


def test_non_intake_artifacts_are_not_held_to_routing(tmp_path: Path) -> None:
    """Designs, evaluations, and plans are outputs, not asks."""
    project = _project(tmp_path, "**Last session:** 2026-08-29\n")
    _artifact(project, "2026-08-29-a2a-evaluation.md", "# Evaluation\n")
    _artifact(project, "2026-08-26-autopilot-plan.md", "# Plan\n")

    assert MODULE.unrouted_intake_findings(project) == []


def test_marker_must_lead_a_line(tmp_path: Path) -> None:
    """Prose that merely mentions the word Routed is not a routing."""
    project = _project(tmp_path, "**Last session:** 2026-08-29\n")
    _artifact(
        project,
        "2026-08-25-intake-x.md",
        "# Intake\n\nThis should eventually be **Routed:** somewhere.\n",
    )

    assert MODULE.unrouted_intake_findings(project) == [
        "2026-08-25-intake-x.md"
    ]
