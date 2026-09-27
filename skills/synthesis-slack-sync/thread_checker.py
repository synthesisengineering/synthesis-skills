#!/usr/bin/env python3
"""
Thread Checker — Pre-sync checklist generator for synthesis-slack-sync.

Reads the local transcript file and daily action plan, extracts every thread TS
and draft target, and outputs a structured checklist of threads that MUST be
re-read during the next sync.

Usage:
    python3 thread_checker.py <transcript_file> [action_plan_file]

Output:
    A checklist of parent thread TSes grouped by channel, with channel IDs.
    The agent MUST re-read every thread listed using slack_read_thread.
"""

import re
from datetime import datetime
from decimal import Decimal
import time
import sys
from pathlib import Path


def acquire_channel(
    channel_id,
    start,
    through,
    *,
    read_channel,
    read_thread,
    search_replies,
    known_thread_ids=(),
    clock=None,
    max_pages=100,
):
    """Collect detailed history, full threads and an in-window search control.

    Callables are owner-selected, read-only connector adapters with their own
    finite request timeouts. They return {ok, messages, response_metadata,
    tool_call_id}; search may use Slack's messages.matches envelope. This
    function neither sends nor writes, and never supplies oldest to threads.
    Raw response custody and account authorization remain with the adapter.
    """
    if not (
        isinstance(channel_id, str) and re.fullmatch(r"[A-Z][A-Z0-9]+", channel_id)
    ):
        raise ValueError("invalid declared channel id")
    if start.tzinfo is None or through.tzinfo is None or start > through:
        raise ValueError("an ordered timezone-aware acquisition window is required")
    if not 1 <= max_pages <= 100:
        raise ValueError("page bound must be between 1 and 100")
    clock = clock or (lambda: datetime.now().astimezone())
    deadline = time.monotonic() + 120
    lo, hi = Decimal(str(start.timestamp())), Decimal(str(through.timestamp()))

    def ts(value):
        if not isinstance(value, str) or not re.fullmatch(r"[1-9]\d{9}\.\d{6}", value):
            raise ValueError("invalid provider timestamp")
        return Decimal(value)

    def pages(call, arguments, search=False):
        rows = []
        cursor = None
        seen = set()
        calls = []
        for _ in range(max_pages):
            if time.monotonic() >= deadline:
                raise ValueError("acquisition time bound reached")
            response = call(**arguments, cursor=cursor, limit=100)
            if time.monotonic() >= deadline:
                raise ValueError("acquisition time bound reached")
            if not isinstance(response, dict) or response.get("ok") is not True:
                raise ValueError("connector read failed; coverage unknown")
            call_id = response.get("tool_call_id")
            if not isinstance(call_id, str) or not call_id:
                raise ValueError("raw tool-call provenance missing")
            calls.append(call_id)
            if response.get("truncated") is True or response.get("complete") is False:
                raise ValueError("connector explicitly reports incomplete coverage")
            data = response.get("messages")
            if search and isinstance(data, dict):
                paging = data.get("pagination", {})
                legacy = data.get("paging", {})
                if not isinstance(paging, dict) or not isinstance(legacy, dict):
                    raise ValueError("invalid search pagination metadata")
                counts = [paging.get("page_count", 1), legacy.get("pages", 1)]
                if any(type(count) is not int or count < 1 for count in counts):
                    raise ValueError("invalid search page count")
                if max(counts) > 1 and not data.get(
                    "response_metadata", response.get("response_metadata", {})
                ).get("next_cursor"):
                    raise ValueError(
                        "search uses unsupported page pagination; adapter must expose complete cursors"
                    )
                next_cursor = data.get(
                    "response_metadata", response.get("response_metadata", {})
                ).get("next_cursor")
                data = data.get("matches")
            else:
                next_cursor = response.get("response_metadata", {}).get("next_cursor")
            if not isinstance(data, list) or len(data) > 1000:
                raise ValueError("unbounded or absent message page")
            for message in data:
                if not isinstance(message, dict):
                    raise ValueError("invalid message object")
                observed_channel = message.get("channel", channel_id)
                if isinstance(observed_channel, dict):
                    observed_channel = observed_channel.get("id")
                if observed_channel != channel_id:
                    raise ValueError("message belongs to a different channel")
            rows.extend(data)
            if len(rows) > 10000:
                raise ValueError("message bound exceeded")
            if next_cursor not in (None, "") and not isinstance(next_cursor, str):
                raise ValueError("invalid pagination cursor")
            if next_cursor is None or next_cursor == "":
                metadata = response.get("response_metadata")
                if search and isinstance(response.get("messages"), dict):
                    metadata = response["messages"].get("response_metadata", metadata)
                explicit_terminal = (response.get("has_more") is False or response.get("complete") is True
                                     or isinstance(metadata, dict) and "next_cursor" in metadata)
                if not explicit_terminal:
                    raise ValueError("pagination completion is not explicitly observed")
                if response.get("has_more") is True:
                    raise ValueError("pagination cursor absent; coverage unknown")
                return rows, {
                    "complete": True,
                    "next_cursor": None,
                    "observed_at": clock().isoformat(),
                    "tool_call_id": calls[-1],
                    "tool_call_ids": calls,
                }
            if not isinstance(next_cursor, str) or next_cursor in seen:
                raise ValueError("repeated or invalid pagination cursor")
            seen.add(next_cursor)
            cursor = next_cursor
        raise ValueError("page bound reached; coverage unknown")

    history, hproof = pages(
        read_channel,
        {
            "channel_id": channel_id,
            "oldest": str(lo),
            "latest": str(hi),
            "detail": "detailed",
        },
    )
    hits, sproof = pages(
        search_replies,
        {
            "channel_id": channel_id,
            "oldest": str(lo),
            "latest": str(hi),
            "detail": "detailed",
        },
        search=True,
    )
    parents = set(known_thread_ids)
    controls = []
    for row in history:
        ts(row.get("ts"))
        if row.get("reply_count", 0):
            parents.add(row["ts"])
    for row in hits:
        value = ts(row.get("ts"))
        if lo <= value <= hi:
            controls.append(row["ts"])
            if row.get("thread_ts"):
                parents.add(row["thread_ts"])
    if not controls:
        raise ValueError("no in-window positive control; absence remains unknown")
    threads = []
    for parent in sorted(parents):
        ts(parent)
        rows, proof = pages(
            read_thread,
            {"channel_id": channel_id, "message_ts": parent, "detail": "detailed"},
        )
        ids = [row.get("ts") for row in rows]
        if parent not in ids or len(ids) != len(set(ids)):
            raise ValueError("thread parent missing or duplicate reply")
        for value in ids:
            ts(value)
        if any(
            row.get("thread_ts") == parent
            and lo <= ts(row["ts"]) <= hi
            and row["ts"] not in ids
            for row in hits
        ):
            raise ValueError("thread pass missed an in-window search reply")
        threads.append({**proof, "parent_ts": parent, "messages": rows})
    return {
        "id": channel_id,
        "known_thread_ids": list(known_thread_ids),
        "history": {
            **hproof,
            "detail": "detailed",
            "from": start.isoformat(),
            "through": through.isoformat(),
            "messages": history,
        },
        "reply_search": {
            **sproof,
            "from": start.isoformat(),
            "through": through.isoformat(),
            "messages": hits,
            "positive_control_ids": controls,
        },
        "threads": threads,
    }


