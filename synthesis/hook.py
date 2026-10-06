"""Hook entry point for every harness: `python3 -S <plugin>/synthesis/hook.py <event>`.

session-start: register the session and re-inject the active project's brief
(also after compaction, R1.2). user-prompt-submit: grant typed approvals, deliver
board messages, and brief a session whose project changed since its last brief
(Muse runs session-start only when a session is created). pre-tool-use: run the
guards (R3). stop: check the reply and the autopilot run. Each event
reads one JSON payload on stdin and must finish fast (R8.1), so modules load
only for the event that needs them.
"""

import json
import os
import re
import sys
import time

if __package__ in (None, ""):  # run as a file with -S: make the package importable
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _defuse(text):
    """Hook text never holds the approval phrase itself, so no harness can record our words, or words an
    agent put in a board message or a reply, as a prompt the principal typed (R3.0)."""
    import re
    return re.sub(r"(?i)\bapprove\s+(\d[0-9a-f]{5})\b", r"approve code \1", text)


def _emit(event, context="", deny=""):
    context, deny = _defuse(context), _defuse(deny)
    if deny:
        print(json.dumps({"hookSpecificOutput": {
            "hookEventName": event, "permissionDecision": "deny", "permissionDecisionReason": deny}}))
    elif context:
        print(json.dumps({"hookSpecificOutput": {"hookEventName": event, "additionalContext": context}}))
    return 0


def _upgrade_note(session_id, me) -> str:
    """Once per release, tell a session that last saw an older runtime what changed (Rajiv, 2026-10-06)."""
    from synthesis import __version__, board, paths
    if me is None or me.version == __version__:
        return ""
    seen = me.version
    board.touch(session_id, version=__version__)
    log = paths.home() / "current" / "CHANGELOG.md"
    text = log.read_text(encoding="utf-8") if seen and log.is_file() else ""
    number = lambda v: tuple(int(x) for x in re.findall(r"\d+", v)[:3])  # noqa: E731
    sections = [s.strip() for s in re.split(r"(?m)^(?=## \[)", text) if (m := re.match(r"## \[([\d.]+)\]", s))
                and number(seen) < number(m.group(1)) <= number(__version__)]
    return "" if not seen else (
        f"synthesis was upgraded from {seen} to {__version__} since this session last saw it. Hooks and guards already "
        f"run {__version__}; skill text loaded earlier in this conversation is {seen}'s. Before relying on a skill the "
        "changes below name, re-read its SKILL.md, or run the synthesis-checkpoint skill in refresh-and-report mode for a "
        "full pass; restarting the app reloads everything.\n\n" + ("\n\n".join(sections) or "(no changelog found)")[:3000])


def session_start(payload):
    from synthesis import autopilot, board, paths, project

    session_id = paths.session_id(payload)
    if not session_id:
        return 0
    known = board.load(session_id)
    session = board.touch(session_id, harness=paths.harness(payload), cwd=payload.get("cwd") or None,
                          briefed=known.project if known else "")
    notes = [time.strftime("Local time: %A %Y-%m-%d %H:%M %Z (%z), from the session-start hook.")]
    notes += [n for n in [_upgrade_note(session_id, known)] if n]
    project_dir = project.find(session.project) if session.project else None
    notes += [project.brief(project_dir)] if project_dir else []
    run = autopilot.brief(payload)
    try:  # one ritual line: last close, streak, workdays never closed, weekly review owed (R5.1)
        from synthesis import rituals
        line = rituals.session_line(str(payload.get("cwd") or os.getcwd()))
    except Exception:
        line = ""  # a ritual line must never cost a session its start
    notes += [n for n in (run, line) if n]
    unread = board.inbox(session_id, session.project)
    notes += [f"{len(unread)} unread board message(s): run `synthesis inbox`."] if unread else []
    return _emit("SessionStart", context="\n\n".join(notes))


def user_prompt_submit(payload):
    """Grant approvals the principal typed, brief a session whose project changed, deliver board messages."""
    from synthesis import approvals, board, paths

    notes = [f"Approved by the principal: {s}" for s in approvals.grant_from_prompt(
        str(payload.get("prompt") or payload.get("user_prompt") or ""))]
    session_id = paths.session_id(payload)
    if session_id:
        me = board.load(session_id)
        notes += [n for n in [_upgrade_note(session_id, me)] if n]
        if me and me.project and me.project != me.briefed:  # after `synthesis use`, once
            from synthesis import project
            found = project.find(me.project)
            notes += [project.brief(found)] if found else []
            board.touch(session_id, briefed=me.project)
        unread = board.inbox(session_id, me.project if me else "", mark_read=True)
        notes += [f"Board message from {m['from']} to {m['to']}:\n{m['text'][:1500]}" for m in unread[:5]]
        if len(unread) > 5:
            notes.append(f"{len(unread) - 5} more unread: run `synthesis inbox`.")
    return _emit("UserPromptSubmit", context="\n\n".join(notes))


def pre_tool_use(payload):
    from synthesis import approvals, guards, paths

    tool = str(payload.get("tool_name", ""))
    tool_input = payload.get("tool_input") or {}
    try:
        config = paths.config()
    except (OSError, ValueError) as exc:
        return (_emit("PreToolUse", deny=f"synthesis guard config is unreadable ({exc}); fix {paths.config_file()}")
                if guards.guarded(tool, tool_input) else 0)
    try:
        reason = guards.check(tool, tool_input, config, cwd=str(payload.get("cwd") or "") or None, session=payload)
    except approvals.Unverified as exc:
        reason = str(exc)
    except Exception as exc:  # a guard that can't decide must not wave the call through
        reason = f"synthesis guard failed ({type(exc).__name__}: {exc}); blocked rather than allowed"
    return _emit("PreToolUse", deny=reason) if reason else 0


def stop(payload):
    """Revise the reply once if it defers work or quotes words with no source (S15), then
    let an autopilot run that owns a plan continue to its next item (R6)."""
    try:
        from synthesis import autopilot, paths, reply_check
        config = paths.config()
        safe = "".join(c if c.isalnum() or c in "-_." else "_" for c in paths.session_id(payload))
        marker = paths.state() / "stop" / f"{safe}.json" if safe else None
        last = paths.read_json(marker).get("by", "") if marker is not None and payload.get("stop_hook_active") else ""
        reason, note, by = None, None, ""
        if last != "reply":  # the reply this check already sent back is never sent back twice
            reason = reply_check.check({**payload, "stop_hook_active": False}, config)
            by = "reply" if reason else ""
        if not reason:
            reason, note = autopilot.evaluate(payload, config)
            by = "autopilot" if reason else ""
        if marker is not None and (by or marker.exists()):
            marker.parent.mkdir(parents=True, exist_ok=True)
            marker.write_text(json.dumps({"by": by}), encoding="utf-8")
    except Exception:
        return 0  # fail open: a turn-end check that fails closed loops forever
    if reason:
        print(json.dumps({"decision": "block", "reason": _defuse(reason)}))
    elif note:
        print(json.dumps({"systemMessage": _defuse(note)}))
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
