#!/usr/bin/env python3
"""Stop hook: detect fabricated Slack TSes in transcript / daily-plan / context writes.

Scans the current session's conversation transcript for Slack TS-shaped values
(NNNNNNNNNN.NNNNNN floats or /pNNNNNNNNNNNNNNNN permalink suffixes) that were
written into transcripts/, daily-plans/, or project context files (CONTEXT.md,
REFERENCE.md, sessions/) but did NOT appear anywhere ELSE in the session — no
MCP slack_read_* result, no Read of a transcript file, no user message containing
the TS, no other tool input.

A TS that appears only inside a Write/Edit/MultiEdit and nowhere else is a
candidate for fabrication: the agent constructed the TS from imagination
rather than reading it from MCP, a synced transcript, or the user.

Logs candidates to ~/.claude/quote-provenance-log.jsonl. Does NOT block.

This is the backstop for the "Quote provenance" posture in the project
instructions. A prose rule fails when narrative coherence overrides factual
rigor; the hook makes the violation visible after the fact.

The motivating incident: an agent fabricated a chat message by tweaking the
millisecond suffix of a real message TS. The fake TS appeared in
transcript/sessions/CONTEXT writes but in no chat-read result. The hook
flags exactly this pattern.

Invoked by Claude Code's Stop hook mechanism. Stdin JSON:
  - session_id
  - transcript_path  (JSONL of all session events)
  - cwd

Exit 0 always. The user is the enforcer; this tool just makes violations visible.
"""

import hashlib
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

HOOKS_DIR = Path(__file__).resolve().parent
if str(HOOKS_DIR) not in sys.path:
    sys.path.insert(0, str(HOOKS_DIR))
HOOKS_ROOT = HOOKS_DIR.parent
if str(HOOKS_ROOT) not in sys.path:
    sys.path.insert(0, str(HOOKS_ROOT))
from _settings import doctor_prologue, hook_enabled  # noqa: E402
from _transcript_state import project_jsonl, provenance_state_valid  # noqa: E402

HOOK_NAME = "quote_provenance_checker"

REDUCER_REVISION = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()

LOG_FILE = Path.home() / ".claude" / "quote-provenance-log.jsonl"

# Slack TS in float form: 10 digits + dot + 6 digits.
TS_FLOAT = re.compile(r'\b(\d{10}\.\d{6})\b')
# Slack permalink form: /p + 16 digits (10 + 6 with no dot).
TS_PERMALINK = re.compile(r'/p(\d{10})(\d{6})\b')

# File-path patterns whose Edit/Write/MultiEdit calls we audit.
CHECKED_PATH_PATTERNS = [
    re.compile(r'/transcripts/slack/'),
    re.compile(r'/transcripts/(gchat|email|meetings)/'),
    re.compile(r'/daily-plans/'),
    re.compile(r'/projects/[^/]+/(CONTEXT|REFERENCE)\.md\b'),
    re.compile(r'/projects/[^/]+/sessions/'),
]

WRITING_TOOLS = {"Edit", "Write", "MultiEdit", "NotebookEdit"}


def extract_tses(text):
    """Return Slack TSes from `text` normalized to 'NNNNNNNNNN.NNNNNN' form."""
    if not text:
        return set()
    if not isinstance(text, str):
        try:
            text = json.dumps(text, default=str)
        except Exception:
            text = str(text)
    out = set()
    for m in TS_FLOAT.finditer(text):
        out.add(m.group(1))
    for m in TS_PERMALINK.finditer(text):
        out.add(f"{m.group(1)}.{m.group(2)}")
    return out


def path_is_checked(path):
    if not path or not isinstance(path, str):
        return False
    return any(p.search(path) for p in CHECKED_PATH_PATTERNS)


