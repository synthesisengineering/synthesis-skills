"""Tests for prep_lint.py — the meeting-prep content-contract backstop."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from prep_lint import lint  # noqa: E402

CLEAN_PACK = """\
# Rivera 1:1 — Tue, 13:00 ET

*Peer executive, non-technical. Cares about her org and the partnership.*

Basis: 2026-09-14 transcript with Rivera; #product channel 09-12/09-14; principal notes 09-15.

## Open with

- The tools are used daily now by people outside our team.

## Credit

- **Jamie Park** wrote down how our content data flows, end to end.

## Where things stand

- Closed a gap where internal-only pages were publicly reachable.
- Adoption is uneven across teams given the same tools.

## Decisions

- Reimburse the past charges. The filing route was blocked.

## Ask them

- What does she need from me or my team?

## Don't raise

Reductions in her group. Vendor scores.
"""

FORUM_PACK = """\
# Quarterly forum talking points

*Forum of 40, mixed technical depth. Decide the roadmap.*

Basis: roadmap draft v3 09-15; forum transcript 06-20.

## Open with

- Jordan and I were talking about the roadmap timeline.

## Where things stand

- Three launches shipped since June.

## Don't raise

Unannounced personnel changes.
"""


def codes(text: str, **kwargs: str) -> set[str]:
    return {f.code for f in lint(text, **kwargs)}


def test_clean_pack_passes() -> None:
    assert lint(CLEAN_PACK) == []


def test_body_avoid_language_flagged() -> None:
    pack = CLEAN_PACK.replace(
        "## Ask them",
        "## Discussion\n\n- Don't mention the outage timeline.\n\n## Ask them",
    )
    findings = lint(pack)
    assert any(f.code == "R1" and "body section" in f.message for f in findings)


def test_footer_not_last_flagged() -> None:
    pack = CLEAN_PACK.replace("## Don't raise", "## Don't raise", 1)
    pack = pack.replace("## Ask them", "## Don't raise\n\nVendor scores.\n\n## Ask them")
    # remove the original trailing footer so the mid-doc one is the footer
    pack = pack.replace("## Don't raise\n\nReductions in her group. Vendor scores.\n", "")
    findings = lint(pack)
    assert any(f.code == "R1" and "not the last section" in f.message for f in findings)


def test_bold_trailing_footer_counts() -> None:
    pack = CLEAN_PACK.replace(
        "## Don't raise\n\nReductions in her group. Vendor scores.\n",
        "**Don't raise unless she does:** reductions in her group.\n",
    )
    assert "R1" not in codes(pack)


def test_ticket_number_flagged_for_nontechnical_reader() -> None:
    pack = CLEAN_PACK.replace(
        "Closed a gap where internal-only pages were publicly reachable.",
        "Closed PGS-1042 where internal-only pages were publicly reachable.",
    )
    findings = lint(pack, reader="nontechnical")
    assert any(f.code == "R2" and "PGS-1042" in f.message for f in findings)


def test_ticket_number_allowed_for_technical_reader() -> None:
    pack = CLEAN_PACK.replace(
        "Closed a gap where internal-only pages were publicly reachable.",
        "Closed PGS-1042 where internal-only pages were publicly reachable.",
    )
    assert "R2" not in codes(pack, reader="technical")


def test_reader_auto_detects_nontechnical() -> None:
    pack = CLEAN_PACK.replace(
        "Closed a gap where internal-only pages were publicly reachable.",
        "Closed PGS-1042 where internal-only pages were publicly reachable.",
    )
    # The pack's own reader line says non-technical; auto must catch it.
    assert "R2" in codes(pack)


def test_infra_term_flagged_for_nontechnical_reader() -> None:
    pack = CLEAN_PACK.replace(
        "Adoption is uneven across teams given the same tools.",
        "Cut the bundle size in half for the same tools.",
    )
    assert "R2" in codes(pack, reader="nontechnical")


def test_announcing_opener_flagged() -> None:
    pack = CLEAN_PACK.replace(
        "The tools are used daily now by people outside our team.",
        "One thing that's changed is daily use outside our team.",
    )
    assert "R7b" in codes(pack)


def test_x_not_y_flagged() -> None:
    pack = CLEAN_PACK.replace(
        "The tools are used daily now by people outside our team.",
        "The rollout is a management question, not a technology one.",
    )
    assert "R7b" in codes(pack)


def test_namedrop_opener_flagged_in_forum() -> None:
    findings = lint(FORUM_PACK, room="forum")
    assert any(f.code == "R7c" for f in findings)


def test_namedrop_opener_allowed_in_small_room() -> None:
    assert "R7c" not in codes(FORUM_PACK, room="1:1")


def test_invented_precision_flagged() -> None:
    pack = CLEAN_PACK.replace(
        "Adoption is uneven across teams given the same tools.",
        "Adoption is wildly uneven across teams given the same tools.",
    )
    findings = lint(pack)
    assert any(f.code == "R7" and "wildly" in f.message for f in findings)


def test_missing_basis_flagged() -> None:
    pack = "\n".join(line for line in CLEAN_PACK.splitlines() if not line.startswith("Basis:"))
    assert "R10" in codes(pack)


def test_cli_exit_codes(tmp_path: Path) -> None:
    script = Path(__file__).resolve().parent / "prep_lint.py"
    clean = tmp_path / "clean.md"
    clean.write_text(CLEAN_PACK, encoding="utf-8")
    ok = subprocess.run(
        [sys.executable, str(script), str(clean)], capture_output=True, text=True
    )
    assert ok.returncode == 0, ok.stdout
    dirty = tmp_path / "dirty.md"
    dirty.write_text(CLEAN_PACK.replace("Basis:", "Sources:"), encoding="utf-8")
    bad = subprocess.run(
        [sys.executable, str(script), str(dirty)], capture_output=True, text=True
    )
    assert bad.returncode == 1
    assert "R10" in bad.stdout
