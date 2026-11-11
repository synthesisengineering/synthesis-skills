# Critical deadlines

Read at day-start, at every deadline sweep, and the day a deadline with irreversible stakes is
first seen. `<rituals>` is this skill's folder; `<W>` is the workspace.

Contents: What is critical · The tag · Where it lives in the plan · The sweep's critical view ·
Alerts · Closing one · The ritual record · Declared plan folders · Why.

## What is critical

A deadline is critical when missing it causes harm that cannot be undone, or cannot be fixed
until the next cycle, often a year away. The usual classes: benefits and insurance enrollment,
taxes, legal and patent filings, immigration and identity documents, pay, time-off and award
actions for the principal's reports, and account-security checks. The principal's chief-of-staff
config names their own classes (`critical_deadlines.classes`).

Classify by class, the day the deadline is first seen. Whether the principal needs to act is
theirs to say: many enrollments need an active election or a re-verification even when nothing
else changes, so an agent never writes one up as optional and never decides that nothing is
needed.

## The tag

A critical deadline is a deadline item ([decay-sweep.md](decay-sweep.md)) with four more lines:

```markdown
### Open enrollment closes Friday, November 6, 11:59 PM Eastern
[The enrollment page](https://example.com/enroll): elections, flexible spending, dependents.
**Critical:** benefits enrollment
**Decays:** 2026-11-06 (the window closes)
**Decay ID:** enrollment-2027
**Calendar:** all-day marker on 2026-11-06, event 4f2a; working block 2026-10-21 14:00
```

- `**Critical:** <class>` marks it. Once an item has carried the tag, a later copy that drops it
  is still critical.
- `**Decay ID:**` is required, so a carried copy is known to be the same deadline.
- `**Calendar:**` names the calendar entries that mark the closing date and the working block
  (the chief-of-staff skill places them at intake). Without it the sweep reports that nothing
  shows the date is on the calendar.
- The heading carries the closing date and the exact time with its time zone. The first line
  under it is the direct link and what the principal has to do.

