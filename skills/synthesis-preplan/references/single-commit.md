# Single-commit workflow

The workflow for work that is one reviewable commit and decides nothing. The
companion to [`commit-by-commit.md`](commit-by-commit.md), which stays canonical
for multi-commit plans and owns every rule this file does not restate.

**This file states only what differs.** The cycle's shared parts — the
fast-check / full-gate split, the amend-over-follow-up rule, the audit
dimensions — live one file away. Do not re-type them here; a copy of that file
has drifted every time one has been made.

## The routing test

Two conditions, both required:

1. **One commit.** The change is a single coherent, independently reviewable
   unit. Not "could be squashed into one" — genuinely one seam.
2. **Nothing is being decided.** The work is *mechanical* in the sense
   `commit-by-commit.md`'s plan format uses: determinate once the ticket is
   read. Diff size is not the signal. A twenty-line commit that settles how two
   subsystems talk is judgment work and does not belong here; a
   four-hundred-line rename sweep does.

### Hard disqualifiers

Any one of these sends the work to the full lane regardless of size:

- A schema migration, or any change that is awkward to reverse.
- A change to a public or cross-service contract (API response shape, event
  payload, exported module surface).
- An auth, permission, or input-validation boundary.
- A data flow carrying personal or behavioral data, in a project that flags a
  privacy lens.
- Work stacked on in-flight work, where the parent's choices are not yet
  settled.

These are checkable. The two conditions above are judgment calls, and
judgment calls under time pressure default to "small" — the disqualifier list
is what actually holds the line.

### Who chooses

State the lane and the one-line reason before touching a file, and let the user
redirect. Choosing silently is the failure this section exists to prevent: the
lane gets picked by whichever workflow the session happened to be thinking
about, in both directions.

## Why these gates drop and those do not

The full lane's gates are not dropped because they are expensive. They are
dropped where **their subject does not exist** in a one-commit change. That
test, not cost, decides what survives — and it also fixes exactly what cannot
be dropped:

| Full-lane gate | One-commit change | Verdict |
|---|---|---|
| Per-commit brief × N, plan document, per-commit pauses | one commit, no plan | drop |
| Final audit on the cumulative diff | same diff the commit audit already read | drop (merged into the one audit) |
| Plan-conformance review | no plan to conform to, no cross-commit drift | drop |
| Convention-sweep half of branch-wide reconciliation | no earlier commits to sweep | drop |
| Audit of this diff, in a fresh context | subject exists | **keep** |
| Runtime execution of what changed | subject exists | **keep**, scaled |
| Test-sufficiency | subject exists | **keep**, as one check inside the review |
| Number re-derivation half of reconciliation | shared append-only files still collide | **keep** if one is touched |
| Changelog, PR, any deploy-verification gate | project gates, not process ceremony | **keep** |

Two of the kept rows — the isolated audit and the runtime execution — can be
waived by a project that declares the waiver in writing. See **Project
deltas**. Nothing in that mechanism is available per ticket.

**This lane drops ceremony, never project gates.** A project's changelog
requirement, its pre-push guard, its pre-PR checklist, and its deploy
verification gate apply at whatever weight the work is. "The project has no
changelog" is a fact about the project; "we skip the changelog because this is
small" is this rule being broken.

## The cycle

### Step 0 — Todo list and branch, before any file is touched

1. **Write the todo list** with each step below as its own named item, opening
   with these two: write the list, create the branch. Then brief, implement,
   fast-check, commit, audit, amend if findings, full gate, runtime execution,
   close-out, ship. The collapse into a single "implement the ticket" line is
   the same failure the full lane's todo discipline exists to prevent, and a
   short workflow is *more* prone to it.
2. **Create and check out the branch.** Confirm with `git branch
   --show-current` that the trunk is not checked out before the first edit. If
   a command is about to write a file and the trunk is current, stop and
   branch. No exception for a one-line change.

### Step 1 — Brief

One paragraph: what the commit does and why this seam. Where a decisions file
from the pre-planning skill exists, its rows are non-negotiable inputs. Where
none exists, the ticket plus the nearest already-shipped sibling is sufficient
grounding — do not manufacture a decisions file for work this lane already
judged decision-free.

### Step 2 — Implement

One commit. If a second independently reviewable unit appears, that is a signal
about the routing test, not a license to split — see the tripwires.

### Step 3 — Fast checks

The commit's own tests, types and lint, plus any standing hygiene checks the
project defines. Not the whole-tree gate; that runs once, at Step 6.

