# Commit-by-commit workflow

The canonical workflow for executing multi-commit plans. Referenced by
the `synthesis-preplan` skill (which produces the inputs) and by your
planning step (which consumes this doc when drafting the plan). Used
directly when executing a plan by hand.

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

## Briefing structure

Every pre-commit briefing has these sections, in order:

**Goal** → **Focus** → **How** → **Verify** → **Independence** → **Risks** → **Conflicts**

The **Verify** section is a numbered list of `command` → `expected
outcome` pairs, plus a one-line note on any gates that can't be
checked locally (e.g., remote CI like GitHub Actions or Bitbucket Pipelines runs only after push).

Verification is its own section, not a tail bullet inside How. When
it lives at the end of a How list it gets skimmed past or skipped.
Surfacing it as a first-class section makes "what proof looks like"
visible before the commit is final.

## Per-commit cycle

Do not skip steps. Do not bundle.

1. **Brief** the commit (Goal → Focus → How → Verify → Independence → Risks → Conflicts).
2. **Execute** the implementation.
3. **Run the Verify section commands.** Confirm each expected outcome
   before proceeding.
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
7. **Re-run the Verify section commands** after the amend. The
   audit-driven changes may have shifted behavior; the original
   Verify run was against pre-fix code.
8. **Pause and wait for user approval** before starting the next
   commit's brief, even in auto mode. The brief is the natural
   checkpoint; the user can always say "go" to advance, but the
   default is to wait.

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

For each commit, the todo list must contain these as distinct items:

- Brief commit N
- Implement commit N
- Verify commit N (run the brief's Verify commands)
- Commit (or amend if audit findings landed)
- Audit commit N (run the isolated `synthesis-code-audit` skill, or your project's equivalent, on the commit's diff — never an inline audit)
- Amend + re-verify if findings (the amend-over-new-commit rule applies)
- Pause for user approval before commit N+1's brief

For the end of the plan, the todo list must additionally contain:

- Final audit on the cumulative diff (`main...HEAD`, or your base range)
- End-to-end verification against a real runtime, including edge cases
- Address findings as new commits (the amend-over-new-commit rule
  does NOT apply at end of plan — see below)
- Open the PR (your ship / PR-open step)

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
in a real runtime. Two additional gates run **after the last
commit's per-commit cycle finishes** and **before opening the PR**.

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
  can't see**, such as a missing `session.commit()` in the request
  dependency, middleware ordering issues, or environment-variable
  defaults that differ between test and runtime configuration.

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

The integration-test harness in most projects uses a session
override that wraps the test in an outer transaction and rolls it
back at teardown. That pattern is fast and isolates tests, but it
short-circuits the real `get_session` dependency — so a missing
commit in the production dependency is invisible to the suite. The
first time it surfaces is the moment a real client hits the
endpoint and the row doesn't persist.

Other classes of bug that test harnesses routinely miss: middleware
ordering, connection-pool exhaustion, environment-variable defaults
that differ between test and runtime, background-task lifecycle
issues, and any code path that depends on real network conditions.

A 30-minute E2E run at the end of an 8-commit plan is cheap
insurance against shipping that class of bug.

## Workflow summary

**Per commit (N times):**

1. Brief → Execute → Verify → Commit → Audit → Amend if findings → Re-Verify → Pause for user "go".

**End of plan (once):**

1. Final audit on `main...HEAD` → fix findings as new commits.
2. End-to-end run against the live local stack, including edge
   cases → fix findings as new commits.
3. Then open the PR (your ship / PR-open step).
