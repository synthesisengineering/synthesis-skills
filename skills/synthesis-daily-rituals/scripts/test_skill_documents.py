"""Budget and structure contracts for the daily-rituals and slack-sync documents.

AGENTS.md rule 4: keep SKILL.md below 500 lines; detailed material lives in
references/. On 2026-09-01 both documents were restructured (1,319 and 762
lines): version history, formats, worked examples, and rationale moved into
references while every operating rule and checklist step stayed. These tests
pin the budget, keep load-bearing rule anchors in the main documents, verify
that each moved block still exists in its reference, and refuse orphaned
references or templates — so regrowth fails CI instead of accumulating.

slack-sync has no scripts directory in CI; its contract lives here beside the
daily-rituals tests, in the CI group both skills share.
"""

from __future__ import annotations

from pathlib import Path

SKILLS_ROOT = Path(__file__).resolve().parents[2]
RITUALS = SKILLS_ROOT / "synthesis-daily-rituals"
SLACK = SKILLS_ROOT / "synthesis-slack-sync"
BUDGET = 500


def _document(skill_dir: Path) -> str:
    return (skill_dir / "SKILL.md").read_text(encoding="utf-8")


def _assert_budget(skill_dir: Path) -> str:
    text = _document(skill_dir)
    count = len(text.splitlines())
    assert count < BUDGET, f"{skill_dir.name}/SKILL.md is {count} lines; the budget is <{BUDGET}"
    return text


def _assert_anchors(text: str, anchors: tuple[str, ...], name: str) -> None:
    for anchor in anchors:
        assert anchor in text, f"load-bearing rule left {name}/SKILL.md: {anchor}"


def _assert_moved_blocks(skill_dir: Path, moved: tuple[tuple[str, str], ...]) -> None:
    for reference_name, marker in moved:
        reference = (skill_dir / "references" / reference_name).read_text(encoding="utf-8")
        assert marker in reference, f"moved block missing from {reference_name}: {marker}"


def _assert_no_orphans(skill_dir: Path, text: str, subdirs: tuple[str, ...]) -> None:
    for subdir in subdirs:
        for path in sorted((skill_dir / subdir).glob("*.md")):
            assert path.name in text, f"unlinked {subdir} file: {path.name}"


# --- synthesis-daily-rituals ---------------------------------------------------------------


def test_rituals_skill_document_stays_within_repo_budget() -> None:
    text = _assert_budget(RITUALS)
    _assert_anchors(
        text,
        (
            "### 1. Temporal & State Verification",
            "Archive FIRST, delete second",
            "#### 3b. Channel Sync",
            "Watermark gate",
            "## Mid-Day Sync Protocol",
            "re-reads every declared target",
            "### Day-End Modes",
            "send-or-release pass",
            "### 11. Remote Readiness and Final Verification",
            "The desk is the registry's `desk_seat`",
            "The coverage line is mandatory",
            "Alert-confidentiality rule",
            "Investigate first, ask questions later",
            "Preserve all information, reorganize for clarity",
            "item-currency",  # synthesis-context-lifecycle/test_item_currency.py depends on it
        ),
        "synthesis-daily-rituals",
    )


def test_rituals_moved_blocks_survive_in_their_references() -> None:
    _assert_moved_blocks(
        RITUALS,
        (
            ("version-history.md", "## v2.30.0 — Watermarks carry a time and a target"),
            ("version-history.md", "v2.27.0 (2026-08-27) replaces run-anchored sync windows"),
            ("version-history.md", "lead_time_preps:"),
            ("version-history.md", "streak_day_end"),
            ("version-history.md", "Budget before backlog"),
            ("version-history.md", "## v2.3.0 — Workspace-Rooted Paths"),
            ("version-history.md", "Match the horizon to what the item is"),
            ("version-history.md", "**Idempotency:**"),
            ("version-history.md", "Dependency-ordered"),
            ("plan-format.md", "### Canonical Section Vocabulary (Authoritative)"),
            ("plan-format.md", "### Internal Structure Conventions"),
            ("plan-format.md", "### File Revert Protection"),
            ("draft-grounding.md", "### Investigate First, Ask Questions Later"),
            ("draft-grounding.md", "Blank line after every bullet"),
            ("draft-grounding.md", "### Temporal Integrity"),
            ("draft-grounding.md", "### Pre-Send Review Gate"),
            ("draft-grounding.md", "### Appreciation Message Quality"),
        ),
    )


def test_rituals_references_are_all_linked() -> None:
    _assert_no_orphans(RITUALS, _document(RITUALS), ("references",))


# --- synthesis-slack-sync -----------------------------------------------------------------------


def test_slack_sync_skill_document_stays_within_repo_budget() -> None:
    text = _assert_budget(SLACK)
    _assert_anchors(
        text,
        (
            "## ⛔ NEVER Use Slack Search API for Lookups",
            "A zero-result search is NEVER evidence of absence",
            "### Step 0: Preflight",
            "### Step 2: Re-read ALL active threads",
            "WINDOW_OLDEST",
            "RESOLVED_CONVERSATION_ID",
            "sync_watermark.py advance",
            "own outbound",
            "#### Draft Message Format (MANDATORY)",
            "## Provenance Discipline",
            "Always record the TS",
            "never invent a domain",
        ),
        "synthesis-slack-sync",
    )


def test_slack_sync_moved_blocks_survive_in_their_references() -> None:
    _assert_moved_blocks(
        SLACK,
        (
            ("version-history.md", "## v3.8.0 — Windows are computed"),
            ("version-history.md", "v3.6.0 (2026-08-27) fixes a class of bug"),
            ("version-history.md", "### `-private` Discovery Protocol (ADR-014)"),
            ("version-history.md", "## v3.0.0 — Per-Channel-Per-Day Layout"),
            ("version-history.md", "## Why Each Step Matters"),
            ("transcript-formats.md", "### Channel file (`slack/YYYY-MM-DD/<channel>.md`)"),
            ("transcript-formats.md", "### DMs aggregator file"),
            ("transcript-formats.md", "## Slack Permalink Construction"),
            ("transcript-formats.md", "### Retrofitting older daily plans"),
        ),
    )


def test_slack_sync_references_and_templates_are_all_linked() -> None:
    _assert_no_orphans(SLACK, _document(SLACK), ("references", "templates"))
