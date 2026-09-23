#!/usr/bin/env python3
"""Stop hook that scans the last assistant message for lazy-shortcut phrases.

Reads detections from the shared catalog via the _anti_shortcut_catalog
loader. Logs every detection to ~/.claude/lazy-shortcut-log.jsonl with full
structure (phrase_id, category, severity, excerpt, suggested rewrite hint,
lesson link, skill reference).

Implements an escalation policy: tracks per-session violation counts in
~/.claude/lazy-shortcut-session-counts.json. On the FIRST violation in a session,
emits a loud stderr warning. On the Nth violation (block_threshold from the
catalog, default 3), emits an escalation message telling the agent to
acknowledge the antipattern explicitly. If the agent's message contains an
explicit acknowledgment (detected via _anti_shortcut_catalog.is_acknowledgment),
the session count resets.

Does NOT block — Stop hooks fire after the message has been sent. This hook
is the SAFETY NET behind the pre-response self-check and the constraint-first
protocol in the project instructions (full catalog: the
synthesis-anti-shortcuts skill), alongside the PreToolUse hook on
sub-agent dispatch (sub_agent_brief_scanner.py). The user is the final
enforcer; this hook makes violations visible and tracks trends.

Invoked by Claude Code's Stop hook mechanism. Receives JSON on stdin with:
  - session_id
  - transcript_path (JSONL of all session events)
  - cwd

Exit 0 always.
"""

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

# Make the sibling loader importable when invoked as a script.
HOOKS_DIR = Path(__file__).resolve().parent
if str(HOOKS_DIR) not in sys.path:
    sys.path.insert(0, str(HOOKS_DIR))
HOOKS_ROOT = HOOKS_DIR.parent
if str(HOOKS_ROOT) not in sys.path:
    sys.path.insert(0, str(HOOKS_ROOT))

from _settings import doctor_prologue, hook_enabled  # noqa: E402
from _transcript_state import last_messages  # noqa: E402

from _anti_shortcut_catalog import (  # noqa: E402
    load_catalog,
    match_in_text,
    suggested_rewrite_hint,
    is_acknowledgment,
)

HOOK_NAME = "lazy_shortcut_detector"


LOG_FILE = Path.home() / ".claude" / "lazy-shortcut-log.jsonl"
SESSION_COUNTS_FILE = Path.home() / ".claude" / "lazy-shortcut-session-counts.json"


# ---------------------------------------------------------------------------
# Transcript projection — shared by the Claude text detectors
# ---------------------------------------------------------------------------


def get_last_assistant_text(transcript_path: str) -> str:
    """Return the last assistant text from the verified shared projection."""
    return last_messages(transcript_path)[0]


# ---------------------------------------------------------------------------
# Session-count tracking for escalation
# ---------------------------------------------------------------------------


def _load_session_counts() -> dict:
    """Load the session-counts file. Returns {} on any failure."""
    if not SESSION_COUNTS_FILE.exists():
        return {}
    try:
        with open(SESSION_COUNTS_FILE, "r") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _save_session_counts(counts: dict) -> None:
    """Persist the session-counts file. Best-effort — failures are logged but ignored."""
    try:
        SESSION_COUNTS_FILE.parent.mkdir(parents=True, exist_ok=True)
        # Atomic write: temp file + rename
        tmp = SESSION_COUNTS_FILE.with_suffix(".json.tmp")
        with open(tmp, "w") as f:
            json.dump(counts, f, indent=2)
        os.replace(tmp, SESSION_COUNTS_FILE)
    except Exception as e:
        print(f"[lazy-shortcut-detector] failed to save session counts: {e}", file=sys.stderr)


def _bump_session_count(counts: dict, session_id: str, detections: list, timestamp: str) -> dict:
    """Update the per-session counter with new detections."""
    entry = counts.get(session_id) or {"count": 0, "last_seen_ts": "", "categories_seen": []}
    entry["count"] = int(entry.get("count", 0)) + len(detections)
    entry["last_seen_ts"] = timestamp
    cats = set(entry.get("categories_seen") or [])
    cats.update(d.category for d in detections)
    entry["categories_seen"] = sorted(cats)
    counts[session_id] = entry
    return entry


def _reset_session(counts: dict, session_id: str, timestamp: str) -> None:
    """Reset a session's counter after an acknowledgment."""
    counts[session_id] = {
        "count": 0,
        "last_seen_ts": timestamp,
        "categories_seen": [],
        "last_acknowledged_ts": timestamp,
    }


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------


def _append_log(entries: list) -> None:
    """Append detection entries to the JSONL log. Best-effort."""
    if not entries:
        return
    try:
        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(LOG_FILE, "a") as f:
            for e in entries:
                f.write(json.dumps(e) + "\n")
    except Exception as e:
        print(f"[lazy-shortcut-detector] failed to write log: {e}", file=sys.stderr)


