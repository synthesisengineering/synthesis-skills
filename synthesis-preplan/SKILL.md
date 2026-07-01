---
name: synthesis-preplan
description: >
  Architecture-decision pre-planning for tickets or issues with real design
  choices. Runs a structured Q&A loop that locks the load-bearing architectural
  decisions before any commit plan is drafted, then hands a clean, reviewable
  decision set to your planning step. Use when asked to: preplan, pre-plan this
  ticket, let's pre-plan, lock decisions for, design questions for, what are the
  open questions on, plan a ticket with real design choices.
license: "CC0-1.0"
user-invocable: true
depends_on: ["synthesis-code-audit"]
metadata:
  author: "Emil Peñaló"
  version: "1.0.0"
  source_repo: "github.com/synthesisengineering/synthesis-skills"
  source_type: "public"
---

# Synthesis Preplan — Architecture-Decision Locker

Runs the pre-planning Q&A loop on tickets or issues with real design choices. Produces a locked-decisions file and hands off to your planning step with a previewed prompt.

The skill exists because the hard part of planning is **deciding what to build**, not breaking the build into commits. Once architectural decisions are locked, the commit-by-commit plan is mechanical. This skill makes the decision-locking explicit so your planner inherits a clear, reviewable input instead of designing inside its own output.

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

If unsure, ask the user.

## Step 1: Source-of-truth grounding

