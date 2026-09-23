#!/usr/bin/env python3
"""PreToolUse hook that blocks sub-agent dispatches with lazy-shortcut framings.

Triggered before the `Agent` tool fires (the dispatch tool for sub-agents in
Claude Code). Scans the brief that would be passed to the sub-agent for
costume vocabulary from the anti-shortcut catalog. If detected, blocks the
dispatch and tells the orchestrating agent to revise the brief.

This is the highest-leverage hook in the anti-shortcut system. Bad framing in
sub-agent briefs propagates through entire sub-agent runs — by the time the
sub-agent reports back with "I left X as a follow-up" (the costume), the
half-applied work is already done. Catching the costume in the BRIEF before
dispatch prevents the cascade.

Receives JSON on stdin per Claude Code's PreToolUse hook protocol:
  - tool_name
  - tool_input  (the parameters being passed to the tool)
  - session_id
  - cwd

Decision protocol:
  - For tool_name == "Agent" (the sub-agent dispatch tool): scan tool_input.prompt
    for catalog phrases; if detected, emit JSON to stdout with
    {"decision": "block", "reason": "<reason>"} and exit 0. The reason lists
    the detected phrases and concrete rewrite suggestions.
  - For any other tool_name: exit 0 silently with no stdout output (does not
    affect tool execution).

Logs blocked dispatches to ~/.claude/anti-shortcut-brief-block-log.jsonl for
the audit trail.

This hook complements (does not replace) the Stop-hook backstop at
lazy-shortcut-detector.py, which catches phrases that survived to the
final assistant message.
"""

import json
import os
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
from _anti_shortcut_catalog import (  # noqa: E402
    load_catalog,
    match_in_text,
    suggested_rewrite_hint,
)

HOOK_NAME = "sub_agent_brief_scanner"


LOG_FILE = Path.home() / ".claude" / "anti-shortcut-brief-block-log.jsonl"

# The tool names that dispatch sub-agents. Different Claude Code versions and
# tool catalogs use different names — we scan a small set to be robust.
SUB_AGENT_DISPATCH_TOOLS = {"Agent", "Task", "task"}


def _append_block_log(entry: dict) -> None:
    """Append a block-event log entry. Best-effort."""
    try:
        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(LOG_FILE, "a") as f:
            f.write(json.dumps(entry) + "\n")
    except Exception as e:
        print(f"[sub-agent-brief-scanner] failed to write log: {e}", file=sys.stderr)


def _extract_brief(tool_input: dict) -> str:
    """Find the brief/prompt text inside the tool_input dict.

    Different tool variants use different field names. We check the common
    ones in order.
    """
    if not isinstance(tool_input, dict):
        return ""

    for key in ("prompt", "instructions", "message", "task", "description"):
        v = tool_input.get(key)
        if isinstance(v, str) and v:
            return v
    return ""


def _build_block_reason(detections: list) -> str:
    """Compose the human-readable block reason."""
    lines = [
        "Sub-agent dispatch BLOCKED — the brief contains costume vocabulary "
        "that signals the lazy-shortcut antipattern. Sub-agents read these "
        "framings as license to leave half-applied work. Revise the brief "
        "to specify the COMPLETENESS required, not the minimization of effort.",
        "",
        "Detected phrases:",
    ]
    # Deduplicate by phrase_id while preserving first-seen order.
    seen = set()
    for d in detections:
        if d.phrase_id in seen:
            continue
        seen.add(d.phrase_id)
        lines.append(
            f"  • {d.phrase_id} [{d.category}, severity={d.severity}]: "
            f"{d.matched_text!r}"
        )
        lines.append(f"      hint: {suggested_rewrite_hint(d.phrase_id)}")

    lines.extend([
        "",
        "Reference: the 'Sub-agent dispatch and acceptance hygiene' posture in "
        "the project instructions and the synthesis-anti-shortcuts skill.",
    ])
    return "\n".join(lines)


def doctor() -> int:
    catalog = load_catalog()
    lines, _healthy = doctor_prologue(HOOK_NAME)
    lines.append(f"log_file={LOG_FILE}")
    lines.append(f"catalog_phrases={len(catalog.phrases)}")
    lines.append(f"dispatch_tools={sorted(SUB_AGENT_DISPATCH_TOOLS)}")
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
        # Malformed stdin — let the tool proceed.
        return 0

    tool_name = input_data.get("tool_name", "")
    tool_input = input_data.get("tool_input", {}) or {}
    session_id = input_data.get("session_id", "unknown")
    cwd = input_data.get("cwd", "")

    # Only act on sub-agent dispatch tools.
    if tool_name not in SUB_AGENT_DISPATCH_TOOLS:
        return 0

    brief = _extract_brief(tool_input)
    if not brief:
        return 0

    detections = match_in_text(brief, exclude_exempt=True)
    if not detections:
        return 0

    # We have detections. Build the block decision.
    reason = _build_block_reason(detections)

    timestamp = datetime.now(timezone.utc).isoformat()
    log_entry = {
        "timestamp": timestamp,
        "session_id": session_id,
        "cwd": cwd,
        "tool_name": tool_name,
        "brief_preview": brief[:300] + ("…" if len(brief) > 300 else ""),
        "detections": [
            {
                "phrase_id": d.phrase_id,
                "category": d.category,
                "severity": d.severity,
                "matched_text": d.matched_text,
                "position": d.position,
            }
            for d in detections
        ],
    }
    _append_block_log(log_entry)

    # Emit JSON decision to stdout. Claude Code's PreToolUse hook protocol
    # reads this and blocks the tool call.
    decision = {"decision": "block", "reason": reason}
    print(json.dumps(decision))

    return 0


if __name__ == "__main__":
    sys.exit(main())