def extract_threads(transcript_path: str) -> list[dict]:
    """Extract parent thread TSes and metadata from a transcript file."""
    content = Path(transcript_path).read_text()
    lines = content.split("\n")

    threads = []
    seen_ts = set()
    current_channel = None
    current_channel_id = None

    # Channel header with ID: ## #channel-name (CHANNEL_ID)
    channel_header_with_id = re.compile(r"^#{1,3}\s+#([\w-]+)\s*\(([A-Z][A-Z0-9]+)\)")
    # Channel header without ID: ### #channel-name (used in mid-day/evening sync sections)
    channel_header_no_id = re.compile(r"^#{1,3}\s+#([\w-]+)\s*$")

    # TS pattern in parentheses: (TS: 1775064672.791199) — legacy pre-v3.1.0 format
    ts_in_parens = re.compile(r"\(TS:\s*([\d.]+)\)")
    # TS embedded in Slack permalink path: /p1775064672791199 — v3.1.0+ format.
    # Captures the 16-digit suffix; we re-insert the dot to normalize.
    ts_in_permalink = re.compile(r"/p(\d{10})(\d{6})\b")

    # Reply count patterns
    reply_count_pattern = re.compile(r"(\d+)\s*repl(?:y|ies)")
    thread_label = re.compile(r"\*\*Thread\s*\((\d+)\s*repl")

    # First pass: build channel name → ID map from headers that have IDs
    channel_id_map = {}
    for line in lines:
        m = channel_header_with_id.match(line.strip())
        if m:
            channel_id_map[m.group(1)] = m.group(2)

    for i, line in enumerate(lines):
        # Track channel context — try header with ID first, then without
        ch_match = channel_header_with_id.match(line.strip())
        if ch_match:
            current_channel = ch_match.group(1)
            current_channel_id = ch_match.group(2)
            continue
        ch_match_no_id = channel_header_no_id.match(line.strip())
        if ch_match_no_id:
            current_channel = ch_match_no_id.group(1)
            current_channel_id = channel_id_map.get(current_channel)
            continue

        # Find TSes — only from lines that look like message headers or thread parents
        # (lines starting with #### or containing "TS:" or a Slack permalink in a
        # header-like context). Both legacy `(TS: ...)` text and v3.1.0+ permalink
        # URLs are accepted.
        ts_matches = list(ts_in_parens.findall(line))
        for prefix, suffix in ts_in_permalink.findall(line):
            ts_matches.append(f"{prefix}.{suffix}")
        if not ts_matches:
            continue

        for ts in ts_matches:
            if ts in seen_ts:
                continue

            # Determine if this is a parent message or a reply
            # Parent messages are on lines starting with ####, or top-level entries
            # Reply TSes are typically on lines starting with "- " (list items)
            stripped = line.strip()
            is_reply = stripped.startswith("- ") or stripped.startswith("> ")

            # Skip reply TSes — we only want parent messages
            if is_reply:
                continue

            # Get reply count from surrounding context
            reply_count = 0
            context_window = "\n".join(lines[max(0, i) : min(len(lines), i + 5)])
            thread_match = thread_label.search(context_window)
            if thread_match:
                reply_count = int(thread_match.group(1))
            else:
                reply_match = reply_count_pattern.search(context_window)
                if reply_match:
                    reply_count = int(reply_match.group(1))

            # Get context
            context = stripped[:100]

            seen_ts.add(ts)
            threads.append(
                {
                    "ts": ts,
                    "channel": current_channel or "unknown",
                    "channel_id": current_channel_id or "?",
                    "reply_count": reply_count,
                    "context": context,
                }
            )

    return threads


