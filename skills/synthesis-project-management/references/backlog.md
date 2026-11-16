# The backlog

One ordered list per project, and it must shrink. The principal's rulings of
2026-11-16 set it, so that a project's own follow-on work cannot quietly outgrow
what the principal asked for: a review of the work's own fixes can always find
one more thing, and each thing found becomes an item.

## One list, in order

A project keeps one ordered list: the checklist of the plan its CONTEXT.md names
on `**Plan:**` (`resources/artifacts/<date>-<slug>-plan.md`; an autopilot run's
plan file is that plan). Order is priority: the top open item is the next one
worked. CONTEXT.md's next actions name the top of that list; they are not a
second list. Findings files, decision packets, action sheets, peer messages and
chat feed the list: what they ask for becomes an item at its place, or is
declined, and none of them holds open work of its own.

## Two kinds of item

- **Principal:** the item delivers the principal's request, their backlog, or a
  build their ruling ordered. A request from another session counts, since the
  principal added that scope.
- **Self:** the item only fixes, reviews or re-reviews what the work itself
  produced: a review round's findings, a fix to a fix, another look at the
  project's own change.

When unsure, ask whether the item would exist had the work not produced the thing
it fixes or reviews. If not, it is self-generated.

Mark each item in its text, as synthesis-autopilot's plan file does, so one
convention serves supervised work and autopilot runs alike. An item added after
the plan was written carries `added <time>`, and a checked item carries
`closed <time>`, ISO times with the offset:

```text
- [x] 1. Migrate /users (origin: principal, closed 2026-11-16T11:02-05:00) — 42 tests pass
- [ ] 2. Migrate /orders (origin: principal)
- [ ] 3. Close the gap the second review found (origin: self, added 2026-11-16T09:30-05:00)
```

## The count at every checkpoint

At every checkpoint (synthesis-checkpoint, a phase boundary, a session's end),
count the principal items closed and the self-generated items added since the
last checkpoint. When, over a day, the second outnumbers the first, stop all new
work and ask the principal one line: continue, narrow or stop. Leave the work in
flight at a safe point (committed, nothing half-written) and start nothing else
until they answer. In an autopilot run, `cycle` makes this count at every wake
and refuses the advance (synthesis-autopilot, `references/plan-file.md`,
"Origins and the count").

## The daily count must fall

At each day's first session (an autopilot run's first wake), write the count of
open principal items under the plan's `## Backlog count`, one line a day:

```text
## Backlog count

- 2026-11-15: 9 open principal item(s)
- 2026-11-16: 7 open principal item(s)
```

It must fall day by day. When it rises two days running, stop and re-plan with
the principal: bring the same one line, continue, narrow or stop, with the three
counts. The principal's own new requests can raise it; re-planning is how the
principal chooses what waits.

## Finish, ship and install before anything new

Work the list from the top: finish, ship and install each item before starting
anything new. An item is finished when it is shipped and in place where it is
used: merged and released, published, or delivered by the project's own route,
then installed in every harness for a skill, deployed for a site, read back for a
record. Done on a branch, or waiting on another review round, is not finished.

## The side-quest test

A side quest is anything other than the current item: a tool to build, a cleanup
noticed in passing, a second problem. It is fine only when it serves the
principal's goals: it unblocks the current item, or the principal asked for it.
Name the goal it serves before starting it. If none can be named, it is an item:
it goes on the list at its place, `origin: self` when it only fixes or reviews
the work's own output, and waits its turn.
