#!/usr/bin/env python3
"""Tests for header currency — fixtures derived from the four real defects.

The control this module replaces missed the defect it was built for, twice,
because it had no test derived from a real instance. Every regression fixture
here reproduces an actual on-disk failure, verbatim in the parts that matter.
"""

from __future__ import annotations

from pathlib import Path

from context_currency import (
    STALENESS_KINDS,
    audit_project,
    currency_findings,
    first_ordinals,
    header_incoherence,
    log_state,
)


def staleness(findings: list[dict]) -> list[dict]:
    return [f for f in findings if f["kind"] in STALENESS_KINDS]


def project(tmp_path: Path, context: str, log: str | None) -> Path:
    root = tmp_path / "proj"
    root.mkdir()
    (root / "CONTEXT.md").write_text(context, encoding="utf-8")
    if log is not None:
        (root / "sessions").mkdir()
        (root / "sessions" / "2026-08.md").write_text(log, encoding="utf-8")
    return root


def kinds(findings: list[dict]) -> list[str]:
    return sorted(f["kind"] for f in findings)


# --- Real defect 1: round-10/11 — the union-max masking miss ---------------
# Phase was fresh (Round 11), Last session stale (round 10), and the shipped
# check unioned both fields under max(), so 11 masked 10 and nothing fired.

ROUND_10_11_CONTEXT = """# Publish Article Backlog — Context

**Phase:** Round 11 — 5 article holds and 2 control defects closed; convergence call was wrong
**Status:** Active
**Last session:** 2026-08-23 (Codex adversarial review round 10)
"""

ROUND_10_11_LOG = """# Session Archive

### 2026-08-23 (principal decisions, and the authorship reversal)

body

### 2026-08-23 (Codex adversarial review round 10)

body

### 2026-08-23 (round 11, Claude — round 10 refuted my convergence call)

body
"""


def test_real_defect_round_10_11_stale_last_session_is_not_masked(
    tmp_path: Path,
) -> None:
    root = project(tmp_path, ROUND_10_11_CONTEXT, ROUND_10_11_LOG)

    findings = audit_project(root)

    stale = [f for f in findings if f["kind"] == "header-field-stale"]
    assert len(stale) == 1
    assert stale[0]["field"] == "Last session"
    assert stale[0]["header_ordinal"] == 10 and stale[0]["log_ordinal"] == 11


def test_real_defect_round_10_11_log_current_ignores_trailing_mention(
    tmp_path: Path,
) -> None:
    """'round 11 ... round 10 refuted' must read as round 11, not round 10."""
    root = project(tmp_path, ROUND_10_11_CONTEXT, ROUND_10_11_LOG)

    _, _, current = log_state(root)

    assert current == {"round": 11}


def test_real_defect_round_10_11_reaches_the_doctor_view(tmp_path: Path) -> None:
    root = project(tmp_path, ROUND_10_11_CONTEXT, ROUND_10_11_LOG)

    assert len(currency_findings(root)) == 1


# --- Real defect 2: round-2/3 — both header fields lag the log --------------
# The original same-day miss: dates all equal, ordinals live in prose. Note
# "round-2" is hyphenated on disk; the matcher must accept it.

ROUND_2_3_CONTEXT = """# Publish Article Backlog — Context

**Phase:** Adversarial round 2 complete — challenges adjudicated, repairs attacked
**Status:** Active
**Last session:** 2026-08-23 (Codex round-2 adjudication and repair attack)
"""

ROUND_2_3_LOG = """# Session Archive

### 2026-08-23 (round 2 adjudication, Codex)

body

### 2026-08-23 (round 3, Claude — adversarial cross-agent review)

body
"""


