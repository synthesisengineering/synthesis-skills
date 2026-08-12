# Handoff template

This file is the template the `synthesis-preplan` skill fills and previews to the user before handing off to your planning step. Slot placeholders use `{CURLY_BRACES}` and are replaced verbatim before preview.

## Slots

| Slot | Source | Required |
|---|---|---|
| `{TICKET_KEY}` | Ticket identifier (e.g., `PROJ-123`). `none` if no tracker. | yes |
| `{TICKET_URL}` | Full URL to the ticket. `none` if no tracker. | yes |
| `{DECISIONS_FILE_PATH}` | Path to the decisions file written in Step 5. | yes |
| `{BRANCH_BASE}` | Base branch the new work stacks on. | yes |
| `{WORKFLOW_DOC_PATH}` | **Resolved absolute path** to the bundled `references/commit-by-commit.md`, as it exists on the machine the planner runs on. See "Why this slot is absolute" below. | yes |
| `{PROJECT_LENSES_BLOCK}` | Populated when the project flags specific lenses (privacy, security, etc.); an empty string otherwise. See "Project-lenses block" below. | optional |

## Template body

Everything below the dashed line is the prompt body. Fill the slots and preview the result to the user.

---

Now let's write a plan. Use the commit-by-commit workflow defined in `{WORKFLOW_DOC_PATH}` — follow it exactly.

**Ticket:** {TICKET_URL}
**Ticket key:** {TICKET_KEY}
**Branch base:** {BRANCH_BASE}
**Locked decisions:** {DECISIONS_FILE_PATH}

Read the locked decisions file in full before drafting. The decisions are non-negotiable inputs to the plan — they were arrived at through explicit Q&A in the pre-planning skill and the user has already confirmed each one. If drafting the plan would require deviating from a locked decision, surface that as an open question rather than silently deviating.

{PROJECT_LENSES_BLOCK}

## Workflow requirements

The commit-by-commit workflow at `{WORKFLOW_DOC_PATH}` is the canonical reference. The points below are restated here so the plan inherits them directly. If the path above does not resolve, the restatement is sufficient to draft the plan; say so rather than stopping.

### Step 0, before any file is touched

The plan's todo list opens with these two items, and they run once, after the plan is approved and before the first edit:

1. Write the full todo list — every cycle step for every commit, plus the end-of-plan block. In full, not grown commit by commit: a list that arrives one commit at a time cannot show what is being skipped.
2. Create and check out the branch on the base named above, and confirm with `git branch --show-current` that the merge target is not checked out.

Both get skipped unless they are their own named items, and neither becomes visibly missing until commit time, which is the worst moment to find either.

### Per-commit todo discipline

Each commit's todo list must include these as **separate, explicit** items — never collapsed into a single "implement commit N":

1. Brief commit N (the Goal → Focus → How → Verify → Independence → Risks → Conflicts brief)
2. Implement commit N
3. Fast-check commit N (the brief's Verify fast checks: the commit's own tests, types, lint — NOT the full gate)
4. Commit
5. Audit commit N (run the isolated `synthesis-code-audit` skill, or your project's equivalent, on the commit's diff)
6. Amend if findings (the amend-over-new-commit rule applies — see below)
7. Full gate on commit N, once, after the amend (the whole-tree suite, including any container-backed integration tests), plus a re-run of the fast checks
8. Pause for user approval before commit N+1's brief

The brief's **Verify** section is split into *fast checks* (step 3) and *the full gate* (step 7). The full gate runs exactly once per commit and only after the audit's findings are amended in. Running it before the audit wastes a full run, because the audit routinely produces amendments and that run then tested code that no longer exists.

Collapsing these into fewer items is the most common failure mode. Audit and verify get silently skipped because they look like part of "implement". Keep them as separate items.

### Amend-over-new-commit rule

Findings discovered during a commit's per-commit audit and verify must be addressed by **amending the commit**, NOT by adding a new `fix:`/`refactor:` commit. The audit-fix pair is part of the same logical unit of work and hasn't been pushed yet; the amend keeps history clean.

This is a deliberate exception to the general "never amend" rule and applies only to per-commit findings before push.

### End-of-plan steps

After the last commit's per-commit cycle finishes, the plan's todo list must include these as **explicit, separate** items:

1. Final audit on the cumulative diff (`main...HEAD`, or your base range) — see the workflow doc for what this catches that per-commit audits miss
2. End-to-end verification against a real runtime, exercising:
   - The golden path
   - Edge cases: boundary inputs (max/min/empty/oversize), malformed inputs, auth boundaries, concurrency (process kill mid-flight if durability is claimed), adversarial values (PII-shaped strings, injection-shaped strings, Unicode edge cases), and confirmation that every documented error status code is actually returned
