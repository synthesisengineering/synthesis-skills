#!/usr/bin/env python3
"""Shared validation for client-owned SessionStart transcript evidence."""

from __future__ import annotations

import json
from pathlib import Path


MAX_BINDING_LINES = 1_000


def transcript_binds_session(
    transcript: Path, client: str, session_id: str
) -> bool:
    """Return whether a client transcript declares the claimed session id.

    Both clients write the binding at the start of their JSONL transcript.
    The bounded scan fails closed on malformed or unexpectedly shaped files
    without reading an arbitrarily large transcript during SessionStart.
    """
    try:
        with transcript.open(encoding="utf-8") as handle:
            for index, line in enumerate(handle):
                if index >= MAX_BINDING_LINES:
                    break
                try:
                    payload = json.loads(line)
                except (TypeError, ValueError):
                    continue
                if not isinstance(payload, dict):
                    continue
                if client == "codex":
                    metadata = payload.get("payload")
                    if (
                        payload.get("type") == "session_meta"
                        and isinstance(metadata, dict)
                        and session_id
                        in {str(metadata.get("id") or ""), str(metadata.get("session_id") or "")}
                    ):
                        return True
                elif client == "claude" and str(payload.get("sessionId") or "") == session_id:
                    return True
    except (OSError, UnicodeError):
        return False
    return False
