#!/usr/bin/env python3
"""Shared validation for client-owned SessionStart transcript evidence."""

from __future__ import annotations

import json
from pathlib import Path


MAX_BINDING_LINES = 1_000


def claude_root_transcript_path(
    transcript: Path, transcript_root: Path, session_id: str
) -> bool:
    """Return whether a path is Claude's canonical root-session transcript.

    Root transcripts use ``projects/<encoded-cwd>/<session-id>.jsonl``.
    Claude subagent transcripts also carry the parent session UUID, so root
    containment plus a matching JSON field is not sufficient provenance.
    """
    if not transcript.is_absolute() or not session_id:
        return False
    root = transcript_root.expanduser().absolute()
    candidate = transcript.expanduser().absolute()
    try:
        relative = candidate.relative_to(root)
    except ValueError:
        return False
    if (
        len(relative.parts) != 3
        or relative.parts[0] != "projects"
        or any(part in {".", ".."} for part in relative.parts)
        or relative.parts[-1] != f"{session_id}.jsonl"
    ):
        return False
    current = root
    for part in relative.parts:
        current = current / part
        if current.is_symlink():
            return False
    try:
        candidate.resolve(strict=False).relative_to(root.resolve())
    except (OSError, ValueError):
        return False
    return True


def transcript_binding_state(
    transcript: Path, client: str, session_id: str
) -> str:
    """Return ``bound``, ``pending``, ``conflicting``, or ``invalid``.

    ``pending`` covers a transcript Claude has not created or populated yet.
    Once a transcript declares any different session id, the state is
    ``conflicting`` and must not be preserved as genuine evidence.
    """
    if not transcript.exists():
        return "pending"
    if transcript.is_symlink() or not transcript.is_file():
        return "invalid"
    declared: set[str] = set()
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
                    if payload.get("type") == "session_meta" and isinstance(
                        metadata, dict
                    ):
                        declared.update(
                            value
                            for value in (
                                str(metadata.get("id") or ""),
                                str(metadata.get("session_id") or ""),
                            )
                            if value
                        )
                elif client == "claude":
                    value = str(payload.get("sessionId") or "")
                    if value:
                        declared.add(value)
    except (OSError, UnicodeError):
        return "invalid"
    if declared == {session_id}:
        return "bound"
    if declared:
        return "conflicting"
    return "pending"


def transcript_binds_session(
    transcript: Path, client: str, session_id: str
) -> bool:
    """Return whether a client transcript declares the claimed session id.

    Both clients write the binding at the start of their JSONL transcript.
    The bounded scan fails closed on malformed or unexpectedly shaped files
    without reading an arbitrarily large transcript during SessionStart.
    """
    return transcript_binding_state(transcript, client, session_id) == "bound"