# ---------------------------------------------------------------------------
# Stderr presentation
# ---------------------------------------------------------------------------


def _emit_first_violation_warning(detections: list) -> None:
    """Loud warning on the first violation of a session."""
    print("", file=sys.stderr)
    print("[ANTI-SHORTCUT DETECTOR]", file=sys.stderr)
    print("The last message contained lazy-shortcut antipattern(s):", file=sys.stderr)
    for d in detections:
        print(f"  - {d.phrase_id}  [{d.category}, severity={d.severity}]", file=sys.stderr)
        print(f"      matched: {d.matched_text!r}", file=sys.stderr)
        hint = suggested_rewrite_hint(d.phrase_id)
        print(f"      hint:    {hint}", file=sys.stderr)
    print(f"Logged to: {LOG_FILE}", file=sys.stderr)
    print(
        "See methodology: synthesis-skills/skills/synthesis-anti-shortcuts",
        file=sys.stderr,
    )
    print("", file=sys.stderr)


def _emit_escalation_warning(session_entry: dict) -> None:
    """Stronger stderr message when block_threshold is crossed."""
    count = session_entry.get("count", 0)
    cats = session_entry.get("categories_seen", [])
    print("", file=sys.stderr)
    print("[ANTI-SHORTCUT DETECTOR — ESCALATION]", file=sys.stderr)
    print(
        f"Escalation: {count} violations across categories {cats} this session.",
        file=sys.stderr,
    )
    print(
        "Subsequent agent output should explicitly acknowledge the antipattern "
        "before proceeding (e.g., 'acknowledging the antipattern; applying the "
        "constraint-first protocol').",
        file=sys.stderr,
    )
    print(
        "See: the shortcut and deferral rules in the project instructions "
        "and the synthesis-anti-shortcuts skill.",
        file=sys.stderr,
    )
    print("", file=sys.stderr)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def doctor() -> int:
    catalog = load_catalog()
    lines, _healthy = doctor_prologue(HOOK_NAME)
    lines.append(f"log_file={LOG_FILE}")
    lines.append(f"catalog_phrases={len(catalog.phrases)}")
    lines.append(f"ack_signals={len(catalog.ack_signals)}")
    esc = catalog.escalation
    lines.append(f"warn_threshold={esc.warn_threshold}")
    lines.append(f"block_threshold={esc.block_threshold}")
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

    last_text = get_last_assistant_text(transcript_path)
    if not last_text:
        return 0

    # Run the matcher
    detections = match_in_text(last_text, exclude_exempt=True)

    timestamp = datetime.now(timezone.utc).isoformat()
    counts = _load_session_counts()

    # Acknowledgment check FIRST. If the agent explicitly acknowledged the
    # antipattern, reset the session count before processing new detections.
    # (An acknowledgment in the same message as new detections still counts
    # the new detections — the reset applies to the running tally.)
    catalog = load_catalog()
    if catalog.escalation.reset_on_acknowledgment and is_acknowledgment(last_text):
        _reset_session(counts, session_id, timestamp)

    if not detections:
        # No new violations. If we reset above, persist that.
        if catalog.escalation.reset_on_acknowledgment and is_acknowledgment(last_text):
            _save_session_counts(counts)
        return 0

    # Build log entries
    log_entries = []
    for d in detections:
        # Look up the catalog entry for lesson/skill_ref metadata.
        cat_entry = next((p for p in catalog.phrases if p.id == d.phrase_id), None)
        log_entries.append({
            "timestamp": timestamp,
            "session_id": session_id,
            "cwd": cwd,
            "phrase_id": d.phrase_id,
            "category": d.category,
            "severity": d.severity,
            "excerpt": d.excerpt,
            "matched_text": d.matched_text,
            "position": d.position,
            "suggested_rewrite_hint": suggested_rewrite_hint(d.phrase_id),
            "lesson": cat_entry.lesson if cat_entry else None,
            "skill_ref": cat_entry.skill_ref if cat_entry else None,
        })

    _append_log(log_entries)

    # Update session counts
    session_entry = _bump_session_count(counts, session_id, detections, timestamp)
    _save_session_counts(counts)

    # Stderr presentation: first violation gets the loud warning; escalation
    # threshold gets the stronger message in addition.
    pre_existing = session_entry["count"] - len(detections)
    is_first_in_session = pre_existing == 0

    if is_first_in_session:
        _emit_first_violation_warning(detections)
    else:
        # Subsequent violations get a terser warning to avoid noise.
        print(
            f"[ANTI-SHORTCUT DETECTOR] {len(detections)} more detection(s) this "
            f"session (running total: {session_entry['count']})",
            file=sys.stderr,
        )

    if session_entry["count"] >= catalog.escalation.block_threshold:
        _emit_escalation_warning(session_entry)

    return 0


if __name__ == "__main__":
    sys.exit(main())
