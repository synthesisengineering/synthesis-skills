#!/usr/bin/env python3
"""Thread Checker — Pre-sync checklist generator for synthesis-slack-sync.

Reads the local transcript file and daily action plan, extracts every thread TS
and draft target, and outputs a structured checklist of threads that MUST be
re-read during the next sync.

Usage:
    python3 thread_checker.py <transcript_file> [action_plan_file]

Output:
    A checklist of parent thread TSes grouped by channel, with channel IDs.
    The agent MUST re-read every thread listed using slack_read_thread.

Why: on 2026-03-10 incremental thread reads lost replies and a reply was drafted
that the principal had already posted; on 2026-04-01 three drafts turned out to
be answered already, found only once this script listed every thread.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

# Channel header with ID: ## #channel-name (CHANNEL_ID)
CHANNEL_WITH_ID = re.compile(r"^#{1,3}\s+#([\w-]+)\s*\(([A-Z][A-Z0-9]+)\)")
# Channel header without ID: ### #channel-name (used in mid-day/evening sync sections)
CHANNEL_NO_ID = re.compile(r"^#{1,3}\s+#([\w-]+)\s*$")
# TS pattern in parentheses: (TS: 1775064672.791199) — legacy pre-v3.1.0 format
TS_IN_PARENS = re.compile(r"\(TS:\s*([\d.]+)\)")
# TS embedded in Slack permalink path: /p1775064672791199 — v3.1.0+ format.
# Captures the 16-digit suffix; the dot is re-inserted to normalize.
TS_IN_PERMALINK = re.compile(r"/p(\d{10})(\d{6})\b")
REPLY_COUNT = re.compile(r"(\d+)\s*repl(?:y|ies)")
THREAD_LABEL = re.compile(r"\*\*Thread\s*\((\d+)\s*repl")


def structural_lines(content: str) -> list[str]:
    """The transcript with fenced code, block quotes and indented code blanked out: a TS inside
    a quoted or fenced message body is not a thread parent."""
    lines, fence = [], None
    for line in content.split("\n"):
        marker = re.match(r"^ {0,3}(`{3,}|~{3,})(.*)$", line)
        if fence is not None:
            if marker and marker[1][0] == fence[0] and len(marker[1]) >= len(fence) and not marker[2].strip():
                fence = None
            lines.append("")
        elif marker:
            fence = marker[1]
            lines.append("")
        elif line.lstrip().startswith(">") or line.startswith(("    ", "\t")):
            lines.append("")
        else:
            lines.append(line)
    return lines


def extract_threads(transcript_path: str | None, *, content: str | None = None) -> list[dict]:
    """Extract parent thread TSes and metadata from a transcript file."""
    if content is None:
        content = Path(transcript_path).read_text()
    lines = structural_lines(content)
    # First pass: channel name -> ID map from headers that carry an ID.
    channel_ids = {}
    for line in lines:
        found = CHANNEL_WITH_ID.match(line.strip())
        if found:
            channel_ids[found.group(1)] = found.group(2)

    threads, seen = [], set()
    channel = channel_id = None
    for i, line in enumerate(lines):
        found = CHANNEL_WITH_ID.match(line.strip())
        if found:
            channel, channel_id = found.group(1), found.group(2)
            continue
        found = CHANNEL_NO_ID.match(line.strip())
        if found:
            channel = found.group(1)
            channel_id = channel_ids.get(channel)  # never inherit the previous channel's ID
            continue
        # TSes come from message-header-like lines: legacy `(TS: ...)` text or a v3.1.0+ permalink.
        stamps = TS_IN_PARENS.findall(line) + [f"{a}.{b}" for a, b in TS_IN_PERMALINK.findall(line)]
        stripped = line.strip()
        if not stamps or stripped.startswith(("- ", "> ")):  # list items are replies, not parents
            continue
        for ts in stamps:
            if (channel_id, ts) in seen:
                continue
            context = "\n".join(lines[i:i + 5])
            count = THREAD_LABEL.search(context) or REPLY_COUNT.search(context)
            seen.add((channel_id, ts))
            threads.append({"ts": ts, "channel": channel or "unknown", "channel_id": channel_id or "?",
                            "reply_count": int(count.group(1)) if count else 0, "context": stripped[:100]})
    return threads


def extract_unsent_drafts(action_plan_path: str) -> list[dict]:
    """Extract unsent draft thread TSes from the action plan.

    A draft is considered SENT (and is skipped) when ANY of these signals are
    present:
      - The H3 line itself contains `SENT` or `~~` markers (legacy pre-v3.2.0
        form: ``### ~~Draft N: title~~ ✅ SENT by <name> at ... in #channel``).
      - A `**Sent:**` paragraph appears within the draft's section (the v3.2.0+
        canonical form, also written by synthesis-console's mark-as-sent
        endpoint).

    Either signal alone is sufficient. The parser is intentionally tolerant —
    files on disk may contain either form during the transition.
    """
    lines = Path(action_plan_path).read_text().split("\n")
    drafts, seen = [], set()
    for i, line in enumerate(lines):
        found = re.match(r"^###\s+Draft\s+(\d+):\s*(.*)", line.strip())
        if not found or "~~" in line or "SENT" in line:
            continue
        end = i + 1
        while end < len(lines) and not re.match(r"^#{1,3}\s", lines[end]):
            end += 1
        if re.search(r"^\s*\*\*\s*Sent(?:\s*at)?\s*:?\s*\*\*", "\n".join(lines[i:end]), re.MULTILINE):
            continue
        number = int(found.group(1))
        if number in seen:
            continue
        seen.add(number)
        # The draft's own section (at most 20 lines) carries the target: legacy `TS: ...` text or a
        # /pNNNN permalink. Reading past the next heading took the following draft's target.
        block = "\n".join(lines[i:min(end, i + 20)])
        ts = re.search(r"TS:\s*([\d.]+)", block)
        link = re.search(r"/p(\d{10})(\d{6})\b", block)
        channel = re.search(r"Channel.*?([A-Z][A-Z0-9]{8,})", block) or re.search(r"/archives/([A-Z][A-Z0-9]{8,})/", block)
        drafts.append({"number": number, "title": found.group(2),
                       "ts": ts.group(1) if ts else (f"{link.group(1)}.{link.group(2)}" if link else None),
                       "channel_id": channel.group(1) if channel else None})
    return drafts


def main() -> None:
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help"):
        print("Usage: python3 thread_checker.py <transcript_file> [action_plan_file]")
        sys.exit(0 if len(sys.argv) > 1 else 1)
    transcript_path = sys.argv[1]
    action_plan_path = sys.argv[2] if len(sys.argv) > 2 else None
    if not Path(transcript_path).exists():
        print(f"ERROR: Transcript file not found: {transcript_path}")
        sys.exit(1)

    threads = extract_threads(transcript_path)
    print("=" * 70)
    print("THREAD CHECKER — Pre-Sync Checklist")
    print("=" * 70)
    print(f"Transcript: {Path(transcript_path).name}")
    print(f"Parent threads found: {len(threads)}")
    print()
    by_channel: dict = {}
    for thread in threads:
        by_channel.setdefault((thread["channel"], thread["channel_id"]), []).append(thread)
    print("THREADS TO RE-READ:")
    print("-" * 70)
    total = 0
    for (channel, channel_id), channel_threads in sorted(by_channel.items()):
        print(f"\n  #{channel} ({channel_id})")
        for thread in channel_threads:
            total += 1
            replies = f" — {thread['reply_count']} replies recorded" if thread["reply_count"] > 0 else ""
            print(f'    [{total:2d}] message_ts="{thread["ts"]}"{replies}')
            print(f"         {thread['context'][:80]}")
    print(f"\n  TOTAL: {total} threads. Re-read ALL using slack_read_thread.")
    print()

    if action_plan_path and Path(action_plan_path).exists():
        drafts = extract_unsent_drafts(action_plan_path)
        if drafts:
            print("=" * 70)
            print("UNSENT DRAFT VERIFICATION")
            print("Before marking any draft as 'not sent', re-read its target thread:")
            print("-" * 70)
            for draft in drafts:
                target = f'message_ts="{draft["ts"]}"' if draft["ts"] else "NO TS FOUND — search manually"
                print(f"    Draft {draft['number']}: {draft['title']}")
                print(f"      → slack_read_thread({target})")
            print()
        else:
            print("No unsent drafts with thread TSes found.")
            print()

    print("=" * 70)
    print("Run slack_read_thread for EVERY thread above. Compare reply counts.")
    print("Append new replies to transcript. Do NOT skip any thread.")
    print("=" * 70)


if __name__ == "__main__":
    main()
