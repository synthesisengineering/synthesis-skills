# Deadline collection and reconciliation

Read at Day-End Step 4b, before the send-or-release pass. A deadline whose miss cannot be undone
is handled apart from everything here: the `**Critical:**` tag, its own view in the report,
alerts, and closure only on evidence are in [critical-deadlines.md](critical-deadlines.md).

Day-End Step 4 selects by a tag's target date, not the date of its plan. A
deadline noticed in an older plan must remain visible when due, even after a
long interruption. The collector is read-only and grants no send authority.

## Design decision

Two approaches were considered: widening the agent's plan-reading window, or
collecting dated tags deterministically across the complete declared plan
scope. A wider window is simple but still loses old unresolved deadlines and
requires rereading every old plan with paid tokens. The deterministic collector
is selected: it reads all locally available dated plans, returns source
locators and coverage, and leaves contextual decisions to the agent and user.
It does not infer that local files represent all history or all workspaces.

## Source boundary

Run `python3 <rituals>/scripts/decay_sweep.py --as-of YYYY-MM-DD
--plans-dir <declared-daily-plans-directory> --json` (`<rituals>` is this skill's folder). It
prints a JSON report: `status` (`CLEAR`, `REVIEW` or `BLOCKED`), the `due` items with source
locators, the `critical` view, and the coverage of every root and file. Repeat `--plans-dir` for
each plan directory declared for this seat, or pass `--workspace <W>` to read the folders the
workspace declares in the ritual config (`plans_dirs`, `artifacts_dirs`, and `records_dirs` for drafts or
a ledger that carry their own deadlines: [critical-deadlines.md](critical-deadlines.md)). Include archived subdirectories
under each declared root: there is no lookback cutoff. Supply `--artifacts-dir
<declared-ritual-workers-directory>` for this workspace's worker artifacts when
the distributed contract uses them. That option accepts dated day-start,
midday (and `midday-N` for a later mid-day run that day) and day-end Markdown artifacts; plan directories accept dated Markdown
plans (`YYYY-MM-DD.md`). Pass today's verified calendar date as `--as-of`, even
when closing an earlier logical workday.

The desk reads its person-scoped plans. Workers collect their own workspace
records and put the count, source pointers and gaps in their existing artifact;
the desk folds those results and names missing worker coverage. Do not crawl
other workspaces or follow a plan's links into workspace-owned source records.
Declare any separately stored plan archive explicitly, under its owning seat.

The helper reports every selected file, skipped future file, excluded unrelated
file, malformed date, unreadable directory/file and refused symlink. Missing or
empty declared roots, incomplete enumeration, invalid tags, ambiguous identity
or conflicting same-day states produce `BLOCKED` and exit 2. Existing candidates
remain in the result alongside gaps. A scan with due candidates, an untagged
commitment or a dated item with no Decay ID is `REVIEW`; only a complete scan
with none of those is `CLEAR` (a ledger's open rows are a view of their own). Successful scans exit 0;
that means collection succeeded, not that communications are approved or the
day may close. Fenced/inline code examples and blockquotes are not operative
plan items. Unterminated fences or frontmatter are coverage gaps.

A gap blocks a clean sweep conclusion, not the rest of the ritual. Continue
reviewing recovered candidates and performing other required ritual steps;
record the incomplete coverage instead of claiming a clean close. Historical
malformed input does not authorize broad plan repair or silently remove an
obligation. Reconcile it at its source under the existing authority rules.

## Item identity and outcomes

Keep the existing `**Decays:** YYYY-MM-DD (reason)` grammar. For new items add
an optional `**Decay ID:** <stable-id>` line in the same item block. Use a unique
ID per obligation, retain it when carrying or re-dating that obligation, and
never reuse it for a new task. This is ordinary Markdown metadata; it does not
change the Decays field or require rewriting old plans. IDs are scoped to the
declared plan/artifact roots passed in one invocation for the same seat.

An item block starts at a Markdown heading or list item and ends at the next
heading or peer list item. Put metadata directly under that heading/list item,
not in a separate subheading. The collector does not use a matching title to
merge obligations. Existing tags without IDs retain a source-path-and-line
identity and remain review candidates until a grounded outcome is recorded at
their original item. Do not bulk-generate IDs or infer resolutions from prose; a workspace that checks
commitments gives each open dated item its ID where it sits, one at a time.

Carry the ID and Decays line into the new plan, including on the due date. A
later dated plan with that ID can re-date the obligation with a stated reason,
or record `**Sent:** <ISO timestamp>`, `**Released:** YYYY-MM-DD (reason)` or
`**Resolved:** YYYY-MM-DD (reason)`. Record only user-authorized actions or
directly verified outcomes. A checked task (`[x]`) or struck-through item title
also closes its own item; preserve the accompanying reason/evidence. A struck
deadline (`**Decays:** ~~YYYY-MM-DD~~ (release reason)`) follows the existing
release convention; without a reason it remains a blocked review candidate.
An optional check mark before a Sent timestamp does not alter that timestamp. Copied
plain prose without identity does not extinguish the original tagged item.

Identical copies with the same ID coalesce. The latest plan date determines the
operative entry; within one file the last entry wins. Day-start, midday and
day-end artifacts follow that declared run order. Different states in separate
files at the same date/run rank are ambiguous: the scan keeps the candidate
and reports a conflict rather than guessing which author won. A changed date
without a reason is likewise blocked. Future plans and future completion
timestamps cannot close today's obligations.

Read every returned item at its source, reconcile against current sent/released
evidence, then ask for the actual send, re-date or release decision. Do not send,
delete, re-date or mark complete merely because a script surfaced the item.

An item tagged `**Critical:**` is never in `due` and never takes the release or lapse outcome
above: it stays in the report's `critical` view until a closing mark carries an `**Evidence:**`
line ([critical-deadlines.md](critical-deadlines.md)).

## What else the sweep reads

Four things a rule once asked an agent to remember. They were counted on three seats' real plans on 2026-11-13
before any of them refused anything; the counts are in each paragraph.

**Commitments with no date and no park (`untagged`).** The sweep keeps in view only what carries a date, so a
commitment written with no tag is carried for as long as someone copies it and no longer.

- *Which plan.* The seat's newest plan, today's or not: every plan of the newest day on or before the sweep's.
  Where the seat keeps no dated plan, the last run of that day in each folder that holds a rituals' artifact of
  that day (a worker that has not run since an earlier day is not read). The files read are listed under
  `plans_read`.
- *Which headings.* A heading of the second level or deeper places commitments under it where its words are the
  plan format's for tasks, things waited on or things carried: `Priority Tasks`, `Tasks`, `Task list`, `Action
  Items`, `To do`, `Follow-ups`, `Today's Priorities`, `Still To Do`, `Pending This Session`, `Waiting On Others`,
  `Watch / waiting`, `Delegated`, `Carried Items`, `Carry Forward`, and `This Week` as a heading's whole text
  (`Meetings this week` is another thing). A heading that opens with the name of another kind of section says
  nothing by itself (`Calendar`, `Draft A: to someone who is waiting`, `Standup`, `Decisions`, `Sync`); one whose
  task word such a name only qualifies is read (`Tasks from the sync`, `Waiting on PR review`). A heading of things
  finished holds none: it says completed, done, sent, closed, finished or shipped, and has no word that says the
  thing is still to come (`Not done yet` and `Sent, awaiting reply` are not such headings). The nearest enclosing
  heading that says either way decides: a bucket under the task section is read unless its own words say
  finished, and the plan's own title places nothing. A heading that is all inline code is no heading to the sweep.
- *Which entries.* Each top-level list entry there, and each row of a table that stands directly under such a
  heading, before any list: a row is named by its first cell that says what it is (not a number), and a row that
  is empty, repeats the table's header or opens with a clock time (a schedule's line) is passed over.
- *What is closed.* An entry is closed, and not read, where a mark stands as its status: a tick box, a strike, a
  tick (✅ ✓ ✔ ☑) or DONE or SENT in capitals at its start, with no question mark after the word; ✅ at its end,
  alone or before DONE or SENT; or DONE or SENT after a dash or a colon. A tick or a word inside a sentence closes
  nothing (`Ship it (staging ✅, prod pending)`, `Confirm the deploy is DONE`). So does a Sent, Released or Resolved
  line that gives its day, or a struck date with its reason, anywhere in its block; in a table, such a line or a
  status mark in any cell of the row.
- *What passes.* A `**Decays:**` date in the entry's block (a `**Critical:**` tag needs its date too), or a park
  that says why: `parked (reason)`, or a `**Parked:** reason` line, anywhere in the block, a nested entry's
  included. A table's row can carry a park and no date, since a tag stands under a heading or a list entry: a row
  is listed until it is parked or written as an entry.
- *Not read.* An entry under any other heading (16, 21 and 11 open entries with neither stood under headings of
  notes, where code cannot tell a commitment from a remark); a commitment written as a sentence; a table inside an
  entry or after a list; a plan older than the newest. `Team priorities` under a heading of notes is read, since
  code cannot tell whose they are.

Listed entries make the status REVIEW. Counted: 12, 0 and 11 such entries in three seats' newest plans, under
the task and waiting headings, none of them a task box.

**An open dated item with no Decay ID (`no_id`).** Without the ID no later copy can be matched to it, so the
sweep takes each copy for another item: three plans that copy it are three items, and closing one closes no
other. Counted: none open in any of the three seats.

**A date that passed with nothing written (`unannounced`, on a due item).** True where the item's newest date
is before the sweep's day and no copy, a draft's or a ledger's included, carries a `**Lapsed:**` mark for that date
or a later one (a mark's day is the first date it gives; one that gives none speaks of its plan's day; one dated
ahead of the sweep's day is a gap and speaks of none). A mark for an earlier date says nothing of a later one that
passed too. A seat that runs its rituals re-dates what it carries each day, so in such a seat every due item is
dated today (29 of 29 and 73 of 73 when counted) and none is unannounced: this is the mark of a day with no
ritual. The job that runs with no ritual (`--alert-declared`, at 16:55) counts them over every declared workspace,
an item two workspaces share once, and posts one banner with the count. An item due today is not counted, since
the day has not closed.

**A ledger's open rows (`owed`).** In a `records_dirs` folder, a table whose header has a `Status` cell and an
`Owed since` cell is a correspondence ledger, each of its lines opening with a pipe, and each row is one thing
owed, at its file and line (its `Item` cell names it, or its first). A row is closed where its status, with
anything struck through set aside and a link read as its words, opens with a tick (✅, ✔, ✓, ☑, `[x]`), ends with
✅, or opens with one of the closing words with no question mark after it: SENT, SUPERSEDED, DECAYED, CLOSED,
RELEASED, RESOLVED, LAPSED, DONE, ANSWERED, REPLIED. A top-level `ledger_closed_words` list in the ritual config
adds a seat's own words and phrases to those (`"N/A"`, `"Not needed"`); a value that is no such list adds nothing
and is said in this view (`config`), where it blocks no record. Every other status is open, an empty one included:
a status the reader does not know is not read as finished. The view
gives the count, the oldest date, how many have been owed more than fourteen days, how many carry no date and how
many rows had too few cells to read, then the rows: those with no date first, then the oldest. The text report
prints the count line and the first ten of them. A ledger's rows are never in `due` and change no status: an
owed-since date is when the debt began, not a day it decays on. Counted in the one seat that keeps a ledger: 141
open rows of 341, the oldest four months old, where the due list held 73.

**A record the readers cannot read.** A plan's or a ledger's shape that either reader fails on is a gap for that
file (BLOCKED), and everything else is still read: the critical view, the due list and the evening's alert.

**The record.** A workspace turns the commitment check on in the ritual config: `"commitment_check": true`, or
`{"from": "YYYY-MM-DD"}` for its first day. `ritual_state.py record` then refuses a clean outcome while `untagged`
or `no_id` holds anything, names each with its file and line, and says how to finish each kind; any other outcome
records and says how many. The plan read is the newest on or before the record's day, and what is closed is judged
as of today, so a record made after midnight for the day before takes a closing mark written since. Where no dated
plan was read it says so. Only a missing key or `false` leaves it off, and any other value is refused. The ledger
refuses nothing.

## Regression contract

Fixtures cover an old tag due today, an unresolved tag older than fourteen days,
future tags, invalid dates, unrelated files and quoted examples. Additional
tests cover carry-forward deduplication, reasoned re-dating, later resolution,
distinct obligations with matching titles, missing/unreadable sources, symlink
boundaries and invalid timestamps. The same helper and tests serve both clients.
`tests/test_critical_deadlines.py` covers the critical view, the alerts and the ritual record,
and replays the window of 2026-11-06 day by day. `tests/test_seat_tasks.py` covers the four reads above and the
commitment check.
