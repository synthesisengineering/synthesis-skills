"""Hook entry point for every harness: `python3 -S <plugin>/synthesis/hook.py <event>`.

session-start: register the session and re-inject the active project's brief
(also after compaction, R1.2). pre-tool-use: run the guards (R3). Each event
reads one JSON payload on stdin and must finish fast (R8.1), so modules load
only for the event that needs them.
"""

import json
import os
import sys

if __package__ in (None, ""):  # run as a file with -S: make the package importable
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _emit(event, context="", deny=""):
    if deny:
        print(json.dumps({"hookSpecificOutput": {
            "hookEventName": event, "permissionDecision": "deny", "permissionDecisionReason": deny}}))
    elif context:
        print(json.dumps({"hookSpecificOutput": {"hookEventName": event, "additionalContext": context}}))
    return 0


def session_start(payload):
    from synthesis import board, paths, project

    session_id = paths.session_id(payload)
    if not session_id:
        return 0
    session = board.touch(session_id, harness=paths.harness(), cwd=payload.get("cwd") or None)
    notes = []
    project_dir = project.find(session.project) if session.project else None
    if project_dir:
        notes.append(project.brief(project_dir))
    unread = board.inbox(session_id, session.project)
    if unread:
        notes.append(f"{len(unread)} unread board message(s): run `synthesis inbox`.")
    return _emit("SessionStart", context="\n\n".join(notes))


def user_prompt_submit(payload):
    """Grant approvals the principal typed, and deliver unread board messages."""
    from synthesis import approvals, board, paths

    notes = [f"Approved by the principal: {s}" for s in approvals.grant_from_prompt(
        str(payload.get("prompt") or payload.get("user_prompt") or ""))]
    session_id = paths.session_id(payload)
    if session_id:
        me = board.load(session_id)
        unread = board.inbox(session_id, me.project if me else "", mark_read=True)
        for m in unread[:5]:
            notes.append(f"Board message from {m['from']} to {m['to']}:\n{m['text'][:1500]}")
        if len(unread) > 5:
            notes.append(f"{len(unread) - 5} more unread: run `synthesis inbox`.")
    return _emit("UserPromptSubmit", context="\n\n".join(notes))


def pre_tool_use(payload):
    from synthesis import guards, paths

    tool = str(payload.get("tool_name", ""))
    tool_input = payload.get("tool_input") or {}
    try:
        config = paths.config()
    except (OSError, ValueError) as exc:
        if tool in guards.SHELL_TOOLS or guards.is_send_tool(tool, {}):
            return _emit("PreToolUse", deny=f"synthesis guard config is unreadable ({exc}); fix {paths.config_file()}")
        return 0
    try:
        reason = guards.check(tool, tool_input, config)
    except Exception as exc:  # a guard that can't decide must not wave the call through
        reason = f"synthesis guard failed ({type(exc).__name__}: {exc}); blocked rather than allowed"
    return _emit("PreToolUse", deny=reason) if reason else 0


def stop(payload):
    """Revise the reply once if it defers work or quotes words with no source (S15)."""
    try:
        from synthesis import paths, reply_check
        reason = reply_check.check(payload, paths.config())
    except Exception:
        return 0  # fail open: a turn-end check that fails closed loops forever
    if reason:
        print(json.dumps({"decision": "block", "reason": reason}))
    return 0


def main(argv):
    event = argv[1] if len(argv) > 1 else ""
    try:
        payload = json.loads(sys.stdin.read() or "{}")
    except json.JSONDecodeError:
        payload = {}
    if event == "session-start" and len(argv) > 2 and argv[2]:
        try:  # keep the stable runtime in step with the plugin the harness loaded
            from synthesis import install
            install.install(argv[2])
        except Exception:
            pass  # a failed self-update must never block a session; doctor reports it
    handler = {"session-start": session_start, "user-prompt-submit": user_prompt_submit,
               "pre-tool-use": pre_tool_use, "stop": stop}.get(event)
    return handler(payload) if handler else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
