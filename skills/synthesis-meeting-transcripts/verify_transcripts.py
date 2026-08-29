#!/usr/bin/env python3
"""
verify_transcripts.py — Detect meeting-transcript files that are missing
the full verbatim transcript section.

The synthesis-meeting-transcripts skill mandates that every saved meeting
file contains BOTH:
  1. Gemini notes (summary + paraphrased details + next steps)
  2. The verbatim word-for-word transcript with timestamps + speaker labels

This script enforces that by counting timestamp markers + speaker-attribution
lines in each file. A real Gemini transcript has timestamp markers every
~1-2 minutes (e.g., "00:01:31") and dozens of speaker-attribution lines
(`**Name:**` or `Name Surname:`). Summary-only files lack both.

Failure threshold (configurable): ≥5 timestamps + ≥10 speaker lines.

Skip rules (a file is NOT audited if any of these apply):
  - Filename starts with `_` — meta/documentation files (e.g., _BACKFILL_TODO.md)
  - Filename starts with `gdoc-` — Google Doc imports, not meeting transcripts
  - Filename starts with `email-` — synced email threads, not meetings
  - File contains the literal marker `<!-- VERIFIER: no-source-transcript -->` —
    explicitly tagged as a meeting where Gemini produced notes but NO verbatim
    transcript (Google Meet "Recording" mode without transcription enabled).
    Use this marker for files where the source-Doc legitimately has no
    transcript section to mirror locally.

Usage:
  python3 verify_transcripts.py <dir>
  python3 verify_transcripts.py <dir> --min-markers 10 --min-speakers 20
  python3 verify_transcripts.py <dir> --json
  python3 verify_transcripts.py <dir> --only-incomplete
  python3 verify_transcripts.py <dir> --no-skip       # audit ALL files (debug)

Reporting contract:
  `--only-incomplete` narrows which ROWS are listed. It never narrows the
  summary counters — those always describe the whole audited corpus, so a
  clean run reports "Total: 282 files — 0 incomplete, ..." rather than
  "Total: 0 files", which would be byte-identical to a wrong path. The same
  split holds in --json: `total_files` is the corpus, `listed_count` the rows.

Exit code:
  0 — all audited files have full transcripts
  1 — at least one audited file is incomplete (failures listed)
  2 — directory not found or no .md files

Wire this into:
  - synthesis-meeting-transcripts skill Step 4.5 (post-write verification)
  - synthesis-daily-rituals Day-Start Step 2b
  - Pre-commit hook (optional)
"""

import argparse
import json
import re
import sys
from pathlib import Path

# Bump with every detector-affecting change (regex, thresholds, marker names) OR any change
# to what the run REPORTS, and add a matching entry to SKILL.md's changelog. Output changes
# count because the banner exists to tell a reader which behavior produced the numbers they
# are looking at — and a summary line is behavior. Printed in every run's output specifically
# so a stale copy is self-diagnosing: on 2026-08-06 an orphaned plugin-cache directory
# (v4.9.0, predating the v0.5.0 Plaud-format + undiarized-override fixes) was run in place of
# the actually-installed v4.14.1, producing 26 false-positive INCOMPLETE flags on a corpus the
# fixed detector reads as 0 incomplete. The script had no version banner, so nothing in its
# own output could reveal that the copy being run was stale. This constant plus the banner
# line below close that gap — if the printed version doesn't match SKILL.md's frontmatter
# version, the copy being run is not the one you think it is.
SCRIPT_VERSION = "0.9.0"

# Any HH:MM:SS or MM:SS anywhere — Gemini uses bare, bold, heading, and markdown-link forms
TIMESTAMP_RE = re.compile(r"\b\d{1,2}:\d{2}(?::\d{2})?\b")

