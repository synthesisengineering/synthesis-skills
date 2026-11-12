#!/usr/bin/env python3
"""Record and query daily-ritual state: one append-only log, every view per workspace.

There is no mutable state file. On 2026-09-02 one seat's close overwrote
another's single `last_day_end` slot; a lock would not have helped, because the
second writer still replaces the slot. So records are appended and every view
is derived. Each record carries two clocks: `date`, the logical workday opened
or closed (required, never inferred: a close written at 01:30 belongs to the
day before), and `ts`, when it was written. On 2026-09-14 an unscoped weekly
review query let one workspace's Friday review silence every other workspace,
so every view answers for one workspace, and an empty `--workspace ""` (an
unset shell variable) is refused rather than read as "all workspaces".

    ritual_state.py record --direction day-end --workspace W --date YYYY-MM-DD \\
        [--mode quick] [--outcome clean] [--session ID] [--pointer FILE] [--count sent=3] [--travel FILE]
    ritual_state.py query summary|last|open|streak|weekly-review [--workspace W] [--json]

`record` first reads the plan folders the workspace declares in the ritual config (`plans_dirs`,
`artifacts_dirs`) with the deadline sweep. It refuses while a critical deadline is past due and open,
and refuses a clean outcome over plans it could not read whole (2026-11-06: an enrollment window
closed unanswered and the day was recorded clean). A workspace that declares neither key is refused.
A workspace that turns the travel check on (`"travel_check": true`, or `{"days": N}`) must also pass
`--travel`, the output of `travel_check.py --json` for that day and the days ahead: no result, or one
that holds an in-person event without its travel, and the ritual is not recorded (2026-11-11: an evening
28 miles from home had been carried through three plans and a day-start with no way to get there).
It also reads the day's plan in each declared plan folder: an open item that offers options with no
recommendation, or with no word on what it costs where it would commit the principal's time, and the
ritual is not recorded (the invitation to that evening had been put as a bare accept or decline).

The log is `<synthesis home>/rituals/history.jsonl` (`RITUAL_STATE_DIR` or
`--state-dir` points elsewhere, to exercise a copy). Derivations live in the
plugin's `synthesis/rituals.py`, which the SessionStart line and the nudge share.
"""

from __future__ import annotations

import argparse
import fcntl
import json
import os
import re
import sys
from datetime import date, datetime, time, timedelta
from pathlib import Path

_PLUGIN = Path(__file__).resolve().parents[3]
sys.dont_write_bytecode = True  # an installed plugin must stay byte-identical; Muse verifies its bundle
for _root in (_PLUGIN, Path(os.environ.get("SYNTHESIS_HOME") or Path.home() / ".synthesis" / "v5") / "current"):
    if (_root / "synthesis" / "rituals.py").is_file():
        sys.path.insert(0, str(_root))
        break
from synthesis import rituals  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
import decay_sweep  # noqa: E402

MAX_RECORD_BYTES = 2048  # structured data only; the narrative belongs in the session log
DIRECTIONS = ("day-start", "day-end", "weekly-review")
OUTCOMES = ("clean", "complete", "completed", "success", "partial", "failed", "skipped", "blocked", "degraded")
VIEWS = ("summary", "last", "open", "streak", "weekly-review")
CLEAN = ("clean", "complete", "completed", "success")  # outcomes that claim nothing was left uncovered


def today() -> date:
    return date.today()


def refuse(message: str) -> None:
    raise SystemExit(f"ritual_state: {message}")


def check_workspace(value: str | None, form: str) -> None:
    if value is not None and not value.strip():
        refuse(f"--workspace {value!r} is empty, the shape an unset shell variable produces; it is "
               f"neither a workspace nor an omission, so it is refused. Accepted form: {form}")


def append(record: dict) -> None:
    """Append one bounded line under an exclusive lock; refuse an unsafe or interrupted log."""
    line = (json.dumps(record, separators=(",", ":"), sort_keys=True) + "\n").encode("utf-8")
    if len(line) > MAX_RECORD_BYTES:
        refuse(f"record is {len(line)} bytes, over {MAX_RECORD_BYTES}; put prose in the session log "
               "and point to it with --pointer")
    path = rituals.state_dir() / "history.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path, os.O_RDWR | os.O_CREAT | os.O_APPEND | os.O_NOFOLLOW, 0o644)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        size = os.fstat(fd).st_size
        if size and os.pread(fd, 1, size - 1) != b"\n":
            refuse(f"{path} ends in an interrupted line; it is left as found for you to reconcile")
        written = os.write(fd, line)
        os.fsync(fd)
        if written != len(line) or os.pread(fd, len(line), size) != line:
            refuse(f"the append to {path} did not read back whole; inspect the tail before retrying")
    finally:
        os.close(fd)


