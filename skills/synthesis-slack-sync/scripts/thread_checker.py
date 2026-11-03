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
# A heading about one channel's messages: "### #channel-name — Jane's question, [TS](link)" or
# "## #channel-name (afternoon)". It names the channel for a message that carries none of its own, but
# its bullets are replies or details, not a listing. A heading that names several channels names none.
CHANNEL_NAMED = re.compile(r"^#{1,3}\s+#([\w-]+)\s+[—–(-]")
# TS pattern in parentheses: (TS: 1775064672.791199), or (TS 1775064672.791199) in message headers
# of 2026-04 — legacy pre-v3.1.0 format
TS_IN_PARENS = re.compile(r"\(TS(?::\s*|\s+(?=\d{10}\.\d{6}\)))([\d.]+)\)")
# TS embedded in Slack permalink path: /p1775064672791199 — v3.1.0+ format.
# Captures the 16-digit suffix; the dot is re-inserted to normalize.
TS_IN_PERMALINK = re.compile(r"/p(\d{10})(\d{6})\b")
# The same permalink with its channel: /archives/C0123ABC/p1775064672791199. The link's channel
# id wins over the heading's, so a digest or cross-channel link keeps its own channel.
PERMALINK = re.compile(r"/archives/([A-Z][A-Z0-9]+)/p(\d{10})(\d{6})\b")
# A reply's permalink also names its thread: /archives/C0123ABC/p1775064700000000?thread_ts=1775064672.791199
REPLY_LINK = re.compile(r"/archives/([A-Z][A-Z0-9]+)/p(\d{10})(\d{6})\?[^\s)\]]*?\bthread_ts=(\d{10}\.\d{6})")
# Any H1-H3 heading: a section or channel heading ends the previous channel's listing, and every
# channel heading at its level or deeper (2026-11-03: a bare TS 566 lines and many sections after a
# channel heading was filed under that channel).
SECTION = re.compile(r"^(#{1,3})\s")
REPLY_COUNT = re.compile(r"(\d+)\s*repl(?:y|ies)")
THREAD_LABEL = re.compile(r"\*\*Thread\s*\((\d+)\s*repl")
# A section listing the threads a sync read ("## Part C — threads re-read"): every message there is a thread
# parent, at any indent, linked or bare, in the link's channel or the channel id on its line (2026-10-26: a
# DM-half transcript's five threads with replies sat there, as indented bullets, and none was listed).
READ_THREADS = re.compile(r"^#{1,3}\s.*\bthreads?\b.*\b(?:re-?read|read)\b", re.I)
BARE_TS = re.compile(r"(?<![\d.])(\d{10})\.(\d{6})(?!\d)")
# A channel, DM or group id written on a line, backticked or not: `C0123ABC`, (D0123ABC, ...)
CHANNEL_CODE = re.compile(r"(?<![\w/])([CDG](?=[A-Z0-9]*\d)[A-Z0-9]{8,10})(?!\w)")
LINK_TARGET = re.compile(r"\]\([^)\s]*\)|https?://\S+")
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
    """(channel id or None, TS) for every message link or legacy `(TS: ...)` on a line. A reply's
    link stands for its thread, in the link's channel: the thread is what a re-read reads."""
    threads = {f"{m.group(2)}.{m.group(3)}": (m.group(1), m.group(4)) for m in REPLY_LINK.finditer(line)}
    found = [threads.get(f"{m.group(2)}.{m.group(3)}", (m.group(1), f"{m.group(2)}.{m.group(3)}"))
             for m in PERMALINK.finditer(line)]
    linked = {ts for _, ts in found} | set(threads)
    found += [(None, f"{a}.{b}") for a, b in TS_IN_PERMALINK.findall(line) if f"{a}.{b}" not in linked]
    return found + [(None, ts) for ts in TS_IN_PARENS.findall(line)]


