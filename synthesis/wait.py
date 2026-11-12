"""Waiting for an expected event is a task (2026-11-11): `synthesis wait` blocks until the event or its bound, and
while it runs it holds a record on the board. A seat told to expect something ended its turn with nothing armed,
since a board message reaches a session only when a prompt is submitted; its first watcher then read the inbox,
which marks what it prints, and waited half an hour on mail addressed to a project its session was not bound to.

    synthesis wait message [--from <session|short|project:id>] [--for 30m] [--every 2s]
    synthesis wait file <path> [--for 30m] [--every 2s]
    synthesis wait run [--every 30s] [--for 30m] -- <command>
    synthesis wait note "<what>" --by "<what will wake this seat>" [--for 30m]
    synthesis wait clear ["<what>"]
    synthesis wait list

A wait prints one line when its event happens and exits 0; at its bound it exits 3 and says nothing arrived, so
silence cannot look like success; 2 for a bound it cannot read, one over twelve hours or a command that cannot
be started. A message is named by its sender and never printed: the seat reads it with `synthesis inbox`, which
is what marks it read.
"""
from __future__ import annotations

import argparse
import os
import re
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path

from synthesis import board, paths

MAX_SECONDS = 12 * 3600
GRACE = 2  # the seconds a process that was asked to end has before it is killed
EDGE = 0.25  # the seconds before its bound from which a wait for a message or a file looks every 0.05 s
NUDGE = "A board message is waiting for this session. Run `synthesis inbox` to read it."  # fixed, so it carries nothing else


def span(text: str) -> float:
    """The seconds in "45s", "30m" or "2h" (a bare number is seconds), at most twelve hours."""
    found = re.fullmatch(r"(\d+(?:\.\d+)?)\s*([smh]?)", str(text).strip().lower())
    seconds = float(found[1]) * {"": 1, "s": 1, "m": 60, "h": 3600}[found[2]] if found else 0
    if not 0 < seconds <= MAX_SECONDS:
        raise ValueError(f"{text!r} is not a bound this can keep: give seconds, minutes or hours (45s, 30m, 2h), at most 12h")
    return seconds


def said(seconds: float) -> str:
    hours, minutes, rest = int(seconds) // 3600, int(seconds) % 3600 // 60, int(seconds) % 60
    return " ".join([f"{hours} h"] * bool(hours) + [f"{minutes} min"] * bool(minutes) + [f"{rest} s"] * bool(rest or seconds < 60))


def _folder(session_id: str) -> Path:
    return paths.board() / "waits" / board._session_file(session_id).stem


def record(session_id: str, what: str, until: float, *, pid: int = 0, by: str = "", sender: str = "", every: float = 0) -> Path:
    """One wait a session holds: what is awaited, until when, and the process that watches with how often it looks
    (both 0 for a watcher the harness holds, which `by` names)."""
    path = _folder(session_id) / f"{time.time_ns()}-{pid}.json"
    paths.write_json(path, {"session": session_id, "what": what, "since": time.time(), "until": until, "pid": pid, "by": by, "from": sender,
                            "every": every})
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
    """The waits still held, of one session or of all: inside their bound and, where a process watches, that process
    alive. A record alone proves nothing, and one that is over is removed. Each carries its file, as `record`."""
    root = _folder(session_id) if session_id else paths.board() / "waits"
    found = []
    for file in sorted(root.rglob("*.json")) if root.is_dir() else []:
        held = paths.read_json(file)
        if held.get("until", 0) > time.time() and (not held.get("pid") or _alive(int(held["pid"]))):
            found.append({**held, "record": file})
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


def watching(session_id: str, sender: str) -> str:
    """What a live watcher of that session does with a message this sender's would end, said with how often it looks
    (2026-11-12: "within seconds" was printed for one that looked every five minutes); "" when it has none."""
    every = min((w["every"] for w in live(session_id) if w.get("every") and w["what"].startswith("a message")
                 and sent_by({"from": sender}, w.get("from", ""))), default=0)
    return "it is watching and " + ("wakes within seconds" if every < 10 else f"checks every {said(every)}") if every else ""


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


def _signal(proc: subprocess.Popen, sig: int) -> bool:
    """Send a signal to each process of the group a try ran in; whether a process is left in it."""
    proc.poll()  # once collected, the try's own first process is no longer one that is left
    try:
        os.killpg(proc.pid, sig)
    except ProcessLookupError:
        return False
    except PermissionError:  # one of them runs as another user: the others got the signal
        pass
    return True


