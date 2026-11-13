"""Hook entry point for every harness: `python3 -S <plugin>/synthesis/hook.py <event>`.

session-start: register the session and re-inject the active project's brief
(also after compaction, R1.2). user-prompt-submit: grant typed approvals, deliver
board messages, brief a session whose project changed since its last brief
(Muse runs session-start only when a session is created), and say how long ago
the last turn ended after a pause. pre-tool-use: run the guards (R3). stop:
record the turn's end, check the reply and the autopilot run. Each event
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
    """Once per release, tell a session that last saw an older runtime what changed (Rajiv, 2026-10-06). A
    session recorded before 5.0.3 carries no version; if it started before this release was installed it is
    told too, with this release's notes, since what it started on is unknown (2026-10-07, synthesis-movement)."""
    from synthesis import __version__, board, paths
    from synthesis.install import version_tuple as number
    if me is None or me.version == __version__:
        return ""
    seen = me.version
    board.touch(session_id, version=__version__)
    try:
        older = bool(me.started) and me.started < (paths.home() / "current" / "HASH").stat().st_mtime
    except OSError:
        older = False
    if not seen and not older:
        return ""  # a session that began on this release has nothing to catch up on
    if seen and number(seen) > number(__version__):  # a deliberate rollback: say so plainly, no changelog
        return f"synthesis was rolled back from {seen} to {__version__}; hooks and guards now run {__version__}."
    log = paths.home() / "current" / "CHANGELOG.md"
    text = log.read_text(encoding="utf-8") if log.is_file() else ""
    sections = [s.strip() for s in re.split(r"(?m)^(?=## \[)", text) if (m := re.match(r"## \[([\d.]+)\]", s))
                and (number(seen) if seen else number(__version__)[:2] + (number(__version__)[2] - 1,)) < number(m.group(1))
                <= number(__version__)]
    was = f"from {seen} " if seen else ""
    loaded = f"{seen}'s" if seen else "from the release this session started on, which was not recorded"
    return (
        f"synthesis was upgraded {was}to {__version__} since this session last saw it. Hooks and guards already "
        f"run {__version__}; skill text loaded earlier in this conversation is {loaded}. Before relying on a skill the "
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
    try:  # uncommitted work in this checkout stays recoverable from the start of the session (2026-10-20)
        from synthesis import checkout
        checkout.snapshot(checkout.repo_of(str(payload.get("cwd") or os.getcwd())), "session start", session_id,
                          untracked=False)  # inside the hook's budget: tracked changes alone
    except Exception:
        pass  # a snapshot must never cost a session its start
    try:  # messages another Mac's handoff carried in the project's records (plan item 13.5, part 4)
        unreadable = board.carry(session.project, project_dir) if project_dir else []
    except OSError as exc:
        unreadable = [f"{project_dir}/inbox ({exc})"]
    notes += [f"{len(unreadable)} file(s) in the project's inbox/ could not be read as messages: {unreadable[0]}"] if unreadable else []
    unread = board.inbox(session_id, session.project)
    notes += [f"{len(unread)} unread board message(s): run `synthesis inbox`."] if unread else []
    kept = [] if session.project else board.waiting(session_id)
    notes += [f"This session is bound to no project, so mail addressed to one does not reach it. Mail it has not read is "
              f"waiting for: {', '.join(kept[:8])}{f' and {len(kept) - 8} more' if len(kept) > 8 else ''}. If this session works on one of them, `synthesis resume "
              f"{kept[0]}` binds it and delivers the mail."] if kept else []
    _ran(payload, "session_start")  # this hook is running: struck before the note is read, so a harness's own start does not name it
    notes += [n for n in (_window_note(), _unguarded_note()) if n]
    return _emit("SessionStart", context="\n\n".join(notes))


HARNESSES = {"codex hook trust": "Codex", "muse hook approval": "Muse"}


def _ran(payload: dict, event: str) -> None:
    """A hook that runs is one its harness has approved: strike its own event from what the doctor saw not running
    there under this release, and no other (2026-11-13, a review: a start hook that ran was taken for proof that
    the guard runs). What was seen under another release is the doctor's to look at again. The harness is the one
    in whose own folder of session records the payload's transcript is a file, read past any link: never the
    environment's, since the doctor's self-test runs this hook from whatever shell the doctor is in, and never a
    path that only looks like a record (measured 2026-11-13 on 35 Codex sessions: each one's record was at least a
    second old when its first hook ran). Muse hands its hooks no transcript, so only the doctor's next look clears
    Muse; in Claude Code, which asks for no approval, nothing is read. The strike is this process's own word, made
    once the handler has answered and only where the note is free: a note someone holds is left for the hook's
    next call, and whoever runs this hook by hand with a real record's path strikes too, until the doctor's next
    look, which reads the harness's own trust, writes what it sees."""
    try:
        from synthesis import __version__, paths
        where = payload.get("transcript_path")
        where = os.path.realpath(where) if isinstance(where, str) and where else ""
        for name, harness in paths.HOOK_APPROVALS.items() if where and os.path.isfile(where) else ():
            if where.startswith(os.path.realpath(paths.transcript_roots()[harness]) + os.sep) and event in paths.waits().get(name, {}).get("waiting", ()):
                paths.note_wait(name, lambda old: {**old, "waiting": [e for e in old["waiting"] if e != event],
                                                   "struck": {**old["struck"], event: time.time()}}
                                if old and old["version"] == __version__ and event in old["waiting"] else None, wait=False)
    except Exception:
        pass  # a note must never cost a hook its answer


def _unguarded_note() -> str:
    """What was last seen of the hooks in Codex and in Muse, where not all is well: the hooks that were not running
    when the doctor looked and have not run since, with the doctor's own line for what mends it (an approval, or a
    plugin that registers no hooks), and a harness nothing has looked at since this release replaced the one it was
    seen under (a harness can ask for its approval again when the plugin changes)."""
    try:
        from synthesis import __version__, paths
        said, stale = [], []
        for name, entry in paths.waits().items():
            hooks, one = [e.replace("_", "-") for e in entry["waiting"]], len(entry["waiting"]) == 1
            when, since = time.strftime("%a %H:%M", time.localtime(entry["at"])), f"{'has' if one else 'have'} not been seen to run since"
            listed = f"its {' and '.join(filter(None, [', '.join(hooks[:-1]), hooks[-1]]))} hook{'' if one else 's'}" if hooks else ""
            if entry["version"] != __version__:
                stale.append(HARNESSES[name])
            elif hooks and entry["untold"]:
                said.append(f"{HARNESSES[name]}: the doctor could not tell whether its hooks run when it looked ({when}: {entry['said']}), "
                            f"and {listed} {since}.")
            elif hooks:
                said.append(f"{HARNESSES[name]}: {listed} {'was' if one else 'were'} not running when the doctor looked ({when}) and {since}"
                            + f" (the doctor's line then: {entry['said']})" * bool(entry["said"]) + ".")
            if hooks and entry["version"] == __version__ and "pre-tool-use" in hooks:
                said[-1] += " Nothing is known to guard a send or a deploy made from there."
        said += ["A harness's hook approval is the person's to give in that harness: tell them what waits, and give none yourself."] * bool(said)
        return " ".join(said + [f"Whether {' and '.join(stale)} run{'s' * (len(stale) == 1)} synthesis's hooks has not been checked since "
                                f"synthesis changed to {__version__}: `synthesis doctor` checks it."] * bool(stale))
    except Exception:
        return ""  # a note must never cost a session its start


def _window_note() -> str:
    from synthesis import sends
    window = sends.window()
    return sends.describe(window) if window else ""


AWAY = 600  # seconds: the checkpoint skill's trigger, a pause of ten minutes or more


def _away_note(me, now=None) -> str:
    """How long ago this session's last turn ended, once that is ten minutes or more. An agent cannot perceive a pause,
    and after an idle compaction its summary reads as current though written long before it took effect (2026-11-05:
    a summary of a conversation whose last turn ended at 11:52, written at 12:46, took effect at 14:14). A turn the
    person interrupts records no end, so the note then counts from the turn before it."""
    ended = me.ended if me else 0.0
    now = time.time() if now is None else now
    if not ended or now - ended < AWAY:
        return ""
    minutes = int((now - ended) // 60)
    hours, days = minutes // 60, minutes // 1440
    span = (f"{minutes} min" if minutes < 60 else f"{hours} h {minutes % 60} min" if hours < 24
            else f"{days} day{'s' * (days > 1)} {hours % 24} h")
    when = time.strftime("%H:%M" if time.localtime(ended)[:3] == time.localtime(now)[:3] else "%A %Y-%m-%d %H:%M",
                         time.localtime(ended))
    return (f"It is {time.strftime('%H:%M', time.localtime(now))}; this session's last turn ended at {when}, {span} "
            "ago. What the conversation says is in flight (background tasks, CI runs, deploys, replies awaited) is as "
            "of then: check each before relying on it or reporting it.")


def user_prompt_submit(payload):
    """Grant approvals the principal typed, brief a session whose project changed, deliver board messages."""
    from synthesis import approvals, board, paths

    prompt = str(payload.get("prompt") or payload.get("user_prompt") or "")
    waiting = set(approvals.pending())
    notes = [f"Approved by the principal: {s}" for s in approvals.grant_from_prompt(prompt)]
    # A typed code that matched nothing is said aloud, so no one assumes it took (2026-10-13)
    typed = approvals.typed_codes(prompt)
    notes += [f"Not granted: no pending request has the code {c}; it may have expired (15 minutes), been used, or "
              "been mistyped. Run the call again for a new code." for c in typed if c not in waiting]
    # So is a pending code that is in the message and was not approved (2026-11-11: eight of nine were passed over)
    notes += [f"Not granted: the pending code {c} is in the message, but not in a list right after the word approve on "
              "its line in the principal's own words (a new line, another word, a negation or a tagged block came "
              "between). If the principal meant it, ask them to type the word and the code together."
              for c in approvals.mentioned(prompt) if c in waiting and c not in typed]
    session_id = paths.session_id(payload)
    if session_id:
        me = board.load(session_id)
        notes += [n for n in [_away_note(me), _upgrade_note(session_id, me)] if n]
        if me and me.project and me.project != me.briefed:  # after `synthesis use`, once
            from synthesis import project
            found = project.find(me.project)
            notes += [project.brief(found)] if found else []
            board.touch(session_id, briefed=me.project)
        unread = board.inbox(session_id, me.project if me else "")
        board.mark_read_messages(session_id, unread[:5])  # only what is shown; the rest stay for `synthesis inbox`
        cut = "\n[cut: {} more characters; `synthesis inbox --recent 24` shows it whole]"
        notes += [f"Board message from {m['from']} to {m['to']}:\n{m['text'][:1500]}"
                  + (cut.format(len(m["text"]) - 1500) if len(m["text"]) > 1500 else "") for m in unread[:5]]
        if len(unread) > 5:
            notes.append(f"{len(unread) - 5} more unread: run `synthesis inbox`.")
    notes += [n for n in [_window_note()] if n]  # every session sees an open window (Rajiv, 2026-10-13)
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
    try:  # the turn's end, for the next prompt's time-away note; a turn sent back ends later and records again
        from synthesis import board, paths
        if paths.session_id(payload):
            board.touch(paths.session_id(payload), ended=time.time())
    except Exception:
        pass  # a note's bookkeeping never costs a turn its end
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
            install.install(argv[2], forward_only=True)
        except Exception:
            pass  # a failed self-update must never block a session; doctor reports it
    from synthesis import paths
    if paths.old_board():  # seven lstat calls; true only after an older release wrote the board where it used to be
        try:
            from synthesis import install
            install.move_board(paths.home())
        except Exception:
            pass  # never blocks a call; doctor names what is left
    handler = {"session-start": session_start, "user-prompt-submit": user_prompt_submit,
               "pre-tool-use": pre_tool_use, "stop": stop}.get(event)
    if not handler:
        return 0
    code = handler(payload)
    _ran(payload, event.replace("-", "_"))  # once it has answered: a handler that fails has not shown that it runs
    return code


if __name__ == "__main__":
    sys.exit(main(sys.argv))
