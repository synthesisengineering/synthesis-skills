---
name: synthesis-preplan
description: >
  Architecture-decision pre-planning for tickets or issues with real design
  choices. Resolves delegated technical decisions and asks structured questions
  for choices the user owns, then hands a reviewable decision set to the planning
  step. Use when asked to: preplan, pre-plan this
  ticket, let's pre-plan, lock decisions for, design questions for, what are the
  open questions on, plan a ticket with real design choices.
license: "CC0-1.0"
user-invocable: true
depends_on: ["synthesis-code-audit"]
metadata:
  author: "Emil Peñalo"
  version: "1.1.0"
  source_repo: "github.com/synthesisengineering/synthesis-skills"
  source_type: "public"
---

# Synthesis Preplan — Architecture-Decision Locker

Resolves architectural choices on tickets or issues, records their owners and evidence, and hands a decision set to the planning step. Use Q&A for choices the user owns; decide technical choices inside delegated work.

## Decision ownership and execution mode

Apply the shared [decision ownership contract](../synthesis-thinking-framework/references/decision-ownership.md) before asking or locking a choice. Record `supervised` or `delegated`, its controlling instruction, delegated scope and remaining approval gates. User and project instructions take precedence over this workflow's defaults. Existing grants remain usable within their scope; preferences and packet records do not create authority.

For an explicitly supervised preplanning session, pause at the assessment, decision summary and handoff review points below. For delegated work, publish those artifacts as checkpoints and continue through technical choices without another approval. An explicit user-requested pause remains binding in either mode. Keep the same verification and independent audit obligations.

The skill exists because the hard part of planning is **deciding what to build**, not breaking the build into commits. Once architectural decisions are locked, the commit-by-commit plan is mechanical. This skill makes the decision-locking explicit so your planner inherits a clear, reviewable input instead of designing inside its own output.

### Where this sits

This skill runs **before** any code exists, on the architectural layer: which base branch, what's in and out of scope, and the design questions a competent engineer could answer more than one way. Two siblings sit next to it:

- `synthesis-code-planning` evaluates **code-level** approaches once the architecture is settled — competing implementations of a decision this skill has already locked. Reach for it inside a commit; reach for this skill before the commit list exists.
- `synthesis-preflight` is the **pre-merge** gate at the other end of the arc. The plan this skill hands off ends in that gate.

The full lifecycle: preplan → code-planning → implementation-integrity → code-audit → preflight → pr-review.

## When to use

Heuristic: a competent engineer could reasonably implement this ticket in three or more valid ways AND the choice has long-term consequences. Apply for:

- Backend infrastructure / substrate tickets (the ones with "Open questions for implementer" sections)
- Cross-cutting changes (schema + code + ops surface all touched)
- Tickets with real architectural alternatives, not just "implement X"
- Privacy / security-sensitive tickets where defaults matter
- Tickets stacked on in-flight work where the parent's choices constrain the child

## When not to use

Skip for:
- Simple bug fixes (plan directly, or no plan at all)
- UI tweaks, copy changes, dependency bumps
- Tickets with one obvious implementation path
- Things already designed in the current conversation that just need to be executed

If the task is ambiguous, inspect its constraints and existing design first; ask only when missing information materially changes the requested outcome.

## Step 1: Source-of-truth grounding