def test_real_defect_round_2_3_flags_both_stale_fields(tmp_path: Path) -> None:
    root = project(tmp_path, ROUND_2_3_CONTEXT, ROUND_2_3_LOG)

    stale = [f for f in audit_project(root) if f["kind"] == "header-field-stale"]

    assert sorted(f["field"] for f in stale) == ["Last session", "Phase"]
    assert all(f["header_ordinal"] == 2 and f["log_ordinal"] == 3 for f in stale)


# --- Real defects 3 and 4: cross-day staleness (rajiv-operations, ----------
# synthesis-console-build). Dates differ; the date check must fire.


def test_real_defect_header_date_behind_log(tmp_path: Path) -> None:
    root = project(
        tmp_path,
        "# P\n\n**Phase:** steady\n**Last session:** 2026-08-19\n",
        "# S\n\n## 2026-08-20: ritual close\n\nbody\n",
    )

    findings = audit_project(root)

    assert kinds(findings) == ["header-behind-log"]
    assert "2026-08-19" in findings[0]["detail"]
    assert "2026-08-20" in findings[0]["detail"]


def test_real_defect_month_boundary_behind(tmp_path: Path) -> None:
    root = project(
        tmp_path,
        "# P\n\n**Last session:** 2026-07-07\n",
        "# S\n\n## 2026-07-08: build session\n\nbody\n",
    )

    assert kinds(audit_project(root)) == ["header-behind-log"]


# --- Coherent and boundary cases -------------------------------------------


def test_coherent_same_day_record_is_clean(tmp_path: Path) -> None:
    root = project(
        tmp_path,
        "# P\n\n**Phase:** Round 11 holding\n"
        "**Last session:** 2026-08-23 (round 11, Claude)\n",
        ROUND_10_11_LOG,
    )

    findings = audit_project(root)

    assert staleness(findings) == []
    # Markerless ordinal-paced records surface a coverage finding, never
    # silence: body currency cannot be verified without markers.
    assert kinds(findings) == ["body-marker-absent"]


def test_header_ahead_of_log_is_not_stale(tmp_path: Path) -> None:
    root = project(
        tmp_path,
        "# P\n\n**Phase:** Round 12 opening\n"
        "**Last session:** 2026-08-24 (round 12)\n",
        ROUND_10_11_LOG,
    )

    findings = audit_project(root)

    assert kinds(findings) == ["body-marker-absent", "header-ahead-of-log"]
    assert currency_findings(root) == []


def test_records_without_ordinals_compare_by_date_only(tmp_path: Path) -> None:
    root = project(
        tmp_path,
        "# P\n\n**Phase:** drafting\n**Last session:** 2026-08-23\n",
        "# S\n\n## 2026-08-23: drafting continued\n\nbody\n",
    )

    assert audit_project(root) == []


def test_families_never_compare_across_each_other(tmp_path: Path) -> None:
    """Phase 2 of a project is not older than round 3 of a review."""
    root = project(
        tmp_path,
        "# P\n\n**Phase:** phase 2 rollout\n**Last session:** 2026-08-23\n",
        "# S\n\n## 2026-08-23 (round 3 review)\n\nbody\n",
    )

    assert staleness(audit_project(root)) == []


def test_wave_family_is_covered(tmp_path: Path) -> None:
    root = project(
        tmp_path,
        "# P\n\n**Phase:** Wave 9 closing\n"
        "**Last session:** 2026-08-23 (wave 9)\n",
        "# S\n\n## 2026-08-23 (wave 10 closeout)\n\nbody\n",
    )

    stale = [f for f in audit_project(root) if f["kind"] == "header-field-stale"]

    assert sorted(f["field"] for f in stale) == ["Last session", "Phase"]


def test_out_of_order_same_date_entries_still_yield_max(tmp_path: Path) -> None:
    """Log current is max over newest-date entries, not the last one listed."""
    log = (
        "# S\n\n### 2026-08-23 (round 11, Claude)\n\nbody\n\n"
        "### 2026-08-23 (round 10, Codex)\n\nbody\n"
    )
    root = project(tmp_path, ROUND_10_11_CONTEXT, log)

    _, _, current = log_state(root)

    assert current == {"round": 11}


