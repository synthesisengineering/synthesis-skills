#!/usr/bin/env python3
"""Muse Stop hook backed by the shared anti-shortcut catalog.

Twin of the Codex lazy_shortcut_detector: reads the Stop payload's
last_assistant_message from stdin, scans it with the shared detection core,
and appends detections to the Muse-local log. Log-only by design: Muse's
Stop-hook stdout contract is undocumented (W1), so this hook prints nothing
to stdout and always exits 0. A stderr line names the matched phrasing for
sessions that surface hook stderr.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path


SHARED_HOOKS = Path(__file__).resolve().parents[1] / "claude"
if str(SHARED_HOOKS) not in sys.path:
    sys.path.insert(0, str(SHARED_HOOKS))
HOOKS_ROOT = SHARED_HOOKS.parent
if str(HOOKS_ROOT) not in sys.path:
    sys.path.insert(0, str(HOOKS_ROOT))

from _anti_shortcut_catalog import (  # noqa: E402
    load_catalog,
    match_in_text,
    suggested_rewrite_hint,
)
from _settings import doctor_prologue, hook_enabled  # noqa: E402

HOOK_NAME = "lazy_shortcut_detector"
LOG_FILE = Path.home() / ".local" / "share" / "muse" / "lazy-shortcut-log.jsonl"


def doctor() -> int:
    catalog = load_catalog()
    lines, _healthy = doctor_prologue(HOOK_NAME)
    lines.append(f"log_file={LOG_FILE}")
    lines.append(f"catalog_phrases={len(catalog.phrases)}")
    lines.append(f"ack_signals={len(catalog.ack_signals)}")
    lines.append("detection_core=../claude/_anti_shortcut_catalog.py")
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
        payload = json.load(sys.stdin)
    except Exception:
        return 0

    text = payload.get("last_assistant_message") or ""
    if not text:
        return 0
    detections = match_in_text(text, exclude_exempt=True)
    if not detections:
        return 0

    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "session_id": payload.get("session_id", "unknown"),
        "turn_id": payload.get("turn_id", "unknown"),
        "cwd": payload.get("cwd", ""),
        "detections": [
            {
                "phrase_id": detection.phrase_id,
                "category": detection.category,
                "severity": detection.severity,
                "matched_text": detection.matched_text,
                "excerpt": detection.excerpt,
                "suggested_rewrite_hint": suggested_rewrite_hint(
                    detection.phrase_id
                ),
            }
            for detection in detections
        ],
    }
    try:
        with LOG_FILE.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except OSError:
        pass

    phrases = ", ".join(
        dict.fromkeys(detection.matched_text for detection in detections)
    )
    print(
        "lazy-shortcut detector: phrasing that can dismiss or postpone work "
        f"the user asked to complete: {phrases}. Rewrite from the stated "
        "constraints.",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