### Step 4 — Commit

The project's commit conventions apply unchanged. Ticket keys belong in the
branch name, the commit subject where the project allows it, and tracker
artifacts — never in source.

### Step 5 — Audit, in a fresh context

**One isolated audit of the one diff**, using the `synthesis-code-audit` skill
or your project's equivalent. This is a single call for the whole ticket
against the full lane's N+1, which is why it survives the cut: isolation was
never the expensive part.

Do not substitute an inline pass. An inline audit reads the diff with the
context that wrote it, and the full lane names that as the exact failure the
step prevents. Two exceptions, and neither is a per-ticket judgment call:

- A diff that is mechanical in the strict sense — a rename sweep, a fixture
  regeneration, a docs pass — where an inline walk of the ten dimensions is
  enough. If arguing that the diff qualifies takes more than a sentence, it
  does not.
- A project that has declared an inline-review waiver (see **Project
  deltas**).

Fold in as one-line checks rather than separate gates:

- **Test-sufficiency.** Does every new branch, callback and transition have at
  least one test? Glue and wiring are the standing blind spot. Ground each
  candidate gap in shipping behavior first — this check reduces scope as
  readily as it adds it.
- **Falsified claims.** Grep repo-wide, including outside the commit's stated
  scope, for assertions about the state this commit just changed.
- **Shared numbers.** If the change appends to a file other branches also
  append to (changelog rows, decision rows, migration versions), re-derive the
  first free number against the merge target, and tell the merger it needs
  re-deriving if the target moves.

Findings amend this commit. No follow-up `fix:`.

### Step 6 — Full gate, once, after the amend

The whole-tree suite, from the repository root, over the whole tree — never
path-scoped, because CI is not. Re-run the fast checks with it: Step 3 tested
pre-amend code.

Running this before the audit wastes the run, since the audit routinely
produces amendments. One run against the final state is the same signal at half
the cost.

### Step 7 — Runtime execution

Execute the changed path once, on the real thing, in whatever form is cheapest
for the project: the dev server and the one screen, a request against the
running service, one CLI invocation. Include any error path the change
introduces and any documented status code it promises.

Not the full lane's edge-case matrix — that scales with a plan's surface area,
and this has one. But not nothing: typechecked and audited is *unverified*, and
runtime-only defects live in exactly the glue layer a small change usually is.

Two ways this step is legitimately absent, and both are declarations rather
than omissions. If the project's harness cannot reach the runtime, name the
ceiling explicitly and say what stays unproven. If the project has declared a
runtime waiver (see **Project deltas**), the waiver carries the reason once and
the step does not recur per ticket. What is not allowed is the step quietly
evaporating because the change felt small — that is the state a waiver exists
to make visible.

### Step 8 — Close-out and ship

The project's own close-out (ticket status, changelog section, decision log),
folded into this commit rather than a second one. Then the project's PR flow,
the changelog's PR-number backfill, and any deploy verification gate the
project defines.

## Tripwires — abort to the full lane

Stop and re-route the moment any of these appears, rather than finishing the
lane you started:

- A decision you did not expect has to be made.
- A second independently reviewable unit appears in the diff.
- The change reaches a subsystem the brief did not name.
- A disqualifier surfaces that the ticket did not disclose.
- The fast checks fail in a way that indicates a design problem, not a typo.

Re-routing costs one message. Discovering at ship time that a multi-subsystem
change was reviewed as one unit costs the review.

## Project deltas

A project opts in by naming this file in its agent-instruction file
(`CLAUDE.md`, `AGENTS.md`, or equivalent), along with only what differs: the
concrete fast-check and gate commands, the close-out artifacts, and whether
this lane or the full one is the default. Everything else is read from here. A
project file that restates the cycle has re-created the drift this split exists
to remove.

### Waivers

A project may waive Step 5's isolated audit (reviewing inline instead) or
Step 7's runtime execution. Both are real reductions in signal, so a waiver is
valid only as a **written declaration in the project's own agent-instruction
file**, carrying: which step, what the project's cost or capability reason is,
and what consequently goes unverified.

The declaration is the whole mechanism. A waiver decided once, in a file, is a
choice the next session inherits and can argue with. The same reduction reached
per ticket, by a session judging its own change small, is not a choice — it is
the gate eroding, and it erodes fastest on the tickets that turn out not to
have been small. Sessions in a project without a declaration do not get to
grant themselves one.

Waivers do not reach the disqualifier list or the tripwires. A change that
trips either of those has left this lane, and the waiver does not travel with
it.
