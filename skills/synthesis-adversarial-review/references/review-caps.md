# Review caps

The principal's rulings of 2026-11-16 bound every review, whichever protocol
section is running. They exist because a review of the work's own fixes can
always find one more way around them: each finding becomes a fix, each fix goes
back for review, and the plan grows with work the review made while the
principal's own work waits. Binding rules 15 and 16 carry them; this page holds
them in full.

## Two rounds per item

An item is one piece of work the review judges: a backlog item, a fix, a change
set. It gets at most two review rounds. Round one judges the work; round two
judges the repairs round one asked for.

After the second round, a finding, whether still open or new, blocks the item
only when it passes the materiality test:

- **An honest agent would hit it in ordinary work.** An agent doing the job the
  work is for, without trying to get around it, would meet the failure. A gap
  that needs a crafted input, a spelling made to slip past a check, or a sequence
  of steps no ordinary task produces fails this test.
- **Or it appears in the principal's records.** The failure has already happened
  in the principal's own work: their transcripts, logs, incident notes, or a
  report they made. A finding a reviewer only constructed is not in their records.

Anything else goes on the open list: the project's written record of known gaps
that do not block (for software, its documented limitations), with the finding's
reproducer and the round that found it. In the findings file it is
`ship-improving`, with the open list as its follow-up, and it never returns to
the delivery on its own. A third round happens only on the principal's own
decision, like generation N+2 of a control (binding rule 11).

## The coordinator bounds the review, not the reviewer

The coordinator is the agent that dispatches the review and owns the delivery:
an autopilot run's owner, or the integrator. It sets the bounds and holds them.
It records each item's round count in the findings file's header
(`- Rounds: <item>: 2 of 2`), refuses a third round without the principal's
decision, and applies the materiality test to every finding after the second
round. A reviewer reports findings; it does not extend the review, add a round,
or rule its own finding blocking. A reviewer's request for another round is a
finding like any other, and the coordinator judges it by the same test.

## At most three agents at once

The coordinator runs no more than three agents at once on a review: reviewers,
repairers and the adjudicator together. It waits for one to return before it
dispatches another. More reviewers at once does not make a review more
independent, since blind-spot rotation does that (binding rule 5); it spends the
principal's model quota faster.

## A release never waits for another round

A release ships what has passed review. A finding still open after its rounds is
on the open list, not a reason to hold the release, and no round is started to
make a release wait. The release's notes name what it does not cover.

## Where the caps meet the rest of the protocol

- A `ship-blocking` finding (binding rule 8) that fails the materiality test
  after the second round becomes `ship-improving` and goes on the open list.
- Bounded control depth (binding rule 11) still applies; the caps limit rounds on
  any work, requested or not.
- In an autopilot run, each finding that becomes a checklist item is a
  self-generated item, so the run's count weighs it against the principal's work
  (synthesis-autopilot, `references/plan-file.md`, "Origins and the count").
