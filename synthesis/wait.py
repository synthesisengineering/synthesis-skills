"""Waiting for an expected event is a task (2026-11-11): `synthesis wait` blocks until the event or its bound, and
while it runs it holds a record on the board. A seat told to expect something ended its turn with nothing armed,
since a board message reaches a session only when a prompt is submitted; its first watcher then read the inbox,
which marks what it prints, and waited half an hour on mail addressed to a project its session was not bound to.

    synthesis wait message [--from <session|short|project:id>] [--for 30m] [--every 2s]
    synthesis wait file <path> [--for 30m] [--every 2s]
    synthesis wait run [--every 30s] [--for 30m] -- <command>
    synthesis wait note "<what>" --by "<what will wake this seat>" [--for 2h]
    synthesis wait list

A wait prints one line when its event happens and exits 0; at its bound it exits 3 and says nothing arrived, so
silence cannot look like success; 2 for a bound it cannot read or one over twelve hours. A message is named by
its sender and never printed: the seat reads it with `synthesis inbox`, which is what marks it read.
"""
from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
import time
from pathlib import Path

from synthesis import board, paths

MAX_SECONDS = 12 * 3600
NUDGE = "A board message is waiting for this session. Run `synthesis inbox` to read it."  # fixed, so it carries nothing else


def span(text: str) -> float:
    """The seconds in "45s", "30m" or "2h" (a bare number is seconds), at most twelve hours."""
    found = re.fullmatch(r"(\d+(?:\.\d+)?)\s*([smh]?)", str(text).strip().lower())
    seconds = float(found[1]) * {"": 1, "s": 1, "m": 60, "h": 3600}[found[2]] if found else 0
    if not 0 < seconds <= MAX_SECONDS:
        raise ValueError(f"{text!r} is not a bound this can keep: give seconds, minutes or hours (45s, 30m, 2h), at most 12h")
    return seconds


def said(seconds: float) -> str:
    hours, minutes = divmod(int(round(seconds / 60)), 60)
    return f"{int(seconds)} s" if seconds < 60 else " ".join([f"{hours} h"] * bool(hours) + [f"{minutes} min"] * bool(minutes))


def _folder(session_id: str) -> Path:
    return paths.board() / "waits" / board._session_file(session_id).stem


def record(session_id: str, what: str, until: float, *, pid: int = 0, by: str = "", sender: str = "") -> Path:
    """One wait a session holds: what is awaited, until when, and the process that watches (0 for a watcher the
    harness holds, which `by` names)."""
    path = _folder(session_id) / f"{time.time_ns()}-{pid}.json"
    paths.write_json(path, {"session": session_id, "what": what, "since": time.time(), "until": until, "pid": pid, "by": by, "from": sender})
    return path


def _alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except OSError:
        pass  # it exists and is someone else's
    return True


def live(session_id: str = "") -> list[dict]:
    """The waits still held, of one session or of all: inside their bound and, where a process watches, that
    process alive. A record alone proves nothing, and one that is over is removed."""
    root = _folder(session_id) if session_id else paths.board() / "waits"
    found = []
    for file in sorted(root.rglob("*.json")) if root.is_dir() else []:
        held = paths.read_json(file)
        if held.get("until", 0) > time.time() and (not held.get("pid") or _alive(int(held["pid"]))):
            found.append(held)
        else:
            file.unlink(missing_ok=True)
    return found


def sent_by(message: dict, sender: str) -> bool:
    """Whether a message is from the sender a wait names: a session id, its short name or project:<id>."""
    author = str(message.get("from", ""))
    if sender.startswith("project:"):
        return getattr(board.load(author), "project", "") == sender[len("project:"):]
    return not sender or sender in (author, board.short_name(author))


def unread(session_id: str, sender: str = "") -> list[dict]:
    me = board.load(session_id)
    return [m for m in board.inbox(session_id, me.project if me else "") if sent_by(m, sender)]


def watching(session_id: str, sender: str) -> bool:
    """A live wait of that session for a message this sender's would end."""
    return any(w["what"].startswith("a message") and sent_by({"from": sender}, w.get("from", "")) for w in live(session_id))


