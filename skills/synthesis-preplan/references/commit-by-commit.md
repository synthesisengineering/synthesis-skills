# Commit-by-commit workflow

The canonical workflow for executing multi-commit plans. Referenced by
the `synthesis-preplan` skill (which produces the inputs) and by your
planning step (which consumes this doc when drafting the plan). Used
directly when executing a plan by hand.

## Not every change belongs here

Work that is **one reviewable commit and decides nothing** runs
[`single-commit.md`](single-commit.md) instead. That file owns the
routing test; in short, both conditions must hold — a single coherent
seam, and work that is mechanical in the sense this file's plan format
uses (determinate once the ticket is read; diff size is not the
signal). Five disqualifiers override size either way: a migration or
other awkward-to-reverse change, a public or cross-service contract
change, an auth/permission/validation boundary, a personal-or-behavioral
data flow in a privacy-flagged project, and work stacked on unsettled
in-flight work.

The sibling file drops only the gates whose *subject does not exist* in
a one-commit change, and it can re-route back here mid-flight. When the
lane is ambiguous, state the choice and its reason before touching a
file rather than inheriting whichever workflow the session was already
thinking about.

## Preconditions

This workflow assumes:

1. **Architectural decisions are already locked.** For tickets with
   real design choices, run the `synthesis-preplan` skill first to
   produce the locked-decision document. Plans built without locked
   decisions are speculative and tend to drift mid-execution.
2. **The branch is named and based on the correct parent.** Stacking
   decisions are part of `synthesis-preplan`'s output.
3. **The plan itself exists as a checked-in or referenced document.**
   Drafting commit briefs ad hoc, without a written plan, is the
   pattern this workflow is designed to replace.

## Step 0: todo list and branch, before the first commit

Runs once, after the plan is approved and **before any file is
touched** — not at the first commit, and never discovered at commit
time. Both parts are hard requirements, in this order:

1. **Write the todo list** in whatever todo mechanism your agent
   provides, with every cycle step for every commit as its own named
   item, plus the end-of-plan block. The shape is defined in
   **Todo-list discipline** below. Write it in full here, not commit by
   commit: a list that arrives one commit at a time cannot show what is
   being skipped, which is the only thing it is for.
2. **Create and check out the branch** on the base the decisions file
   names. Confirm with `git branch --show-current` that the merge
   target is not checked out before the first edit. If a command is
   about to write a file and the trunk is current, stop and branch. No
   exception for a one-line change, a docs-only commit, or "just
   checking something".

Both parts get skipped in practice unless they are their own step, and
the skipping is not visible until commit time, which is the worst
moment to find either. A plan with no todo list collapses into
"implement the plan" and the audit and verify steps quietly disappear
with it; work started on the trunk has to be moved after the fact,
with the diff already written.

## Briefing structure

Every pre-commit briefing has these sections, in order:

**Goal** → **Focus** → **How** → **Verify** → **Independence** → **Risks** → **Conflicts**

The **Verify** section is a numbered list of `command` → `expected
outcome` pairs, plus a one-line note on any gates that can't be
checked locally (e.g., remote CI like GitHub Actions or Bitbucket Pipelines runs only after push).

Split it into two parts, because they run at different points in the
cycle:

- **Fast checks** — the commit's own tests, types, and lint. Seconds
  to a minute. These run before the commit.
- **The full gate** — the whole-tree suite, including any
  container-backed or otherwise slow integration tests. Minutes. This
  runs **once per commit, after the audit's findings are amended in**,
  and never before.

Running the full gate before the audit wastes a full run: the audit
routinely produces amendments, so that run tested code that no longer
exists. One run against the final state is the same signal at half the
cost.

Run the full gate from the repository root, over the whole tree, never
path-scoped to what the commit touched. CI is not path-scoped, so a
scoped local run is a different check wearing the same name.

Verification is its own section, not a tail bullet inside How. When
it lives at the end of a How list it gets skimmed past or skipped.
Surfacing it as a first-class section makes "what proof looks like"
visible before the commit is final.

## Per-commit cycle

Do not skip steps. Do not bundle.

1. **Brief** the commit (Goal → Focus → How → Verify → Independence → Risks → Conflicts).
2. **Execute** the implementation.
3. **Run the Verify section's fast checks.** Confirm each expected
   outcome before proceeding. Not the full gate — that comes at step 7.
