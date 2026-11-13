#!/usr/bin/env python3
"""Record and query daily-ritual state: one append-only log, every view per workspace.

There is no mutable state file. On 2026-09-02 one seat's close overwrote
another's single `last_day_end` slot; a lock would not have helped, because the
second writer still replaces the slot. So records are appended and every view
is derived. Each record carries two clocks: `date`, the logical workday opened
or closed (required, never inferred, never a day ahead: a close written at 01:30
belongs to the day before), and `ts`, when it was written. On 2026-09-14 an unscoped weekly
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
For a workspace that turns prompt reconciliation on (`"prompt_reconcile": {"records": ["<folder>"]}`,
with `"from": "YYYY-MM-DD"` for the first day it applies) a day-end record runs
`synthesis sessions prompts` itself over that day and those folders: a clean outcome is refused while
a prompt the principal typed that day is cited by no record, a partial one says how many are open, and
nothing is recorded when the listing cannot be made (2026-11-11: what he asked reached a record only
if an agent remembered). Only a missing key or `false` turns it off: any other value that is not that
setting is refused, and so is a first day that is not a day.

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
import shutil
import subprocess
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


def _is_day(text) -> bool:
    """Whether text is one day written YYYY-MM-DD: Python 3.11 and later also read 20261112 and 2026-W46-4 as dates."""
    try:
        return bool(re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", text)) and bool(date.fromisoformat(text))
    except (TypeError, ValueError):
        return False


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


def prompts(workspace: str, day: str, direction: str, outcome: str) -> str:
    """The line a day-end prints about what the principal typed that day, or a refusal: the listing cannot be made,
    it answers for another workspace, day or set of folders or at odds with itself, or the close is clean while a
    prompt is cited by no record (2026-11-11: what he asked reached a record only if an agent remembered). The
    record lists the prompts itself: a result made earlier, or against other folders, says nothing about now
    (2026-11-12, a review)."""
    wanted = rituals.settings(rituals.config(), workspace).get("prompt_reconcile", False)
    if wanted is False or direction != "day-end":  # off by a missing key or `false` alone: null and 0 closed a day unchecked
        return ""
    roots = wanted.get("records") if isinstance(wanted, dict) else None
    where = f'{rituals.state_dir() / "config.json"}, under workspaces.{workspace}'
    if not (isinstance(roots, list) and roots and all(isinstance(r, str) and r for r in roots)):
        refuse(f"{workspace} sets prompt_reconcile to {json.dumps(wanted)[:80]}, which names no folder of records: the check can "
               f'neither run nor count as off, so this ritual is not recorded. In {where}, write "prompt_reconcile": '
               '{"records": ["<folder of project records>"]}; only false, or no key at all, turns the check off')
    since = wanted.get("from", "")
    if "from" in wanted and not _is_day(since):  # compared as text, `tomorrow` or a number put every day before it
        refuse(f'{workspace} starts prompt_reconcile "from" {json.dumps(since)[:80]}, which is not a day written YYYY-MM-DD, so no '
               f'day can be told to come before it and this ritual is not recorded. In {where}, write "from": "YYYY-MM-DD", '
               "or leave it out")
    if day < since:  # a session exported before the workspace turned this on keeps the kinds its records were given
        return f"\nprompts: checked from {since}"
    tool, again = shutil.which("synthesis"), f"synthesis sessions prompts --workspace {workspace} --date {day} " + " ".join(
        f"--records {r}" for r in roots)
    if not tool:
        refuse(f"{workspace} checks that what the principal asked reached a record, and the `synthesis` command is not on "
               f"the PATH to list it. Nothing is recorded until `{again}` can run")
    done = subprocess.run([tool, "sessions", "prompts", "--workspace", workspace, "--date", day,
                           *[word for r in roots for word in ("--records", r)], "--json"], capture_output=True, text=True)
    if done.returncode not in (0, 1):
        refuse(f"what the principal typed on {day} could not be listed, so nothing is recorded: "
               f"{(done.stderr or done.stdout).strip()[:400]}\nRun `{again}` to see it")
    try:
        found = json.loads(done.stdout)
        total, left = found["prompts"], found["open"]
        sound = (type(total) is int and isinstance(left, list) and all(isinstance(c, str) and c for c in left)
                 and len(set(left)) == len(left) <= total and done.returncode == (1 if left else 0))
        answered = (found["workspace"], found["date"], found["records"])
    except (ValueError, KeyError, TypeError) as exc:
        refuse(f"the listing of {day}'s prompts cannot be read ({exc!r}); run `{again} --json` to see it")
    if not sound:  # 2026-11-12: an exit of 1 with `prompts: 1, open: []` was taken as a clean day
        refuse(f"the listing of {day}'s prompts does not agree with itself: it exits 1 exactly while it lists a prompt open, "
               f"lists no more than were typed and each once, and this answer exited {done.returncode} (or a field has another "
               f"shape), so nothing is recorded; run `{again} --json` to see it")
    read = [os.path.realpath(os.path.expanduser(r)) for r in roots]  # each as the listing's walk reads it and its answer names it: links followed
    if answered != (workspace, day, read):
        refuse(f"the listing answered for {answered[0]} on {answered[1]} against {answered[2]}, and this record is for {workspace} on "
               f"{day} against {read}. Run `{again}`")
    if left and outcome in CLEAN:
        refuse(f"{len(left)} of {total} prompts typed on {day} {'is' if len(left) == 1 else 'are'} cited by no record, so "
               f"outcome {outcome!r} would claim nothing was lost:\n" + "\n".join(f"  {c}" for c in left[:40])
               + ("\n  ..." if len(left) > 40 else "")
               + "\nRead each with `synthesis sessions show <session> --seq <n>`. Where its substance is in a record, "
               "cite it in the sentence that says so (`<harness> <session> #<seq>`, or `#<first>-<last>` for a stretch one "
               "entry covers; an entry of citations alone counts for nothing, and a JSON or YAML record holds them in a "
               "field named `cites`); where it is not, write the record first. A citation says its record accounts for "
               "the prompt, so do not copy this list into one. Or "
               "record --outcome partial, which says the day left some open.")
    if not total:
        return f"\nprompts: none typed on {day}"
    return (f"\nprompts: all {total} typed on {day} are cited by a record" if not left else
            f"\nprompts: {len(left)} of {total} typed on {day} {'is' if len(left) == 1 else 'are'} cited by no record")


# A line of an item: plain, bold or italic, quoted, a list entry or a task-list box, a heading or a row of a table,
# in any order and however deep (`- > **Option A:**` is a quote inside a list entry).
ITEM = r"(?im)^ *(?:> *|\| *|#{1,6} +|(?:[-*+]|\d+[.)]) +(?:\[[ xX]\] +)?)*[*_]*"
LED = r"(?:[^\w\s*_>|#+.\[\]()\"'`~:-]{1,3}\s*[*_]*)?"  # a pin, a pointing hand or a tick before the word
# An option's label ends at the mark that closes its emphasis, or at a colon, a dash, a bracket, a full stop or the
# end of the line: `Option A was fine last time` is a sentence.
OPTION = re.compile(ITEM + r"Option [A-Z0-9]+(?![A-Za-z0-9])((?:[*_]+|\s*(?:$|[:\-–—().|])).*)$")
SAID = re.compile(ITEM + LED + r"(?:(?:My|Our|The) +)?(Recommend(?:ation|ed)s?|Consequences?|Commits)[*_]*\s*(?::|[-–—](?=[*_\s]))[*_\s]*(.*)$")
CLOSED = re.compile(ITEM + LED + r"(?:Decided|Decision|Resolved|Released|Lapsed|Withdrawn)[*_]*\s*:[*_\s]*(.*)$")
# A line that says nothing yet, as a decision or as a recommendation: a word that puts it off, however the line goes
# on, or one of three that are also the first word of a sentence that says something, when little follows.
OPEN = re.compile(r"(?i)\W*(?:pending|undecided|unknown|unsure|awaiting|not yet|to be |\?|(?:open|waiting|needed)\b(?:\W+\w+){0,3}\W*$)")
# What Markdown does not show as the plan's own text: a fenced block (quoted or not, closed or not), which is an
# example, and an HTML comment. Whichever opens first runs to its own end: a fence closes at a line of its own
# mark alone, at least as long as the one that opened it, so four backticks hold a sample fenced with three.
FENCE = re.compile(r"(?ms)^\s*(?:>\s*|(?:[-*+]|\d+[.)])\s+)*(?P<fence>(?P<mark>[`~])(?P=mark){2,}).*?(?:^\s*(?:>\s*)*(?P=fence)(?P=mark)*[ \t]*$|\Z)"
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
            elif label is not None and HEAD.match(line) and not (SAID.match(line) or CLOSED.match(line)):
                fresh = True  # a deeper heading or a bold title after a choice's options: what follows is another choice
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
            if above is not None and not depth(above) and not (ENTRY.match(lines[above]) or HEAD.match(lines[above])):
                # a sentence between a title and its options: the title is the nearest heading or bold line above it
                for j in range(above - 1, floor - 1, -1):
                    if HEAD.match(lines[j]) and not (SAID.match(lines[j]) or CLOSED.match(lines[j])):
                        above = j
                    if HEAD.match(lines[j]) or OPTION.match(lines[j]) or ENTRY.match(lines[j]):
                        break
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
                    for m in [*SAID.finditer(item), *TITLED.finditer(title)] if not NOTHING.fullmatch(m[2]) and not OPEN.match(m[2])}
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
    if not _is_day(args.date):  # 20261111 or 2026-W46-3, a date to Python 3.11, names no day a listing or a view finds
        refuse(f"--date {args.date!r} is not YYYY-MM-DD; the logical workday is required and never inferred")
    now, review = today(), args.direction == "weekly-review"
    early = rituals.friday(now + timedelta(days=6)).isoformat()  # the Friday a weekly review done before it satisfies
    if args.date > now.isoformat() and not (review and args.date == early):  # 2026-11-12: tomorrow closed clean, `prompts: none typed`
        refuse(f"--date {args.date} has not come: today is {now}. A ritual is recorded for the workday it opened or closed, and "
               "nothing has been typed, planned or decided on a day ahead, so every check would pass over nothing. Record it on "
               "that day" + (f". A weekly review done early takes the Friday it satisfies, {early}, and no other day ahead" * review))
    if args.mode == "migration":
        refuse("mode 'migration' marks old bookkeeping and cannot be written")
    critical = (critical_deadlines(args.workspace, args.outcome) + travel(args.workspace, args.date, args.travel)
                + choices(args.workspace, args.date) + prompts(args.workspace, args.date, args.direction, args.outcome))
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
