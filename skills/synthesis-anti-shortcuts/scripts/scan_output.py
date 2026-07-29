#!/usr/bin/env python3
"""
scan_output.py — Lazy-shortcut antipattern scanner.

Detects costume-vocabulary phrases that signal the lazy-shortcut antipattern
in AI-assistant output. Reads text from stdin or a file argument, scans it
against a catalog of phrases organized by category, and reports each detection
with a suggested rewrite framing.

Designed to run standalone from a terminal, as a hook in any agent platform
(Claude Code, Codex, Cursor, GitHub Copilot, or any other agent that can
shell out), or as a CI step on PR descriptions and design documents.

Companion to the methodology at:
  github.com/synthesisengineering/synthesis-skills/skills/synthesis-anti-shortcuts

Zero required external dependencies — Python 3.8+ stdlib is sufficient. The
optional --catalog flag accepts a YAML file (requires PyYAML); without it,
the scanner uses an embedded baseline catalog.

Exit codes:
  0 — Clean (no detections)
  1 — One or more detections found
  2 — Error (e.g., unreadable input, malformed catalog)

Examples:

  # Scan stdin
  echo "We can revisit this for now." | ./scan_output.py

  # Scan a file
  ./scan_output.py draft.md

  # Use a custom catalog (requires PyYAML)
  ./scan_output.py --catalog ~/.synthesis/anti-shortcut-catalog.yaml draft.md

  # JSON output for programmatic consumption
  ./scan_output.py --json draft.md

  # Quiet (exit code only, no stdout) — for hooks
  ./scan_output.py --quiet draft.md

  # Show context window around each hit (default 80 chars)
  ./scan_output.py --context 120 draft.md

License: Apache-2.0
SPDX-License-Identifier: Apache-2.0
"""

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Iterable, Optional


# -----------------------------------------------------------------------------
# Embedded baseline catalog
#
# Mirrors the phrase set in the public anti-shortcut catalog. Public references
# point at case-studies.md within this skill rather than at incident-specific
# lesson files. The catalog can be overridden by passing --catalog <yaml>.
#
# Each entry: id, phrase, match, category, [exempt_when], rationale,
# [replacement], [case_ref].
# -----------------------------------------------------------------------------

CATEGORIES = {
    "backward_compat": (
        "Preserving old APIs / paths / behaviors when the user has stated "
        "breaking changes are fine."
    ),
    "minimal_diff": (
        "Leaving half-applied work as a follow-up. Surfaces as residual styling, "
        "residual stale references, half-migrated code."
    ),
    "asking_as_shortcut": (
        "Surfacing decisions as questions when the user's stated constraints "
        "already determine the answer."
    ),
    "deferral": (
        "Pushing real work to 'later' / 'follow-up' / 'next phase' when the "
        "user has explicitly said 'complete this, no shortcuts.'"
    ),
    "archive_value": (
        "Leaving stale content under labels like 'archive' or 'historical "
        "reference' when the user wants clean public-facing artifacts."
    ),
    "dismissal": (
        "Dismissing user-raised concerns as 'not a real issue' or 'theoretical' "
        "instead of solving them."
    ),
    "scope_excuse": (
        "Using 'pre-existing' / 'out of scope' / 'not introduced by this change' "
        "to avoid fixing problems in code being actively modified."
    ),
}