def stringify(content):
    """Best-effort string from an anthropic content-block list, dict, or scalar."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for c in content:
            if isinstance(c, dict):
                t = c.get("type")
                if t == "text":
                    parts.append(c.get("text", ""))
                elif t == "tool_result":
                    parts.append(stringify(c.get("content", "")))
                else:
                    try:
                        parts.append(json.dumps(c, default=str))
                    except Exception:
                        parts.append(str(c))
            else:
                parts.append(str(c))
        return "\n".join(parts)
    if isinstance(content, dict):
        try:
            return json.dumps(content, default=str)
        except Exception:
            return str(content)
    return str(content)


def handle_message(event):
    seen_tses = set()
    written_records = []
    msg = event.get("message", {}) or {}
    content = msg.get("content", [])

    # Scalar string content (rare but possible)
    if isinstance(content, str):
        seen_tses.update(extract_tses(content))
        return seen_tses, written_records
    if not isinstance(content, list):
        return seen_tses, written_records

    for c in content:
        if not isinstance(c, dict):
            continue
        ct = c.get("type")

        if ct == "text":
            seen_tses.update(extract_tses(c.get("text", "")))
        elif ct == "tool_result":
            seen_tses.update(extract_tses(stringify(c.get("content", ""))))
        elif ct == "tool_use":
            name = c.get("name", "")
            inp = c.get("input", {}) or {}

            if name in WRITING_TOOLS:
                file_path = inp.get("file_path") or inp.get("notebook_path") or ""
                if not path_is_checked(file_path):
                    # Still count input TSes as "seen" — they were
                    # presumably read from somewhere visible.
                    seen_tses.update(extract_tses(stringify(inp)))
                    continue

                if name == "Write":
                    new_text = inp.get("content", "")
                    old_text = ""
                elif name == "Edit":
                    new_text = inp.get("new_string", "")
                    old_text = inp.get("old_string", "")
                elif name == "MultiEdit":
                    edits = inp.get("edits", []) or []
                    new_text = "\n".join(e.get("new_string", "") for e in edits if isinstance(e, dict))
                    old_text = "\n".join(e.get("old_string", "") for e in edits if isinstance(e, dict))
                else:
                    new_text = stringify(inp)
                    old_text = ""

                added = extract_tses(new_text) - extract_tses(old_text)
                if added:
                    written_records.append({
                        "tool": name,
                        "file": file_path,
                        "added_tses": sorted(added),
                    })
                # Old-string TSes are seen (they were already in the file).
                seen_tses.update(extract_tses(old_text))
            else:
                # Non-writing tool_use — input TSes count as "seen"
                # (e.g., slack_read_thread message_ts argument).
                seen_tses.update(extract_tses(stringify(inp)))
    return seen_tses, written_records


def scan_transcript(transcript: Path, cwd: str):
    def reduce(state, event):
        seen, written = handle_message(event)
        state["seen"].update((value, True) for value in seen)
        state["written"].extend(written)

    state = project_jsonl(
        transcript, namespace="claude-quote-provenance", revision=REDUCER_REVISION,
        context={"cwd": cwd, "home": str(Path.home())},
        initial=lambda: {"seen": {}, "written": []}, reduce=reduce,
        validate=provenance_state_valid,
    )
    return set(state["seen"]), state["written"]


def doctor() -> int:
    lines, _healthy = doctor_prologue(HOOK_NAME)
    lines.append(f"log_file={LOG_FILE}")
    lines.append(f"checked_path_patterns={len(CHECKED_PATH_PATTERNS)}")
    lines.append(f"writing_tools={sorted(WRITING_TOOLS)}")
    print("\n".join(lines))
    return 0


def main(argv: list[str] | None = None) -> int:
    if argv is None:
        argv = sys.argv[1:]
    if "--doctor" in argv:
        return doctor()
    if not hook_enabled(HOOK_NAME):
        return 0

    try:
        input_data = json.load(sys.stdin)
    except Exception:
        return 0

    transcript_path = input_data.get("transcript_path", "")
    session_id = input_data.get("session_id", "unknown")
    cwd = input_data.get("cwd", "")

    if not transcript_path or not os.path.isfile(transcript_path):
        return 0

    try:
        seen_tses, written_records = scan_transcript(Path(transcript_path), cwd)
    except Exception:
        return 0

    # Compute violations: TSes added in writes that appeared nowhere else.
    violations = []
    for rec in written_records:
        fabricated = sorted(set(rec["added_tses"]) - seen_tses)
        if fabricated:
            violations.append({
                "tool": rec["tool"],
                "file": rec["file"],
                "fabricated_tses": fabricated,
            })

    if not violations:
        return 0

    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "session_id": session_id,
        "cwd": cwd,
        "seen_ts_count": len(seen_tses),
        "violations": violations,
    }
    try:
        with open(LOG_FILE, "a") as f:
            f.write(json.dumps(entry) + "\n")
    except Exception:
        pass

    print("", file=sys.stderr)
    print("[QUOTE-PROVENANCE CHECKER]", file=sys.stderr)
    print(
        "Slack-TS-shaped values were written into transcript / daily-plan / "
        "context files that did NOT appear in any other tool input/output, "
        "user message, or assistant text in this session. Possible "
        "fabrication of Slack messages or quote provenance failure.",
        file=sys.stderr,
    )
    for v in violations:
        print(f"  {v['tool']} -> {v['file']}", file=sys.stderr)
        for ts in v["fabricated_tses"]:
            print(f"    fabricated TS: {ts}", file=sys.stderr)
    print(f"Logged to: {LOG_FILE}", file=sys.stderr)
    print(
        "See: the 'Quote provenance' posture in the project instructions.",
        file=sys.stderr,
    )
    print("", file=sys.stderr)

    return 0


if __name__ == "__main__":
    sys.exit(main())
