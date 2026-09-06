#!/usr/bin/env python3
"""Deliver the coordination board's addressed messages to the seat they name.

The board's ``## Messages`` section is the one lane every session has — a
Codex thread, a session on another machine, a session that never claimed a
direct handle — but a message nobody reads is a dead letter. This hook runs
at SessionStart and on every UserPromptSubmit in both clients and injects
the unread messages addressed to this session's seat (any identity form) or
to its project, then advances a per-seat watermark. Latency is one turn,
the same class as the harness's own queue.

Only a claimed seat receives messages: the global active-project pointer is
another session's cache, never an address.

For a Codex session it also states the session's coordination identity,
because a Codex shell carries no thread id: the agent exports it as
``SYNTHESIS_CLIENT_SESSION_REF`` so claims and receipts are filed under the
same key the gate sees.

Prints nothing when there is nothing to say; never blocks a prompt.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from peer_addressing import (  # noqa: E402
    CLIENT_CLAUDE,
    SelfIdentity,
    identity_from_hook,
    mark_seen,
    parse_iso,
    render_inbox,
    seat_for_identity,
    unread_messages,
)

DEFAULT_BOARD = Path.home() / ".synthesis" / "coordination" / "active-sessions.md"


def _board_rows(text: str, *, strict: bool = False):
    """Use the engine's parser, checking diagnostic input cannot disappear."""
    from coordination import board_schema, parse_cells, rows
    from coordination_schema import SCHEMA_VERSION, V1_COLUMNS, V2_COLUMNS, V3_COLUMNS, V4_COLUMNS, validate_identity

    if strict:
        declared = board_schema(text)
        if (
            declared is None or not 1 <= declared <= SCHEMA_VERSION
            or sum(line.startswith("Schema:") for line in text.splitlines()) != 1
        ):
            raise ValueError("coordination board has an invalid or unsupported schema")
        lines = text.splitlines()
        if sum(line.strip() == "## Active sessions" for line in lines) != 1:
            raise ValueError("coordination board must have one Active sessions section")
        if sum(line.strip() == "## Messages" for line in lines) != 1:
            raise ValueError("coordination board must have one Messages section")
        start = next(i for i, line in enumerate(lines) if line.strip() == "## Active sessions")
        end = next((i for i in range(start + 1, len(lines)) if lines[i].startswith("## ")), len(lines))
        table = [line for line in lines[start + 1:end] if line.strip()]
        columns = {1: V1_COLUMNS, 2: V2_COLUMNS, 3: V3_COLUMNS, 4: V4_COLUMNS}[declared]
        header_cells = [cell.strip() for cell in table[0].split("|")[1:-1]] if table else []
        separator_cells = [cell.strip() for cell in table[1].split("|")[1:-1]] if len(table) > 1 else []
        if (
            len(table) < 2 or any(not line.startswith("|") or not line.rstrip().endswith("|") for line in table[:2])
            or header_cells != list(columns) or len(separator_cells) != len(columns)
            or any(re.fullmatch(r"-{3,}", cell) is None for cell in separator_cells)
        ):
            raise ValueError("coordination board has an invalid active-session table header")
        for line in table[2:]:
            cells = parse_cells(line)
            if not line.rstrip().endswith("|") or cells is None or len(cells) != len(columns):
                raise ValueError("coordination board has an invalid active-session row")
    board_rows = rows(text)
    if strict:
        for row in board_rows:
            if (declared >= 3 and not row.session_uuid) or (row.session_uuid and validate_identity(row.identity)):
                raise ValueError("coordination board has an invalid session identity")
    return board_rows


def identity_forms_for(
    board: Path, identity: SelfIdentity, *, board_text: str | None = None, strict: bool = False
) -> tuple[set[str], str, str, str]:
    """(identity forms, project, compact id, started) for this session's seat, if any."""
    try:
        text = board.read_text(encoding="utf-8") if board_text is None else board_text
        board_rows = _board_rows(text, strict=strict)
    except (OSError, ValueError):
        if strict:
            raise
        return set(), "", "", ""
    seat = seat_for_identity(board, identity, strict=strict)
    if seat is None:
        return set(), "", "", ""
    matches = [row for row in board_rows if row.session_uuid == seat.session_uuid]
    if strict and len(matches) > 1:
        raise ValueError("multiple coordination rows match this session's seat")
    row = matches[0] if matches else None
    if row is None:
        return set(), "", "", ""
    if strict and (row.compact_id != seat.compact_id or not row.project or parse_iso(row.started) is None):
        raise ValueError("coordination inbox cannot verify its seat's addressing or start time")
    forms = {row.session_uuid, row.compact_id, row.speakable_id}
    if row.legacy_id:
        forms.add(row.legacy_id)
    return forms, row.project, row.compact_id, row.started


def identity_notice(identity: SelfIdentity) -> str:
    if identity.client == CLIENT_CLAUDE or not identity.harness_session_id:
        return ""
    ref = identity.sender_key
    return (
        f"Coordination identity for this session: {ref}. Export "
        f"SYNTHESIS_CLIENT_SESSION_REF={ref} in every shell that runs "
        "coordination.py claim or resolve, so your seat and delivery receipts "
        "are filed under the id the send gate sees."
    )


def inbox_text(
    payload: dict,
    *,
    board: Path = DEFAULT_BOARD,
    environ: dict[str, str] | None = None,
    mark: bool = True,
    strict: bool = False,
) -> str:
    """Messages for this session's claimed seat, or nothing.

    A session without a seat has no address. The global active-project
    pointer is another session's cache and is never consulted: on
    2026-09-03 a fallback to it delivered one project's message to a
    seatless session working on a different project."""
    identity = identity_from_hook(payload, environ)
    key = identity.sender_key
    if not key and not strict:
        return ""
    try:
        text = board.read_text(encoding="utf-8")
    except FileNotFoundError:
        if strict and board.is_symlink():
            raise
        return ""
    except OSError:
        if strict:
            raise
        return ""
    forms, project, _compact, started = identity_forms_for(board, identity, board_text=text, strict=strict)
    if not forms:
        return identity_notice(identity)
    messages = unread_messages(
        text, board=board, sender_key=key, identity_forms=forms, project=project, since=started, strict=strict
    )
    rendered = render_inbox(messages)
    if messages and mark:
        mark_seen(board, key, {message.key for message in messages})
    notice = identity_notice(identity)
    return "\n".join(part for part in (notice, rendered) if part)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--board", type=Path, default=DEFAULT_BOARD)
    parser.add_argument("--hook", action="store_true", help="read the hook payload on stdin and emit hook JSON")
    parser.add_argument("--no-mark", action="store_true", help="do not advance the watermark")
    args = parser.parse_args()
    board = args.board.expanduser()
    payload: dict = {}
    if args.hook:
        try:
            payload = json.load(sys.stdin)
        except Exception:
            payload = {}
        if not isinstance(payload, dict):
            payload = {}
    try:
        text = inbox_text(payload, board=board, mark=not args.no_mark)
    except Exception as exc:  # never block a prompt on inbox trouble; say what failed
        text = f"Coordination inbox could not be read: {exc}"
    if not text:
        return 0
    if args.hook:
        event = payload.get("hook_event_name") or "UserPromptSubmit"
        print(json.dumps({"continue": True, "hookSpecificOutput": {"hookEventName": event, "additionalContext": text}}))
    else:
        print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