EMBEDDED_PHRASES = [
    # -- backward_compat --
    {
        "id": "bc_backward_compatible",
        "phrase": "backward compatible",
        "match": "literal",
        "category": "backward_compat",
        "exempt_when": [r'"backward compat',  r"the phrase backward compat"],
        "rationale": "Preserves old APIs after user has said breaking changes are fine.",
        "replacement": "Name the clean refactor that updates all consumers.",
        "case_ref": "case-studies.md#case-1",
    },
    {
        "id": "bc_preserves_existing",
        "phrase": "preserves existing",
        "match": "literal",
        "category": "backward_compat",
        "rationale": "Justifies a shim or partial migration by what it preserves.",
        "replacement": "Name what the change accomplishes for the new architecture.",
        "case_ref": "case-studies.md#case-1",
    },
    {
        "id": "bc_shim_layer",
        "phrase": "shim layer",
        "match": "literal",
        "category": "backward_compat",
        "rationale": "Compatibility shims preserve old import paths or APIs.",
        "replacement": "Update the consumers; the work is mechanical and bounded.",
        "case_ref": "case-studies.md#case-1",
    },
    {
        "id": "bc_easier_rollback",
        "phrase": "easier rollback",
        "match": "literal",
        "category": "backward_compat",
        "rationale": "Optimizes for the failure scenario instead of the success one.",
        "replacement": "Name the architectural improvement the change delivers.",
        "case_ref": "case-studies.md#case-1",
    },
    {
        "id": "bc_lower_risk_of_breaking",
        "phrase": "lower risk of breaking",
        "match": "literal",
        "category": "backward_compat",
        "rationale": "User has stated breaking changes are acceptable.",
        "replacement": "Name the completeness criterion instead.",
        "case_ref": "case-studies.md#case-1",
    },
    {
        "id": "bc_no_breaking_changes",
        "phrase": "no breaking changes",
        "match": "literal",
        "category": "backward_compat",
        "rationale": "Imposes a constraint the user did not state.",
        "replacement": "List the specific breaking changes and what consumers update to.",
        "case_ref": "case-studies.md#case-1",
    },

    # -- minimal_diff --
    {
        "id": "md_minimal_diff",
        "phrase": "minimal diff",
        "match": "literal",
        "category": "minimal_diff",
        "exempt_when": [r'"minimal diff"', r"phrase like 'minimal diff'"],
        "rationale": "License to leave half-applied work as a follow-up.",
        "replacement": "Name the full semantic scope; diff size is a consequence, not a constraint.",
        "case_ref": "case-studies.md#case-2",
    },
    {
        "id": "md_keep_changes_minimal",
        "phrase": "keep changes minimal",
        "match": "literal",
        "category": "minimal_diff",
        "rationale": "Same pattern, gerund form.",
        "replacement": "Define the work in terms of outcomes, not diff size.",
        "case_ref": "case-studies.md#case-2",
    },
    {
        "id": "md_tinting_not_redesigning",
        "phrase": "tinting not redesigning",
        "match": "literal",
        "category": "minimal_diff",
        "rationale": "Pre-licenses a partial pass in dispatch briefs.",
        "replacement": "Apply the change everywhere it semantically belongs.",
        "case_ref": "case-studies.md#case-2",
    },
    {
        "id": "md_low_risk_change",
        "phrase": "low risk change",
        "match": "literal",
        "category": "minimal_diff",
        "rationale": "Optimizing for risk minimization when completeness was the goal.",
        "replacement": "Name the completeness criterion explicitly.",
        "case_ref": "case-studies.md#case-2",
    },
    {
        "id": "md_preserve_existing_layout",
        "phrase": "preserve existing layout",
        "match": "literal",
        "category": "minimal_diff",
        "rationale": "Licenses sub-agents to leave design problems untouched.",
        "replacement": "'The existing layout is the canvas; the new layer is X.'",
        "case_ref": "case-studies.md#case-2",
    },
    {
        "id": "md_light_touch",
        "phrase": "light touch",
        "match": "literal",
        "category": "minimal_diff",
        "rationale": "Vocabulary that pre-licenses a partial pass.",
        "replacement": "State the job's actual size.",
        "case_ref": "case-studies.md#case-2",
    },
    {
        "id": "md_surgical_change",
        "phrase": "surgical change",
        "match": "literal",
        "category": "minimal_diff",
        "rationale": "Vocabulary that pre-licenses a partial pass.",
        "replacement": "Fix the root cause; if design issues touch the fix, fix them too.",
        "case_ref": "case-studies.md#case-2",
    },

    # -- asking_as_shortcut --
    {
        "id": "as_recommendation_colon",
        # Specifically the question-shaped 'Recommendation:' in agent output.
        "phrase": r"\brecommendation:\s",
        "match": "regex",
        "category": "asking_as_shortcut",
        "exempt_when": [
            r"recommendation:\s+see",      # references
            r"recommendation:\s+read",
            r"recommended reading",
            r"his recommendation",
            r"their recommendation",
        ],
        "rationale": "'Recommendation: X. Your call?' framing when X is constraint-determined.",
        "replacement": "Execute on the constraint-determined answer; report what was done.",
        "case_ref": "case-studies.md#case-3",
    },
    {
        "id": "as_your_call",
        "phrase": "your call",
        "match": "literal",
        "category": "asking_as_shortcut",
        "rationale": "Surfaces a decision as the user's call when constraints decide it.",
        "replacement": "Execute on the constraint-determined answer.",
        "case_ref": "case-studies.md#case-3",
    },
    {
        "id": "as_up_to_you",
        "phrase": "up to you",
        "match": "literal",
        "category": "asking_as_shortcut",
        "rationale": "Same offloading pattern in a softer register.",
        "replacement": "Execute; tell the user what was done.",
        "case_ref": "case-studies.md#case-3",
    },
    {
        "id": "as_should_i_do_x",
        "phrase": r"\bshould I (do|use|build|pick|choose|select|remove|delete|keep|leave)\b",
        "match": "regex",
        "category": "asking_as_shortcut",
        "rationale": "Should-I questions are legitimate only when constraints leave a real open.",
        "replacement": "Scan constraints first; if determined, execute.",
        "case_ref": "case-studies.md#case-3",
    },
    {
        "id": "as_would_you_like",
        "phrase": r"would you like me to",
        "match": "regex",
        "category": "asking_as_shortcut",
        "rationale": "Softer offloading pattern.",
        "replacement": "Scan constraints; execute if determined.",
        "case_ref": "case-studies.md#case-3",
    },

    # -- deferral --
    {
        "id": "df_for_now",
        "phrase": r"\bfor now[,.\s]",
        "match": "regex",
        "category": "deferral",
        "rationale": "Classic deferral. Banned when user has said 'complete this, no shortcuts.'",
        "replacement": "Do the work, or name a concrete scope split with cuts.",
        "case_ref": "case-studies.md#case-4",
    },
    {
        "id": "df_as_a_first_pass",
        "phrase": "as a first pass",
        "match": "literal",
        "category": "deferral",
        "rationale": "Implies a follow-up pass that often never happens.",
        "replacement": "Name the complete version.",
        "case_ref": "case-studies.md#case-4",
    },
    {
        "id": "df_as_a_starting_point",
        "phrase": "as a starting point",
        "match": "literal",
        "category": "deferral",
        "rationale": "Same pattern, different phrasing.",
        "replacement": "Name the complete version.",
        "case_ref": "case-studies.md#case-4",
    },
    {
        "id": "df_can_revisit_later",
        "phrase": "can revisit later",
        "match": "literal",
        "category": "deferral",
        "rationale": "The revisit is not on anyone's calendar.",
        "replacement": "Do it now or name the specific trigger.",
        "case_ref": "case-studies.md#case-4",
    },
    {
        "id": "df_revisit_later",
        "phrase": "revisit later",
        "match": "literal",
        "category": "deferral",
        "rationale": "Same pattern, terser phrasing.",
        "replacement": "Do it now or name the specific trigger.",
        "case_ref": "case-studies.md#case-4",
    },
    {
        "id": "df_follow_up_orchestrator",
        "phrase": "follow-up the orchestrator can request",
        "match": "literal",
        "category": "deferral",
        "rationale": "Sub-agent report costume that licenses leaving work undone.",
        "replacement": "Orchestrator finishes the work in-session.",
        "case_ref": "case-studies.md#case-2",
    },
    {
        "id": "df_leave_for_follow_up",
        "phrase": r"leave (for|as) (a |the )?follow-up",
        "match": "regex",
        "category": "deferral",
        "rationale": "Explicit deferral language.",
        "replacement": "Finish in-session.",
        "case_ref": "case-studies.md#case-2",
    },
    {
        "id": "df_tackle_in_a_follow_up",
        "phrase": "tackle in a follow-up",
        "match": "literal",
        "category": "deferral",
        "rationale": "Same pattern, different verb.",
        "replacement": "Finish in-session.",
        "case_ref": "case-studies.md#case-4",
    },
    {
        "id": "df_future_session",
        "phrase": "future session",
        "match": "literal",
        "category": "deferral",
        "rationale": "Distances work from the current session.",
        "replacement": "Name the work and do it.",
        "case_ref": "case-studies.md#case-4",
    },
    {
        "id": "df_next_phase",
        "phrase": "next phase",
        "match": "literal",
        "category": "deferral",
        "rationale": "Phase boundary often invoked as deferral cover.",
        "replacement": "Name the work and the trigger that makes it phase-N work, not phase-(N+1) work.",
        "case_ref": "case-studies.md#case-4",
    },
    {
        "id": "df_in_the_interim",
        "phrase": "in the interim",
        "match": "literal",
        "category": "deferral",
        "rationale": "Distancing vocabulary.",
        "replacement": "Present-tense action or concrete scheduling.",
        "case_ref": "case-studies.md#case-4",
    },
    {
        "id": "df_audit_later",
        "phrase": "audit later",
        "match": "literal",
        "category": "deferral",
        "rationale": "Explicit deferral.",
        "replacement": "Audit now.",
        "case_ref": "case-studies.md#case-4",
    },
    {
        "id": "df_handle_later",
        "phrase": "handle later",
        "match": "literal",
        "category": "deferral",
        "rationale": "Explicit deferral.",
        "replacement": "Handle now or name the specific blocker.",
        "case_ref": "case-studies.md#case-4",
    },
    {
        "id": "df_we_can_defer",
        "phrase": "we can defer",
        "match": "literal",
        "category": "deferral",
        "rationale": "Explicit deferral.",
        "replacement": "Name a concrete reason if real, otherwise execute.",
        "case_ref": "case-studies.md#case-4",
    },
    {
        "id": "df_well_tackle",
        "phrase": r"we'?ll tackle",
        "match": "regex",
        "category": "deferral",
        "rationale": "Future-tense vagueness covering present-tense avoidance.",
        "replacement": "Present-tense action or concrete scheduling.",
        "case_ref": "case-studies.md#case-4",
    },

    # -- archive_value --
    {
        "id": "av_archive_value",
        "phrase": "archive value",
        "match": "literal",
        "category": "archive_value",
        "rationale": "Excuse for leaving stale content; git history is the real archive.",
        "replacement": "Delete the stale content.",
        "case_ref": "case-studies.md#case-5",
    },
    {
        "id": "av_historical_archive",
        "phrase": "historical archive",
        "match": "literal",
        "category": "archive_value",
        "rationale": "Same pattern.",
        "replacement": "Delete; git history serves the archival role.",
        "case_ref": "case-studies.md#case-5",
    },
    {
        "id": "av_historical_reference",
        "phrase": "historical reference",
        "match": "literal",
        "category": "archive_value",
        "exempt_when": [
            r"historical reference (frame|article|piece|implementation)",
        ],
        "rationale": "Often a costume for 'I left it because deleting was work.'",
        "replacement": "Delete and rely on git history, or rewrite as current-context commentary.",
        "case_ref": "case-studies.md#case-5",
    },
    {
        "id": "av_as_is_for_legacy",
        "phrase": "as-is for legacy",
        "match": "literal",
        "category": "archive_value",
        "rationale": "Invokes legacy as permission to leave alone.",
        "replacement": "Identify the actual constraint; if none, update.",
        "case_ref": "case-studies.md#case-5",
    },
    {
        "id": "av_legacy_reasons",
        "phrase": "legacy reasons",
        "match": "literal",
        "category": "archive_value",
        "rationale": "Same pattern.",
        "replacement": "Name the specific constraint or update.",
        "case_ref": "case-studies.md#case-5",
    },

    # -- dismissal --
    {
        "id": "dm_not_a_pain_point",
        "phrase": "not a pain point",
        "match": "literal",
        "category": "dismissal",
        "rationale": "Predicts away a user-raised concern by guessing about the future.",
        "replacement": "Solve the concern.",
        "case_ref": "case-studies.md#patterns-across-the-cases",
    },
    {
        "id": "dm_doesnt_bite_hard",
        "phrase": r"doesn'?t bite hard",
        "match": "regex",
        "category": "dismissal",
        "rationale": "Dismissal via predicted impact.",
        "replacement": "Solve, or name conditions.",
        "case_ref": "case-studies.md#patterns-across-the-cases",
    },
    {
        "id": "dm_not_a_real_concern",
        "phrase": "not a real concern",
        "match": "literal",
        "category": "dismissal",
        "rationale": "Contradicts the user's own framing.",
        "replacement": "Take the concern at face value.",
        "case_ref": "case-studies.md#patterns-across-the-cases",
    },
    {
        "id": "dm_not_a_real_issue",
        "phrase": "not a real issue",
        "match": "literal",
        "category": "dismissal",
        "rationale": "Same pattern.",
        "replacement": "Take the concern at face value.",
        "case_ref": "case-studies.md#patterns-across-the-cases",
    },
    {
        "id": "dm_only_real_con",
        "phrase": "the only real con is",
        "match": "literal",
        "category": "dismissal",
        "rationale": "Pre-dismisses other listed concerns.",
        "replacement": "List the real cons honestly.",
        "case_ref": "case-studies.md#patterns-across-the-cases",
    },
    {
        "id": "dm_theoretical_concern",
        "phrase": "theoretical concern",
        "match": "literal",
        "category": "dismissal",
        "rationale": "Invokes 'theoretical' to avoid defenses.",
        "replacement": "Name when the theoretical becomes practical.",
        "case_ref": "case-studies.md#patterns-across-the-cases",
    },
    {
        "id": "dm_still_unused",
        "phrase": "still unused",
        "match": "literal",
        "category": "dismissal",
        "rationale": "Deferral and dismissal merged.",
        "replacement": "Solve now or name the specific trigger.",
        "case_ref": "case-studies.md#patterns-across-the-cases",
    },
    {
        "id": "dm_wont_matter_until",
        "phrase": r"won'?t matter until",
        "match": "regex",
        "category": "dismissal",
        "rationale": "Future-guessing dismissal.",
        "replacement": "Solve now or name the trigger.",
        "case_ref": "case-studies.md#patterns-across-the-cases",
    },
    {
        "id": "dm_not_urgent",
        "phrase": "not urgent",
        "match": "literal",
        "category": "dismissal",
        "exempt_when": [
            r"marking.{0,30}not urgent",
            r"flagged.{0,30}not urgent",
            r"flagged as not urgent",
        ],
        "rationale": "Triage vocabulary used to deprioritize a user-raised concern.",
        "replacement": "Name higher priorities concretely; don't strand the concern with a label.",
        "case_ref": "case-studies.md#patterns-across-the-cases",
    },

    # -- scope_excuse --
    {
        "id": "se_pre_existing",
        "phrase": r"pre-existing[,.]?\s+(so|and|but)",
        "match": "regex",
        "category": "scope_excuse",
        "rationale": "Invokes age to avoid fixing in code being actively modified.",
        "replacement": "Fix while touching; the mental model is loaded.",
        "case_ref": "case-studies.md#patterns-across-the-cases",
    },
    {
        "id": "se_out_of_scope",
        "phrase": "out of scope",
        "match": "literal",
        "category": "scope_excuse",
        "exempt_when": [
            r"scope of (this PR|this MR|this CL|this commit|this task|this change)",
            r"is in scope",
        ],
        "rationale": "Often a costume for 'I don't feel like doing this.'",
        "replacement": "Name the scope boundary explicitly and why the item falls outside.",
        "case_ref": "case-studies.md#patterns-across-the-cases",
    },
    {
        "id": "se_not_introduced_by",
        "phrase": "not introduced by this",
        "match": "literal",
        "category": "scope_excuse",
        "rationale": "Same pattern.",
        "replacement": "Fix while touching.",
        "case_ref": "case-studies.md#patterns-across-the-cases",
    },
    {
        "id": "se_thats_a_larger_task",
        "phrase": r"that'?s a larger task",
        "match": "regex",
        "category": "scope_excuse",
        "rationale": "Invokes size to defer.",
        "replacement": "If larger, propose the split; otherwise do it.",
        "case_ref": "case-studies.md#patterns-across-the-cases",
    },
    {
        "id": "se_yagni_dismissal",
        "phrase": r"\byagni\b",
        "match": "regex",
        "category": "scope_excuse",
        "exempt_when": [
            r'"YAGNI"',
            r"the YAGNI principle",
            r"YAGNI principle",
        ],
        "rationale": "YAGNI applied to user-raised concerns is dismissal in costume.",
        "replacement": "Solve the user-raised concern; YAGNI is about speculative future features.",
        "case_ref": "case-studies.md#patterns-across-the-cases",
    },
]