4. **Commit.**
5. **Audit** the commit with an isolated code-review step (the
   `synthesis-code-audit` skill, or your project's equivalent) scoped
   to the commit's diff. The point is a fresh-context auditor —
   performing the audit inline in the current conversation is **not** a
   substitute: it carries the implementer's confirmation bias and is
   the exact failure the isolated audit exists to prevent. Always run
   the isolated audit; never hand-roll it inline.
6. **If valid findings exist, amend the commit they audited** — not
   a follow-up `fix:` or `refactor:` commit. The amend keeps history
   clean; the published commit is the corrected one, not a "we
   tried, then fixed it" pair. This is a deliberate exception to the
   general "never amend" rule because the audit-fix pair is part of
   the same logical unit of work and hasn't been pushed yet.
7. **Run the full gate, once, against the amended commit.** Re-run the
   fast checks with it — the audit-driven changes may have shifted
   behavior, and the step-3 run was against pre-fix code. This is the
   only place the whole-tree suite runs for this commit. If it fails,
   fix and amend again, then re-run it.
8. **Pause and wait for user approval** before starting the next
   commit's brief, even in auto mode. The brief is the natural
   checkpoint; the user can always say "go" to advance, but the
   default is to wait.

### Three rules the verify step keeps needing

Each of these earned its place by recurring inside a single plan after
being written down as a lesson, which is what makes it a rule rather
than an incident.

**Verify every citation against the artifact, not against memory or
the brief.** Before citing any document for a specific value — a row
number, a port, a profile, a count, a condition, a cause — open it and
locate that value. If it is not there, write it as an expectation and
name what will measure it. **This applies to the brief's own citations,
which are not pre-verified**: a brief is written by the orchestrator
and inherits its errors. The failure shape is always the same and
always plausible-looking: an inference hardened into a citation,
attributed to a nearby record that says something narrower. One plan
produced seven instances of it across five commits.

**Sweep for claims the commit has just falsified.** A commit that
changes some state must grep for assertions about the *old* state
repo-wide, **including files outside its stated scope**, and either
correct them or declare them left alone with a reason. A document that
describes the pre-commit state is a defect the commit introduced.
Typical instances: a scope item still calling work pending that this
commit did, a status line that now contradicts its own subject, an
index entry that reads as achieved.

**A grep for a literal string checks wording, not state.** Where the
assertion is about state, pair the negative grep with the positive
one: the old string is gone **and** the replacement is present. A
negative-only grep fails the moment a document legitimately mentions
the old thing as the thing being ruled out. And take diff shape from
`git diff --numstat`, never from `grep -c '^-'`, which counts the
`---` header and reads one high.

### Why per-commit verification, not bundled at end

- Catches regressions immediately, not after several commits' worth
  of debugging.
- The Verify section in each brief covers that commit's unit;
  per-commit verification is necessary but not sufficient (see
  end-of-plan section below for what it can't catch).
- A failing verify mid-plan is cheaper to fix than a failing verify
  after multiple commits are stacked.

### Why pause between commits

- Gives the user a moment to course-correct scope or design before
  the next commit's diff is locked in.
- Prevents auto-mode from sprinting through a multi-commit plan
  without checkpoints. The user reads the brief and decides whether
  to proceed or redirect.
- The pause is the single per-commit handoff. No extra approval
  prompts for sub-steps within a commit.

## Todo-list discipline

The cycle steps are tracked as explicit, separate todo items —
never collapsed into "implement commit N" as a single line.

The list is written in full at **Step 0**, before the first edit, not
grown commit by commit. It opens with the two Step 0 items themselves:

- Write this todo list
- Create and check out the branch on the plan's base, and confirm with
  `git branch --show-current`

For each commit, the todo list must contain these as distinct items:

- Brief commit N
- Implement commit N
- Fast-check commit N (the brief's Verify fast checks — not the full gate)
- Commit (or amend if audit findings landed)
- Audit commit N (run the isolated `synthesis-code-audit` skill, or your project's equivalent, on the commit's diff — never an inline audit)
- Amend if findings (the amend-over-new-commit rule applies)
- Full gate on commit N, once, after the amend
- Pause for user approval before commit N+1's brief

For the end of the plan, the todo list must additionally contain all
of these. **This list and the Workflow summary below are the same items
in the same order**; if they ever differ, that is the defect, not a
difference of scope.

- Final audit on the cumulative diff (`main...HEAD`, or your base range)
- End-to-end verification against a real runtime, including edge cases
- Test-sufficiency self-review
- Plan-conformance review, including whether the plan's own remaining
  gates are still executable
- Branch-wide reconciliation (shared numbers against the merge target;
  conventions discovered mid-plan)
- Address findings as new commits (the amend-over-new-commit rule
  does NOT apply at end of plan — see below)
- The project's changelog section, where it keeps one: a single heading
  for this change carrying the ticket key, with the PR number left as
  the project's placeholder until the PR exists
- Open the PR (your ship / PR-open step)
- Backfill the real PR number into that changelog heading once the PR
  is open

This block must carry all nine items: the five review gates and the
four close-out steps. It is the operative list at execution time, so
anything missing here is skipped in practice no matter how fully the
sections below describe it, and it sits directly above a warning about
collapsing items. The count is stated deliberately — "every gate"
would exclude the four close-out steps, which are the ones most often
dropped.

Collapsing these into fewer items is the most common failure mode.
Audit and verify get silently skipped because they look like part of
"implement". Keep them as separate items, mark each complete only
when actually done.

## Audit dimensions

Both per-commit audits and the end-of-plan general audit use the
10-dimension methodology in the `synthesis-code-audit` skill:
project-convention compliance, code reuse, consistency with existing
patterns, security, scalability, future-proofing, code quality, test
coverage, documentation, cleanup.

Project context (loaded via your project's agent-instruction file —
`CLAUDE.md`, `AGENTS.md`, or equivalent — and project docs) may
introduce additional lenses for specific kinds of work —
accessibility, performance budgets, privacy, compliance. Apply those
alongside the 10 dimensions where they're flagged as priorities.
The workflow itself is neutral on which lenses apply.

## End-of-plan phase

The per-commit cycle catches per-unit regressions but cannot catch
integration-level defects that span the full diff or only manifest
in a real runtime. Five **review gates** run **after the last commit's
per-commit cycle finishes** and **before opening the PR**. They are the
first five entries of the nine end-of-plan todo items above; the
remaining four are the findings commits, the changelog, the PR, and the
backfill. "The gates" in this document means these five reviews.

### 1. Final audit on the full diff

Run the isolated `synthesis-code-audit` skill (or your project's
equivalent) against `main...HEAD` (or the appropriate base range) —
same rule as per-commit audits: an isolated auditor, never an inline
pass. This is distinct from per-commit audits — the per-commit pass
scrutinizes a single commit in isolation; the final pass evaluates
the cumulative change as a whole.

What the final audit catches that per-commit audits miss:

- Cross-commit duplication (a primitive introduced in commit 3 that
  should have been reused in commit 7).
- Asymmetries that only become visible across multiple commits (read
  path filters X, write path doesn't — undocumented).
- Convention drift between sibling commits.
- Stale TODOs / debug code introduced in early commits and forgotten.

Findings land as a follow-up `refactor:`, `fix:`, or `docs:` commit
on the branch. **Do not amend prior commits at this stage.** They
may already be in someone's mental model; the follow-up commit makes
the audit-driven changes legible.

### 2. End-to-end verification against a real runtime

Per-commit verification typically runs against the test harness,
which uses fixtures, overrides, and in-memory or transactional-
rollback databases. Those harnesses bypass real production-shape
code paths (real session lifecycle, real connection pool, real
middleware ordering).

Bring up the actual local stack (`just dev` or the project's
equivalent), seed minimal prerequisites, and exercise every new
endpoint with curl or an equivalent. Verify:

- Happy paths return the documented status code and body.
- Error paths return the documented status codes (precondition
  failures, validation, auth, missing resources).
- Side effects persist after the response. Query the database
  directly to confirm rows are actually committed, columns are
  populated, version bumps fired, soft-deletes set the right
  columns. **This is the gate that catches bugs the test harness
  can't see**: an uncommitted write in the request's own persistence
  scope (in a Python web stack, for example, a missing
  `session.commit()` in the request dependency), middleware ordering
  issues, or environment-variable defaults that differ between test
  and runtime configuration.

### Edge cases to exercise during end-to-end

The happy-path runs are necessary but not sufficient. Every E2E run
must additionally exercise:

- **Boundary inputs:** maximum sizes, minimum sizes, empty payloads,
  oversize payloads (just above the cap to confirm the cap fires).
- **Malformed inputs:** invalid JSON, wrong types, missing required
  fields, extra fields where extras are forbidden.
- **Auth boundaries:** missing token, expired token, wrong role.
- **Concurrency:** where the feature has durability claims (writes,
  background workers), simulate a process kill mid-flight and
  confirm recovery on restart.
- **Adversarial values:** PII-shaped strings, injection-shaped
  strings, Unicode edge cases (combining marks, RTL overrides) if
  text fields are present.
- **Error paths return documented status codes:** every 4xx the
  endpoint promises is actually returned for the right input.

E2E findings often manifest as production-blocking bugs (the
symptom: tests pass, real runtime lies). Fix them in **new commits**
on the branch, not by amending. Like the final audit findings, the
amend-over-new-commit rule does not apply at end of plan.

### Why a separate end-of-plan E2E run matters

The integration-test harness in most projects wraps each test in an
outer transaction and rolls it back at teardown. That pattern is fast
and isolates tests, but it substitutes its own persistence scope for
the one production uses, so a write the production path never commits
is invisible to the suite. (In a Python web stack, for example, the
harness overrides the session dependency the request would otherwise
resolve.) The first time it surfaces is the moment a real client hits
the endpoint and the row doesn't persist.

Other classes of bug that test harnesses routinely miss: middleware
ordering, connection-pool exhaustion, environment-variable defaults
that differ between test and runtime, background-task lifecycle
issues, and any code path that depends on real network conditions.

A 30-minute E2E run at the end of an 8-commit plan is cheap
insurance against shipping that class of bug.

### 3. Test-sufficiency self-review

Ask, in the project's own terms, whether the testing performed is
enough to send this to review with confidence. Treat it as an
adversarial self-audit of coverage, not a formality.

Ground every candidate gap in real, shipping behavior first: a
surfaced item is only a gap if it covers an intended, in-design
surface on a code path real users reach. Do not add tests or
instrumentation for speculative, flag-gated or prototype elements —
closing a "gap" on a non-product surface is itself the over-reach the
plan exists to avoid. Then enumerate the real gaps: **untested
layers** (glue and wiring are the usual blind spot),
**wired-but-never-run surfaces** (statically audited but never
executed against a real runtime — unverified, not a pass), and
**unobserved branches** (the `else` of a new conditional, error paths,
alternate surfaces, every documented status code).

For each real gap: close it, or consciously accept it and surface it
in the PR with the residual-risk rationale. Accepting is the user's
call, not the implementer's.

### 4. Plan-conformance review

Did each commit do what was approved, and does the accumulated drift
change anything locked in the decisions file? This is what the
per-commit approvals structurally cannot see: eight commits each
defensible alone whose sum has moved away from what was agreed.

It also surfaces what a later commit revealed about an earlier one,
which could not have been known when the earlier one was approved.

**It also asks whether the plan's own remaining gates are still
executable.** This is the first reader holding both the plan and the
whole shipped result at once, and a gate that misfires when re-run
literally is a defect the same size as a commit that drifted. The
sharpest instance: a plan whose central question resolves *negative*
leaves its close-out gates written for the positive branch, and one
such gate required a merge message to state three facts that had all
become false. Following it literally writes falsehoods into permanent
history.

### 5. Branch-wide reconciliation

Two checks that are invisible to every per-commit audit, because each
commit was scoped to its own diff and to the branch rather than to
what it merges into.

**Reconcile numbers against the merge target, not the branch base.**
Where the plan allocated numbers in a file other branches also append
to — changelog or decision rows, ticket keys, migration versions —
re-derive the first free number against the merge target **now**, and
renumber. Also re-verify any "existing entries untouched" invariant
against the merge target: verifying it against the branch base proves
nothing if the base has moved.

**This gate has two beats, because a number cannot be made final
here.** Renumber now, so the branch is not obviously wrong and the
reviewer is not reading colliding identifiers. Then **hand the merger a
re-check**: say in the handoff which target commit the allocation was
derived against, and that it must be re-derived if the target has
moved since. A number derived before the merge can go stale while the
work is still in flight, and has — once inside a single commit's own
execution window, about ninety seconds. Only the merge pins the target,
and taking the merge is not this workflow's step.

**Sweep any convention discovered mid-plan back over the commits that
predate it.** Decide sweep-or-accept once, explicitly. Forward-only
application leaves the branch internally inconsistent in a way no
per-commit audit can see, because the early commits were correct under
the rules known at the time and the later ones under different rules.

**Whatever this gate changes lands as a new commit**, like every other
end-of-plan finding. Renumbering and sweeping both read as though they
touch earlier commits. They do not: no rebase, no amend.

## Workflow summary

**Once, before the first edit:**

0. Step 0 — write the whole todo list, then create and check out the
   branch and confirm with `git branch --show-current`.

**Per commit (N times):**

1. Brief → Execute → Fast-check → Commit → Audit → Amend if findings → Full gate (once) → Pause for user "go".

**End of plan (once):**

1. Final audit on `main...HEAD` → fix findings as new commits.
2. End-to-end run against the live local stack, including edge
   cases → fix findings as new commits.
3. Test-sufficiency self-review → close the real gaps, or accept and
   surface them.
4. Plan-conformance review → conformance, drift against locked
   decisions, whether the plan's own remaining gates still execute,
   patterns worth adopting as standards.
5. Branch-wide reconciliation → re-derive shared numbers against the
   merge target, and sweep any convention discovered mid-plan.
6. Address findings as new commits (never amendments, at this stage).
7. The project's changelog section, where it keeps one.
8. Then open the PR (your ship / PR-open step).
9. Backfill the real PR number into that changelog heading.

This list is canonical. Copies elsewhere — a progress document's
checkbox block, the pre-planning skill's handoff — follow it.
