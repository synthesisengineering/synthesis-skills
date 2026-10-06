#!/usr/bin/env python3
"""Autopilot plan helpers an agent runs by hand (R6): engage, status, cycle, close, alert,
wake-prompt and takeover.

The turn-end check the Stop and SessionStart hooks call, and the plan reader it
uses, stay in the core (synthesis/autopilot.py); these commands import them from
there. The install copies this file into the runtime, so the stable path is

    python3 -S "$HOME/.synthesis/v5/current/skills/synthesis-autopilot/scripts/autopilot_cli.py" <command> --help
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))  # the plugin root or the installed runtime: holds synthesis/
from synthesis import board, paths  # noqa: E402
from synthesis.autopilot import (  # noqa: E402
    FIELD, FIRST_WAKE_GRACE, LIST, OPEN, Plan, _continuation_problems, _pointer_file, _read_pointer,
    _write_pointer, close_problems, load)

SILENT_DEFAULT_MINUTES = 8 * 60
DEFAULT_STANDING = (
    ("end-to-end", "Complete the work end to end: every item closed or the run closed honestly incomplete."),
    ("framework-decisions", "Open important decisions go through the thinking framework, recorded with rationale."),
    ("plan-current", "Plan re-read after any suspected compaction or wake, and updated at every phase boundary."),
    ("project-files-current", "Project files (CONTEXT.md, session log) current at every phase boundary and at close."),
    ("verify-before-done", "Verification before any completion claim: focused tests per change, full suites per phase."),
    ("lessons-filed", "Durable lessons filed as work proceeds, not at the end."),
    ("completion-report", "Completion report plus batched questions (a decision packet when complex) ready at close."),
)


def _now() -> str:
    return datetime.now().astimezone().isoformat(timespec="minutes")


def _header_end(lines: list[str]) -> int:
    return next((i for i, line in enumerate(lines) if line.startswith("## ")), len(lines))


def set_field(text: str, name: str, value: str) -> str:
    lines = text.splitlines()
    end = _header_end(lines)
    fields = [i for i in range(end) if FIELD.match(lines[i].strip()) and not lines[i].startswith("#")]
    for i in fields:
        if FIELD.match(lines[i].strip()).group(1).strip().lower() == name.lower():
            lines[i] = f"{name}: {value}"
            return "\n".join(lines) + "\n"
    title = next((i for i in range(end) if lines[i].startswith("# ")), -1)
    at = fields[-1] + 1 if fields else title + 1
    lines[at:at] = [f"{name}: {value}"] + ([""] if not fields and title >= 0 else [])
    return "\n".join(lines) + "\n"


def append_to_section(text: str, section: str, entries: list[str]) -> str:
    lines = text.rstrip("\n").splitlines()
    start = next((i for i, l in enumerate(lines) if l.startswith("## ") and l[3:].lower().startswith(section.lower())), None)
    if start is None:
        return "\n".join(lines + ["", f"## {section}", ""] + entries) + "\n"
    end = next((i for i in range(start + 1, len(lines)) if lines[i].startswith("## ")), len(lines))
    while end > start + 1 and not lines[end - 1].strip():
        end -= 1
    lines[end:end] = entries
    return "\n".join(lines) + "\n"


def _write(path: Path, text: str) -> None:
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


def _session(args) -> str:
    return args.session or paths.session_id()


def _settings() -> dict:
    try:
        return paths.config().get("autopilot") or {}
    except (OSError, ValueError):
        return {}


def _fail(message: str) -> int:
    print(message, file=sys.stderr)
    return 1


def _owned(args, plan: Plan) -> str:
    """This session's id when it owns the plan; empty after printing why not."""
    session = _session(args)
    if not session:
        _fail("no session id: pass --session (Claude Code shells carry $CLAUDE_CODE_SESSION_ID, Codex $CODEX_THREAD_ID)")
        return ""
    if plan.field("owner session") != session:
        _fail(f"refused: {plan.path} is owned by session {plan.field('owner session') or '(none)'}, not {session}")
        return ""
    return session