# -----------------------------------------------------------------------------
# Data classes
# -----------------------------------------------------------------------------


@dataclass
class Detection:
    """One match against the catalog."""

    phrase_id: str
    category: str
    matched_text: str
    start: int
    end: int
    line: int
    column: int
    context: str
    rationale: str
    replacement: str
    case_ref: str

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class CatalogEntry:
    """One phrase entry in the catalog."""

    id: str
    phrase: str
    match: str  # "literal" | "regex" | "phrase_with_context"
    category: str
    rationale: str = ""
    replacement: str = ""
    case_ref: str = ""
    exempt_when: list = field(default_factory=list)


# -----------------------------------------------------------------------------
# Catalog loading
# -----------------------------------------------------------------------------


def load_embedded_catalog() -> list:
    """Convert the embedded dict catalog into CatalogEntry objects."""
    entries = []
    for spec in EMBEDDED_PHRASES:
        entries.append(
            CatalogEntry(
                id=spec["id"],
                phrase=spec["phrase"],
                match=spec["match"],
                category=spec["category"],
                rationale=spec.get("rationale", ""),
                replacement=spec.get("replacement", ""),
                case_ref=spec.get("case_ref", ""),
                exempt_when=spec.get("exempt_when", []) or [],
            )
        )
    return entries