def critical_deadlines(workspace: str, outcome: str) -> str:
    """The line `record` prints about critical deadlines, or a refusal: one past due, plans unread, none declared."""
    try:
        roots = decay_sweep.declared(rituals.config(), workspace)
    except ValueError as exc:
        refuse(f"{exc}; refusing to guess")
    if roots is None:
        refuse(f"{workspace} declares no plan folders, so its critical deadlines cannot be checked and this ritual is "
               f"not recorded. In {rituals.state_dir() / 'config.json'}, under workspaces.{workspace}, add "
               '"plans_dirs": ["<folder of dated plans>"] (and "artifacts_dirs" for ritual-worker artifacts), '
               'or "plans_dirs": [] for a workspace that keeps no dated plans')
    if not roots:
        return f"critical deadlines: {workspace} declares that it keeps no dated plans, so none are tracked"
    report = decay_sweep.collect(roots, today(), workspace)
    late = [row for row in report["critical"]["open"] if row["past_due"]]
    if late:
        refuse(f"{len(late)} critical deadline(s) past due and open, so this ritual is not recorded:\n"
               + "\n".join(f"  {r['due_date']} {r['title']} [{r['class']}] ({r['path']}:{r['line']})" for r in late)
               + "\nAsk the principal now. Each closes only with a closing mark and an **Evidence:** line at the item (a "
               "confirmation, or the principal's own words quoted with the time), or carries a new date with its reason. "
               "Never decide for the principal that nothing is needed, and never mark it Lapsed.")
    if report["gaps"] and outcome in CLEAN:
        refuse(f"{len(report['gaps'])} plan source(s) could not be read whole, so critical deadlines are not fully "
               f"covered and outcome {outcome!r} would claim they are. Record --outcome partial and name the gaps "
               "(decay_sweep.py lists each as NOT COVERED)")
    rows = report["critical"]["open"]
    return f"critical deadlines: {len(rows)} open, {sum(r['lead'] for r in rows)} within {decay_sweep.LEAD_DAYS} days"


def _when(moment) -> datetime:
    """A whole date and time, as the travel check writes one; anything else is no result of that check."""
    return datetime.fromisoformat(str(moment).replace("Z", "+00:00"))


def _day(moment) -> str:
    return _when(moment).date().isoformat()


def travel(workspace: str, day: str, given) -> str:
    """The line `record` prints about travel, or a refusal: no result, one for other days, an event without its travel."""
    wanted = rituals.settings(rituals.config(), workspace).get("travel_check")
    if not wanted:
        return ""
    days = int(wanted.get("days", 7)) if isinstance(wanted, dict) else 7
    last = (date.fromisoformat(day) + timedelta(days=days - 1)).isoformat()
    again = "travel_check.py --json (in synthesis-chief-of-staff)"
    if not given:
        refuse(f"{workspace} checks travel, and this record names no result. Read the calendar for the next {days} days, run "
               f"{again} over it, save what it prints and pass --travel <that file>")
    try:
        found = json.loads(Path(given).read_text(encoding="utf-8"))
        first, through = (date.fromisoformat(found["window"][key]).isoformat() for key in ("from", "through"))
        events = found["events"]
        bare = [e for e in events if e["lacks"]]
        sound = (isinstance(events, list) and all(isinstance(e["lacks"], list) for e in events) and
                 (found["in_person"], found["flagged"], found["verdict"]) == (len(events), len(bare), "REFUSE" if bare else "OK")
                 and all(first <= _day(e["end"]) and _day(e["start"]) <= through and _when(e["start"]) <= _when(e["end"])
                         for e in events))  # each event within its days, and ending after it starts
    except (OSError, ValueError, KeyError, TypeError) as exc:
        refuse(f"the travel result {given} cannot be read ({exc!r}); run {again} again")
    if not sound:  # a result edited by hand, or cut short
        refuse(f"the travel result {given} does not agree with itself (its counts, its verdict and its events differ), "
               f"so it is not what {again} printed; run it again")
    if first != day or through < last:
        refuse(f"the travel result covers {first} through {through}, and this record needs {day} "
               f"through {last}. Run {again} for those days")
    if bare:
        refuse(f"{len(bare)} in-person event(s) through {last} lack their travel, so this ritual is not recorded:\n"
               + "\n".join(f"  {str(e.get('start'))[:16]} {e.get('summary')}: " + "; ".join(map(str, e["lacks"])) for e in bare)
               + "\nWork each trip out from a live source and add its blocks, or put the event to the principal. Never "
               "write a time that no block gives.")
    return f"\ntravel: {len(events)} in-person event{'s' * (len(events) != 1)} through {last}, each with its travel"