def cmd_engage(args) -> int:
    session = _session(args)
    path = Path(args.plan).expanduser().resolve()
    if not session:
        return _fail("no session id: pass --session (Claude Code shells carry $CLAUDE_CODE_SESSION_ID, Codex $CODEX_THREAD_ID)")
    if not path.is_file():
        return _fail(f"no plan file at {path}; write it from references/plan-file.md first")
    plan = load(path)
    owner = plan.field("owner session")
    problems = [] if not owner or owner == session else [f"it is owned by session {owner}; run takeover if that session has gone silent"]
    problems += [] if plan.items("checklist") else ["## Checklist has no '- [ ] item' lines"]
    problems += [] if plan.items("completion criteria") else ["## Completion criteria has no '- [ ] criterion' lines"]
    problems += [] if plan.field("horizon") else ["no 'Horizon:' line (turn, sitting, overnight or days)"]
    problems += [] if plan.status in ("",) + OPEN else [f"Status is {plan.status}; a closed run is not engaged again"]
    if problems:
        return _fail(f"refused: {path}\n- " + "\n- ".join(problems))
    try:
        board.claim(session, [str(path)], goal=f"autopilot: {plan.title}"[:120], harness=paths.harness())
    except board.ClaimConflict as exc:
        return _fail(f"refused: {exc}")
    text = set_field(plan.text, "Owner session", session)
    if not plan.status:
        text = set_field(text, "Status", "running")
    if not plan.field("engaged"):
        text = set_field(text, "Engaged", _now())
    extra = [(i.get("id", ""), i.get("text", "")) for i in _settings().get("standing_checklist", [])]
    have = {re.split(r"[:\s]", t, maxsplit=1)[0] for _, t in plan.items("standing checklist")}
    missing = [f"- [ ] {i}: {t}" for i, t in DEFAULT_STANDING + tuple(extra) if i and i not in have]
    if missing:
        text = append_to_section(text, "Standing checklist", missing)
    _write(path, text)
    _write_pointer(session, {"plan": str(path), "streak": 0, "digest": "", "at": time.time()})
    plan = Plan(path, text)
    print(f"engaged: {path}\nowner session: {session}  status: {plan.status}  horizon: {plan.field('horizon')}")
    print(f"next item: {(plan.open_items() or ['none'])[0]}")
    for warning in _continuation_problems(plan, {}, FIRST_WAKE_GRACE) if plan.long_horizon else []:
        print(f"before this turn ends: {warning}")
    return 0


def _questions(plan: Plan) -> list[str]:
    return [m.group(2) for m in map(LIST.match, plan.sections.get("questions for the principal", []))
            if m and m.group(2) and m.group(1) in (None, " ")]


def cmd_status(args) -> int:
    session = _session(args)
    folder = paths.state() / "autopilot"
    files = sorted(folder.glob("*.json")) if args.all and folder.is_dir() else (
        [_pointer_file(session)] if session else [])
    shown = 0
    for file in files:
        try:
            plan = load(json.loads(file.read_text(encoding="utf-8"))["plan"])
        except (OSError, ValueError, KeyError, TypeError):
            continue
        shown += 1
        owner = plan.field("owner session")
        age = int((time.time() - plan.path.stat().st_mtime) / 60)
        items, total = plan.open_items(), len(plan.items("checklist"))
        print(f"{plan.path}\n  status: {plan.field('status') or '?'}  owner: {owner}"
              f"{' (this session)' if owner == session else ''}  plan edited {age} min ago")
        print(f"  next: {items[0] if items else '-'}  ({len(items)} of {total} items open)")
        for name in ("waiting on", "continuation", "first wake", "backstop"):
            if plan.field(name):
                print(f"  {name}: {plan.field(name)}")
        for text in [t for done, t in plan.items("blockers") if not done]:
            print(f"  blocker: {text}")
        for text in _questions(plan):
            print(f"  question: {text}")
    if not shown:
        print("no autopilot plan engaged" + (" on this machine" if args.all else " by this session"))
    return 0