def load_yaml_catalog(path: Path) -> list:
    """Load a YAML catalog (e.g. the operational catalog at ~/.synthesis/).

    Requires PyYAML. If PyYAML is not installed, raises ImportError with
    a message that points at the embedded catalog as a fallback.
    """
    try:
        import yaml  # type: ignore
    except ImportError as exc:
        raise ImportError(
            "PyYAML is required to load a custom catalog. Install with "
            "`pip install pyyaml`, or run without --catalog to use the "
            "embedded baseline catalog."
        ) from exc

    with path.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh)

    if not isinstance(data, dict) or "phrases" not in data:
        raise ValueError(
            f"Catalog at {path} does not contain a 'phrases' list. "
            "Expected the operational anti-shortcut-catalog.yaml format."
        )

    entries = []
    for spec in data["phrases"]:
        entries.append(
            CatalogEntry(
                id=spec.get("id", ""),
                phrase=spec["phrase"],
                match=spec.get("match", "literal"),
                category=spec.get("category", "uncategorized"),
                rationale=spec.get("rationale", "").strip(),
                replacement=spec.get("replacement", ""),
                case_ref=spec.get("skill_ref") or spec.get("lesson", ""),
                exempt_when=spec.get("exempt_when", []) or [],
            )
        )
    return entries