1. Read the ticket. Fetch it from your issue tracker (Jira, GitHub Issues, Linear, or whatever the project uses) **including comments** — dev notes appended after the original body often add scope, constraints, or alternative directions that materially change the design.
2. Read predecessor branches / PRs / tickets that this work stacks on or depends on. Inspect the codebase for already-shipped pieces this ticket builds on. Constraints set by the parent shape the child.
3. Read the roadmap document if the project maintains one (check the project's agent-instruction file — `CLAUDE.md`, `AGENTS.md`, or equivalent — and project docs for its location).
4. Identify the dependency graph: what's upstream (constrains design), what's downstream (consumes this work), what's parallel (shares assumptions but ships independently).

**Soft-fail behavior.** If the tracker is unavailable, warn the user, ask them to paste the ticket body and comments inline, then proceed. The skill works for any context: a Jira ticket, a GitHub issue, a written-up Linear ticket, or a planning doc. Privilege primary sources but don't require them.

## Step 2: Initial assessment

Produce five short artifacts before any planning:

1. **One-sentence ticket goal.** What the ticket buys the system, stated as plainly as possible.
2. **Branch stacking recommendation.** Which base branch this work should be cut from, and why. Walk through 2–3 candidate bases if the choice is non-obvious, with pros/cons each.
3. **Dependency clarification.** Depends on (X, Y, Z); does NOT depend on (A, B, C). Eliminate common misconceptions explicitly.
4. **Scope boundary statement.** Requested deliverables, explicit exclusions and unresolved dependencies. Do not quietly turn an unfinished requirement into an exclusion.
5. **Execution lane, with a one-line reason.** Either the full commit-by-commit workflow ([references/commit-by-commit.md](references/commit-by-commit.md)) or the single-commit workflow ([references/single-commit.md](references/single-commit.md)); the latter file owns the routing test and its disqualifiers. State the lane explicitly even where the project declares a default, and name the condition or disqualifier that decided it. A lane inherited silently is the failure this artifact prevents, and it fails in both directions: a ticket routed heavy because the session was in a planning frame, and one routed light because it looked small. If the lane is single-commit, the rest of this skill usually does not apply — say so and stop, rather than producing a decisions file for work that decides nothing.

In supervised mode, confirm the assessment before moving on. In delegated mode, record it and continue, raising only material outcome ambiguity or an unsatisfied approval gate. Architectural disagreements still require evidence and disposition by their owner.

## Step 3: Preliminary plan with load-bearing decisions surfaced

Produce a commit-shaped preliminary plan with three explicit parts:

1. **Load-bearing decisions stated up front.** A numbered list of the architectural choices the rest of the plan rides on. Each one is one or two sentences. Be precise — vague decisions become disagreements later.
2. **Task breakdown (commits).** Each commit gets one paragraph: what it does (the "what") and why this seam (the "why"). Don't write the implementation here.
3. **Open questions called out at the bottom.** Each question gets a one-line summary and is fully expanded in Step 4. The point at this stage is to make the question list visible.

The preliminary plan is not the real plan. It's a vehicle to surface architectural questions that must be decided before the real plan can be written. Stating load-bearing decisions explicitly forces you to confront them rather than baking them silently into commits.

## Step 4: Open-questions Q&A loop

Classify each open question by the shared decision ownership contract. Apply predetermined choices directly. Resolve delegated technical choices with a concise record. For each question that belongs to the user, present:

1. **The question, restated cleanly.** One sentence.
2. **Concrete options.** The viable alternatives, each labeled in one line. Do not manufacture alternatives ruled out by the constraints.
3. **Why it matters.** The consequence of getting it wrong. Reference the relevant audit dimension(s) lightly when applicable — privacy for routing decisions, security for input validation boundaries, future-proofing for cutover points. Not a formal scorecard, just a habit baked into the rubric.
4. **Recommended lean.** The option you'd take and why, in 2–3 sentences.

### The three response modes

The user replies in one of three modes. Recognize all three:

- **Accept** — short approval ("yes", "go with that", "approved"). Lock the lean, move on.
- **Redirect** — short directive picking an alternative ("do option 2", "no, the other one"). Lock the alternative, move on.
- **Depth** — they ask for more reasoning ("explain further", "why so strict", "what's the long-term shape"). Expand with:
  - First-principles re-derivation if the question is foundational
  - Tier ladders if there's a scaling axis (MVP → next step → ceiling)
  - Tradeoff matrices if there are multiple comparable axes
  - Concrete code shapes if the abstract argument isn't landing
  - **Willingness to fully reverse the lean** if the user's pushback exposes a flaw in the original reasoning

The depth mode is where the real value is. Pushback that exposes a flaw is the highest-leverage moment in the workflow. Genuinely reconsider rather than defend.

### Loop continuation

Resolve each question through its owner. New factual evidence may reopen a premise; record the amendment and invalidate its dependent checks. A pending user question blocks its dependent work only, and silence never supplies a ruling.

Track locked decisions as you go. At any time the user can ask for a partial summary; produce a running table of what's locked and what's still open.

## Step 5: Decision summary file

When all open questions are resolved, write a decision summary file to:

```
plans/<ticket-slug>-decisions.md
```

This path is relative to the project root and is the default. If your agent-instruction file (`CLAUDE.md`, `AGENTS.md`, or equivalent) specifies a different home for planning artifacts, use that instead. Use the ticket key in the slug (e.g., `payments-webhooks-decisions.md`), or a descriptive slug if the ticket isn't from a tracker.

### File structure

```markdown
# <Ticket key>: <Ticket title> — Locked decisions

Source: <ticket URL>
Branch base: <branch name>
Project lenses: <e.g. privacy, security, accessibility, performance — whichever your project flags; "none" otherwise>
Last updated: <YYYY-MM-DD>
Execution mode and source: <supervised or delegated; controlling instruction>
Delegated scope: <technical choices and permitted work>
Remaining approval gates: <owner, exact action and required source; none if satisfied>

## <Topic group 1>

| # | Decision | Choice | Why | Owner / source | Reopen if |
|---|---|---|---|---|---|
| 1 | ... | ... | ... | ... | ... |

## <Topic group 2>

| # | Decision | Choice | Why | Owner / source | Reopen if |
|---|---|---|---|---|---|

## Out of scope

| # | Decision | Choice | Why | Owner / source | Reopen if |
|---|---|---|---|---|---|

## Documentation & conventions

| # | Decision | Choice | Why | Owner / source | Reopen if |
|---|---|---|---|---|---|
```

Group rows by topic. Each row records the choice, one-line reason, owner, authority source and reopening condition. A linked per-row record may hold long references. Documentation and explicit scope exclusions are load-bearing groups; include them without recategorizing incomplete deliverables.

**Where the project keeps a changelog, the documentation group must carry a changelog row.** Decide here what the change's section says: which subsections it needs (`Added` / `Changed` / `Fixed` / `Removed` / `Security`, or the project's own set) and the one user- or operator-visible fact each records — or that the change does not qualify, with the reason. Deciding it at this stage is what keeps it from being discovered at push time, when it becomes a scramble to reconstruct what shipped.