def cmd_cycle(args) -> int:
    advanced, waiting = (args.advanced or "").strip(), (args.waiting_on or "").strip()
    if not advanced and not waiting:
        return _fail("refused: a cycle that advanced nothing must name the external wait it is on (--waiting-on). "
                     "There is no way to record a bare spin: if nothing advanced and nothing external is awaited, "
                     "the run is spinning, so record a blocker and alert, or close.")
    path = Path(args.plan).expanduser().resolve()
    plan = load(path)
    if not _owned(args, plan):
        return 1
    entry = "; ".join(p for p in (advanced and f"advanced: {advanced}", waiting and f"waiting on: {waiting}") if p)
    text = append_to_section(plan.text, "Cycle ledger", [f"- {_now()} {entry}"])
    _write(path, text)
    count = sum(1 for line in Plan(path, text).sections.get("cycle ledger", []) if LIST.match(line))
    print(f"cycle recorded ({count} in the ledger)")
    return 0


def cmd_close(args) -> int:
    path = Path(args.plan).expanduser().resolve()
    if not path.is_file():
        return _fail(f"refused: no plan file at {path}; a run without a plan cannot close as done")
    plan = load(path)
    session = _owned(args, plan)
    if not session:
        return 1
    status, why = ("done", "") if args.done else ("incomplete", args.incomplete) if args.incomplete is not None else ("cancelled", args.cancelled)
    if status != "done" and not (why or "").strip():
        return _fail(f"refused: closing as {status} needs the reason")
    text = set_field(plan.text, "Status", status + (f" — {why.strip()}" if why else ""))
    problems = close_problems(Plan(path, text), status)
    if problems:
        return _fail(f"refused: {path} cannot close as {status}:\n- " + "\n- ".join(problems)
                     + ("\nClosing as incomplete with the reason stays available." if status == "done" else ""))
    _write(path, text)
    claimed = os.path.realpath(path)
    board.release(session, [claimed])
    if _read_pointer(session).get("plan") == str(path):
        _pointer_file(session).unlink()
    print(f"closed as {status}: {path}\nnext: send the completion alert and the completion report")
    return 0


ALERTS = {
    "blocked": "Autopilot run is blocked: {n} question(s) need you. Run autopilot status for details.",
    "done": "Autopilot run finished. The report is in its plan.",
    "budget": "Autopilot run stopped at its budget: {n} item(s) left. Run autopilot status for details.",
}


def alert(kind: str, count: int, *, mute_flag: Path, run=None, which=None) -> list[tuple[str, str]]:
    """Banner and sound with counts and a pointer only. Returns (channel, outcome) pairs to record."""
    import shutil
    import subprocess

    run, which = run or subprocess.run, which or shutil.which
    text = ALERTS[kind].format(n=count)
    outcomes = []

    def attempt(channel: str, command: list[str]) -> None:
        try:
            done = run(command, capture_output=True, timeout=20)
            outcomes.append((channel, "posted" if channel == "banner" and done.returncode == 0 else
                             "played" if done.returncode == 0 else f"failed (exit {done.returncode})"))
        except Exception as exc:  # report, never raise: the written report still goes out
            outcomes.append((channel, f"failed ({type(exc).__name__})"))

    if which("osascript"):
        attempt("banner", ["osascript", "-e", f'display notification "{text}" with title "Autopilot"'])
    else:
        outcomes.append(("banner", "unavailable (no osascript)"))
    if mute_flag.exists():
        outcomes.append(("audio", "suppressed (mute flag)"))
    elif which("say"):
        attempt("audio", ["say", text])
    else:
        outcomes.append(("audio", "unavailable (no say)"))
    return outcomes


def cmd_alert(args) -> int:
    mute = Path(os.path.expanduser(_settings().get("mute_flag", "~/.synthesis/quiet-audio")))
    outcomes = alert(args.kind, args.count, mute_flag=mute)
    for channel, outcome in outcomes:
        print(f"{channel}: {outcome}")
    print(f"record on the blocker or close line: alerted {_now()} ("
          + "; ".join(f"{c} {o}" for c, o in outcomes) + ")")
    return 0 if any(o in ("posted", "played") for _, o in outcomes) else 1