# -----------------------------------------------------------------------------
# Matching
# -----------------------------------------------------------------------------


def compile_pattern(entry: CatalogEntry) -> re.Pattern:
    """Compile the catalog entry into a regex pattern.

    - literal: case-insensitive whole-phrase match
    - regex: case-insensitive regex compile of the phrase
    - phrase_with_context: same as literal but expect the caller to apply
      exempt_when checks (we do that uniformly anyway)
    """
    if entry.match == "regex":
        return re.compile(entry.phrase, re.IGNORECASE)
    # literal or phrase_with_context
    return re.compile(re.escape(entry.phrase), re.IGNORECASE)


def is_exempt(window: str, exemptions: Iterable[str]) -> bool:
    """Return True if any exemption regex matches the surrounding window."""
    for pat in exemptions:
        if not pat:
            continue
        try:
            if re.search(pat, window, re.IGNORECASE):
                return True
        except re.error:
            # Treat malformed exemption as literal substring (case-insensitive)
            if pat.lower() in window.lower():
                return True
    return False


def line_column_for(text: str, offset: int) -> tuple[int, int]:
    """Translate a 0-based offset into 1-based (line, column)."""
    if offset <= 0:
        return 1, 1
    prefix = text[:offset]
    line = prefix.count("\n") + 1
    last_newline = prefix.rfind("\n")
    column = offset - last_newline if last_newline >= 0 else offset + 1
    return line, column