# Speaker attribution line at start of line, in any form Gemini, Plaud, or our agents use:
#   - Bolded full name:      **Name Surname:** text...   (newer Gemini output, our agent-curated)
#   - Unbolded full name:    Name Surname: text...       (older Gemini output, March-April vintage)
#   - Bolded first only:     **Name:** text...           (our agent-curated, brevity form)
#   - Plaud (timestamp-led): **[00:00] Name Surname:** text...  or  **[0:20] Speaker 2:** text...
#     Plaud puts a bracketed [MM:SS]/[H:MM:SS] BEFORE the name, so the older name-anchored
#     regex missed every Plaud dialogue line and flagged full Plaud transcripts as incomplete.
#     v0.5.1: Plaud emits SPACED ranges — `**[00:00 - 00:08] Name:**` — and the v0.5.0 pattern
#     only accepted the unspaced `[00:00-00:08]` form, so real Plaud transcripts still failed.
#     Whitespace around the separator is now optional, and en/em dashes are accepted alongside `-`.
#   - Plaud (timestamp-led, INFERRED SPEAKER): **[00:00] Name (Plaud Speaker N, mapped):** text...
#     or **[0:00] Name (Plaud Speaker 1 — inferred, high confidence: <reasoning>):** text... —
#     when Plaud only diarizes by number, our agents annotate the inferred real name with a
#     parenthetical BEFORE the colon. v0.5.1 had no path for this: the parenthetical broke the
#     match immediately after the name, silently undercounting speaker lines (dozens of lines
#     missed per affected file — confirmed 2026-08-06 against a production corpus). The affected
#     files still passed only because they happened to have enough OTHER unannotated lines; a
#     file with fewer bare-name lines and more annotated ones would have been a genuine false positive.
#     v0.5.2 accepts an optional "(...)" annotation, but ONLY on the timestamp-led branch — never
#     on the bare no-timestamp branch, where it would start matching ordinary markdown field
#     headers like "**Attendees (Invited):**" or "**Decision (Gemini "Aligned"):**" that appear
#     in genuinely summary-only files and would erode the detector's precision.
# A real verbatim transcript has dozens of these per file; a summary-only save has none.
# The high min-speakers threshold (default 10) ensures cumulative false positives from
# non-dialogue patterns can't push a summary-only file over.
_NAME = r"[A-Z][a-zA-Z]{2,}(?:\s+(?:[A-Z][a-zA-Z]+|\d{1,3})){0,3}"  # Name, Name Surname, or "Speaker 2"
_TS = r"\d{1,2}:\d{2}(?::\d{2})?"
SPEAKER_RE = re.compile(
    r"^(?:\*\*)?"                                                     # optional bold
    r"(?:"
    rf"\[\s*{_TS}(?:\s*[-–—]\s*{_TS})?\s*\]\s*{_NAME}"                 # [t] or [t - t] Name (Plaud; spaces/en-dash OK)
    r"(?:\s*\([^()\n]{1,200}\))?"                                     # optional inferred-speaker annotation — timestamp-led only
    r"|"
    rf"{_NAME}"                                                       # bare Name (Gemini / our agent-curated) — no annotation allowed
    r")"
    r":(?:\*\*)?\s",                                                  # colon, optional closing bold, space
    re.MULTILINE,
)

# A verbatim transcript the host recorded WITHOUT speaker diarization is a running transcript:
# each utterance is preceded by a bare timestamp ON ITS OWN LINE (e.g. exec-offsite: 72 such lines).
# It is still the full primary record, so a high count of standalone-timestamp lines marks it complete
# even when speaker-line count is low. Crucially this is the signal a Details-SUMMARY lacks: a summary
# embeds its timestamps INLINE in prose bullets ("...discussed X (00:05:12)."), never on their own line.
# Total-timestamp-count cannot tell the two apart (a dense summary has 30+ inline timestamps and may
# even carry a "Verbatim transcript" heading); standalone-timestamp-line count can.
STANDALONE_TS_RE = re.compile(
    r"^[ \t]*\*{0,2}\[?\d{1,2}:\d{2}(?::\d{2})?\]?\*{0,2}[ \t]*$",
    re.MULTILINE,
)
DENSE_STANDALONE_TS_LINES = 20

# Files whose names start with these prefixes are not meeting transcripts.
SKIP_PREFIXES = ("_", "gdoc-", "email-")

# Files containing this marker are explicitly tagged as "Gemini notes exist but
# no verbatim transcript was produced at the source" — Google Meet was recorded
# but transcription was not enabled. The verifier accepts these as OK.
NO_SOURCE_TRANSCRIPT_MARKER = "<!-- VERIFIER: no-source-transcript -->"

# Completeness is a corpus diagnostic, not an attribution-authority gate. These
# limits accompany every successful completion signal so a clean detector run
# cannot be mistaken for proof that the files are authentic, exhaustive, or
# source-grade for a particular claim.
CONTROL_CLASS = "diagnostic"
UNVERIFIED_REMAINDER = [
    "whether a no-source-transcript marker truthfully reflects the provider source",
    "capture completeness beyond the bytes in the audited files",
    "attribution-level primary-source eligibility; use transcript_primary.py",
]


def count_timestamps(content: str) -> int:
    return len(TIMESTAMP_RE.findall(content))