# --- Coverage-limit classes stay honest ------------------------------------


def test_unparseable_header_is_a_coverage_limit_not_staleness(
    tmp_path: Path,
) -> None:
    root = project(
        tmp_path,
        "# P\n\n**Status:** Superseded\n",
        "# S\n\n## 2026-08-23: entry\n\nbody\n",
    )

    findings = audit_project(root)

    assert kinds(findings) == ["header-unparseable"]
    assert currency_findings(root) == []


def test_missing_log_is_a_coverage_limit_not_staleness(tmp_path: Path) -> None:
    root = project(tmp_path, "# P\n\n**Last session:** 2026-08-23\n", None)

    assert kinds(audit_project(root)) == ["log-missing"]
    assert currency_findings(root) == []


# --- Ordinal extraction discipline -----------------------------------------


def test_first_ordinal_is_identity_not_max() -> None:
    assert first_ordinals("(round 11, Claude — round 10 refuted)") == {"round": 11}


def test_hyphenated_and_cased_ordinals_match() -> None:
    assert first_ordinals("Codex round-2 adjudication") == {"round": 2}
    assert first_ordinals("Round 11 — closed") == {"round": 11}


def test_embedded_words_and_plurals_do_not_match() -> None:
    assert first_ordinals("background 3 processing") == {}
    assert first_ordinals("rounds 2-3 registered") == {}


# --- Intra-header coherence (the write-time guard's primitive) --------------


def test_header_incoherence_names_the_disagreeing_family() -> None:
    assert header_incoherence(ROUND_10_11_CONTEXT) == [("round", 11, 10)]


def test_coherent_header_reports_nothing() -> None:
    text = "**Phase:** Round 11 done\n**Last session:** 2026-08-23 (round 11)\n"
    assert header_incoherence(text) == []


def test_header_incoherence_ignores_disjoint_families() -> None:
    text = "**Phase:** phase 2 rollout\n**Last session:** 2026-08-23 (round 9)\n"
    assert header_incoherence(text) == []


# --- CLI zero-scan refusal (2026-08-24 fail-open) ---------------------------


def _run_cli(tmp_path: Path, target: Path) -> "subprocess.CompletedProcess[str]":
    import subprocess
    import sys

    script = Path(__file__).with_name("context_currency.py")
    return subprocess.run(
        [sys.executable, str(script), str(target)],
        capture_output=True, text=True,
    )


def test_zero_scan_fails_closed(tmp_path: Path) -> None:
    """Pointed at a directory holding no project records, the audit must
    refuse (exit 2), never print a green zero-finding result — the real
    misuse was passing a project's own subtree and reading 'clean'."""
    empty = tmp_path / "not-a-projects-root"
    (empty / "drafts").mkdir(parents=True)
    completed = _run_cli(tmp_path, empty)
    assert completed.returncode == 2
    assert "no project records scanned" in completed.stderr


def test_project_directory_is_accepted_directly(tmp_path: Path) -> None:
    """The sibling doctor takes --project <dir>; passing the same shape
    here must audit that record instead of scanning nothing."""
    project = tmp_path / "some-project"
    project.mkdir()
    (project / "CONTEXT.md").write_text(
        "**Phase:** Round 2 done\n**Last session:** 2026-08-23 (round 2)\n",
        encoding="utf-8",
    )
    sessions = project / "sessions"
    sessions.mkdir()
    (sessions / "2026-08.md").write_text(
        "### 2026-08-23 (round 2)\nwork\n", encoding="utf-8",
    )
    completed = _run_cli(tmp_path, project)
    # The record IS audited (its markerless body is a legitimate finding);
    # the defect under test was scanning nothing and reporting clean.
    assert completed.returncode != 2
    assert "scanned 1 project record(s)" in completed.stdout