# A line of an item: plain, bold or italic, quoted, a list entry or a task-list box, a heading or a row of a table,
# in any order and however deep (`- > **Option A:**` is a quote inside a list entry).
ITEM = r"(?im)^ *(?:> *|\| *|#{1,6} +|(?:[-*+]|\d+[.)]) +(?:\[[ xX]\] +)?)*[*_]*"
# An option's label ends at the mark that closes its emphasis, or at a colon, a dash, a bracket, a full stop or the
# end of the line: `Option A was fine last time` is a sentence.
OPTION = re.compile(ITEM + r"Option [A-Z0-9]+(?![A-Za-z0-9])((?:[*_]+|\s*(?:$|[:\-–—().|])).*)$")
SAID = re.compile(ITEM + r"(?:(?:My|Our|The) +)?(Recommend(?:ation|ed)s?|Consequences?|Commits)[*_]*\s*(?::|[-–—](?=[*_\s]))[*_\s]*(.*)$")
CLOSED = re.compile(ITEM + r"(?:Decided|Decision|Resolved|Released|Lapsed|Withdrawn)[*_]*\s*:[*_\s]*(.*)$")
OPEN = re.compile(r"(?i)\W*(?:pending|open\b|awaiting|waiting|needed|not yet|to be )")  # a closing line that closes nothing
# What Markdown does not show as the plan's own text: a fenced block (quoted or not, closed or not), which is an
# example, and an HTML comment. Whichever opens first runs to its own end: a fence closes at a line of its own
# mark alone, at least as long as the one that opened it, so four backticks hold a sample fenced with three.
FENCE = re.compile(r"(?ms)^\s*(?:>\s*)*(?P<fence>(?P<mark>[`~])(?P=mark){2,}).*?(?:^\s*(?:>\s*)*(?P=fence)(?P=mark)*[ \t]*$|\Z)"
                   r"|<!--.*?(?:-->|\Z)")
QUOTE = re.compile(r"^( *)(?:> ?)+")  # what marks a line as quoted: the line is read as the one it quotes, as far in as the quote stands
NOTHING = re.compile(r"(?i)[*_\s]*(?:tbd|tbc|none|n/?a|no recommendation|your call|up to you|either)?[\s.*_]*")
COMMITS = re.compile(r"(?i)\b(?:accept|decline|rsvp|attend|go|join|host|schedule|meet|say (?:yes|no))\b")


TITLED = re.compile(r"(?i)(?<![A-Za-z0-9])(Recommendation|Consequences|Commits)[*_]*\s*:[*_\s]*(.*)$")  # the same word and colon on a title line
MARK = re.compile(r"^ *(?:> *|#{1,6} +|(?:[-*+]|\d+[.)]) +)*")  # what stands before a title that is a list entry or a heading; a task-list box stays, since a ticked one closes it
HEAD = re.compile(r"(?i) *(?:#{4,6} +(?!(?:the +)?(?:options?|choices?)\W*$)\S|(?:\*\*|__)[^*_\n].*(?:\*\*|__)\s*$)")  # a deeper heading or a line all in bold: a title
ENTRY = re.compile(r" *(?:>\s*)*(?:[-*+] |\d+[.)] )")  # a list entry, up to where its own text starts
LABEL = re.compile(r"(?i)Option ([A-Z0-9]+)(?![A-Za-z0-9])")