def extract_unsent_drafts(action_plan_path: str) -> list[dict]:
    """Extract unsent draft thread TSes from the action plan.

    A draft is considered SENT (and is skipped) when ANY of these signals are
    present:
      - The H3 line itself contains `SENT` or `~~` markers (legacy pre-v3.2.0
        form: ``### ~~Draft N: title~~ ✅ SENT by Rajiv at ... in #channel``).
      - A `**Sent:**` paragraph appears within the draft's section (the v3.2.0+
        canonical form, also written by synthesis-console's mark-as-sent
        endpoint).

    Either signal alone is sufficient. The parser is intentionally tolerant —
    files on disk may contain either form during the transition.
    """
    content = Path(action_plan_path).read_text()
    drafts = []
    seen_drafts = set()

    # Find draft sections that are NOT yet sent.
    lines = content.split("\n")
    i = 0
    while i < len(lines):
        line = lines[i]

        # Match draft headers: ### Draft N: ...
        draft_match = re.match(r"^###\s+Draft\s+(\d+):\s*(.*)", line.strip())
        if not draft_match:
            i += 1
            continue

        # Legacy sent-state signals in the heading line itself.
        if "~~" in line or "SENT" in line:
            i += 1
            continue

        # New (v3.2.0+) sent-state signal: a `**Sent:**` paragraph within the
        # draft's body region (before the next H3/H2 or end of section).
        section_end = i + 1
        while section_end < len(lines):
            nxt = lines[section_end]
            if re.match(r"^#{1,3}\s", nxt):
                break
            section_end += 1
        section_block = "\n".join(lines[i:section_end])
        if re.search(
            r"^\s*\*\*\s*Sent(?:\s*at)?\s*:?\s*\*\*", section_block, re.MULTILINE
        ):
            i += 1
            continue

        draft_num = int(draft_match.group(1))
        draft_title = draft_match.group(2)

        if draft_num in seen_drafts:
            i += 1
            continue
        seen_drafts.add(draft_num)

        # Scan the next ~20 lines for a TS — accept legacy `TS: ...` text or
        # v3.1.0+ Slack permalink path `/pNNNNNNNNNNNNNNNN`.
        block = "\n".join(lines[i : i + 20])
        ts_match = re.search(r"TS:\s*([\d.]+)", block)
        permalink_match = re.search(r"/p(\d{10})(\d{6})\b", block)
        channel_match = re.search(r"Channel.*?([A-Z][A-Z0-9]{8,})", block)
        if not ts_match and permalink_match:
            # Synthesize a match-like wrapper exposing group(1) for the
            # downstream code below.
            class _M:
                def __init__(self, ts):
                    self._ts = ts

                def group(self, _n):
                    return self._ts

            ts_match = _M(f"{permalink_match.group(1)}.{permalink_match.group(2)}")
        # Permalink also carries the channel id under /archives/ — pull it.
        if not channel_match:
            channel_match = re.search(r"/archives/([A-Z][A-Z0-9]{8,})/", block)

        drafts.append(
            {
                "number": draft_num,
                "title": draft_title,
                "ts": ts_match.group(1) if ts_match else None,
                "channel_id": channel_match.group(1) if channel_match else None,
            }
        )

        i += 1

    return drafts


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 thread_checker.py <transcript_file> [action_plan_file]")
        sys.exit(1)

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

    # Group by channel
    by_channel = {}
    for t in threads:
        key = (t["channel"], t["channel_id"])
        if key not in by_channel:
            by_channel[key] = []
        by_channel[key].append(t)

    print("THREADS TO RE-READ:")
    print("-" * 70)
    total = 0
    for (channel, channel_id), channel_threads in sorted(by_channel.items()):
        print(f"\n  #{channel} ({channel_id})")
        for t in channel_threads:
            total += 1
            replies = (
                f" — {t['reply_count']} replies recorded"
                if t["reply_count"] > 0
                else ""
            )
            print(f'    [{total:2d}] message_ts="{t["ts"]}"{replies}')
            print(f"         {t['context'][:80]}")

    print(f"\n  TOTAL: {total} threads. Re-read ALL using slack_read_thread.")
    print()

    # Unsent draft verification
    if action_plan_path and Path(action_plan_path).exists():
        drafts = extract_unsent_drafts(action_plan_path)

        if drafts:
            print("=" * 70)
            print("UNSENT DRAFT VERIFICATION")
            print("Before marking any draft as 'not sent', re-read its target thread:")
            print("-" * 70)
            for d in drafts:
                ts_info = (
                    f'message_ts="{d["ts"]}"'
                    if d["ts"]
                    else "NO TS FOUND — search manually"
                )
                print(f"    Draft {d['number']}: {d['title']}")
                print(f"      → slack_read_thread({ts_info})")
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
