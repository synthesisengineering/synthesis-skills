#!/usr/bin/env python3
"""Read declared dated plans and report due obligations without making decisions.

No lookback cutoff, state writes, network access or inferred title-based identity.
Exit 2 means incomplete/ambiguous evidence; exit 0 means collection succeeded.
The REVIEW result still requires a grounded human decision for each due item.

An item tagged `**Critical:** <class>` is a deadline whose miss cannot be undone. It is reported
apart from the dated list (`critical`), leads from seven days out, is due an alert three days
and one day out, on its day and after, never lapses, and closes only when a closing mark comes
with an `**Evidence:**` line (2026-11-06: an enrollment window closed as one dated row among a
hundred). `--alert` posts one banner and spoken line with a count and no title.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
from datetime import date, timedelta
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

sys.dont_write_bytecode = True  # an installed plugin must stay byte-identical; Muse verifies its bundle
for _root in (Path(__file__).resolve().parents[3], Path(os.environ.get("SYNTHESIS_HOME") or Path.home() / ".synthesis" / "v5") / "current"):
    if (_root / "synthesis" / "rituals.py").is_file():
        sys.path.insert(0, str(_root))
        break
try:
    from synthesis import rituals  # noqa: E402
except ImportError as exc:  # no runtime beside this copy; one that fails otherwise as it loads keeps its traceback
    print(f"{__file__} needs the synthesis runtime, which cannot be imported ({exc}), so nothing ran. Run it from the "
          "installed synthesis-skills plugin or a checkout of it", file=sys.stderr)
    sys.exit(2)

DATE = r"\d{4}-\d{2}-\d{2}"
PLAN = re.compile(rf"^({DATE})\.md$")
ARTIFACT = re.compile(rf"^({DATE})-(day-start|midday|day-end)\.md$")
RECORD = re.compile(rf"^({DATE})(?!\d)")  # a record named with a leading date speaks as of that day; any other as of the sweep's
MIDDAY_RUN = re.compile(rf"^({DATE})-midday-([2-9]|[1-9][0-9]{{1,2}})\.md$")  # a later mid-day run that day (2026-10-31)
FIELD = re.compile(r"\*\*(Decays|Decay ID|Sent|Released|Resolved|Critical|Calendar|Evidence|Lapsed):\*\*\s*(.*)", re.I)
HEADING = re.compile(r"^\s{0,3}#{1,6}\s+(.+)")
LIST = re.compile(r"^(\s*)(?:[-*+] |\d+[.)] )(.*)")
ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
RUN_ORDER = {"day-start": 0, "midday": 1, "day-end": 2}
LEAD_DAYS, ALERT_DAYS = 7, (3, 1, 0)  # a critical item leads from a week out; alerts three days and one day out and on its day
WORDS = ("enrollment", "insurance", "tax(?:es)?", "patent", "visa", "passport", "immigration", "payroll", "FSA", "HSA")
DONE = re.compile(r"(?:\[[xX]\]\s|~~.+~~|✅|(?:DONE|SENT)\b)")  # a title that closes its own dated item
# A commitment's entry is closed where a mark stands as its status. At its start: a tick box, a tick, DONE or SENT
# in capitals with no question mark after the word, or its whole title struck (what follows the strike is nothing,
# or opens with a mark and not a word: `~~Tuesday~~ Thursday: send it` is open). At its end: a tick, alone or
# before DONE or SENT and a time; or done or sent after a dash or a colon, alone or before a time. A tick or a word
# inside a sentence closes nothing (the reviews: read at the title's start alone, `**Call** ✅ DONE 10:00` was
# listed as open; read anywhere, `Ship it (staging ✅, prod pending)` was closed, and so was `Deploy (✅ DONE for
# staging; prod still pending)` while `✅ DONE` could be followed by anything).
CLOSED_ENTRY = re.compile(r"^[*_\s]*(?:\[[xX]\]\s|~~.+?~~[*_\s]*(?:$|[^\w\s*_])|[✅✓✔☑]|(?:DONE|SENT)\b(?!\s*\?))"
                          r"|[✅✓✔☑]\uFE0F?[*_\s]*(?:(?:DONE|SENT)\b[*_\s]*(?:\d{1,2}:\d{2}\S*)?[*_\s.)]*)?$"
                          r"|(?:—|–|-|:)\s*[*_]*(?i:done|sent)\b(?!\s*\?)[*_\s]*(?:\d{1,2}:\d{2}.*)?$")
# A table's cell that says its row is done (a strike is the whole cell's), and a header that names such a column.
STATUS_CELL = re.compile(r"[*_\s]*(?:\[[xX]\]|~~.+~~[*_\s]*$|[✅✓✔☑]|(?:DONE|SENT)\b(?!\s*\?))")
STATUS_HEAD = re.compile(r"(?i)\b(?:status|state|done|sent|closed|outcome|result|shipped|completed?|finished)\b|[✅✓✔☑]")
RELEASED = re.compile(rf"\*\*Decays:\*\*\s*~~{DATE}~~\s*\(?\s*\w")  # a struck date with its reason: let go
# The headings under which the plan format keeps commitments: the task section and its synonyms, what is waited on,
# what is carried (`This Week` only as a heading's whole text: `Meetings this week` is another thing). A heading
# that opens with the name of another kind of section says nothing by itself (`Draft A: to someone who is
# waiting`); one whose task word is only qualified by such a name is read (`Tasks from the sync`). A heading of
# things finished holds none: it says completed, done, sent, closed, finished or shipped, and has no word that
# says the thing is still to come (`Not done yet`, `Sent, awaiting reply`).
COMMIT = re.compile(r"(?i)\btasks?\b|action items?|\bto[- ]?dos?\b|follow-?ups?|priorities|still to do|pending (?:this|from)"
                    r"|waiting|delegated|carried|carry[- ](?:forward|over)|^\W*this week\W*$")
OTHER = re.compile(r"(?i)\W*(?:calendar|drafts?|unsent|standup|decisions?|open ask|sync|things to know|what happened|what changed|prs?\b|bugs)")
FINISHED = re.compile(r"(?i)\b(?:completed|done|closed|finished|shipped|sent(?!\s+from\b))\b")  # `sent from my phone` says nothing
# What is still to come: a word that says so anywhere, or `to` or `get` before the finishing word (`Tasks to get
# done`; `Sent to the team` is a heading of things sent).
UNFINISHED = re.compile(r"(?i)\b(?:not|yet|still|awaiting|waiting|pending|must|needs?|should)\b"
                        r"|\b(?:to|gets?|getting)\b.*\b(?:completed|done|sent|closed|finished|shipped)\b")
# A ledger's status that takes its closing word back, or says the thing is partly done, is open.
UNDONE = re.compile(r"(?i)\b(?:not|yet|still|awaiting|waiting|pending|but|reopened|partly|partial(?:ly)?|in part)\b")
PARKED = re.compile(r"(?i)\bparked\s*\(\s*[^)\s][^)]*\)|\*\*Parked:\*\*\s*\S")  # a park says why
# A ledger's status that opens with one of these, as a word or a phrase, is closed; a seat's own are added to them.
LEDGER_CLOSED = ("SENT", "SUPERSEDED", "DECAYED", "CLOSED", "RELEASED", "RESOLVED", "LAPSED", "DONE", "ANSWERED", "REPLIED")
TICK = re.compile(r"(?:✅|✔|✓|☑|\[[xX]\]|:white_check_mark:)")  # a ledger status that opens with one is closed
OWED_DAYS = 14  # the weekly review's window


def iso_day(value: str) -> date:
    if not re.fullmatch(DATE, value):
        raise ValueError("expected YYYY-MM-DD")
    return date.fromisoformat(value)


def gap(report: dict, path, reason: str, line: int | None = None) -> None:
    entry = {"path": str(path), "reason": reason}
    if line is not None:
        entry["line"] = line
    report["gaps"].append(entry)


def operative_lines(text: str, errors: list[str]):
    """Keep source line numbers; omit fenced examples, quotes and frontmatter."""
    fence = None
    frontmatter = text.splitlines()[:1] == ["---"]
    for number, line in enumerate(text.splitlines(), 1):
        if frontmatter:
            if number > 1 and line.strip() == "---":
                frontmatter = False
            continue
        # A fence may open on the line of a list mark (`- ```md`); the line that closes it stands as far in as the entry's text.
        marker = re.match(r"^\s*(`{3,}|~{3,})(.*)$" if fence else r"^\s{0,3}(?:(?:[-*+]|\d+[.)])\s+)*(`{3,}|~{3,})(.*)$", line)
        if fence:
            if marker and marker[1][0] == fence[0] and len(marker[1]) >= len(fence) and not marker[2].strip():
                fence = None
            continue
        if marker:
            fence = marker[1]
            continue
        if line.lstrip().startswith(">"):
            continue
        # Inline grammar examples are prose, not executable plan metadata.
        yield number, re.sub(r"(`+)(.+?)\1", "", line)
    if fence or frontmatter:
        errors.append("unterminated fence or frontmatter; operative item coverage is incomplete")


def item_blocks(text: str, errors: list[str]):
    block = []
    list_indent = None
    for number, line in operative_lines(text, errors):
        heading = HEADING.match(line)
        listed = LIST.match(line)
        metadata = FIELD.match(line.strip().removeprefix("- "))
        boundary = heading or (listed and not metadata and (list_indent is None or len(listed[1]) <= list_indent))
        if boundary and block:
            yield block
            block = []
        if heading:
            list_indent = None
        elif boundary and listed:
            list_indent = len(listed[1])
        block.append((number, line))
    if block:
        yield block


def parse_plan(path: Path, day: date, rank: int, as_of: date, report: dict) -> list[dict]:
    try:
        before = path.stat()
        text = path.read_text(encoding="utf-8")
        after = path.stat()
    except (OSError, UnicodeError) as exc:
        gap(report, path, f"unreadable source: {exc}")
        return []
    report["scanned"].append(str(path))
    if (before.st_size, before.st_mtime_ns, before.st_ino) != (after.st_size, after.st_mtime_ns, after.st_ino):
        gap(report, path, "source changed during read; rerun collection")
    entries = []
    errors = []
    for block in item_blocks(text, errors):
        prior_gaps = len(report["gaps"])
        fields = defaultdict(list)
        for number, line in block:
            match = FIELD.search(line)
            if match:
                fields[match[1].lower()].append((number, match[2].strip()))
        if not fields.get("decays") and not fields.get("decay id") and not fields.get("critical"):
            continue
        klass = next((value for _, value in fields["critical"] if value), "")
        evidence = next((value for _, value in fields["evidence"] if value), "")
        first_number, first_line = next(((n, l) for n, l in block if l.strip()), block[0])
        title = re.sub(r"^\s*(?:#{1,6}\s+|[-*+]\s+|\d+[.)]\s+)", "", first_line).strip()
        explicit_id = None
        if fields.get("decay id"):
            values = fields["decay id"]
            if len(values) != 1 or not ID.fullmatch(values[0][1]):
                gap(report, path, "invalid or multiple Decay ID fields", values[0][0])
            else:
                explicit_id = values[0][1]
        due = None
        reason = ""
        struck_release = False
        source_line = fields["decays"][0][0] if fields["decays"] else first_number
        if len(fields["decays"]) > 1:
            gap(report, path, "multiple Decays fields in one item; separate the items", source_line)
        for number, value in fields["decays"]:
            struck = re.match(rf"^~~({DATE})~~(?:\s+(.*))?$", value)
            if struck:
                value = struck[1] + " " + (struck[2] or "")
                if (struck[2] or "").strip(" ()"):
                    struck_release = True
                else:
                    gap(report, path, "struck deadline requires a release reason", number)
            parts = value.split(maxsplit=1)
            try:
                parsed = iso_day(parts[0] if parts else "")
            except ValueError:
                gap(report, path, "invalid Decays date", number)
                continue
            # Ambiguous multiple tags must never drop their earliest due date.
            if due is None or parsed < due:
                due = parsed
                reason = parts[1] if len(parts) > 1 else ""
        closed = struck_release or bool(DONE.match(title))
        # the day each Lapsed mark speaks of: the first date it gives, or its plan's own day; one dated ahead speaks of none
        marks = [(number, (re.search(DATE, value) or [day.isoformat()])[0]) for number, value in fields["lapsed"]]
        for number, stamp in marks:
            if stamp > as_of.isoformat():
                gap(report, path, "a Lapsed mark is dated ahead of the sweep's day", number)
        lapsed_on = max((stamp for _, stamp in marks if stamp <= as_of.isoformat()), default="")
        for name in ("sent", "released", "resolved"):
            for number, value in fields[name]:
                try:
                    token = value.removeprefix("✅").strip().split()[0]
                    closed_day = iso_day(token[:10])
                    if len(token) > 10:
                        from datetime import datetime
                        datetime.fromisoformat(token.replace("Z", "+00:00"))
                    if closed_day > as_of:
                        raise ValueError("future resolution")
                except (ValueError, IndexError):
                    gap(report, path, f"invalid or future {name} timestamp", number)
                else:
                    closed = True
        if due is None and not closed:
            gap(report, path, "a Critical item needs a valid Decays date" if klass else
                "identified item has no valid Decays date or resolution", source_line)
        entries.append({
            "identity": f"id:{explicit_id}" if explicit_id else f"source:{path}:{source_line}",
            "title": title, "due_date": due.isoformat() if due else None,
            "reason": reason, "closed": closed, "path": str(path), "line": source_line,
            "plan_date": day.isoformat(), "run_rank": rank, "invalid": len(report["gaps"]) > prior_gaps,
            "critical": "" if re.match(r"no\b", klass, re.I) else klass, "not_critical": bool(re.match(r"no\b", klass, re.I)),
            "evidence": evidence, "calendar": next((value for _, value in fields["calendar"] if value), ""),
            "lapsed": bool(fields["lapsed"]),
            "lapsed_on": lapsed_on,
        })
    for error in errors:
        gap(report, path, error)
    return entries


def _holds(heading: str):
    """True where a heading's own words place commitments under it, False where they place finished things, None
    where they say neither: it opens with the name of another kind of section (a calendar, a draft to someone who
    is waiting), or has none of these words."""
    if FINISHED.search(heading) and not UNFINISHED.search(heading):
        return False
    return True if COMMIT.search(heading) and not OTHER.match(heading) else None


def _cells(line: str) -> list[str]:
    """One table row's cells: the pipe at each end is the row's own, an escaped pipe is text, and an empty last cell
    is a cell."""
    body = line.strip()
    body = body[1:] if body.startswith("|") else body
    body = body[:-1] if body.endswith("|") and not body.endswith("\\|") else body
    return [cell.strip() for cell in re.split(r"(?<!\\)\|", body)]


def _closing_line(line: str) -> bool:
    """A Sent, Released or Resolved line that gives its day: `**Resolved:** not yet` closes nothing."""
    found = FIELD.search(line)
    return bool(found and found[1].lower() in ("sent", "released", "resolved") and re.match(rf"(?:✅\s*)?{DATE}", found[2].strip()))


def commitments(path: Path) -> list[dict]:
    """The open commitments of one plan: each top-level list entry, and each row of a table that stands directly
    under its heading, beneath a heading of the second level or deeper which the plan format places among tasks,
    things waited on or things carried. The nearest enclosing heading that says either way decides: a bucket under
    the task section is read unless its own words say finished, a heading of things finished holds none wherever it
    stands, and the plan's own title places nothing. An entry is closed, and not read, where a mark closes it as
    its status (not as a word in a sentence), or a Sent, Released or Resolved line with its day, or a struck date
    with its reason, stands in its block. `bare` is true where an open entry's block carries no Decays date and no
    park that says why; a table's row can carry a park and no date (2026-11-13, counted on three seats' newest
    plans: 12, 0 and 11 such entries, none a task box)."""
    text = path.read_text(encoding="utf-8")
    raw, rows, chain, section = text.splitlines(), [], {}, ""

    def held() -> bool:
        return bool(next((chain[level] for level in sorted(chain, reverse=True) if chain[level] is not None), False))

    def row(title: str, number: int, body: str, dated: bool, closed: bool) -> None:
        if not (closed or CLOSED_ENTRY.search(title) or RELEASED.search(body)):
            rows.append({"title": title, "path": str(path), "line": number, "section": section,
                         "bare": not (dated or PARKED.search(body))})
    for block in item_blocks(text, []):
        number, first = next(((n, line) for n, line in block if line.strip()), block[0])
        heading = HEADING.match(first)
        if heading:
            level = len(first.lstrip()) - len(first.lstrip().lstrip("#"))
            chain = {k: v for k, v in chain.items() if k < level}
            chain[level], section, table, head = (None if level < 2 else _holds(heading[1])), heading[1].strip(), 0, []
            for at, line in block[1:] if held() else ():  # a table directly under the heading: each row after its rule is an entry
                table = table + 1 if line.strip().startswith("|") else 0
                cells = _cells(raw[at - 1]) if table else []
                head = cells if table == 1 else head
                # its first cell that says what it is: not a number, and not a time
                named = [cell for cell in cells if cell and not re.fullmatch(r"[#\d.]+|\d{1,2}:\d{2}\S*", cell)]
                # Under a heading that only stands in the task section, a row that opens with a clock time is a
                # schedule's line; under one whose own words place tasks, it is a task with its time.
                timed = chain[level] is None and re.match(r"\d{1,2}:\d{2}", cells[0]) if cells else False
                if table > 1 and named and cells != head and not timed and not all(re.fullmatch(r":?-*:?", cell) for cell in cells):
                    # the row's status: the cell under a header that names one, or the last cell where none does
                    states = [cells[i] for i, name in enumerate(head) if STATUS_HEAD.search(name) and 0 < i < len(cells)] or cells[-1:]
                    row(named[0], at, raw[at - 1], False, _closing_line(raw[at - 1]) or any(STATUS_CELL.match(cell) for cell in states if cell is not named[0]))
        elif LIST.match(first) and held():
            fields = {match[1].lower() for _, line in block for match in [FIELD.search(line)] if match}
            row(re.sub(r"^\s*(?:[-*+]\s+|\d+[.)]\s+)", "", raw[number - 1]).strip(), number, "\n".join(line for _, line in block),
                "decays" in fields, any(_closing_line(line) for _, line in block))
    return rows


def _status(cell: str, closed: tuple) -> tuple[bool, str]:
    """(whether a ledger's status says the row is finished, its first word): with anything struck through set
    aside and a link read as its words, it opens with a tick, or with a closing word or phrase that no question mark
    follows, and no word after takes that back (`Paid in part`, `Done, but reopened`, `✔ waiting on them`). A tick
    at its end closes nothing by itself: `In review ✅` is open, `Replied ✅` is closed by its word."""
    text = re.sub(r"[*`]", "", re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", re.sub(r"~~.*?~~", "", cell))).strip()
    lead = re.sub(r"^[^\w\[:]+", "", text)
    word = re.match(r"[A-Za-z][\w/'-]*", lead)
    said = next((phrase for phrase in closed if lead.upper().startswith(phrase) and not re.match(r"[\w-]", lead[len(phrase):])), None)
    done = said is not None and not re.match(r"\s*\?", lead[len(said):])
    rest = lead[len(said):] if said is not None else text  # a seat's own phrase may hold such a word itself (`Not needed`)
    return bool((TICK.match(text) or done) and not UNDONE.search(rest)), (word[0].upper() if word else "")


def ledger_rows(path: Path, as_of: date, closed: tuple) -> tuple[list[dict], int]:
    """(the open rows, the rows that could not be read) of each table in a record whose header has a `Status` cell
    and an `Owed since` cell: a correspondence ledger, each of its lines opening with a pipe. A row is closed by
    its status (`_status`); every other status, an empty one included, is open, since a status the reader does not
    know is not read as finished. A row with too few cells for those columns or for its item's is counted as not
    read, and the header written again is passed over."""
    text = path.read_text(encoding="utf-8")
    raw, rows, unread, head, names, last = text.splitlines(), [], 0, None, [], 0
    for number, _ in operative_lines(text, []):  # outside fences, quotes and frontmatter; the line itself keeps its code spans
        line = raw[number - 1].strip()
        if number != last + 1 or not line.startswith("|"):
            head = None
        last = number
        if not line.startswith("|"):
            continue
        cells = _cells(line)
        named = [re.sub(r"[*_`]", "", cell).strip().lower() for cell in cells]
        if head is None:  # a table's first row is its header
            names = named
            head = (named.index("status"), named.index("owed since"), named.index("item") if "item" in named else 0) if {
                "status", "owed since"} <= set(named) else False
        elif head and named != names and not all(re.fullmatch(r":?-*:?", cell) for cell in cells):  # not the rule under the header
            if len(cells) <= max(head):
                unread += 1
                continue
            done, word = _status(cells[head[0]], closed)
            if done:
                continue
            since = re.search(DATE, cells[head[1]])
            try:
                since = iso_day(since[0]) if since else None
            except ValueError:
                since = None
            rows.append({"item": re.sub(r"[*`~]", "", cells[head[2]]).strip(), "status": word, "path": str(path), "line": number,
                         "owed_since": since.isoformat() if since else None, "days": (as_of - since).days if since else None})
    return rows, unread


def declared(cfg: dict, workspace: str):
    """The plan and artifact folders a workspace declares in the ritual config, with any folders of other records
    (drafts, a ledger) whose items it wants swept; None when it declares neither plans nor artifacts."""
    conf = rituals.settings(cfg, workspace)
    if "plans_dirs" not in conf and "artifacts_dirs" not in conf:
        return None
    kinds = ("plans", "artifacts", "records")
    if not all(isinstance(p, str) for kind in kinds for p in conf.get(f"{kind}_dirs") or []):
        raise ValueError(f"ritual config: plans_dirs, artifacts_dirs and records_dirs of {workspace} must be lists of folders")
    return [(Path(p), kind) for kind in kinds for p in conf.get(f"{kind}_dirs") or []]


def alert_today(due: date, as_of: date, working) -> bool:
    """Three days out, one day out, on the day and after; an alert day off moves to the last working day before it."""
    if due < as_of:
        return True
    for days in ALERT_DAYS:
        day = due - timedelta(days=days)
        if day == as_of:
            return True
        for _ in range(14):
            if working(day):
                break
            day -= timedelta(days=1)
        if day == as_of:
            return True
    return False


def _tool(tool: str, *args: str) -> str:
    path = shutil.which(tool)
    return "unavailable" if not path else "" if subprocess.run([path, *args], capture_output=True).returncode == 0 else "failed"


def alert(count: int) -> dict:
    """One banner and one spoken line: a count and a pointer, never a title. The mute flag silences the audio only."""
    if not count:
        return {"count": 0}
    text = f"{count} critical deadline{'' if count == 1 else 's'} closing soon or past due. Details are in your day plan."
    banner = _tool("osascript", "-e", f'display notification "{text}" with title "Synthesis"') or "posted"
    muted = (Path.home() / ".synthesis" / "quiet-audio").exists()
    return {"count": count, "banner": banner, "audio": "suppressed (mute flag)" if muted else _tool("say", text) or "played"}


def passed(count: int) -> dict:
    """One banner for dated items whose date passed with nothing written: a count and a pointer, never a title, and
    no spoken line (these are ordinary items; a deadline whose miss cannot be undone has the alert above)."""
    if not count:
        return {"count": 0}
    text = (f"{count} dated item{' passed its' if count == 1 else 's passed their'} date with nothing written. "
            "Details are in your day plan.")
    return {"count": count, "banner": _tool("osascript", "-e", f'display notification "{text}" with title "Synthesis"') or "posted"}


def critical_row(identity: str, history: list, settled: bool, as_of: date, working, report: dict):
    """("closed", row) once a closing mark carries evidence; otherwise ("open", row) with what is wrong with it."""
    latest = history[-1]
    row = {"identity": identity, "title": latest["title"], "path": latest["path"], "line": latest["line"],
           "class": next(e["critical"] for e in reversed(history) if e["critical"])}
    dates = [e["due_date"] for e in history if e["due_date"]]
    if settled and latest["closed"] and latest["evidence"]:
        return "closed", {**row, "due_date": dates[-1] if dates else None, "evidence": latest["evidence"], "closed_in": latest["plan_date"]}
    if not dates:
        if not latest["invalid"]:
            gap(report, latest["path"], "a Critical item needs a valid Decays date", latest["line"])
        return "open", None
    due = date.fromisoformat(dates[-1] if settled else min(dates))  # an unsettled history keeps its earliest date
    calendar = next((e["calendar"] for e in reversed(history) if e["calendar"]), "")
    problems = [text for wrong, text in (
        (identity.startswith("source:"), "no Decay ID line: a carried copy cannot be matched to this item"),
        (not calendar, "no Calendar line: nothing shows its closing date is on the calendar"),
        (latest["closed"] and not latest["evidence"], "marked closed with no Evidence line: it stays open"),
        (any(e["lapsed"] for e in history), "marked Lapsed: a critical item cannot lapse; it stays open until evidence or "
                                            "the principal's own words close it")) if wrong]
    left = (due - as_of).days
    return "open", {**row, "due_date": due.isoformat(), "days_left": left, "lead": left <= LEAD_DAYS, "past_due": left < 0,
                    "alert": alert_today(due, as_of, working), "calendar": calendar, "problems": problems,
                    "redated_from": sorted(set(dates) - {due.isoformat()})}


def collect(roots: list[tuple[Path, str]], as_of: date, workspace: str | None = None, plan_day: date | None = None) -> dict:
    """The sweep's report as of a day. `plan_day`, where it is earlier, is the day whose newest plan is read for
    commitments: a record made after midnight for the day before reads that day's plan, and judges what is closed
    as of today."""
    report = {"schema_version": 1, "as_of": as_of.isoformat(), "status": "BLOCKED",
              "scope": "all available dated Markdown within explicitly declared roots; no lookback cutoff",
              "declared_roots": [{"path": str(p), "kind": k} for p, k in roots],
              "scanned": [], "excluded": [], "future_files": [], "gaps": [], "due": [],
              "critical": {"open": [], "closed": [], "unclassified": []}, "untagged": [], "commitments": 0, "no_id": [], "ahead": []}
    conf, words, closed_words, unlisted = dict(rituals.DEFAULTS), WORDS, LEDGER_CLOSED, ""
    try:
        cfg = rituals.config()
        conf, words = rituals.settings(cfg, workspace or ""), cfg.get("critical_words") or WORDS
        given = cfg.get("ledger_closed_words")
        if given is not None and not (isinstance(given, list) and all(isinstance(word, str) and word.strip() for word in given)):
            # said in the ledger's own view: a slip here must not block a record over plans that were all read
            unlisted = "ledger_closed_words in the ritual config must be a list of words or phrases; the built-in closing words are used"
        elif given:
            closed_words = LEDGER_CLOSED + tuple(word.strip().upper() for word in given)
        unclassified = re.compile(r"\b(?:" + "|".join(words) + r")\b", re.I)
    except (ValueError, OSError, TypeError, re.error) as exc:
        gap(report, rituals.state_dir() / "config.json", f"ritual config unreadable: {exc}")
        unclassified = re.compile(r"\b(?:" + "|".join(WORDS) + r")\b", re.I)
    entries = []
    seen = set()
    newest, owed, unread = defaultdict(list), [], 0  # the plans and the artifacts read, by kind; a ledger's open rows
    if not roots:
        gap(report, "", "no plan or artifact roots declared")
    for raw_root, kind in roots:
        root = raw_root.expanduser().absolute()
        if any(part.is_symlink() for part in (root, *root.parents)):
            gap(report, root, "symlink root or ancestor refused; declare its intended physical directory")
            continue
        if not root.is_dir():
            gap(report, root, "declared directory missing or not a directory")
            continue
        pattern = PLAN if kind == "plans" else ARTIFACT
        selected = 0
        for directory, dirs, files in os.walk(root, followlinks=False, onerror=lambda exc: gap(report, exc.filename or root, f"directory unreadable: {exc}")):
            dirs.sort()
            for name in list(dirs):
                child = Path(directory) / name
                if child.is_symlink():
                    gap(report, child, "symlink directory not scanned")
                    dirs.remove(name)
            for name in sorted(files):
                path = Path(directory) / name
                if path.is_symlink():
                    gap(report, path, "symlink file not scanned")
                    continue
                if kind == "records":  # any Markdown file: a draft, a ledger
                    match = RECORD.match(name) if name.endswith(".md") else None
                    if not name.endswith(".md"):
                        report["excluded"].append(str(path))
                        continue
                else:
                    match = pattern.fullmatch(name) or (kind == "artifacts" and MIDDAY_RUN.fullmatch(name))
                    if not match:
                        report["excluded"].append(str(path))
                        continue
                selected += 1
                try:
                    day = iso_day(match[1]) if match else as_of
                except ValueError:
                    gap(report, path, "invalid date in source filename")
                    continue
                if day > as_of:
                    report["future_files"].append(str(path))
                    continue
                if path in seen:
                    continue
                seen.add(path)
                if kind == "records":
                    found = parse_plan(path, day, 0, as_of, report)
                    entries.extend(dict(entry, record=True) for entry in found)
                    try:
                        rows, missed = ledger_rows(path, as_of, closed_words)
                    except Exception as exc:  # noqa: BLE001  one record's table must never cost the sweep its other reads
                        gap(report, path, f"its tables could not be read: {type(exc).__name__}: {exc}")
                    else:
                        owed, unread = owed + rows, unread + missed
                    continue
                if kind != "artifacts":
                    rank = 2
                elif match.re is MIDDAY_RUN:  # midday-2 after midday, before the day-end
                    rank = RUN_ORDER["midday"] + int(match[2]) / 1000
                else:
                    rank = RUN_ORDER[match[2]]
                entries.extend(parse_plan(path, day, rank, as_of, report))
                if day <= (plan_day or as_of):
                    newest[kind].append((day, rank, str(root), path))
        if selected == 0 and kind != "records":  # a folder of drafts may hold none today
            gap(report, root, "no dated source files; coverage is not established")
    # The seat's commitments stand in its newest plan, today's or not: every plan of that day, or, where the seat
    # keeps no dated plan, the last run of that day in each folder that holds a rituals' artifact of that day (a
    # worker that has not run since an earlier day is not read: its newest is not the seat's).
    files = newest["plans"] or newest["artifacts"]
    last = max((found[0] for found in files), default=None)
    current = [found for found in files if found[0] == last]
    unreadable = {entry["path"] for entry in report["gaps"] if entry["reason"].startswith("unreadable source")}
    report["plans_read"] = []
    for path in sorted({found[3] for found in current} if newest["plans"] else {
            max(f for f in current if f[3].parent == found[3].parent)[3] for found in current}):
        if str(path) in unreadable:  # already a gap: one source, said once
            continue
        try:
            found = commitments(path)
        except Exception as exc:  # noqa: BLE001  nor may one plan's shape
            gap(report, path, f"its commitments could not be read: {type(exc).__name__}: {exc}")
            continue
        report["plans_read"].append(str(path))
        report["commitments"] += len(found)
        report["untagged"] += [{k: v for k, v in row.items() if k != "bare"} for row in found if row["bare"]]
    owed.sort(key=lambda row: (row["owed_since"] is not None, row["owed_since"] or "", row["path"], row["line"]))
    dated = [row["owed_since"] for row in owed if row["owed_since"]]
    report["owed"] = {"open": len(owed), "oldest": min(dated) if dated else None, "undated": len(owed) - len(dated), "unread": unread,
                      "over_14_days": sum(row["days"] > OWED_DAYS for row in owed if row["days"] is not None), "rows": owed,
                      **({"config": unlisted} if unlisted else {})}
    grouped = defaultdict(list)
    for entry in entries:
        grouped[entry["identity"]].append(entry)
    for identity, history in grouped.items():
        copies = history  # every copy, a record's included: a Lapsed mark on the item's draft is a mark on the item
        # A plan outranks a record: once a plan or ritual artifact carries the item, the plans decide it.
        history = [e for e in history if not e.get("record")] or history
        history.sort(key=lambda r: (r["plan_date"], r["run_rank"], r["path"], r["line"]))
        # Resolve each file's last occurrence first, without ordering peer files by name.
        latest = history[-1]
        slot = (latest["plan_date"], latest["run_rank"])
        peers = {}
        for entry in history:
            if (entry["plan_date"], entry["run_rank"]) == slot:
                peers[entry["path"]] = entry
        states = {(e["due_date"], e["closed"], e["reason"]) for e in peers.values()}
        ambiguous = len(states) > 1
        if ambiguous:
            gap(report, latest["path"], f"conflicting same-day states for {identity}", latest["line"])
        earlier_dates = {e["due_date"] for e in history[:-1] if e["due_date"]}
        bad_redate = bool(latest["due_date"] and earlier_dates - {latest["due_date"]} and not latest["closed"] and not latest["reason"].strip(" ()"))
        if bad_redate:
            gap(report, latest["path"], "changed Decays date requires a stated reason", latest["line"])
        choices = history if ambiguous or bad_redate or latest["invalid"] else [latest]
        if any(e["critical"] for e in history):  # once critical, always critical: a copy that drops the tag demotes nothing
            state, row = critical_row(identity, history, choices == [latest], as_of, lambda day: rituals.expected(day, conf), report)
            recent = state == "closed" and (as_of - date.fromisoformat(row["closed_in"])).days <= LEAD_DAYS
            report["critical"][state] += [row] if row and (state == "open" or recent) else []
            continue  # never in the dated list, whose items may be released or lapse
        if not latest["closed"] and not any(e["not_critical"] for e in history) and unclassified.search(f"{latest['title']} {latest['reason']}"):
            report["critical"]["unclassified"].append({k: latest[k] for k in ("identity", "title", "due_date", "path", "line")})
        if identity.startswith("source:") and latest["due_date"] and not latest["closed"]:  # no copy of it can be matched to it
            report["no_id"].append({k: latest[k] for k in ("title", "due_date", "path", "line")})
        due_choices = [e for e in choices if e["due_date"] and e["due_date"] <= as_of.isoformat() and not e["closed"]]
        if due_choices:
            chosen = min(due_choices, key=lambda e: e["due_date"])
            result = {k: v for k, v in chosen.items() if k not in ("closed", "run_rank", "invalid", "record")}
            result["sources"] = [{"path": e["path"], "line": e["line"]} for e in history]
            # its date passed and no copy says it lapsed: nobody was told (a seat that runs its rituals re-dates
            # what it carries each day, so this is the mark of a day with no ritual)
            result["unannounced"] = chosen["due_date"] < as_of.isoformat() and not any(
                e["lapsed_on"] >= chosen["due_date"] for e in copies)  # a mark for an earlier date says nothing of this one
            report["due"].append(result)
        elif latest["due_date"] and not latest["closed"]:  # open and not yet due: for a list of everything open
            report["ahead"].append({k: latest[k] for k in ("identity", "title", "due_date", "path", "line")})
    report["due"].sort(key=lambda e: (e["due_date"], e["path"], e["line"]))
    report["no_id"].sort(key=lambda e: (e["due_date"], e["path"], e["line"]))
    report["ahead"].sort(key=lambda e: (e["due_date"], e["path"], e["line"]))
    report["critical"]["open"].sort(key=lambda e: (e["due_date"], e["path"], e["line"]))
    report["total_obligations"] = len(grouped)
    review = (report["due"] or report["critical"]["unclassified"] or any(r["lead"] or r["problems"] for r in report["critical"]["open"])
              or report["untagged"] or report["no_id"])  # a ledger's open rows are a view of their own and change no status
    report["status"] = "BLOCKED" if report["gaps"] else "REVIEW" if review else "CLEAR"
    return report


def critical_lines(critical: dict) -> list[str]:
    """The block that opens the text report whenever a critical item is open, just closed or unclassified."""
    rows, lines = critical["open"], []
    for row in rows:
        when = f"PAST DUE {row['due_date']}" if row["past_due"] else f"{row['due_date']} ({row['days_left']} days left)"
        was = f" (was {', '.join(row['redated_from'])})" if row["redated_from"] else ""
        lines.append(f"  {when}{was} {row['title']} [{row['class']}] ({row['path']}:{row['line']})")
        lines += [f"      problem: {problem}" for problem in row["problems"]]
    lines += [f"  closed in the last {LEAD_DAYS} days: {row['title']} — on: {row['evidence']}" for row in critical["closed"]]
    lines += [f"  possibly critical, not classified: {row['due_date']} {row['title']} ({row['path']}:{row['line']})"
              for row in critical["unclassified"]]
    head = (f"CRITICAL: {len(rows)} open ({sum(r['past_due'] for r in rows)} past due, "
            f"{sum(r['lead'] and not r['past_due'] for r in rows)} within {LEAD_DAYS} days); "
            f"{sum(r['alert'] for r in rows)} due an alert today")
    return [head, *lines] if rows or lines else []


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--as-of", required=True, help="verified current calendar date, YYYY-MM-DD")
    parser.add_argument("--plans-dir", action="append", default=[], type=Path)
    parser.add_argument("--artifacts-dir", action="append", default=[], type=Path)
    parser.add_argument("--records-dir", action="append", default=[], type=Path,
                        help="a folder of other Markdown records (drafts, a ledger) whose items are swept unless a plan carries them")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--workspace", help="also read the plan and artifact folders this workspace declares in the ritual config")
    parser.add_argument("--alert", action="store_true", help="post the critical-deadline banner and spoken line when one is due today")
    parser.add_argument("--alert-declared", action="store_true",
                        help="one alert counting every workspace's declared folders, for a day with no ritual")
    args = parser.parse_args(argv)
    roots = [(p, "plans") for p in args.plans_dir] + [(p, "artifacts") for p in args.artifacts_dir] + [(p, "records") for p in args.records_dir]
    try:
        as_of = iso_day(args.as_of)
        cfg = rituals.config() if args.workspace or args.alert_declared else {"workspaces": {}}
        roots += declared(cfg, args.workspace) or [] if args.workspace else []
        sets = {tuple(found): name for name in cfg["workspaces"] if (found := declared(cfg, name))} if args.alert_declared else {}
    except ValueError as exc:
        report = {"status": "BLOCKED", "due": [], "gaps": [{"path": "--as-of or the ritual config", "reason": str(exc)}],
                  "critical": {"open": [], "closed": [], "unclassified": []}}
    else:
        if args.alert_declared:  # a set of folders two workspaces declare alike is read once
            reports = [collect(list(found), as_of, name) for found, name in sets.items()]
            count = sum(row["alert"] for found in reports for row in found["critical"]["open"])
            print(f"critical alert: {count} due across {len(sets)} declared set(s) of plan folders; {alert(count)}")
            # a day with no ritual tells no one; an item two declared sets share is one item
            late = len({(row["path"], row["line"]) for found in reports for row in found["due"] if row["unannounced"]})
            print(f"passed dates: {late} with nothing written across {len(sets)} declared set(s) of plan folders; {passed(late)}")
            return 0
        report = collect(roots, as_of, args.workspace)
    if args.alert:
        report["critical"]["alert"] = alert(sum(row["alert"] for row in report["critical"]["open"]))
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        # Coverage denominators, not bare counts: "3 past due" once hid the
        # shape of the sweep the same way bare checklists did.
        print("\n".join(critical_lines(report["critical"])), end="\n" if critical_lines(report["critical"]) else "")
        print(
            f"Deadline sweep: {report['status']} — {len(report['due'])} due of "
            f"{report.get('total_obligations', '?')} tracked obligations across "
            f"{len(report.get('scanned', []))} scanned sources "
            f"({len(report.get('excluded', []))} excluded, "
            f"{len(report.get('future_files', []))} future); "
            f"{len(report['gaps'])} gaps"
        )
        late = sum(row.get("unannounced", False) for row in report["due"])
        if late:
            print(f"{late} of them passed {'its' if late == 1 else 'their'} date with nothing written: mark each Lapsed where it "
                  "sits and give it a row in the lapse register, or record what was decided")
        for row in report["due"]:
            print(f"{row['due_date']} {row['title']} ({row['path']}:{row['line']})")
        loose, bare, owed = report.get("no_id", []), report.get("untagged", []), report.get("owed", {"open": 0, "rows": []})
        if loose:
            print(f"{len(loose)} open dated item{' has' if len(loose) == 1 else 's have'} no Decay ID, so no copy can be matched to "
                  + ("it:" if len(loose) == 1 else "them:"))
            print("\n".join(f"  {row['due_date']} {row['title']} ({row['path']}:{row['line']})" for row in loose))
        if bare:
            print(f"Commitments with no date and no park: {len(bare)} in the newest plan (of {report.get('commitments', 0)} open); "
                  "the sweep cannot keep these in view")
            print("\n".join(f"  {row['title']} ({row['path']}:{row['line']})" for row in bare))
        if owed.get("config"):
            print(f"Owed: {owed['config']}")
        if owed["open"] or owed.get("unread"):
            print(f"Owed: {owed['open']} open ledger row{'' if owed['open'] == 1 else 's'} (oldest {owed['oldest'] or 'none dated'}, "
                  f"{owed['over_14_days']} owed over {OWED_DAYS} days, {owed['undated']} with no date, "
                  f"{owed['unread']} row{'' if owed['unread'] == 1 else 's'} not read)")
            print("\n".join(f"  {row['owed_since'] or 'no date   '} {row['item']} [{row['status'] or 'no status'}] ({row['path']}:{row['line']})"
                            for row in owed["rows"][:10]))  # those with no date first, then the oldest
        for row in report["gaps"]:
            print(f"NOT COVERED: {row['path']}: {row['reason']}")
    return 2 if report["status"] == "BLOCKED" else 0


if __name__ == "__main__":
    raise SystemExit(main())