def scan(text: str, catalog: list, context_chars: int = 80) -> list:
    """Scan text against the catalog and return a list of Detection objects."""
    detections = []
    for entry in catalog:
        pattern = compile_pattern(entry)
        for match in pattern.finditer(text):
            start, end = match.span()
            window_start = max(0, start - context_chars)
            window_end = min(len(text), end + context_chars)
            window = text[window_start:window_end]

            if is_exempt(window, entry.exempt_when):
                continue

            line, column = line_column_for(text, start)
            detections.append(
                Detection(
                    phrase_id=entry.id,
                    category=entry.category,
                    matched_text=text[start:end],
                    start=start,
                    end=end,
                    line=line,
                    column=column,
                    context=window.replace("\n", " "),
                    rationale=entry.rationale,
                    replacement=entry.replacement,
                    case_ref=entry.case_ref,
                )
            )
    # Sort by position for stable, readable output
    detections.sort(key=lambda d: (d.start, d.phrase_id))
    return detections


# -----------------------------------------------------------------------------
# Output
# -----------------------------------------------------------------------------


def format_text_report(detections: list, source_label: str) -> str:
    """Human-readable detection report."""
    if not detections:
        return f"OK  {source_label}: no costume-vocabulary detections."

    by_category: dict = {}
    for det in detections:
        by_category.setdefault(det.category, []).append(det)

    lines = [
        f"FOUND  {source_label}: {len(detections)} detection(s) across "
        f"{len(by_category)} categor{'y' if len(by_category) == 1 else 'ies'}.",
        "",
    ]

    for category in sorted(by_category):
        cat_desc = CATEGORIES.get(category, "")
        lines.append(f"== {category} ==")
        if cat_desc:
            lines.append(f"   {cat_desc}")
        lines.append("")
        for det in by_category[category]:
            lines.append(
                f"  L{det.line}:C{det.column}  [{det.phrase_id}]  "
                f"matched: {det.matched_text!r}"
            )
            if det.rationale:
                lines.append(f"      why:     {det.rationale}")
            if det.replacement:
                lines.append(f"      rewrite: {det.replacement}")
            if det.case_ref:
                lines.append(f"      see:     {det.case_ref}")
            lines.append(f"      context: ...{det.context}...")
            lines.append("")
    return "\n".join(lines).rstrip()