def line_channel(line: str, at: int = 0) -> str | None:
    """The channel a line writes for a TS at position `at` that carries none: the nearest channel id
    before it ("`D0AAA` ts; `D0BBB` ts, ts"), else the line's one id. An id inside a link counts for
    nothing, and nor does a `#name` in prose (2026-11-03: a sentence mentioning one channel listed
    two threads of two others)."""
    links = [m.span() for m in LINK_TARGET.finditer(line)]
    codes = [(m.start(), m.group(1)) for m in CHANNEL_CODE.finditer(line)
             if not any(start <= m.start() < end for start, end in links)]
    before = [code for start, code in codes if start < at]
    return before[-1] if before else (codes[0][1] if len({code for _, code in codes}) == 1 else None)


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

    seen, rank = {}, {}  # (channel id, TS) -> thread; -> 2 from its own link, 1 its line or heading, 0 none

    def record(stamps, replies, context, where):
        for link_channel, ts in stamps:
            cid = link_channel or where(ts)
            rank[(cid, ts)] = max(rank.get((cid, ts), 0), 2 if link_channel else int(cid is not None))
            if (cid, ts) in seen:  # listed twice, say as a top-level message and as a thread
                seen[(cid, ts)]["reply_count"] = max(seen[(cid, ts)]["reply_count"], replies)
                continue
            name = names.get(cid) or (channel if cid == channel_id else None)
            seen[(cid, ts)] = {"ts": ts, "channel": name or "unknown", "channel_id": cid or "?",
                               "reply_count": replies, "context": context[:100]}

    channel = channel_id = None
    scope = []  # (level, channel, id) of each enclosing heading that names a channel, outermost first
    listing = parent_open = False  # under a channel heading; a parent recorded since that heading
    read_section = with_replies = False  # in a section of threads read; under its "with replies" bullet
    for i, line in enumerate(lines):
        stripped = line.strip()
        heading = SECTION.match(stripped)
        if heading:
            level = len(heading.group(1))
            scope = [entry for entry in scope if entry[0] < level]
            found = CHANNEL_WITH_ID.match(stripped)
            listing = bool(found or CHANNEL_NO_ID.match(stripped))
            named = found or CHANNEL_NO_ID.match(stripped) or CHANNEL_NAMED.match(stripped)
            code = None if named else line_channel(stripped)  # "## Outside the targets: #name (C0123ABC)"
            if named:  # never inherit the previous channel's ID
                scope.append((level, named.group(1), found.group(2) if found else channel_ids.get(named.group(1))))
            elif code:
                scope.append((level, names.get(code), code))
            channel, channel_id = scope[-1][1:] if scope else (None, None)
            parent_open = with_replies = False
            # A heading that carries a message's TS names that one message, even when it says the
            # thread was read in full; only a heading over several threads opens a section of them.
            read_section = not listing and bool(READ_THREADS.match(stripped)) and not stamps_in(stripped)
        if read_section:
            if stripped.startswith("- ") and not line[:1].isspace():
                with_replies = bool(re.search(r"\b(?:with|gained) repl", stripped, re.I))
            stamps = stamps_in(line)
            linked = {ts for _, ts in stamps} | {f"{a}.{b}" for a, b in TS_IN_PERMALINK.findall(line)}
            stamps += [(None, f"{a}.{b}") for a, b in
                       BARE_TS.findall(NAMED_MESSAGE.sub("", line)) if f"{a}.{b}" not in linked]
            count = REPLY_COUNT.search(stripped)
            # A list of threads read gathers several channels: each TS takes the id written before it.
            record(stamps, int(count.group(1)) if count else int(with_replies and line[:1].isspace()), stripped,
                   lambda ts: line_channel(line, line.find(ts)) or channel_id)
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
        # A message header belongs to the channel whose heading encloses it.
        record(stamps, int(count.group(1)) if count else 0, stripped,
               lambda ts: channel_id or line_channel(line, line.find(ts)))
    # A TS read again with weaker evidence of its channel is the same message: keep the best reading,
    # with the highest reply count any reading recorded.
    best = {}
    for key, strength in rank.items():
        if strength > rank.get(best.get(key[1]), -1):
            best[key[1]] = key
    weaker = {key for key in seen if rank[key] < rank[best[key[1]]]}
    for key in weaker:
        kept = seen[best[key[1]]]
        kept["reply_count"] = max(kept["reply_count"], seen[key]["reply_count"])
    return [thread for key, thread in seen.items() if key not in weaker]


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