1. Read the ticket. Fetch it from your issue tracker (Jira, GitHub Issues, Linear, or whatever the project uses) **including comments** — dev notes appended after the original body often add scope, constraints, or alternative directions that materially change the design.
2. Read predecessor branches / PRs / tickets that this work stacks on or depends on. Inspect the codebase for already-shipped pieces this ticket builds on. Constraints set by the parent shape the child.
3. Read the roadmap document if the project maintains one (check the project's agent-instruction file — `CLAUDE.md`, `AGENTS.md`, or equivalent — and project docs for its location).
4. Identify the dependency graph: what's upstream (constrains design), what's downstream (consumes this work), what's parallel (shares assumptions but ships independently).

**Soft-fail behavior.** If the tracker is unavailable, warn the user, ask them to paste the ticket body and comments inline, then proceed. The skill works for any context: a Jira ticket, a GitHub issue, a written-up Linear ticket, or a planning doc. Privilege primary sources but don't require them.

## Step 2: Initial assessment

Produce four short artifacts before any planning:

1. **One-sentence ticket goal.** What the ticket buys the system, stated as plainly as possible.
2. **Branch stacking recommendation.** Which base branch this work should be cut from, and why. Walk through 2–3 candidate bases if the choice is non-obvious, with pros/cons each.
3. **Dependency clarification.** Depends on (X, Y, Z); does NOT depend on (A, B, C). Eliminate common misconceptions explicitly.
4. **Scope boundary statement.** In scope / out of scope / deferred. The "out of scope" list is load-bearing — it documents what was deliberately not chosen and prevents scope creep in later phases.

Pause here and confirm the assessment with the user before moving on. Architectural disagreements at this layer cascade into the rest of the workflow.

## Step 3: Preliminary plan with load-bearing decisions surfaced

Produce a commit-shaped preliminary plan with three explicit parts:

1. **Load-bearing decisions stated up front.** A numbered list of the architectural choices the rest of the plan rides on. Each one is one or two sentences. Be precise — vague decisions become disagreements later.
2. **Task breakdown (commits).** Each commit gets one paragraph: what it does (the "what") and why this seam (the "why"). Don't write the implementation here.
3. **Open questions called out at the bottom.** Each question gets a one-line summary and is fully expanded in Step 4. The point at this stage is to make the question list visible.

The preliminary plan is not the real plan. It's a vehicle to surface architectural questions that must be decided before the real plan can be written. Stating load-bearing decisions explicitly forces you to confront them rather than baking them silently into commits.

## Step 4: Open-questions Q&A loop

The core mechanic of the skill. For each open question, present:

1. **The question, restated cleanly.** One sentence.
2. **Concrete options.** Two to four. Each labeled, each one line.
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

Keep iterating the Q&A loop until no open questions remain. New questions surface during depth mode — that's normal. Add them to the list and work through them.

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

## <Topic group 1>

| # | Decision | Choice | Why |
|---|---|---|---|
| 1 | ... | ... | ... |

## <Topic group 2>

| # | Decision | Choice | Why |
|---|---|---|---|

## Out of scope

| # | Decision | Choice | Why |
|---|---|---|---|

## Documentation & conventions

| # | Decision | Choice | Why |
|---|---|---|---|
```

Group rows by topic. Each row: numbered, the decision restated, the choice, the one-line "why". Documentation and out-of-scope decisions are load-bearing groups — include them.

Display the file inline in the conversation after writing. Ask the user to confirm before moving to Step 6.

## Step 6: Handoff to your planning step

When the user confirms the decision summary:

1. **Load the handoff template** from [assets/handoff-template.md](assets/handoff-template.md).
2. **Fill the slots:**
   - `{TICKET_KEY}` — e.g., `PROJ-123`, or `none` if there's no tracker
   - `{TICKET_URL}` — the tracker URL, or `none`
   - `{DECISIONS_FILE_PATH}` — path to the file written in Step 5
   - `{BRANCH_BASE}` — base branch name
   - `{PROJECT_LENSES_BLOCK}` — populated if the project flags specific lenses (privacy, security, accessibility, performance, compliance); empty otherwise
3. **Preview the filled prompt to the user inline.** Tell them: "Preview before I hand this to the planner — edit anything, or say 'go'."
4. **Accept edits.** If the user provides an edited version, use it verbatim. If they say "go", use the filled template as-is.
5. **Hand off to your planning step.** Pass the final prompt to whatever planning mechanism your agent provides — a dedicated plan mode, a planning subagent, or a fresh planning pass in a clean context. The plan output is the next thing the user reads.
6. **Persist the returned plan to a document (required).** Write the plan to `plans/<ticket-slug>-plan.md` (same slug as the decisions file, with `-plan` instead of `-decisions`). Many planners run read-only or in an isolated context — their output comes back only as a message, is not on disk, and does not survive context compaction — so persist it yourself as soon as it returns. Fold in any decisions the user redirected during or after the handoff so the document is the final plan, not the pre-handoff draft. The document must follow the **Plan document format** below. Tell the user the path. This is not optional, and the user should never have to ask for it.

The skill ends here. The persisted plan document and the decision summary file are the two durable artifacts; the user reviews the plan and either approves or iterates on it directly.

## Plan document format

Every persisted plan (and the planner's output it is built from) MUST follow this structure. The handoff template carries the same requirements so the planner emits this shape directly.

1. **Title + metadata** — ticket key/URL, branch base, decisions-file path, date.
2. **Goal** — what the work buys the system, in plain terms. Always present.
3. **Context** — the surrounding situation: current state, why now, what it builds on, and the constraints discovered from the codebase. Always present.
4. **Decisions** — ALL decisions rewritten into the plan, grouped by topic, each as decision / choice / why. Not only the Q&A-locked ones from the decisions file: include every decision taken from the ticket, from project conventions, and from the codebase. The plan must be self-contained on decisions — a reader should not need the decisions file open.
5. **Commits** — each commit, in execution sequence:
   - The heading is the commit's own top-level goal.
   - **Goal** — one line: the single thing this commit accomplishes.
   - **Changes** — what it does and the files touched.
   - **Verification** — concrete, testable steps that prove the commit works (commands, expected results). Every commit must be independently testable; a commit that cannot be verified on its own is mis-scoped.
   - **Risks to flag to audit** — the specific things the per-commit audit must scrutinize.
   - Commits are ALWAYS executed in order, so do NOT include ordering, dependency, or "depends on commit N" notes — sequence is implicit. (Intra-commit ordering, e.g. operation order inside one migration, is a Verification/Risk item, not cross-commit ordering.)
   - Size: no commit too large or too small — one coherent, reviewable unit each.
6. **E2E strategy** — an explicit end-to-end validation strategy for the whole change: golden path plus edge cases (boundaries, malformed input, auth boundaries, concurrency, adversarial values, and every documented error code).
7. **Mandatory gates (end-of-plan todos)** — final audit on the cumulative diff (`main...HEAD` or your base range), the E2E run, a **test-sufficiency self-review** (see below), address findings as new commits, then open the PR (your ship / PR-open step) — as explicit todo items, not prose.

The per-commit **Verification** and **Risks to flag to audit** subsections ARE the mandatory verify and audit todos (the commit-by-commit workflow requires both as separate items). They are established in the plan, never improvised at execution time.

### Test-sufficiency self-review (end-of-plan gate)

After the E2E run and before you open the PR, the plan MUST include an explicit step that asks, in the project's own terms: **is the testing performed enough to send this to review with confidence?** Treat it as an adversarial self-audit of coverage, not a formality. Enumerate, concretely:

- **Ground every gap in real, shipping behavior first.** A surfaced item is only a gap if it covers an intended, in-design product surface that exists on a code path real users reach. Before treating anything as a gap to close, check it against the design, the feature-flag registry, and the existing code. Finding an untracked element is **not** automatically a gap: do not add instrumentation, tests, or abstractions for speculative, flag-gated, prototype, or not-yet-designed elements (a feature-flagged preview, leftover prototype markup, a hypothetical future surface). Closing a "gap" on a non-product surface is itself the speculative over-reach the plan exists to avoid; the right move there is to leave it alone or delete the dead UI, never to cover it. This review reduces scope as readily as it adds it.
- **Untested layers.** Which new code has no automated test? Glue/integration layers (UI effects, hooks, wiring, middleware) are the usual blind spot, and are exactly where the per-commit unit tests do not reach. Name them.
- **Wired-but-never-run surfaces.** Which code paths were implemented and statically audited but never actually executed against a real runtime? A surface that has only been typechecked and read is **unverified**, however clean the audit — treat it as a gap, not a pass (once it has cleared the grounding check above).
- **Unobserved branches.** Which documented behaviors were not directly observed: fallbacks (the `else` of a new conditional), error paths, alternate surfaces (desktop vs mobile), and every documented status code? The happy path passing does not cover the branch that does the opposite.

For each **real** gap (one grounded in shipping behavior): either **close it** (run it, or add the missing test), or **consciously accept and surface it** in the PR description with the rationale and residual-risk note. Runtime-only bugs (the kind the E2E exists to catch) frequently live in the untested glue layer, so a plan that ships that layer on typecheck-plus-audit alone has not earned confidence. Findings from this review are addressed as new commits, like other end-of-plan findings — and that includes removing coverage or code that the grounding check exposes as speculative.

## Q&A rubric details

A few patterns to apply consistently inside the Q&A loop:

- **Don't ask questions you can answer from the source of truth.** If the ticket comments already lock a choice, fold it into the load-bearing decisions in Step 3 rather than presenting it as an open question.
- **Don't bundle unrelated questions.** Each open question is independent — independently reviewable, independently lockable. Two coupled decisions get presented as one question with the coupling stated.
- **Use the lean to anchor, not to prescribe.** The lean is the recommendation; the user can take it or move past it without justification. Don't make redirects feel like pushback.
- **Surface privacy / security / scaling implications inside "why it matters".** This is where your code-review dimensions (see the `synthesis-code-audit` skill, or your project's review checklist) get applied early — bake them into the rubric so the resulting plan inherits the audit posture.
- **Note when a decision is forced by the ticket itself.** Some questions only exist because the ticket left them open. Others are forced by an upstream commit or by a project convention. Calling out which is which helps the user know how much latitude they have.

## Skip-Q&A behavior

If the user says "just give me the plan" or similar — honor it, but with a one-line warning:

> Skipping Q&A — decisions stay implicit. Plan will work from the preliminary breakdown alone. Re-run this skill if you want decisions locked.

Some tickets really are mechanical. The skill should accommodate that without ceremony.

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
- **Preview the handoff prompt before handing it to the planner.** The user can always edit before send. Never invoke the planner with an unpreviewed prompt.
- **Lean don't dictate.** Every open question has a recommendation; every recommendation can be redirected with one word.
- **Reverse leans freely when pushed back on with a real argument.** Depth mode often exposes flaws in the initial framing. Reconsider honestly rather than defending the original lean.
- **The commit-by-commit workflow lives at [references/commit-by-commit.md](references/commit-by-commit.md).** The handoff template references it; don't duplicate the rules inside the handoff.