The sweep also lists items with no tag whose title or reason reads like a critical class
(enrollment, insurance, taxes, a patent, a visa, a passport, immigration, payroll, FSA, HSA; the
ritual config's `critical_words`, a list of words or patterns, replaces that list). Each stays
listed until it is classified: tag it, or write `**Critical:** no (<why this one is not>)`.

## Where it lives in the plan

- **From seven days out, the plan opens with `## Critical deadlines: needs your attention`,**
  before every other section, one H3 per item in date order. The same section opens every brief
  and every summary to the principal for as long as an item is inside that week. (The Console
  shows a heading that says "needs your attention" in its NEEDS YOU region.)
- **It never sits in the dated task list, a carried-items list or a decision packet.** A row
  among many is how one was missed; the packet builder refuses a row tagged `critical`.
- **Further out than seven days,** one line under the plan's status line is enough:
  `Critical ahead: 2, the next closes 2026-12-15`. The sweep keeps tracking the item from the
  plan that first carried it; it does not need re-listing every day.

## The sweep's critical view

`python3 <rituals>/scripts/decay_sweep.py --as-of <today> --workspace <W> --alert` (add
`--json` for the full report). `--workspace` reads the plan folders the workspace declares;
`--plans-dir` and `--artifacts-dir` still work and add to them. The text report opens with the
critical items:

```text
CRITICAL: 2 open (1 past due, 1 within 7 days); 2 due an alert today
  PAST DUE 2026-11-06 Open enrollment closes [benefits enrollment] (<plan>:14)
      problem: marked closed with no Evidence line: it stays open
  2026-11-14 (3 days left) (was 2026-11-10) Renew the passport [identity document] (<plan>:31)
  closed in the last 7 days: File the extension — on: confirmation "Extension accepted", 2026-11-08 10:02
  possibly critical, not classified: 2026-11-20 Review the insurance renewal (<plan>:48)
Deadline sweep: REVIEW — 3 due of 41 tracked obligations across 60 scanned sources (...)
```

In the JSON, `critical.open` rows carry `class`, `due_date`, `days_left`, `lead` (inside seven
days), `past_due`, `alert` (due an alert today), `calendar`, `problems` and `redated_from` (the
dates it had before, when its date changed). `critical.closed` lists items closed in a plan from
the last seven days with the evidence each closed on, so the principal sees what closed and why.
`critical.unclassified` lists the untagged items above. Critical items never appear in `due`:
that list feeds the send-or-release pass, whose items may be released or lapse. The status is
REVIEW while any critical item leads, has a problem or waits to be classified. A critical item
with no valid date is a gap, and the sweep is BLOCKED.

Put every `lead` item in the plan's section, name every problem and every unclassified item in
the brief, and repeat each `closed` line once.

## Alerts

An open critical item is due an alert three days before its date, one day before, on the day,
and at every run after it has passed. An alert day the workspace does not work (its `weekdays`
and `non_working_dates` in the ritual config) also alerts on the last working day before it, so
a Monday deadline is heard on Friday.

`--alert` posts one banner and one spoken line when any item is due an alert, and reports what
it did (`critical.alert`): `{"count": 2, "banner": "posted", "audio": "played"}`. The text is a
count and a pointer, never a title: "2 critical deadlines closing soon or past due. Details are
in your day plan." `~/.synthesis/quiet-audio` silences the audio and keeps the banner. Every
ritual runs it: day-start, each mid-day sync and day-end. The 16:55 nudge runs
`decay_sweep.py --alert-declared` over every workspace's declared folders, so a day with no
ritual still alerts; if that check cannot run, the nudge shows a second fixed banner saying so.

## Closing one

A critical item closes only when both are at the item:

1. a closing mark: `**Resolved:**`, `**Sent:**` or `**Released:**` with its date, a checked or
   struck title, or a struck deadline; and
2. `**Evidence:** <what shows it>`: a confirmation (the message or screenshot, with its time),
   or the principal's own words in quotes with the time they said them.

A closing mark with no evidence leaves it open, and the sweep says so. An announcement that says
no action is needed is not evidence, and neither is an agent's reading of the principal's
situation. Letting one go is the principal's decision, recorded in their words. A critical item
is never marked `**Lapsed:**`; the sweep reports the mark and keeps the item open.

A changed date needs its reason on the Decays line, as for any deadline; the sweep then shows
the date it had. When an annual deadline closes, the chief-of-staff skill puts next year's
reminder on the calendar.

## The ritual record

`ritual_state.py record` runs the same sweep over the workspace's declared folders before it
writes, on today's date:

- **A critical item past due and open refuses the record,** in every direction and mode, and
  names each one. Ask the principal then; the record goes through once each item closes with
  evidence or carries a new date with its reason.
- **A clean outcome is refused when a plan source could not be read whole.** Record
  `--outcome partial` and name the gaps.
- **A workspace that declares no plan folders is refused,** because its critical deadlines
  cannot be checked.
- Otherwise it prints `critical deadlines: 2 open, 1 within 7 days` under the usual line.

## Declared plan folders

Each workspace declares where its dated plans live, once, in `<synthesis home>/rituals/config.json`
(an example ships as `assets/ritual-config.example.json`):

```json
{"workspaces": {"<W>": {"plans_dirs": ["~/workspaces/<W>/<knowledge repo>/daily-plans"],
                        "artifacts_dirs": ["~/workspaces/<W>/<knowledge repo>/ritual-workers"]}}}
```

`plans_dirs` holds dated plans (`YYYY-MM-DD.md`); `artifacts_dirs` holds ritual-worker artifacts.
A workspace that keeps no dated plans says so with `"plans_dirs": []`. The sweep, the record
and the nudge all read this one declaration.

## Why

On 2026-11-06 an enrollment window closed with its item still open. It had been seen three weeks
earlier and carried the whole way: in daily email reviews, as one row among two hundred in a
decision packet, then as one dated line among a hundred. It was written up as optional. It was
never on the calendar, never led a plan, and nothing sounded as the window closed. No harm came
of it that time; with a dependent to re-verify it could have cost a year of coverage. The tag,
the section, the alerts, the evidence rule and the refused record each close one of those gaps.