def count_speaker_lines(content: str) -> int:
    return len(SPEAKER_RE.findall(content))


def count_standalone_timestamp_lines(content: str) -> int:
    """Lines that are ONLY a timestamp (optionally bold/bracketed). This is the fingerprint of an
    undiarized running transcript, and the signal a Details-summary lacks (its timestamps are inline)."""
    return len(STANDALONE_TS_RE.findall(content))


def has_transcript_section_heading(content: str) -> bool:
    """Heuristic: real transcripts carry a heading whose text contains "transcript" —
    e.g. '## Verbatim transcript (primary source)', '## Full transcript', '# 📖 Transcript',
    '## Daily Standup - Transcript'. The word need not immediately follow the '#'; matching
    only heading-initial 'Transcript' missed every '## Verbatim transcript' heading our agents
    write, which broke the dense-transcript override for undiarized recordings."""
    return bool(re.search(r"(?:📖\s*[Tt]ranscript|^#+[^\n]*[Tt]ranscript)", content, re.MULTILINE))


def audit_dir(meetings_dir: Path, min_markers: int, min_speakers: int, no_skip: bool = False) -> list[dict]:
    """Audit every .md file in the directory. Returns list of result dicts.

    A file is OK iff EITHER:
    - It has the NO_SOURCE_TRANSCRIPT_MARKER (meaning the source Doc legitimately
      has no verbatim transcript — Google Meet recorded but transcription off), OR
    - It has BOTH ≥ min_markers timestamps AND ≥ min_speakers speaker-attribution lines

    Files matching SKIP_PREFIXES are reported as SKIPPED (not flagged INCOMPLETE).
    Files with only timestamps but no speaker attribution are notes-only — incomplete.

    Pass no_skip=True to disable the prefix-based skip (debug aid).
    """
    results = []
    for path in sorted(meetings_dir.glob("*.md")):
        # Skip prefix-based exclusions unless --no-skip
        if not no_skip and path.name.startswith(SKIP_PREFIXES):
            size_kb = path.stat().st_size / 1024
            results.append({
                "file": path.name,
                "timestamps": 0,
                "speakers": 0,
                "has_transcript_heading": False,
                "size_kb": round(size_kb, 1),
                "status": "SKIPPED",
            })
            continue

        try:
            content = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            content = ""

        # Explicit marker for source-Doc-has-no-transcript meetings
        if NO_SOURCE_TRANSCRIPT_MARKER in content:
            size_kb = path.stat().st_size / 1024
            results.append({
                "file": path.name,
                "timestamps": count_timestamps(content),
                "speakers": count_speaker_lines(content),
                "has_transcript_heading": has_transcript_section_heading(content),
                "size_kb": round(size_kb, 1),
                "status": "OK (no-source-transcript)",
            })
            continue

        timestamps = count_timestamps(content)
        speakers = count_speaker_lines(content)
        standalone = count_standalone_timestamp_lines(content)
        has_heading = has_transcript_section_heading(content)
        size_kb = path.stat().st_size / 1024
        # Diarized case: enough timestamps AND enough speaker lines (Gemini or Plaud, incl. [t-t] range form).
        # Undiarized case: enough standalone-timestamp lines (running transcript with no speaker labels).
        # A Details-SUMMARY passes neither — it has few speaker lines and ~0 standalone-timestamp lines,
        # even when it carries many inline timestamps and a misleading "Verbatim transcript" heading.
        ok = (timestamps >= min_markers and speakers >= min_speakers) or (
            standalone >= DENSE_STANDALONE_TS_LINES
        )
        results.append({
            "file": path.name,
            "timestamps": timestamps,
            "speakers": speakers,
            "standalone_ts_lines": standalone,
            "has_transcript_heading": has_heading,
            "size_kb": round(size_kb, 1),
            "status": "OK" if ok else "INCOMPLETE",
        })
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.strip().split("\n\n", 1)[0])
    parser.add_argument("meetings_dir", nargs="?", help="Path to transcripts/meetings/ dir (not required with --version)")
    parser.add_argument("--min-markers", type=int, default=5, help="Min timestamp markers required (default: 5)")
    parser.add_argument("--min-speakers", type=int, default=10, help="Min speaker-attribution lines required (default: 10)")
    parser.add_argument("--json", action="store_true", help="Output JSON instead of human-readable")
    parser.add_argument("--only-incomplete", action="store_true", help="Only list incomplete files")
    parser.add_argument("--no-skip", action="store_true", help="Audit ALL files including SKIP_PREFIXES + no-source markers (debug)")
    parser.add_argument("--version", action="store_true", help="Print the detector version and exit")
    args = parser.parse_args()

    if args.version:
        print(SCRIPT_VERSION)
        return 0

    if not args.meetings_dir:
        print("ERROR: meetings_dir is required (unless using --version)", file=sys.stderr)
        return 2

    meetings_dir = Path(args.meetings_dir).expanduser().resolve()
    if not meetings_dir.is_dir():
        print(f"ERROR: not a directory: {meetings_dir}", file=sys.stderr)
        return 2

    results = audit_dir(meetings_dir, args.min_markers, args.min_speakers, no_skip=args.no_skip)
    if not results:
        print(f"ERROR: no .md files found in {meetings_dir}", file=sys.stderr)
        return 2

    # Counters describe the CORPUS; --only-incomplete narrows only the LISTING. Computing
    # them from the filtered list (the v0.5.2 behavior) made a clean corpus print
    # "Total: 0 files — 0 incomplete, 0 skipped, 0 no-source-transcript" — a clean bill of
    # health rendered byte-identical to "wrong path / nothing audited", and the daily ritual
    # invokes this script with exactly that flag. A control whose success output reads as a
    # broken invocation is one operators learn to distrust, which is the same failure mode
    # the v0.5.1 false-positive fix existed to prevent, arriving from the other direction.
    incomplete_count = sum(1 for r in results if r["status"] == "INCOMPLETE")
    skipped_count = sum(1 for r in results if r["status"] == "SKIPPED")
    no_source_count = sum(1 for r in results if r["status"] == "OK (no-source-transcript)")

    listed = [r for r in results if r["status"] == "INCOMPLETE"] if args.only_incomplete else results

    if args.json:
        print(json.dumps({
            "script_version": SCRIPT_VERSION,
            "control_class": CONTROL_CLASS,
            "issues_authority_receipt": False,
            "enforcement_outcome": (
                "complete-corpus" if incomplete_count == 0 else "incomplete-corpus"
            ),
            "unverified_remainder": UNVERIFIED_REMAINDER,
            "dir": str(meetings_dir),
            "min_markers": args.min_markers,
            "min_speakers": args.min_speakers,
            "total_files": len(results),      # the corpus that was audited
            "listed_count": len(listed),      # rows present in "results" below
            "only_incomplete": args.only_incomplete,
            "incomplete_count": incomplete_count,
            "skipped_count": skipped_count,
            "no_source_count": no_source_count,
            "results": listed,
        }, indent=2))
    else:
        print(f"=== Transcript completeness audit: {meetings_dir} ===")
        print(f"Detector version: {SCRIPT_VERSION} (must match SKILL.md frontmatter — if you expected a newer fix and don't see it, you're running a stale copy)")
        print(f"Control class: {CONTROL_CLASS}; authority receipt: no")
        print(f"Thresholds: ≥{args.min_markers} timestamps + ≥{args.min_speakers} speaker lines")
        print(f"Skip prefixes: {SKIP_PREFIXES} · No-source-transcript marker: {NO_SOURCE_TRANSCRIPT_MARKER}")
        print()
        print(f"{'STATUS':<25} {'TSTAMPS':<8} {'SPKRS':<6} {'HEAD':<5} {'SIZE_KB':<9} FILE")
        print("-" * 110)
        for r in listed:
            heading = "yes" if r["has_transcript_heading"] else "no"
            print(f"{r['status']:<25} {r['timestamps']:<8} {r['speakers']:<6} {heading:<5} {r['size_kb']:<9} {r['file']}")
        if not listed:
            print("(none — no audited file matches the active listing filter)")
        print()
        filter_note = " (listing filtered to incomplete only)" if args.only_incomplete else ""
        print(f"Total: {len(results)} files — {incomplete_count} incomplete, {skipped_count} skipped, {no_source_count} no-source-transcript.{filter_note}")
        print(
            "Enforcement outcome: "
            + ("complete-corpus" if incomplete_count == 0 else "incomplete-corpus")
        )
        print("Unverified remainder:")
        for item in UNVERIFIED_REMAINDER:
            print(f"- {item}")
        if incomplete_count:
            print()
            print("Incomplete files need backfill: re-fetch the source Google Doc")
            print("with the full transcript content and append under a")
            print("'## 📖 Full Gemini Notes + Verbatim Transcript' section.")

    return 1 if incomplete_count else 0


if __name__ == "__main__":
    sys.exit(main())