def _shown(text: str) -> str:
    """A plan without its examples: a fenced block, and a block Markdown shows as code, which is one indented four
    or more past the text of the list entry it stands in, after an empty line (the seventh review: options indented
    by four under a numbered entry are that entry's own lines, and were read as an example)."""
    lines, columns, blank, example = [], [], True, False
    for line in FENCE.sub("", text).expandtabs(4).splitlines():
        body = QUOTE.sub(r"\1", line)
        indent, entry = len(body) - len(body.lstrip(" ")), ENTRY.match(body)
        if body.strip():
            while columns and indent < columns[-1] and (blank or entry or body.lstrip().startswith("#")):
                columns.pop()  # the line stands left of that entry's text: the entry is over
            example = indent - (columns[-1] if columns else 0) >= 4 and (blank or example)
            columns += [len(entry[0])] if entry and not example else []
        lines.append("" if example else line)
        blank = not body.strip()
    return "\n".join(lines)


def _items(text: str):
    """Each choice a plan puts, as its own lines, the title first. A choice is a run of options with the lines
    around it: under a heading of its own, or one entry of a list under a shared heading. The list's next entry, or
    options whose label starts again (A after B), begin the next choice; a bullet under an option does not (the
    third and fourth reviews: decisions listed under a second-level heading were not read, a heading inside a fenced
    example was read as a choice, and a second entry lettered C and D was read as more options of the first)."""
    for section in re.split(r"(?im)^#{1,3} (?![*_]*Option [A-Z0-9])", _shown(text)):
        lines, firsts, label, entry, fresh = section.splitlines(), [], None, -1, False
        for at, line in enumerate(lines):
            listed = re.match(r"( *)(?:>\s*)*(?:[-*+] |\d+[.)] )", line) if at and not (SAID.match(line) or CLOSED.match(line)) else None
            if OPTION.match(line):
                this = LABEL.search(line)[1].upper()
                firsts += [at] if label is None or this <= label or fresh else []
                label, fresh = this, False
            elif listed and (label is None or fresh):
                entry = len(listed[1])  # the entry a choice's options stand under, by how far it is indented
            elif listed and len(listed[1]) <= entry:
                entry, fresh = len(listed[1]), True  # the list's next entry: its options are another choice, whatever their letters
        def depth(j):  # how far in a line's own text stands, its quote marks set aside
            return len(QUOTE.sub(r"\1", lines[j])) - len(QUOTE.sub(r"\1", lines[j]).lstrip(" "))
        def titled(k):  # the line a choice starts at: the entry just above its options, else the section's own first line
            floor = firsts[k - 1] + 1 if k else 0
            above = next((j for j in range(firsts[k] - 1, floor - 1, -1) if lines[j].strip()
                          and not (OPTION.match(lines[j]) or SAID.match(lines[j]) or CLOSED.match(lines[j]))), None)
            if above is not None and depth(above) and not ENTRY.match(QUOTE.sub(r"\1", lines[above])):
                # a sentence of explanation between an entry and its options: the entry is the one it stands in,
                # the nearest above whose own text begins at or left of it
                for j in range(above - 1, floor - 1, -1):
                    found = ENTRY.match(QUOTE.sub(r"\1", lines[j]))
                    if found and len(found[0]) <= depth(above):
                        above = j
                        break
                    if lines[j].strip() and depth(j) < depth(above):
                        break  # a line left of it that is no entry: the sentence stands in no list
            entry = above is not None and (len(firsts) > 1 or ENTRY.match(lines[above]) or HEAD.match(lines[above]))
            return above if entry else 0 if k == 0 else firsts[k]
        starts = [titled(k) for k in range(len(firsts))]
        for k, start in enumerate(starts):
            yield "\n".join(lines[start:starts[k + 1] if k + 1 < len(starts) else len(lines)])