def _stop(proc: subprocess.Popen) -> None:
    """End what is left of the group a try ran in: each process is asked to end, and what is still there GRACE seconds
    later is killed. A process that moved itself to another group or session, as a daemon does, has left the try."""
    left, ends = _signal(proc, signal.SIGTERM), time.monotonic() + GRACE
    while left and time.monotonic() < ends:
        time.sleep(0.05)
        left = _signal(proc, 0)
    if left:
        _signal(proc, signal.SIGKILL)
    proc.wait()


def attempt(command: list[str], until: float) -> bool:
    """One try of a command: whether it exits 0 by `until`. It runs in a session of its own, so all it starts is one
    process group, and unless it succeeds in time that group is stopped with it: at the bound, when the try fails, and
    when this wait is itself told to end (2026-11-12: a worker a check had started ran on after the bound)."""
    quits = (signal.SIGTERM, signal.SIGHUP) if threading.current_thread() is threading.main_thread() else ()
    kept = {s: signal.signal(s, lambda number, frame: sys.exit(128 + number)) for s in quits if signal.getsignal(s) == signal.SIG_DFL}
    proc, done = None, False
    try:
        proc = subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
        done = proc.wait(timeout=until - time.time()) == 0 and time.time() <= until
    except subprocess.TimeoutExpired:
        pass
    except OSError as exc:  # no program by that name, or a file that is none: nothing started, so the wait refuses the command
        why = {FileNotFoundError: "was not found", PermissionError: "is not executable"}.get(type(exc), f"cannot be run ({exc.strerror})")
        raise ValueError(f"`{' '.join(command)}` could not be started: its program {command[0]!r} {why}")
    finally:
        if proc and not done:
            _stop(proc)
        for s, handler in kept.items():
            signal.signal(s, handler)
    return done


def _watch(session_id: str, what: str, until: float, seconds: float, every: float, ready, sender: str = "", edge: float = EDGE) -> int:
    """Look every `every` seconds until a look finds the event or the bound comes. What a look that ends after the bound
    finds came too late (2026-11-12: mail that came 1.01 s into a wait of 1 s was reported as arrived), so from `edge`
    seconds before the bound, where a sleep that ends a little late still ends inside it, a look is made every 0.05 s."""
    held = record(session_id, what, until, pid=os.getpid(), sender=sender, every=every)
    try:
        while True:
            line, now = ready(), time.time()
            if line and now <= until:
                print(line)
                return 0
            if now >= until:
                print(f"nothing arrived in {said(seconds)}: still waiting for {what}", file=sys.stderr)
                return 3
            left = until - now
            time.sleep(max(0.05, min(every, left - edge)) if left > edge else min(every, left, 0.05))
    finally:
        held.unlink(missing_ok=True)


def main(argv: list[str], session_id: str) -> int:
    command = argv[argv.index("--") + 1:] if "--" in argv else []
    p = argparse.ArgumentParser(prog="synthesis wait", description=__doc__.split("\n\n")[0])
    p.add_argument("kind", choices=["message", "file", "run", "note", "clear", "list"])
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
    if args.kind == "clear":  # a note has no process whose end takes it down: its own seat does, and a watcher's record is not a note
        gone = [w for w in live(session_id) if w["session"] == session_id and not w.get("pid") and args.target in ("", w["what"])]
        for w in gone:
            w["record"].unlink(missing_ok=True)
        print("\n".join(f"cleared: {w['what']}" for w in gone) or "this session holds no note" + f" {args.target!r}" * bool(args.target))
        return 0
    try:  # `span` refuses a bound it cannot keep and `attempt` a command it cannot start: each says why, and the wait exits 2
        seconds, every = span(args.bound), span(args.every or ("30s" if args.kind == "run" else "2s"))
        until = time.time() + seconds
        if args.kind == "run" and command:
            tries, shown = [], f"`{' '.join(command)}`"

            def ready():  # a try has only the time left: none starts when none is left, and none counts after the bound
                tries.append(until > time.time() and attempt(command, until))
                return f"{shown} exited 0 after {len(tries)} tr{'y' if len(tries) == 1 else 'ies'}" if tries[-1] else ""
            return _watch(session_id, f"{shown} to succeed", until, seconds, every, ready, edge=0)  # a try takes time: none starts on the bound's edge
    except ValueError as exc:
        print(exc, file=sys.stderr)
        return 2
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
    print("give the file to wait for, or the command after `--`", file=sys.stderr)
    return 2
