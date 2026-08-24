#!/usr/bin/env python3
"""Body-currency regressions — fixtures from the three real occurrences.

Acceptance rule set by the third occurrence's escalation: a fixture set that
does not flag the state found at current HEAD is not a fix. Occurrence 3 is
therefore encoded verbatim from the live record (repo `d918071d`), in both
its literal markerless form (which must surface a coverage finding, because
unmarked prose cannot be judged for truth) and its marked form (which must be
a staleness defect).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from context_currency import audit_project, body_markers
from context_edit import ContextEditError, replace_once, set_field


def project(tmp_path: Path, context: str, log: str) -> Path:
    root = tmp_path / "proj"
    root.mkdir()
    (root / "CONTEXT.md").write_text(context, encoding="utf-8")
    (root / "sessions").mkdir()
    (root / "sessions" / "2026-08.md").write_text(log, encoding="utf-8")
    return root


def kinds(findings: list[dict]) -> list[str]:
    return sorted(f["kind"] for f in findings)


# --- Occurrence 3, verbatim from HEAD d918071d ------------------------------
# Header and log both current at round 14; the body still routes the next
# agent to the three holds that round 14 closed or re-scoped.

OCC3_HEADER = """# Publish Article Backlog — Context

**Phase:** Round 14 — all 30 article bodies quality-clear; controls repaired, one contract change open
**Status:** Active
**Last session:** 2026-08-24 (round 14: all 30 bodies clear; gate re-scoped with a build authority)

## Current State

Set A wrote 30 articles across staging, builds, and the 455-post calendar.
Three non-article holds remain: the promotion gate has a marker-view defect,
the schedule authority labels are incomplete, and the source-grade rows are
uncorrected.
{marker}
## What's Next

0. [ ] **Set A — repair and independently re-verify three control/evidence
   holds.** All three controls/evidence defects hold the program; nothing
   publishes until they clear.
"""

OCC3_LOG = """# Session Archive

### 2026-08-24 (Codex adversarial review round 13)

body

### 2026-08-24 (round 14, Claude — all 30 bodies clear; gate re-scoped with a build authority)

body
"""


def test_occurrence_3_literal_head_state_is_not_silent(tmp_path: Path) -> None:
    """The exact HEAD state: markerless stale prose under a current header.

    Unmarked prose cannot be judged for truth — pretending otherwise would be
    this control's own unverified claim. What the check CAN do is refuse to
    stay silent: the record must surface as unverifiable, never as clean.
    """
    root = project(tmp_path, OCC3_HEADER.format(marker=""), OCC3_LOG)

    findings = audit_project(root)

    assert kinds(findings) == ["body-marker-absent"]


def test_occurrence_3_with_the_marker_it_would_have_carried(
    tmp_path: Path,
) -> None:
    """The same body, marked as of round 13 when it was last true, is a
    staleness defect against the round-14 log — while every header check
    passes."""
    marked = OCC3_HEADER.format(marker="\n*State as of: 2026-08-24 (round 13)*\n")
    root = project(tmp_path, marked, OCC3_LOG)

    findings = audit_project(root)

    stale = [f for f in findings if f["kind"] == "body-marker-stale"]
    assert len(stale) == 1
    assert stale[0]["section"] == "Current State"
    assert not any(f["kind"].startswith("header-") for f in findings)


def test_occurrence_3_current_marker_is_clean(tmp_path: Path) -> None:
    marked = OCC3_HEADER.format(marker="\n*State as of: 2026-08-24 (round 14)*\n")
    root = project(tmp_path, marked, OCC3_LOG)

    assert kinds(audit_project(root)) == []


# --- Occurrences 1 and 2: header and body stale together --------------------


def test_occurrence_1_shape_body_and_header_both_stale(tmp_path: Path) -> None:
    context = (
        "# P\n\n**Phase:** Adversarial round 2 complete\n"
        "**Last session:** 2026-08-23 (round 2)\n\n"
        "## Current State\n\nRound 2 repairs are under review.\n\n"
        "*State as of: 2026-08-23 (round 2)*\n"
    )
    log = "# S\n\n### 2026-08-23 (round 3, Claude)\n\nbody\n"
    root = project(tmp_path, context, log)

    findings = audit_project(root)

    assert "body-marker-stale" in kinds(findings)
    assert "header-field-stale" in kinds(findings)


# --- The write-time control that would have stopped all three ---------------

GATED = """# P

