"""The `synthesis` command: board, projects, approvals and health in one small CLI."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

from synthesis import __version__, board, paths, project


def _session(args) -> str:
    given, own = getattr(args, "session", ""), paths.session_id()
    if given and own and given != own:  # a shell acts only as the session it belongs to
        sys.exit(f"refused: this shell belongs to session {own}; it cannot act as {given}")
    session_id = given or own
    if not session_id:
        sys.exit("no session id: pass --session or run inside a harness session")
    return session_id


def cmd_claim(args) -> int:
    try:
        session = board.claim(_session(args), args.paths, take_stale=args.take,
                              project=args.project, goal=args.goal, harness=paths.harness())
    except board.ClaimConflict as exc:
        print(f"refused: {exc}", file=sys.stderr)
        return 1
    print("claimed:\n  " + "\n  ".join(session.claims))
    return 0


def cmd_release(args) -> int:
    before = len(getattr(board.load(_session(args)), "claims", []))
    left = len(getattr(board.release(_session(args), args.paths or None), "claims", []))
    print(f"released {before - left} claim(s)" if before > left or not args.paths else "no claim matched: nothing released")
    return 0 if before > left or not args.paths else 1


def cmd_who(args) -> int:
    now = time.time()
    found = board.sessions()
    for name in board.NEWER:
        print(f"note: session file {name} was written by a newer synthesis (schema above {board.SCHEMA}); "
              "update this plugin to read it fully, and never edit the file by hand")
    for s in sorted(found, key=lambda s: -s.seen):
        if s.stale and not args.all:
            continue
        age = int((now - s.seen) / 60)
        print(f"{s.short or '-':<7} {s.session}  {s.harness:<11} {s.project or '-':<34} {age:>4} min ago{'  STALE' if s.stale else ''}")
        for c in s.claims:
            print(f"    {c}")
    return 0


def cmd_msg(args) -> int:
    try:
        board.message(args.to, _session(args), args.text, durable=args.durable)
    except board.AddressError as exc:
        print(f"refused: {exc}", file=sys.stderr)
        return 1
    print(f"sent to {args.to}")
    return 0


def cmd_worktree(args) -> int:
    from synthesis import worktree
    return worktree.main((["--session", args.session] if args.session else []) + args.rest)


def cmd_inbox(args) -> int:
    session_id = _session(args)
    me = board.load(session_id)
    for m in board.inbox(session_id, me.project if me else "", mark_read=True):
        print(f"--- {time.strftime('%Y-%m-%d %H:%M', time.localtime(m['at']))} from {m['from']} to {m['to']}\n{m['text']}")
    return 0


def cmd_use(args) -> int:
    if project.find(args.project) is None:
        print(f"no single project named {args.project} under {[str(r) for r in project.roots()]}", file=sys.stderr)
        return 1
    board.touch(_session(args), project=args.project, harness=paths.harness())
    print(f"active project: {args.project}")
    return 0


def cmd_brief(args) -> int:
    session = board.load(_session(args)) if not args.project else None
    name = args.project or (session.project if session else "")
    project_dir = project.find(name) if name else None
    if project_dir is None:
        print("no active project; run `synthesis use <project>`", file=sys.stderr)
        return 1
    print(project.brief(project_dir))
    problems = project.check(project_dir)
    if problems:
        print("\nRecord problems:\n- " + "\n- ".join(problems))
    return 0


def cmd_resume(args) -> int:
    print(project.resume(args.project, getattr(args, "session", "") or paths.session_id(), switch=args.switch))
    return 0


def cmd_handoff(args) -> int:
    lines = project.handoff(_session(args), args.message)
    print("\n".join(lines))
    return 0 if lines and lines[-1].startswith("READY") else 1


def cmd_approvals(args) -> int:
    directory = paths.state() / "approval-requests"
    for f in sorted(directory.glob("*.json")) if directory.is_dir() else []:
        data = json.loads(f.read_text(encoding="utf-8"))
        print(f"{f.stem}  {time.strftime('%H:%M', time.localtime(data['at']))}  {data['summary']}")
    return 0


def cmd_install(args) -> int:
    from synthesis import install
    plugin = Path(args.plugin) if args.plugin else Path(__file__).resolve().parents[1]
    try:
        print(install.install(plugin))
        if args.git_hooks:
            print(install.register_git_hooks())
    except (OSError, RuntimeError, subprocess.SubprocessError) as exc:
        print(f"install failed: {exc}", file=sys.stderr)
        return 1
    return 0


def cmd_uninstall(args) -> int:
    from synthesis import install
    print("\n".join(install.uninstall(dry_run=args.dry_run)))
    return 0


def cmd_doctor(args) -> int:
    from synthesis import doctor
    return doctor.main(args.rest)


def cmd_version(args) -> int:
    print(__version__)
    return 0


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="synthesis", description=__doc__)
    p.add_argument("--session", default="", help="session id (default: the harness's own)")
    sub = p.add_subparsers(dest="command", required=True)
    s = sub.add_parser("claim", help="claim paths for this session")
    s.add_argument("paths", nargs="+")
    s.add_argument("--project", default=None)
    s.add_argument("--goal", default=None)
    s.add_argument("--take", action="store_true", help="take over overlapping stale claims")
    s.set_defaults(fn=cmd_claim)
    s = sub.add_parser("release", help="release some or all claims")
    s.add_argument("paths", nargs="*")
    s.set_defaults(fn=cmd_release)
    s = sub.add_parser("who", help="list live sessions and claims")
    s.add_argument("--all", action="store_true")
    s.set_defaults(fn=cmd_who)
    s = sub.add_parser("msg", help="message a session id, short name or project:<id>")
    s.add_argument("to")
    s.add_argument("text")
    s.add_argument("--durable", action="store_true", help="reach every session that works on the project")
    s.set_defaults(fn=cmd_msg)
    s = sub.add_parser("worktree", help="create, retire or land a worktree", add_help=False)
    s.add_argument("rest", nargs=argparse.REMAINDER)
    s.set_defaults(fn=cmd_worktree)
    sub.add_parser("inbox", help="show and mark unread messages").set_defaults(fn=cmd_inbox)
    s = sub.add_parser("use", help="set this session's active project")
    s.add_argument("project")
    s.set_defaults(fn=cmd_use)
    s = sub.add_parser("brief", help="print a project's directive and current state")
    s.add_argument("project", nargs="?", default="")
    s.set_defaults(fn=cmd_brief)
    s = sub.add_parser("resume", help="pick up a project: directive, state, next actions and warnings, or the question to ask first")
    s.add_argument("project", help="project id, or the project folder's absolute path")
    s.add_argument("--switch", action="store_true", help="switch this session to the project after the principal agreed")
    s.set_defaults(fn=cmd_resume)
    s = sub.add_parser("handoff", help="commit and push changes inside this session's claims")
    s.add_argument("-m", "--message", default="Update project records")
    s.set_defaults(fn=cmd_handoff)
    sub.add_parser("approvals", help="list sends and deploys waiting for the principal's approval").set_defaults(fn=cmd_approvals)
    s = sub.add_parser("install", help="install the runtime from a plugin folder (default: this one)")
    s.add_argument("plugin", nargs="?", default="")
    s.add_argument("--git-hooks", action="store_true", help="also run the commit check for every repository")
    s.set_defaults(fn=cmd_install)
    s = sub.add_parser("uninstall", help="remove what install wrote; keep config and the board")
    s.add_argument("--dry-run", action="store_true")
    s.set_defaults(fn=cmd_uninstall)
    s = sub.add_parser("doctor", help="check the runtime, hooks and each harness's install", add_help=False)
    s.add_argument("rest", nargs=argparse.REMAINDER)
    s.set_defaults(fn=cmd_doctor)
    sub.add_parser("version").set_defaults(fn=cmd_version)
    return p


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    for name, fn in (("worktree", cmd_worktree), ("doctor", cmd_doctor)):
        if name in argv:  # hand everything after it to that command's own parser untouched
            split = argv.index(name)
            args = parser().parse_args(argv[:split] + [name])
            args.rest = argv[split + 1:]
            return fn(args)
    args = parser().parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
