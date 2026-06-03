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

# Any HH:MM:SS or MM:SS anywhere — Gemini uses bare, bold, heading, and markdown-link forms
TIMESTAMP_RE = re.compile(r"\b\d{1,2}:\d{2}(?::\d{2})?\b")

# Speaker attribution line at start of line, in any form Gemini or our agents use:
#   - Bolded full name:     **Name Surname:** text...   (newer Gemini output, our agent-curated)
#   - Unbolded full name:   Name Surname: text...       (older Gemini output, March-April vintage)
#   - Bolded first only:    **Name:** text...           (our agent-curated, brevity form)
# A real Gemini verbatim transcript has dozens of these per file; a summary-only save has none.
# We accept 1-4 capitalized words ending in a colon. The high min-speakers threshold (default 10)
# ensures cumulative false positives from non-dialogue patterns can't push a summary-only file over.
SPEAKER_RE = re.compile(
    r"^(?:\*\*)?[A-Z][a-zA-Z][a-zA-Z]+(?:\s[A-Z][a-zA-Z]+){0,3}:(?:\*\*)?\s",
    re.MULTILINE,
)

# Files whose names start with these prefixes are not meeting transcripts.
SKIP_PREFIXES = ("_", "gdoc-", "email-")

# Files containing this marker are explicitly tagged as "Gemini notes exist but
# no verbatim transcript was produced at the source" — Google Meet was recorded
# but transcription was not enabled. The verifier accepts these as OK.
NO_SOURCE_TRANSCRIPT_MARKER = "<!-- VERIFIER: no-source-transcript -->"


def count_timestamps(content: str) -> int:
    return len(TIMESTAMP_RE.findall(content))


def count_speaker_lines(content: str) -> int:
    return len(SPEAKER_RE.findall(content))


def has_transcript_section_heading(content: str) -> bool:
    """Heuristic: real transcripts have a '## ... Transcript' or '📖 Transcript' heading."""
    return bool(re.search(r"(?:📖|^#+)\s*[Tt]ranscript", content, re.MULTILINE))


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
        has_heading = has_transcript_section_heading(content)
        size_kb = path.stat().st_size / 1024
        ok = timestamps >= min_markers and speakers >= min_speakers
        results.append({
            "file": path.name,
            "timestamps": timestamps,
            "speakers": speakers,
            "has_transcript_heading": has_heading,
            "size_kb": round(size_kb, 1),
            "status": "OK" if ok else "INCOMPLETE",
        })
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.strip().split("\n\n", 1)[0])
    parser.add_argument("meetings_dir", help="Path to transcripts/meetings/ dir")
    parser.add_argument("--min-markers", type=int, default=5, help="Min timestamp markers required (default: 5)")
    parser.add_argument("--min-speakers", type=int, default=10, help="Min speaker-attribution lines required (default: 10)")
    parser.add_argument("--json", action="store_true", help="Output JSON instead of human-readable")
    parser.add_argument("--only-incomplete", action="store_true", help="Only list incomplete files")
    parser.add_argument("--no-skip", action="store_true", help="Audit ALL files including SKIP_PREFIXES + no-source markers (debug)")
    args = parser.parse_args()

    meetings_dir = Path(args.meetings_dir).expanduser().resolve()
    if not meetings_dir.is_dir():
        print(f"ERROR: not a directory: {meetings_dir}", file=sys.stderr)
        return 2

    results = audit_dir(meetings_dir, args.min_markers, args.min_speakers, no_skip=args.no_skip)
    if not results:
        print(f"ERROR: no .md files found in {meetings_dir}", file=sys.stderr)
        return 2

    if args.only_incomplete:
        results = [r for r in results if r["status"] == "INCOMPLETE"]

    incomplete_count = sum(1 for r in results if r["status"] == "INCOMPLETE")
    skipped_count = sum(1 for r in results if r["status"] == "SKIPPED")
    no_source_count = sum(1 for r in results if r["status"] == "OK (no-source-transcript)")

    if args.json:
        print(json.dumps({
            "dir": str(meetings_dir),
            "min_markers": args.min_markers,
            "min_speakers": args.min_speakers,
            "total_files": len(results),
            "incomplete_count": incomplete_count,
            "skipped_count": skipped_count,
            "no_source_count": no_source_count,
            "results": results,
        }, indent=2))
    else:
        print(f"=== Transcript completeness audit: {meetings_dir} ===")
        print(f"Thresholds: ≥{args.min_markers} timestamps + ≥{args.min_speakers} speaker lines")
        print(f"Skip prefixes: {SKIP_PREFIXES} · No-source-transcript marker: {NO_SOURCE_TRANSCRIPT_MARKER}")
        print()
        print(f"{'STATUS':<25} {'TSTAMPS':<8} {'SPKRS':<6} {'HEAD':<5} {'SIZE_KB':<9} FILE")
        print("-" * 110)
        for r in results:
            heading = "yes" if r["has_transcript_heading"] else "no"
            print(f"{r['status']:<25} {r['timestamps']:<8} {r['speakers']:<6} {heading:<5} {r['size_kb']:<9} {r['file']}")
        print()
        print(f"Total: {len(results)} files — {incomplete_count} incomplete, {skipped_count} skipped, {no_source_count} no-source-transcript.")
        if incomplete_count:
            print()
            print("Incomplete files need backfill: re-fetch the source Google Doc")
            print("with the full transcript content and append under a")
            print("'## 📖 Full Gemini Notes + Verbatim Transcript' section.")

    return 1 if incomplete_count else 0


if __name__ == "__main__":
    sys.exit(main())