Show the decision summary after writing. In supervised mode, obtain its requested confirmation before Step 6. In delegated mode, checkpoint it and proceed within the recorded grant.

## Step 6: Handoff to your planning step

When the summary is resolved under its recorded decision owners:

1. **Load the handoff template** from [assets/handoff-template.md](assets/handoff-template.md).
2. **Fill the slots:**
   - `{TICKET_KEY}` — e.g., `PROJ-123`, or `none` if there's no tracker
   - `{TICKET_URL}` — the tracker URL, or `none`
   - `{DECISIONS_FILE_PATH}` — path to the file written in Step 5
   - `{BRANCH_BASE}` — base branch name
   - `{EXECUTION_CONTRACT}` — execution mode, controlling instruction, decision owners, delegated scope and remaining approval gates; never claim individual user approval for agent-selected choices
   - `{WORKFLOW_DOC_PATH}` — the **resolved absolute path** to this skill's `references/commit-by-commit.md`, derived from wherever the skill is installed on this machine. Resolve it, do not paste a relative path: the filled body becomes the planner's prompt, and a planning subagent or fresh-context pass runs from the project root, where `references/` does not exist. Confirm the path resolves before previewing.
   - `{PROJECT_LENSES_BLOCK}` — populated if the project flags specific lenses (privacy, security, accessibility, performance, compliance); empty otherwise
3. **Show the filled prompt.** In supervised mode, wait for the requested handoff approval. In delegated mode, record the handoff and continue; the preview is a checkpoint, not a new permission request.
4. **Accept user steering.** Incorporate supplied edits and retain their authority. A new instruction changes only the affected portion of the plan and its evidence.
5. **Hand off to your planning step.** Pass the final prompt to whatever planning mechanism your agent provides — a dedicated plan mode, a planning subagent, or a fresh planning pass in a clean context. The plan output is the next thing the user reads.
6. **Persist the returned plan to a document (required).** Write the plan to `plans/<ticket-slug>-plan.md` (same slug as the decisions file, with `-plan` instead of `-decisions`). Many planners run read-only or in an isolated context — their output comes back only as a message, is not on disk, and does not survive context compaction — so persist it yourself as soon as it returns. Fold in any decisions the user redirected during or after the handoff so the document is the final plan, not the pre-handoff draft. The document must follow the **Plan document format** below. Tell the user the path. This is not optional, and the user should never have to ask for it.

The persisted plan and decision summary are the durable handoff. Supervised execution waits at the agreed review point. Delegated execution continues through the recorded plan and its actual remaining gates.

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

## Q&A rubric details

A few patterns to apply consistently inside the Q&A loop:

