# Plan document format

The required shape of every persisted plan, and the rules for the gates a plan writes, as written in 1.1.0. The handoff template carries the same requirements.

Contents:
- Plan document format: title, goal, context, decisions, commits, E2E strategy, mandatory gates
- Gates state their subject by reference, never by restating its content
- Any gate that can resolve negative carries a negative branch, written at plan time
- Test-sufficiency self-review (end-of-plan gate)
- Branch-wide reconciliation (end-of-plan gate)
- Numbers allocated in shared append-only files are provisional

## Plan document format

Every persisted plan (and the planner's output it is built from) MUST follow this structure. The handoff template carries the same requirements so the planner emits this shape directly.

1. **Title + metadata** — ticket key/URL, branch base, decisions-file path, date.
2. **Goal** — what the work buys the system, in plain terms. Always present.
3. **Context** — the surrounding situation: current state, why now, what it builds on, and the constraints discovered from the codebase. Always present.
4. **Decisions** — ALL decisions rewritten into the plan, grouped by topic, each as decision / choice / why / owner and source / reopening condition. Include the execution mode and remaining gates. Not only the Q&A-locked ones from the decisions file: include every decision taken from the ticket, from project conventions, and from the codebase. The plan must be self-contained on decisions — a reader should not need the decisions file open.
5. **Commits** — each commit, in execution sequence:
   - The heading is the commit's own top-level goal.
   - **Goal** — one line: the single thing this commit accomplishes.
   - **Character** — `mechanical` or `judgment`. Mechanical means the work is determinate once the plan is read: a rename sweep, a docs pass, a fixture update. Judgment means a choice is still being made inside the commit. Diff size is not the signal — the largest diffs are usually the most mechanical, and the commit that decides how two subsystems talk can be twenty lines. It tells the reviewer at each pause where the real decisions sit, and it steers how hard the audit looks; it is not a license to check a mechanical commit less carefully.
   - **Changes** — what it does and the files touched.
   - **Verification** — concrete, testable steps that prove the commit works (commands, expected results), split into **fast checks** (the commit's own tests, types, lint; run before the commit) and **the full gate** (the whole-tree suite; runs once, after the audit's findings are amended in). Every commit must be independently testable; a commit that cannot be verified on its own is mis-scoped.
   - **Risks to flag to audit** — the specific things the per-commit audit must scrutinize.
   - In this serial commit lane, sequence supplies the dependency order. Keep the larger task's dependency graph when independent delegated work runs alongside it. Intra-commit operation order belongs in Verification/Risks.
   - Size: no commit too large or too small — one coherent, reviewable unit each.
6. **E2E strategy** — an explicit end-to-end validation strategy for the whole change: golden path plus edge cases (boundaries, malformed input, auth boundaries, concurrency, adversarial values, and every documented error code).
7. **Mandatory gates** — as explicit todo items, not prose. Opening with the two **Step 0** items the workflow requires once, after the plan is approved or resolved under delegation and before any implementation file is touched: write the full todo list, then create and check out the branch on the base named above and confirm with `git branch --show-current`. Both are hard requirements and both get skipped unless the plan names them, because neither becomes visibly missing until commit time. Then the end-of-plan todos: final audit on the cumulative diff (`main...HEAD` or your base range), the E2E run, a **test-sufficiency self-review** (see below), a **plan-conformance review** (did each commit follow its recorded plan and decision owners, does the accumulated drift change anything locked in the decisions file, **and are the plan's own remaining gates still executable**), a **branch-wide reconciliation** (see below), address findings as new commits, the **changelog section** decided in the decisions file where the project keeps one (written, ticket key in the heading, PR number placeholder), then open the PR (your ship / PR-open step), then **backfill the real PR number** into that heading. The order matters: the changelog is written after the findings commits, so it describes what actually ships rather than a pre-findings branch.

The per-commit **Verification** and **Risks to flag to audit** subsections ARE the mandatory verify and audit todos (the commit-by-commit workflow requires both as separate items). They are established in the plan, never improvised at execution time.

### Gates state their subject by reference, never by restating its content

A gate that enumerates facts freezes them at plan time. Write "state what the ticket's outcome section states", not a list of the three things the outcome is expected to be. The list is what goes stale, and it goes stale inside the artifact a gate is about to write.

The live case: a squash-merge gate required the message to state "the new authoritative origin", "the recovery-only status of the old address", and "the one-time install migration". The plan's central question resolved negative, so three of the four became false, and following the gate literally would have written falsehoods into permanent history. This is the same "planned state recorded as present fact" defect that ordinary documents get audited for; the gate list is simply the last place anyone thinks to look for it.

### Any gate that can resolve negative carries a negative branch, written at plan time

If the plan contains a decision gate whose outcome may be "no", pre-specify what a negative changes about **closing**, not only about the commit list. A plan can pre-authorize the negative outcome in the strongest terms and still leave its own close-out gates written as though it could not happen.

At minimum, name what a negative does to: the merge or PR message, the E2E strategy, any version bumps, the test-sufficiency scope, the acceptance criteria, and the ticket's status wording. Four or five lines, drafted while the positive bias is visible and cheap to counter.

Related: **a re-scope block enumerates every section it touches, with a status per section** — superseded, unchanged, or rewritten, as a table. A block that names only the sections its author was thinking about leaves everything that merely *derived* from them still asserting the old branch, and the cost shows up distributed across later commits, each correcting plan prose by hand.

### Test-sufficiency self-review (end-of-plan gate)

After the E2E run and before you open the PR, the plan MUST include an explicit step that asks, in the project's own terms: **is the testing performed enough to send this to review with confidence?** Treat it as an adversarial self-audit of coverage, not a formality. Enumerate, concretely:

- **Ground every gap in real, shipping behavior first.** A surfaced item is only a gap if it covers an intended, in-design product surface that exists on a code path real users reach. Before treating anything as a gap to close, check it against the design, the feature-flag registry, and the existing code. Finding an untracked element is **not** automatically a gap: do not add instrumentation, tests, or abstractions for speculative, flag-gated, prototype, or not-yet-designed elements (a feature-flagged preview, leftover prototype markup, a hypothetical future surface). Closing a "gap" on a non-product surface is itself the speculative over-reach the plan exists to avoid; the right move there is to leave it alone or delete the dead UI, never to cover it. This review reduces scope as readily as it adds it.
- **Untested layers.** Which new code has no automated test? Glue/integration layers (UI effects, hooks, wiring, middleware) are the usual blind spot, and are exactly where the per-commit unit tests do not reach. Name them.
- **Wired-but-never-run surfaces.** Which code paths were implemented and statically audited but never actually executed against a real runtime? A surface that has only been typechecked and read is **unverified**, however clean the audit — treat it as a gap, not a pass (once it has cleared the grounding check above).
- **Unobserved branches.** Which documented behaviors were not directly observed: fallbacks (the `else` of a new conditional), error paths, alternate surfaces (desktop vs mobile), and every documented status code? The happy path passing does not cover the branch that does the opposite.

For each **real** gap (one grounded in shipping behavior): **close it** (run it, or add the missing test), or route the residual-risk decision to its recorded owner. The designated integrator may decide technical sufficiency within delegated acceptance criteria; changing a required criterion needs its actual owner's authority. Surface the rationale in the PR, and never turn missing evidence into a pass. Runtime-only bugs frequently live in the untested glue layer. Findings from this review are addressed as new commits, including removal of coverage or code the grounding check exposes as speculative.

### Branch-wide reconciliation (end-of-plan gate)

Two checks no per-commit audit can perform, because each commit was scoped to its own diff and to the branch rather than to what it merges into. Both land as new commits, like every other end-of-plan finding — neither is a rebase or an amend, however much renumbering reads like one.

**Re-derive any number the plan allocated in a shared append-only file** — changelog or decision rows, ticket keys, migration versions — against the **merge target**, not the branch base, and renumber. Re-verify any "existing entries untouched" invariant against the merge target too: checked against the branch base it proves nothing once the base has moved, and every per-commit audit will faithfully confirm the invariant the plan named while the plan names a number a concurrent branch has already taken.

**Sweep any convention discovered mid-plan back over the commits that predate it.** Decide sweep-or-accept once, explicitly. Applied forward only, the branch is left internally inconsistent in a way no per-commit audit can see, because the early commits were correct under the rules known at the time and the later ones under different rules, and the cost then shows up distributed across the review.

### Numbers allocated in shared append-only files are provisional

Where the plan allocates a number in a file other branches also append to, **state the allocation as provisional** in the plan itself and put the re-derivation in the close-out gates above. A number cannot be made final before the merge, because only the merge pins the target. Renumber at the reconciliation gate so the reviewer is not reading colliding identifiers, then hand the merger the re-check: which target commit the allocation was derived against, and that it needs re-deriving if the target has moved. A number derived before the merge can go stale while the work is still in flight; in one run it went stale twice, the second time within ninety seconds of being committed.