def wake_prompt(path) -> str:
    return (f"Autopilot wake for the plan at {path}. Read that plan before anything else. If its Status is done, "
            f"incomplete or cancelled, do no work: delete this scheduled job, read the deletion back, and stop. If "
            f"another session owns it, run `autopilot_cli.py status --all`; take it over only when the plan has been "
            f"silent longer than its Silent after: line allows, otherwise message the owner and stop. Otherwise "
            f"verify the plan's state against git and the files on disk, record this wake in the cycle ledger, and "
            f"continue the next open checklist item.")


def cmd_wake_prompt(args) -> int:
    print(wake_prompt(Path(args.plan).expanduser().resolve()))
    return 0


def cmd_takeover(args) -> int:
    session = _session(args)
    path = Path(args.plan).expanduser().resolve()
    if not session:
        return _fail("no session id: pass --session")
    plan = load(path)
    owner = plan.field("owner session")
    if plan.status not in OPEN:
        return _fail(f"refused: {path} is {plan.status or 'not engaged'}; there is nothing to take over")
    limit = int(re.match(r"\d*", plan.field("silent after")).group(0) or SILENT_DEFAULT_MINUTES) * 60
    held = board.load(owner) if owner else None
    activity = max(path.stat().st_mtime, held.seen if held else 0)
    if owner and owner != session and time.time() - activity < limit:
        return _fail(f"refused: owner {owner} was active {int((time.time() - activity) / 60)} min ago (limit "
                     f"{limit // 60} min); message it with `synthesis msg {owner} ...` instead")
    claim = os.path.realpath(path)
    if held and claim in held.claims:
        board.release(owner, [claim])
    try:
        board.claim(session, [str(path)], goal=f"autopilot: {plan.title}"[:120], harness=paths.harness())
    except board.ClaimConflict as exc:
        return _fail(f"refused: {exc}")
    if owner and owner != session:
        board.notify(owner, session, f"Took over autopilot plan {path}: no activity for {limit // 60} minutes.")
    text = set_field(plan.text, "Owner session", session)
    text = append_to_section(text, "Cycle ledger", [f"- {_now()} taken over from {owner or '(none)'} by {session}"])
    _write(path, text)
    _write_pointer(session, {"plan": str(path), "streak": 0, "digest": "", "at": time.time()})
    print(f"took over: {path}\nnext item: {(load(path).open_items() or ['none'])[0]}")
    return 0


def main(argv: list[str] | None = None) -> int:
    import argparse

    p = argparse.ArgumentParser(prog="autopilot_cli.py", description="Autopilot plan helpers (synthesis v5).")
    p.add_argument("--session", default="", help="session id (default: the harness's own)")
    sub = p.add_subparsers(dest="command", required=True)
    s = sub.add_parser("engage", help="take ownership of a plan file and turn on the turn-end check")
    s.add_argument("--plan", required=True)
    s.set_defaults(fn=cmd_engage)
    s = sub.add_parser("status", help="this session's run, or every run on this machine with --all")
    s.add_argument("--all", action="store_true")
    s.set_defaults(fn=cmd_status)
    s = sub.add_parser("cycle", help="record a wake in the cycle ledger; a bare spin is refused")
    s.add_argument("--plan", required=True)
    s.add_argument("--advanced", default="")
    s.add_argument("--waiting-on", default="")
    s.set_defaults(fn=cmd_cycle)
    s = sub.add_parser("close", help="close the run honestly")
    s.add_argument("--plan", required=True)
    group = s.add_mutually_exclusive_group(required=True)
    group.add_argument("--done", action="store_true")
    group.add_argument("--incomplete", metavar="REASON")
    group.add_argument("--cancelled", metavar="REASON")
    s.set_defaults(fn=cmd_close)
    s = sub.add_parser("alert", help="banner and sound with counts and a pointer only; honors the mute flag")
    s.add_argument("--kind", choices=sorted(ALERTS), required=True)
    s.add_argument("--count", type=int, default=1)
    s.set_defaults(fn=cmd_alert)
    s = sub.add_parser("wake-prompt", help="print the prompt every scheduled wake uses")
    s.add_argument("--plan", required=True)
    s.set_defaults(fn=cmd_wake_prompt)
    s = sub.add_parser("takeover", help="take over a plan whose owner has gone silent")
    s.add_argument("--plan", required=True)
    s.set_defaults(fn=cmd_takeover)
    args = p.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
