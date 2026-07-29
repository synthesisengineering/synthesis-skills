#!/usr/bin/env python3
"""catchup_scan.py — candidate generator for the synthesis-catchup-ledger skill.

Scans a directory of dated daily-plan markdown files (YYYY-MM-DD*.md) within a
window and emits, grouped by file:

  1. Unchecked task items ("- [ ]" anywhere; numbered items under headings that
     look like priority/task sections)
  2. Draft blocks ("### Draft N" or "### ~~Draft N" headings) lacking a
     "**Sent:**" marker before the next heading of equal/higher level
  3. Decision headings (H3s under a "Decisions needed" H2) lacking a
     "**Decided:**" marker
  4. Carryover / backlog / waiting / stale sections (verbatim, trimmed)

This is a CANDIDATE GENERATOR. Items it emits may already be resolved in
sources it cannot see (Slack threads, merged PRs, meeting decisions). The
classifying agent must cross-check before writing any item into a ledger.

Usage:
  python3 catchup_scan.py <daily_plans_dir> --start YYYY-MM-DD --end YYYY-MM-DD
  python3 catchup_scan.py <daily_plans_dir> --start 2026-04-29 --end 2026-06-10 --max-section-lines 12

Exit codes: 0 = scan completed (regardless of findings), 2 = bad arguments.
"""

import argparse
import re
import sys
from pathlib import Path

DATE_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})")
DRAFT_HEAD_RE = re.compile(r"^###\s+~{0,2}Draft\s+(\w+)", re.IGNORECASE)
SENT_RE = re.compile(r"\*\*Sent:?\*\*", re.IGNORECASE)
DECIDED_RE = re.compile(r"\*\*Decided:?\*\*", re.IGNORECASE)
UNCHECKED_RE = re.compile(r"^\s*[-*]\s+\[ \]\s+(.*)")
NUMBERED_RE = re.compile(r"^\s*\d+\.\s+(.*)")
DONE_HINT_RE = re.compile(r"~~|✅|\bDONE\b|\bSENT\b|\bSHIPPED\b|\bCLOSED\b", re.IGNORECASE)
TASK_HEADING_RE = re.compile(
    r"priorit|task|do today|not negotiable|should make it|can slip|p0|p1|p2",
    re.IGNORECASE,
)
CARRYOVER_HEADING_RE = re.compile(
    r"carryover|carried|backlog|waiting|stale|loose.ends|open items|still open|pending",
    re.IGNORECASE,
)
DECISIONS_HEADING_RE = re.compile(r"decisions? (needed|to make)|open ask", re.IGNORECASE)


def heading_level(line: str) -> int:
    m = re.match(r"^(#{1,6})\s", line)
    return len(m.group(1)) if m else 0


def scan_file(path: Path, max_section_lines: int):
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    findings = {"unchecked": [], "unsent_drafts": [], "undecided": [], "carryover": []}

    current_h2 = ""
    current_h3 = ""
    in_task_section = False
    in_decisions = False

    i = 0
    n = len(lines)
    while i < n:
        line = lines[i]
        lvl = heading_level(line)

        if lvl == 2:
            current_h2 = line.lstrip("# ").strip()
            in_task_section = bool(TASK_HEADING_RE.search(current_h2))
            in_decisions = bool(DECISIONS_HEADING_RE.search(current_h2))
            if CARRYOVER_HEADING_RE.search(current_h2):
                block, j = [], i + 1
                while j < n and heading_level(lines[j]) not in (1, 2):
                    if lines[j].strip():
                        block.append(lines[j])
                    j += 1
                findings["carryover"].append(
                    (i + 1, current_h2, block[:max_section_lines], max(0, len(block) - max_section_lines))
                )
        elif lvl == 3:
            current_h3 = line.lstrip("# ").strip()
            if in_task_section and TASK_HEADING_RE.search(current_h3):
                pass  # bucket heading inside Priority Tasks; items handled below

            dm = DRAFT_HEAD_RE.match(line.strip())
            if dm:
                j = i + 1
                sent = False
                while j < n and heading_level(lines[j]) not in (1, 2, 3):
                    if SENT_RE.search(lines[j]):
                        sent = True
                        break
                    j += 1
                if not sent and "retracted" not in current_h3.lower() and not DONE_HINT_RE.search(current_h3):
                    findings["unsent_drafts"].append((i + 1, current_h3))

            if in_decisions:
                j = i + 1
                decided = False
                while j < n and heading_level(lines[j]) not in (1, 2, 3):
                    if DECIDED_RE.search(lines[j]):
                        decided = True
                        break
                    j += 1
                if not decided:
                    findings["undecided"].append((i + 1, current_h3))

        um = UNCHECKED_RE.match(line)
        if um and not DONE_HINT_RE.search(um.group(1)):
            findings["unchecked"].append((i + 1, um.group(1).strip()[:160]))
        elif in_task_section:
            nm = NUMBERED_RE.match(line)
            if nm and not DONE_HINT_RE.search(nm.group(1)):
                findings["unchecked"].append((i + 1, nm.group(1).strip()[:160]))

        i += 1

    return findings


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("plans_dir")
    ap.add_argument("--start", required=True)
    ap.add_argument("--end", required=True)
    ap.add_argument("--max-section-lines", type=int, default=12)
    args = ap.parse_args()

    root = Path(args.plans_dir).expanduser()
    if not root.is_dir():
        print(f"error: {root} is not a directory", file=sys.stderr)
        sys.exit(2)

    files = []
    for p in sorted(root.glob("*.md")):
        m = DATE_RE.match(p.name)
        if m and args.start <= m.group(1) <= args.end:
            files.append(p)

    total = {"unchecked": 0, "unsent_drafts": 0, "undecided": 0, "carryover": 0}
    print(f"CATCH-UP SCAN — {root}  window {args.start} → {args.end}  files: {len(files)}")
    print("=" * 76)

    for p in files:
        f = scan_file(p, args.max_section_lines)
        if not any(f.values()):
            continue
        print(f"\n## {p.name}")
        for line_no, h in f["unsent_drafts"]:
            print(f"  [DRAFT-UNSENT] L{line_no}: {h}")
        for line_no, h in f["undecided"]:
            print(f"  [UNDECIDED]    L{line_no}: {h}")
        for line_no, t in f["unchecked"]:
            print(f"  [OPEN-ITEM]    L{line_no}: {t}")
        for line_no, h, block, dropped in f["carryover"]:
            print(f"  [CARRYOVER]    L{line_no}: ## {h}")
            for b in block:
                print(f"                 | {b.strip()[:150]}")
            if dropped:
                print(f"                 | … (+{dropped} more lines)")
        for k in total:
            total[k] += len(f[k])

    print("\n" + "=" * 76)
    print(
        f"TOTALS: open-items={total['unchecked']}  unsent-drafts={total['unsent_drafts']}  "
        f"undecided={total['undecided']}  carryover-sections={total['carryover']}"
    )
    print("Candidates only — cross-check against transcripts/tickets before classifying.")


if __name__ == "__main__":
    main()