- **Don't ask questions you can answer from the source of truth.** If the ticket comments already lock a choice, fold it into the load-bearing decisions in Step 3 rather than presenting it as an open question.
- **Don't bundle unrelated questions.** Each open question is independent — independently reviewable, independently lockable. Two coupled decisions get presented as one question with the coupling stated.
- **Use the lean to anchor, not to prescribe.** The lean is the recommendation; the user can take it or move past it without justification. Don't make redirects feel like pushback.
- **Surface privacy / security / scaling implications inside "why it matters".** This is where your code-review dimensions (see the `synthesis-code-audit` skill, or your project's review checklist) get applied early — bake them into the rubric so the resulting plan inherits the audit posture.
- **Note when a decision is forced by the ticket itself.** Some questions only exist because the ticket left them open. Others are forced by an upstream commit or by a project convention. Calling out which is which helps the user know how much latitude they have.

### Three checks that catch a bad decision before it is locked

Decision quality starts here and in Step 3. An audit verifies implementation against the recorded decisions and may challenge a premise with new factual counterevidence. It routes an amendment to that decision's owner rather than silently replacing the yardstick or knowingly verifying an invalid premise.

These three exist because a real run produced a mechanism that satisfied its acceptance criterion by forcing the outcome, passed a careful isolated audit that found a genuine bug *inside* it, and was only caught when a human asked whether it should exist at all.

- **Check every decision against what the downstream tickets consume.** Mechanical, so it survives a dull ticket and a tired author: the dependency graph from Step 1 already names what is downstream. For each locked decision, ask what those tickets read from this work's output, and whether this decision distorts it. The live case: a guarantee that every result row contained at least one item of a given kind pinned that count to a constant, and the very next ticket existed to *measure* that count. The conflict was visible at plan time and nobody looked.
- **Ask what each mechanism makes unobservable.** Any guarantee, floor, quota or minimum pins a variable. Whatever measured that variable now measures the guarantee instead. Before locking a mechanism that forces an outcome, name what can no longer be learned, and check it against the previous bullet. Related: **an acceptance criterion satisfied by fiat is not met.** If the answer to "how do we know X happens?" is "because we force it", that is not evidence, and the row's *why* should say so.
- **Before adding a mechanism to prevent an outcome, ask whether the outcome is a defect or the model working.** An absence is not automatically a gap. In the live case, a low-scoring item being crowded out of a row was the scoring model correctly reporting that it had better evidence; it was read as a hole and a mechanism was invented to plug it. This is the design-time twin of the test-sufficiency gate's grounding rule, and it reduces scope at least as often as it adds it.

**A mechanism introduced inside a lean becomes its own numbered decision.** Record its purpose, viable alternatives, consequences and owner using Step 4. A technical mechanism may be delegated; it must not silently inherit authority for a new external action from the surrounding recommendation.

## Skip-Q&A behavior

If the user says "just give me the plan," honor that cadence. Resolve technical choices from the available evidence and make them explicit in the plan, with owners and assumptions. Ask only for material missing facts or actual principal-only gates; skipping Q&A does not require hiding decisions.

## Soft-fail behaviors

- **Tracker unavailable** → warn, ask user to paste ticket body + comments inline, proceed.
- **No predecessor branch information** → warn, proceed with what's available.
- **Project lenses unspecified** → apply none unless the user states them explicitly.
- **No agent-instruction file** → no project-specific rules applied; use only general conventions.

In every soft-fail case, name what's missing in one sentence so the user knows to fill the gap. Don't silently drop quality.

## Rules

- **Don't skip the source-of-truth fetch.** Ticket comments, parent branches, and project docs frequently contain the decisions you'd otherwise re-litigate. Read them.
- **Don't author the plan inside this skill.** The skill's job is locked decisions + the handoff prompt; the planner authors the commit breakdown. Persisting the planner's returned plan to a file in Step 6 is not authoring — do that.
- **Two durable artifacts: the decision summary file and the plan document.** Both survive context compaction; the conversation log and the planner's output do not. Step 5 writes the decisions; Step 6 writes the plan to `plans/<ticket-slug>-plan.md` after the planner returns (many planners cannot write files themselves, so the orchestrator must).
- **Carry the execution contract in the handoff.** Show the prompt; wait only at the review points the controlling instruction requires. A planner must inherit delegation as well as any explicit supervised pauses.
- **Lean don't dictate.** Every open question has a recommendation; every recommendation can be redirected with one word.
- **Reverse leans freely when pushed back on with a real argument.** Depth mode often exposes flaws in the initial framing. Reconsider honestly rather than defending the original lean.
- **The commit-by-commit workflow lives at [references/commit-by-commit.md](references/commit-by-commit.md).** The handoff template references it; don't duplicate the rules inside the handoff.
- **State the execution lane before touching a file.** The single-commit lane at [references/single-commit.md](references/single-commit.md) owns the routing test. Naming the lane and its reason is Step 2's job; inheriting one silently is what that artifact exists to prevent.

## Acknowledgments

This skill was proposed by [Emil Peñalo](https://github.com/EPenaloColon)
([issue #4](https://github.com/synthesisengineering/synthesis-skills/issues/4)),
whose proposal shaped the decision-locking loop it runs.
