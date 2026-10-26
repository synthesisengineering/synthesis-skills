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
# The same permalink with its channel: /archives/C0123ABC/p1775064672791199. The link's channel
# id wins over the heading's, so a digest or cross-channel link keeps its own channel.
PERMALINK = re.compile(r"/archives/([A-Z][A-Z0-9]+)/p(\d{10})(\d{6})\b")
# Any H1-H3 heading: a section or channel heading ends the previous channel's listing.
SECTION = re.compile(r"^#{1,3}\s")
REPLY_COUNT = re.compile(r"(\d+)\s*repl(?:y|ies)")
THREAD_LABEL = re.compile(r"\*\*Thread\s*\((\d+)\s*repl")
# A section listing the threads a sync read ("## Part C — threads re-read"): every message there is a thread
# parent, at any indent, linked or bare, in the link's channel or the backticked id on its line (2026-10-26: a
# DM-half transcript's five threads with replies sat there, as indented bullets, and none was listed).
READ_THREADS = re.compile(r"^#{1,3}\s.*\bthreads?\b.*\b(?:re-?read|read)\b", re.I)
BARE_TS = re.compile(r"(?<![\d.])(\d{10})\.(\d{6})(?!\d)")
CHANNEL_CODE = re.compile(r"`([CDG][A-Z0-9]{8,})`")
NAMED_MESSAGE = re.compile(r"\(ts \d{10}\.\d{6}\)")  # "(ts …)" names one message, such as a reply


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


def stamps_in(line: str) -> list[tuple[str | None, str]]:
    """(channel id or None, TS) for every message link or legacy `(TS: ...)` on a line."""
    found = [(m.group(1), f"{m.group(2)}.{m.group(3)}") for m in PERMALINK.finditer(line)]
    linked = {ts for _, ts in found}
    found += [(None, f"{a}.{b}") for a, b in TS_IN_PERMALINK.findall(line) if f"{a}.{b}" not in linked]
    return found + [(None, ts) for ts in TS_IN_PARENS.findall(line)]


def extract_threads(transcript_path: str | None, *, content: str | None = None) -> list[dict]:
    """Extract parent thread TSes and metadata from a transcript file.

    Two layouts are read. Per message: a parent is a line or heading carrying a TS, and the
    bullets under it are its replies. Listed (2026-10): a channel heading is followed by one
    bullet per top-level message, and a thread is a channel heading that carries its parent's TS,
    with the replies as bullets under it. An indented bullet is never a parent, and a bullet
    outside a channel listing (a digest such as "Touches the principal") only points at a message
    recorded elsewhere."""
    if content is None:
        content = Path(transcript_path).read_text()
    lines = structural_lines(content)
    # First pass: channel name -> ID map from headers that carry an ID.
    channel_ids = {}
    for line in lines:
        found = CHANNEL_WITH_ID.match(line.strip())
        if found:
            channel_ids[found.group(1)] = found.group(2)
    names = {cid: name for name, cid in channel_ids.items()}

    threads, seen = [], {}

    def record(stamps, replies, context):
        for link_channel, ts in stamps:
            cid = link_channel or channel_id
            if (cid, ts) in seen:  # listed twice, say as a top-level message and as a thread
                seen[(cid, ts)]["reply_count"] = max(seen[(cid, ts)]["reply_count"], replies)
                continue
            name = names.get(cid) or (channel if cid == channel_id else None)
            seen[(cid, ts)] = {"ts": ts, "channel": name or "unknown", "channel_id": cid or "?",
                               "reply_count": replies, "context": context[:100]}
            threads.append(seen[(cid, ts)])

    channel = channel_id = None
    listing = parent_open = False  # under a channel heading; a parent recorded since that heading
    read_section = with_replies = False  # in a section of threads read; under its "with replies" bullet
    for i, line in enumerate(lines):
        stripped = line.strip()
        found = CHANNEL_WITH_ID.match(stripped)
        bare = None if found else CHANNEL_NO_ID.match(stripped)
        if found or bare:
            channel = (found or bare).group(1)
            # never inherit the previous channel's ID
            channel_id = found.group(2) if found else channel_ids.get(channel)
            listing, parent_open, read_section = True, False, False
        elif SECTION.match(stripped):
            listing = parent_open = with_replies = False
            read_section = bool(READ_THREADS.match(stripped))
        if read_section:
            if stripped.startswith("- ") and not line[:1].isspace():
                with_replies = bool(re.search(r"\b(?:with|gained) repl", stripped, re.I))
            stamps = stamps_in(line)
            code = CHANNEL_CODE.search(line)
            stamps += [(code.group(1) if code else None, f"{a}.{b}") for a, b in
                       BARE_TS.findall(NAMED_MESSAGE.sub("", line)) if f"{a}.{b}" not in {ts for _, ts in stamps}]
            count = REPLY_COUNT.search(stripped)
            record(stamps, int(count.group(1)) if count else int(with_replies and line[:1].isspace()), stripped)
            continue
        if stripped.startswith("|"):  # a coverage or watermark table points at messages recorded elsewhere
            continue
        # TSes come from message-header-like lines: legacy `(TS: ...)` text or a v3.1.0+ permalink.
        stamps = stamps_in(line)
        if not stamps:
            continue
        if stripped.startswith("- "):
            if parent_open or not listing or line[:1].isspace():  # a reply, a detail, a digest pointer
                continue
            context = stripped  # the next bullet is another message, not this one's thread label
        else:
            parent_open = True
            context = "\n".join(lines[i:i + 5])
        count = THREAD_LABEL.search(context) or REPLY_COUNT.search(context)
        record(stamps, int(count.group(1)) if count else 0, stripped)
    return threads


def message_links(content: str) -> int:
    """Message links and legacy TSes outside quoted and fenced text: when there are some but no
    parent was recognized, the layout is one this checker cannot read."""
    return sum(len(stamps_in(line)) for line in structural_lines(content))


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
    links = message_links(Path(transcript_path).read_text())
    if links and not threads:
        # An empty checklist reads as "nothing to re-read" (2026-10-22: every channel transcript
        # of a new layout printed zero threads for two days).
        print(f"UNPARSED: {Path(transcript_path).name} has {links} message link(s) but no thread "
              "parent this checker recognizes. Re-read every thread the transcript names; do not "
              "treat this as an empty checklist.")
        sys.exit(2)
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