3. Test-sufficiency self-review — judge whether the testing is enough to send to review with confidence. **First ground every candidate gap in real, shipping behavior**: confirm it covers an intended, in-design surface on a code path real users reach (check the design, the feature-flag registry, and the code). Do NOT add instrumentation/tests/abstractions for speculative, flag-gated, prototype, or not-yet-designed elements — closing a "gap" on a non-product surface is itself over-reach; leave it or delete the dead UI. Then enumerate the real gaps: **untested layers** (new code with no automated test — glue/integration code like UI effects, hooks, wiring, middleware is the usual blind spot); **wired-but-never-run surfaces** (implemented and audited but never executed against a real runtime — treat as unverified, not a pass); and **unobserved branches** (fallbacks/the `else` of a new conditional, error paths, alternate surfaces like desktop vs mobile, every documented status code). For each real gap, close it (run it or add a test) or consciously surface it in the PR with the residual-risk rationale.
4. Plan-conformance review — did each commit do what was approved, does the accumulated drift change anything locked in the decisions file, **and are the plan's own remaining gates still executable** (a gate written for a positive outcome misfires when the plan's central question resolves negative, and a gate that restates facts rather than referencing the artifact of record can require writing falsehoods)
5. Branch-wide reconciliation — two checks no per-commit audit can see, because each was scoped to its own diff and to the branch rather than to what it merges into. **Re-derive any number the plan allocated in a shared append-only file** (changelog or decision rows, ticket keys, migration versions) against the **merge target**, not the branch base, and renumber; re-verify any "existing entries untouched" invariant against the merge target too; and tell the merger which target the allocation was derived against, since only the merge pins it. **Sweep any convention discovered mid-plan** back over the commits that predate it, deciding sweep-or-accept once rather than applying it forward only
6. Address findings as **new commits** — the amend-over-new-commit rule does NOT apply at end of plan
7. The project's changelog section, where it keeps one: one heading carrying the ticket key, with the PR number left as the project's placeholder
8. Open the PR (your ship / PR-open step), which finishes by emitting a one-line, paste-ready PR blurb for the user
9. Backfill the real PR number into that changelog heading once the PR exists

The workflow document governs this list. When it changes, this copy changes with it.

### Plan output expectations

Produce the plan as a document with this exact structure:

1. **Title + metadata** — ticket key/URL, branch base, decisions-file path, date.
2. **Goal** — what the work buys the system, in plain terms.
3. **Context** — current state, why now, what it builds on, constraints found in the codebase.
4. **Decisions** — ALL decisions, rewritten into the plan and grouped by topic (decision / choice / why). Include not only the locked Q&A decisions from the decisions file but every decision taken from the ticket, project conventions, and the codebase. The plan must be self-contained on decisions.
5. **Commits** — in execution sequence. Each commit:
   - heading = the commit's own top-level goal;
   - **Goal** (one line) · **Character** (`mechanical` or `judgment` — determinate once the plan is read, or a choice still being made inside the commit; diff size is not the signal) · **Changes** (what + files) · **Verification** (concrete, testable steps with expected results, split into fast checks and the full gate) · **Risks to flag to audit** (what the per-commit audit must scrutinize).
   - Commits are always run in order — do NOT include ordering, dependency, or "depends on commit N" notes; sequence is implicit. (Operation order inside a single commit, e.g. within one migration, is a Verification/Risk item.)
   - Every commit must be independently testable and sized as one coherent reviewable unit — none too large or too small.
6. **E2E strategy** — explicit end-to-end validation for the whole change: golden path plus edge cases (boundaries, malformed input, auth boundaries, concurrency, adversarial values, every documented error code).
7. **Mandatory gates** — as explicit todo items, not prose: the two Step 0 items above (write the full todo list, then create and check out the branch and confirm it), then the nine end-of-plan todo items listed under "End-of-plan steps" above, in that order. (The first five of those are the review gates; the last four are the findings commits, the changelog, the PR, and the backfill.)

Strict adherence to the locked decisions; plans that diverge are returned for revision. The per-commit **Verification** and **Risks to flag to audit** subsections are the mandatory verify and audit todos — establish them in the plan, never improvise at execution time.

---

## Why this slot is absolute

`{WORKFLOW_DOC_PATH}` is the one slot that must be resolved to an absolute path rather than left relative.

The body above becomes the planner's prompt, and Step 6 of the skill explicitly supports handing it to a planning subagent or a fresh planning pass in a clean context. That planner's working directory is the project root, not the installed skill directory, so a relative `../references/` path points nowhere for exactly the handoffs the skill is designed around. Resolve it at fill time, from the skill's own installed location, and the pointer survives the context boundary.

The restated requirements below the pointer are the reason a dead path degrades rather than breaks. That is a safety net, not a substitute: the canonical document carries material the restatement does not.

## Project-lenses block

When the project flags specific lenses as priorities for this work (privacy, security, accessibility, performance, compliance, or others — check the project's agent-instruction file and project docs), populate `{PROJECT_LENSES_BLOCK}` with a note like the one below, naming the lenses that apply. Otherwise leave it empty.

```
**Project lenses apply.** This ticket touches areas the project flags
under <name the lenses: e.g. privacy, security, accessibility>. Apply
those lenses alongside the standard code-review dimensions. The
trade-off rule applies: prefer the lens-preserving option when costs
are equivalent; surface the gap and take the cheap path when costs
diverge. These considerations belong inside every audit pass
(per-commit and end-of-plan), not as a separate gate.
```

## Notes for the pre-planning skill

- Preview the filled template inline before handing off to the planner. Tell the user: "Preview before I hand this to the planner — edit anything, or say 'go'."
- If the user provides an edited version, use it verbatim. Don't re-apply slot replacements after the user edits.
- Hand the final prompt to your planning step — a dedicated plan mode, a planning subagent, or a fresh planning pass in a clean context. The plan output is the next thing the user reads.
- Do not include conversation context, prior reasoning, or commentary in the prompt to the planner. The locked decisions file plus this prompt are the complete handoff.
