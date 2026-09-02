#!/usr/bin/env python3
"""Deliver the coordination board's addressed messages to the seat they name.

The board's ``## Messages`` section is the one lane every session has — a
Codex thread, a session on another machine, a session that never claimed a
direct handle — but a message nobody reads is a dead letter. This hook runs
at SessionStart and on every UserPromptSubmit in both clients and injects
the unread messages addressed to this session's seat (any identity form) or
to its project, then advances a per-seat watermark. Latency is one turn,
the same class as the harness's own queue.

For a Codex session it also states the session's coordination identity,
because a Codex shell carries no thread id: the agent exports it as
``SYNTHESIS_CLIENT_SESSION_REF`` so claims and receipts are filed under the
same key the gate sees.

Prints nothing when there is nothing to say; never blocks a prompt.
"""
from __future__ import annotations

import argparse
import json
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
    render_inbox,
    seat_for_identity,
    unread_messages,
)

DEFAULT_BOARD = Path.home() / ".synthesis" / "coordination" / "active-sessions.md"
DEFAULT_POINTER = Path.home() / ".synthesis" / "active-project.json"


def pointer_project(pointer: Path) -> str:
    try:
        data = json.loads(pointer.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return ""
    project = data.get("project") if isinstance(data, dict) else None
    return Path(str(project)).name if project else ""


def identity_forms_for(board: Path, identity: SelfIdentity) -> tuple[set[str], str, str, str]:
    """(identity forms, project, compact id, started) for this session's seat, if any."""
    seat = seat_for_identity(board, identity)
    if seat is None:
        return set(), "", "", ""
    from coordination import rows  # local import: the engine parses the board

    try:
        board_rows = rows(board.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return set(), "", "", ""
    row = next((r for r in board_rows if r.session_uuid == seat.session_uuid), None)
    if row is None:
        return set(), "", "", ""
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
    pointer: Path = DEFAULT_POINTER,
    environ: dict[str, str] | None = None,
    mark: bool = True,
) -> str:
    identity = identity_from_hook(payload, environ)
    key = identity.sender_key
    if not key:
        return ""
    try:
        text = board.read_text(encoding="utf-8")
    except OSError:
        return ""
    forms, project, _compact, started = identity_forms_for(board, identity)
    if not forms:
        project = pointer_project(pointer)
        started = ""
    if not forms and not project:
        notice = identity_notice(identity)
        return notice
    messages = unread_messages(
        text, board=board, sender_key=key, identity_forms=forms, project=project, since=started
    )
    rendered = render_inbox(messages)
    if messages and mark:
        mark_seen(board, key, {message.key for message in messages})
    notice = identity_notice(identity)
    return "\n".join(part for part in (notice, rendered) if part)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--board", type=Path, default=DEFAULT_BOARD)
    parser.add_argument("--active-project-file", type=Path, default=DEFAULT_POINTER)
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
        text = inbox_text(payload, board=board, pointer=args.active_project_file.expanduser(), mark=not args.no_mark)
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