def format_json_report(detections: list, source_label: str) -> str:
    """JSON detection report for programmatic consumption."""
    payload = {
        "source": source_label,
        "detection_count": len(detections),
        "detections": [det.to_dict() for det in detections],
    }
    return json.dumps(payload, indent=2)


# -----------------------------------------------------------------------------
# Entry point
# -----------------------------------------------------------------------------


def read_input(path: Optional[Path]) -> str:
    """Read input text from a file path or from stdin."""
    if path is None or str(path) == "-":
        return sys.stdin.read()
    return path.read_text(encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="scan_output.py",
        description=(
            "Scan AI-assistant draft output for costume-vocabulary phrases "
            "that signal the lazy-shortcut antipattern."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Catalog source:\n"
            "  Without --catalog, uses the embedded baseline catalog.\n"
            "  With --catalog <path>, loads a YAML catalog (requires PyYAML).\n"
            "\n"
            "Exit codes:\n"
            "  0 — Clean (no detections)\n"
            "  1 — One or more detections found\n"
            "  2 — Error\n"
        ),
    )
    parser.add_argument(
        "input",
        nargs="?",
        default=None,
        help="File to scan. Omit or pass '-' to read from stdin.",
    )
    parser.add_argument(
        "--catalog",
        type=Path,
        help="Path to a YAML catalog file (overrides the embedded catalog).",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit JSON instead of a human-readable report.",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress stdout; communicate via exit code only.",
    )
    parser.add_argument(
        "--context",
        type=int,
        default=80,
        help="Characters of surrounding context to capture (default: 80).",
    )
    parser.add_argument(
        "--category",
        action="append",
        help="Limit scan to one or more categories (repeatable).",
    )
    return parser


def main(argv: Optional[list] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    # Load catalog
    try:
        if args.catalog:
            catalog = load_yaml_catalog(args.catalog)
        else:
            catalog = load_embedded_catalog()
    except (ImportError, ValueError, OSError) as exc:
        print(f"error loading catalog: {exc}", file=sys.stderr)
        return 2

    # Filter by category if requested
    if args.category:
        wanted = set(args.category)
        catalog = [e for e in catalog if e.category in wanted]

    # Read input
    input_path = Path(args.input) if args.input and args.input != "-" else None
    try:
        text = read_input(input_path)
    except OSError as exc:
        print(f"error reading input: {exc}", file=sys.stderr)
        return 2

    source_label = str(input_path) if input_path else "<stdin>"

    detections = scan(text, catalog, context_chars=max(0, args.context))

    if not args.quiet:
        if args.json:
            print(format_json_report(detections, source_label))
        else:
            print(format_text_report(detections, source_label))

    return 1 if detections else 0


if __name__ == "__main__":
    sys.exit(main())
