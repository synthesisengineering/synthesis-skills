# The preplan workflow, step by step

Steps 1 to 6 as written in 1.1.0, followed by the Q&A rubric and the skip-Q&A behavior that govern Step 4.

Contents:
- Step 1: Source-of-truth grounding (ticket with comments, predecessors, roadmap, dependency graph)
- Step 2: Initial assessment (five artifacts, including the execution lane)
- Step 3: Preliminary plan with load-bearing decisions surfaced
- Step 4: Open-questions Q&A loop (the three response modes, loop continuation)
- Step 5: Decision summary file (`plans/<ticket-slug>-decisions.md`, its structure, the changelog row)
- Step 6: Handoff to your planning step (fill the template, preview, persist `plans/<ticket-slug>-plan.md`)
- Q&A rubric details, and three checks that catch a bad decision before it is locked
- Skip-Q&A behavior

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
5. **Execution lane, with a one-line reason.** Either the full commit-by-commit workflow ([references/commit-by-commit.md](commit-by-commit.md)) or the single-commit workflow ([references/single-commit.md](single-commit.md)); the latter file owns the routing test and its disqualifiers. State the lane explicitly even where the project declares a default, and name the condition or disqualifier that decided it. A lane inherited silently is the failure this artifact prevents, and it fails in both directions: a ticket routed heavy because the session was in a planning frame, and one routed light because it looked small. If the lane is single-commit, the rest of this skill usually does not apply — say so and stop, rather than producing a decisions file for work that decides nothing.

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

1. **Load the handoff template** from [assets/handoff-template.md](../assets/handoff-template.md).
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