def choices(workspace: str, day: str) -> str:
    """The line `record` prints about the choices the day's plan puts to the principal, or a refusal: an open item
    that offers options with no recommendation, or, when it would commit their time (an accept or decline, or a
    `Commits:` line), with no word on what it costs (2026-10-30: a bare accept-or-decline got a yes to an evening
    three hours of travel away)."""
    roots = decay_sweep.declared(rituals.config(), workspace) or []
    open_items, bare = 0, []
    for plan in (folder / f"{day}.md" for folder, kind in roots if kind == "plans"):
        text = plan.read_text(encoding="utf-8", errors="replace") if plan.is_file() else ""
        for item in _items(text):
            title, options = MARK.sub("", item.splitlines()[0]).strip(), OPTION.findall(item)
            done = any(not NOTHING.fullmatch(m[1]) and not OPEN.match(m[1]) for m in CLOSED.finditer(item))  # it says what was decided
            if not options or done or title.lstrip("*_ ").startswith(("~~", "[x]", "[X]", "✓", "✔")) or "✅" in title:
                continue
            said = {"recommendation" if m[1].lower().startswith("recommend") else "consequences" if m[1].lower().startswith("consequence") else m[1].lower(): m[2]
                    for m in [*SAID.finditer(item), *TITLED.finditer(title)] if not NOTHING.fullmatch(m[2])}
            said.update({"recommendation": "on the option"} if any(re.search(r"(?i)(?<!not )\brecommended\b", option) for option in options) else {})
            needs = ["recommendation"] + ["consequences"] * ("commits" in said or any(map(COMMITS.search, options)))
            lacks = [word for word in needs if word not in said]
            open_items += 1
            bare += [f"  {plan.name}: {title}: lacks its {' and its '.join(lacks)}"] if lacks else []
    if bare:
        refuse(f"{len(bare)} choice(s) in today's plan are put to the principal unfinished, so this ritual is not recorded:\n"
               + "\n".join(bare) + "\nA choice put with no view is not neutral: it defaults to yes. Under each, write "
               "`**Consequences:**` (what each answer costs the principal: the time, the trip door to door, the money, when "
               "they are home, the sleep it leaves, what it collides with that day and the next morning) and "
               "`**Recommendation:**` (which you would take and why; say decline plainly when the costs outweigh the event).")
    return f"\nchoices: {open_items} open in today's plan, each with a recommendation" if roots else ""


def cmd_record(args) -> int:
    check_workspace(args.workspace, "record --direction <direction> --workspace <workspace> --date YYYY-MM-DD")
    try:
        date.fromisoformat(args.date)
    except ValueError:
        refuse(f"--date {args.date!r} is not YYYY-MM-DD; the logical workday is required and never inferred")
    if args.mode == "migration":
        refuse("mode 'migration' marks old bookkeeping and cannot be written")
    critical = (critical_deadlines(args.workspace, args.outcome) + travel(args.workspace, args.date, args.travel)
                + choices(args.workspace, args.date))
    record = {"ts": datetime.now().astimezone().isoformat(timespec="seconds"), "date": args.date,
              "direction": args.direction, "workspace": args.workspace, "mode": args.mode,
              "outcome": args.outcome}
    record.update({k: v for k, v in (("session", args.session), ("pointer", args.pointer),
                                     ("note", args.note)) if v})
    counts = {}
    for pair in args.count or []:
        key, sep, value = pair.partition("=")
        if not sep or not key:
            refuse(f"--count expects key=value, got {pair!r}")
        counts[key] = int(value) if value.lstrip("-").isdigit() else value
    if counts:
        record["counts"] = counts
    append(record)
    print(f"recorded {args.direction} {args.workspace} {args.date} ({args.outcome})\n{critical}")
    return 0


def row(records: list[dict], cfg: dict, workspace: str, today: date) -> dict:
    end, start = rituals.last(records, workspace), rituals.last(records, workspace, "day-start")
    review = rituals.last(records, workspace, "weekly-review")
    return {"last_day_end": {k: end[k] for k in ("date", "mode", "outcome") if k in end} if end else None,
            "last_day_start": {k: start[k] for k in ("date", "mode") if k in start} if start else None,
            "streak": rituals.streak(records, cfg, workspace, today),
            "last_weekly_review": review["date"] if review else None,
            "weekly_review_owed": rituals.weekly_owed(records, cfg, workspace, today),
            "quiet_days": rituals.quiet(records, cfg, workspace, today)}