**Phase:** Round 13 review complete
**Status:** Active
**Last session:** 2026-08-24 (round 13)

## Current State

Round 13 findings are being repaired.

*State as of: 2026-08-24 (round 13)*
"""


def test_header_advance_over_lagging_body_is_refused(tmp_path: Path) -> None:
    """In all three occurrences the agent advanced the header and stopped.
    This is the control that interrupts exactly that motion."""
    path = tmp_path / "CONTEXT.md"
    path.write_text(GATED, encoding="utf-8")
    before = path.read_text(encoding="utf-8")

    with pytest.raises(ContextEditError, match="body lags"):
        set_field(
            path,
            field="Last session",
            value="2026-08-24 (round 14: bodies clear)",
        )

    assert path.read_text(encoding="utf-8") == before


def test_header_advance_with_body_updated_in_same_edit_passes(
    tmp_path: Path,
) -> None:
    path = tmp_path / "CONTEXT.md"
    path.write_text(GATED, encoding="utf-8")

    result = replace_once(
        path,
        anchor=(
            "**Last session:** 2026-08-24 (round 13)\n\n## Current State\n\n"
            "Round 13 findings are being repaired.\n\n"
            "*State as of: 2026-08-24 (round 13)*"
        ),
        replacement=(
            "**Last session:** 2026-08-24 (round 14)\n\n## Current State\n\n"
            "Round 14 closed the review; one contract change remains open.\n\n"
            "*State as of: 2026-08-24 (round 14)*"
        ),
    )

    assert "as-of markers current" in (result["note"] or "")


def test_allow_stale_body_records_the_override(tmp_path: Path) -> None:
    path = tmp_path / "CONTEXT.md"
    path.write_text(GATED, encoding="utf-8")

    result = set_field(
        path,
        field="Last session",
        value="2026-08-24 (round 14: bodies clear)",
        allow_stale_body=True,
    )

    assert "override --allow-stale-body recorded" in (result["note"] or "")


def test_marker_bump_with_unchanged_prose_requires_state_reviewed(
    tmp_path: Path,
) -> None:
    """Bumping the marker as mechanically as the header would recreate the
    defect one level down; the flag converts a silent bump into a recorded
    assertion."""
    path = tmp_path / "CONTEXT.md"
    path.write_text(GATED, encoding="utf-8")

    with pytest.raises(ContextEditError, match="prose is unchanged"):
        replace_once(
            path,
            anchor="*State as of: 2026-08-24 (round 13)*",
            replacement="*State as of: 2026-08-24 (round 14)*",
        )

    result = replace_once(
        path,
        anchor="*State as of: 2026-08-24 (round 13)*",
        replacement="*State as of: 2026-08-24 (round 14)*",
        state_reviewed=True,
    )

    assert "reviewed-no-change recorded" in (result["note"] or "")


def test_completion_signal_names_missing_markers(tmp_path: Path) -> None:
    """The honest completion signal: success output must name what it did not
    verify, because an unqualified success message manufactures completion
    for partial work."""
    path = tmp_path / "CONTEXT.md"
    path.write_text(
        "# P\n\n**Phase:** Round 13 done\n"
        "**Last session:** 2026-08-24 (round 13)\n\n## Current State\n\n"
        "prose without a marker\n",
        encoding="utf-8",
    )

    result = set_field(path, field="Phase", value="Round 13 done and recorded")

    assert "body currency unverifiable" in (result["note"] or "")


def test_marker_parsing_attributes_sections(tmp_path: Path) -> None:
    text = GATED
    markers = body_markers(text)

    assert [(m["section"], m["date"]) for m in markers] == [
        ("Current State", "2026-08-24")
    ]
    assert markers[0]["ordinals"] == {"round": 13}