def wake(target, run=subprocess.run) -> str:
    """Nudge an idle session through its own harness, where a command can: the text is fixed and points at the inbox."""
    command, fed = {"codex": (["codex", "queue", "--thread", target.session, "--message", NUDGE], None),
                    "muse": (["muse", "session-message", "send", "--target", target.session], NUDGE)}.get(target.harness, (None, None))
    if not command:
        return f"no command wakes a {target.harness or 'session of an unknown harness'} session from outside it"
    try:
        done = run(command, input=fed, capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.SubprocessError) as exc:
        return f"it could not be woken ({type(exc).__name__})"
    return "woken through its own harness" if done.returncode == 0 else f"it could not be woken ({(done.stderr or '').strip()[:120]})"


def _watch(session_id: str, what: str, until: float, seconds: float, every: float, ready, sender: str = "") -> int:
    held = record(session_id, what, until, pid=os.getpid(), sender=sender)
    try:
        while True:
            line = ready()
            if line:
                print(line)
                return 0
            if time.time() >= until:
                print(f"nothing arrived in {said(seconds)}: still waiting for {what}", file=sys.stderr)
                return 3
            time.sleep(max(0.05, min(every, until - time.time())))
    finally:
        held.unlink(missing_ok=True)


def main(argv: list[str], session_id: str) -> int:
    command = argv[argv.index("--") + 1:] if "--" in argv else []
    p = argparse.ArgumentParser(prog="synthesis wait", description=__doc__.split("\n\n")[0])
    p.add_argument("kind", choices=["message", "file", "run", "note", "list"])
    p.add_argument("target", nargs="?", default="")
    p.add_argument("--from", dest="sender", default="")
    p.add_argument("--for", dest="bound", default="30m")
    p.add_argument("--every", default="")
    p.add_argument("--by", default="")
    args = p.parse_args(argv[:argv.index("--")] if "--" in argv else argv)
    if args.kind == "list":
        for w in live():
            print(f"{board.short_name(w['session'])}  {w['what']}  since {time.strftime('%H:%M', time.localtime(w['since']))} "
                  f"until {time.strftime('%H:%M', time.localtime(w['until']))}  ({'woken by ' + w['by'] if w.get('by') else 'a watcher is running'})")
        return 0
    try:
        seconds, every = span(args.bound), span(args.every or ("30s" if args.kind == "run" else "2s"))
    except ValueError as exc:
        print(exc, file=sys.stderr)
        return 2
    until = time.time() + seconds
    if args.kind == "note":
        if not args.target or not args.by:
            print("a note says what is awaited and, with --by, what will wake this seat", file=sys.stderr)
            return 2
        record(session_id, args.target, until, by=args.by)
        print(f"noted: {args.target}, for {said(seconds)}, woken by {args.by}")
        return 0
    if args.kind == "message":
        me = board.load(session_id)
        if not (me and me.project):
            print("this session is bound to no project: only mail addressed to its id or short name reaches it "
                  "(`synthesis resume <project>` binds it)", file=sys.stderr)

        def ready():
            found = unread(session_id, args.sender)
            names = ", ".join(dict.fromkeys(board.short_name(m["from"]) for m in found))
            return f"message from {names} ({len(found)} unread): run `synthesis inbox` to read" if found else ""
        return _watch(session_id, "a message" + (f" from {args.sender}" if args.sender else ""), until, seconds, every, ready, args.sender)
    if args.kind == "file" and args.target:
        path = Path(args.target).expanduser()
        before = path.stat().st_mtime_ns if path.exists() else None
        return _watch(session_id, f"the file {path}", until, seconds, every,
                      lambda: f"{path} {'appeared' if before is None else 'changed'}" if path.exists() and path.stat().st_mtime_ns != before else "")
    if args.kind == "run" and command:
        tries, shown = [], f"`{' '.join(command)}`"

        def ready():  # a try has only the time left: one still running at the bound is stopped, and none counts after it
            left = until - time.time()
            try:
                tries.append(left > 0 and subprocess.run(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=left).returncode == 0)
            except subprocess.TimeoutExpired:
                tries.append(False)
            return f"{shown} exited 0 after {len(tries)} tr{'y' if len(tries) == 1 else 'ies'}" if tries[-1] and time.time() <= until else ""
        return _watch(session_id, f"{shown} to succeed", until, seconds, every, ready)
    print("give the file to wait for, or the command after `--`", file=sys.stderr)
    return 2