def cmd_query(args) -> int:
    check_workspace(args.workspace, f"query {args.view} --workspace <workspace>")
    records, bad = rituals.read()
    try:
        cfg = rituals.config()
    except ValueError as exc:
        refuse(f"{exc}; refusing to guess")
    today = date.fromisoformat(args.today) if args.today else date.today()
    named = sorted({r["workspace"] for r in records if r.get("workspace") not in (None, "", "unknown")})
    workspace, inferred = args.workspace, False
    if args.view in ("streak", "weekly-review") and not workspace:
        if args.view == "streak" or len(named) != 1:
            refuse(f"query {args.view} needs --workspace: the log holds records for {len(named)} workspaces "
                   f"({', '.join(named) or 'none'}), so none can be assumed, and one workspace must not answer "
                   f"for another. Accepted form: query {args.view} --workspace <workspace>")
        workspace, inferred = named[0], True
    if args.view == "streak":
        out: dict = {"workspace": workspace, "streak": rituals.streak(records, cfg, workspace, today)}
    elif args.view == "weekly-review":
        review = rituals.last(records, workspace, "weekly-review")
        out = {"workspace": workspace, "last_weekly_review": review["date"] if review else None,
               "owed": rituals.weekly_owed(records, cfg, workspace, today)}
        out.update({"workspace_inferred": True} if inferred else {})
    else:
        out = {}
        if args.view in ("summary", "last"):
            out["workspaces"] = {w: row(records, cfg, w, today) for w in ([workspace] if workspace else named)}
        if args.view in ("summary", "open"):
            out["open_workdays"] = [{"workspace": w, "date": d}
                                    for w, d in rituals.open_days(records, today, workspace)]
        if args.view == "summary":
            moment = datetime.now().astimezone() if not args.today else datetime.combine(today, time(12)).astimezone()
            out["stale_mailboxes"] = [{"workspace": w, "address": a, "read_through": t or None}
                                      for w, a, t in rituals.stale_mailboxes(moment) if workspace in (None, w)]
    unnamed = sum(1 for r in records if r.get("workspace") in (None, "", "unknown"))
    out.update({k: v for k, v in (("records_without_workspace", unnamed), ("malformed_lines", bad)) if v})
    if args.json:
        print(json.dumps(out, indent=2, sort_keys=True))
        return 0
    for name, view in (out.get("workspaces") or {}).items():
        end, still = view["last_day_end"], view["quiet_days"]
        print(f"  {name:14} close {end['date'] if end else '—':10}  streak "
              f"{'n/a' if view['streak'] is None else view['streak']:<4}  weekly "
              f"{view['last_weekly_review'] or '—'}{'  OWED' if view['weekly_review_owed'] else ''}"
              f"{'' if still is None else f'  QUIET {still} days (worked occasionally)'}")
    for item in out.get("open_workdays", []):
        print(f"  OPEN  {item['workspace']:14} {item['date']} (started, never closed)")
    for item in out.get("stale_mailboxes", []):
        print(f"  MAIL  {item['workspace']:14} {item['address']} read through {item['read_through'] or 'never'}"
              " (past its sweep cadence; run that workspace's ritual)")
    if "last_weekly_review" in out:
        print(f"  last weekly review ({workspace}): {out['last_weekly_review'] or '—'}"
              f"{'  OWED' if out['owed'] else ''}{'  (the only workspace in the log)' if inferred else ''}")
    if "streak" in out:
        print(f"  streak ({workspace}): {'n/a' if out['streak'] is None else out['streak']}")
    if unnamed:
        print(f"  {unnamed} record(s) name no workspace (written before records were stamped); "
              "every view leaves them out")
    if bad:
        print(f"  {bad} malformed line(s) in the log")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--state-dir", help="read and write another log directory")
    sub = parser.add_subparsers(dest="command", required=True)
    rec = sub.add_parser("record", help="append one ritual record")
    rec.add_argument("--direction", required=True, choices=DIRECTIONS)
    rec.add_argument("--workspace", required=True)
    rec.add_argument("--date", required=True, help="the logical workday, YYYY-MM-DD")
    rec.add_argument("--mode", default="full")
    rec.add_argument("--outcome", default="clean", choices=OUTCOMES)
    rec.add_argument("--session")
    rec.add_argument("--pointer", help="the session log that holds the narrative")
    rec.add_argument("--note")
    rec.add_argument("--count", action="append", metavar="KEY=VALUE")
    rec.add_argument("--travel", help="the output of travel_check.py --json, for a workspace that checks travel")
    rec.set_defaults(fn=cmd_record)
    query = sub.add_parser("query", help="derive a view")
    query.add_argument("view", choices=VIEWS)
    query.add_argument("--workspace")
    query.add_argument("--today", help="YYYY-MM-DD, to ask about another day")
    query.add_argument("--json", action="store_true")
    query.set_defaults(fn=cmd_query)
    args = parser.parse_args(argv)
    if args.state_dir:
        os.environ["RITUAL_STATE_DIR"] = args.state_dir
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
