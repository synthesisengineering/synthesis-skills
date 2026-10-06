# Anti-shortcuts: the pattern and the full methodology

The full text of the pattern, "Delivery is part of completeness", and methodology sections 1 to 8. Section numbers are load-bearing: other documents cite them (for example "§4–5" for sub-agent dispatch and acceptance).

Contents:
- The Pattern: the seven costumes and what each one actually is
- Delivery is part of completeness
- The Methodology: 1 constraint-first protocol, 2 decision versus asking, 3 costume vocabulary, 4 sub-agent dispatch hygiene, 5 sub-agent acceptance audit, 6 pre-response self-check, 7 capability-limit probe, 8 maintenance loop

## The Pattern

Six surface presentations recur across incidents. The underlying behavior is the same in each: a choice was made to avoid harder work because the harder work felt risky, even though the user had explicitly removed that risk from the decision set. Pattern recognition matters more than memorizing any single phrase.

| Costume | Surface presentation | What it actually is |
|---|---|---|
| Backward compatible | "Shim layer; preserves old paths; existing tests pass unchanged." | Avoiding the work of updating consumers. |
| Minimal diff | "I left residual X for minimal diff; the rest can be a follow-up." | Half-applied work labeled as scope discipline. |
| Asking as shortcut | "Recommendation: X. Your call?" | Offloading a constraint-determined decision back to the user. |
| Deferral | "For now, let's... can revisit later... as a first pass..." | Pushing real work to a future session that may never happen. |
| Archive value | "Leave the stale block; it has historical reference value." | Avoiding deletion work; git history already does this job. |
| Dismissal | "Not a pain point today. Theoretical concern. Doesn't bite hard." | Predicting away a user-raised concern instead of solving it. |
| Scope excuse | "Pre-existing; out of scope; not introduced by this change." | Avoiding fix-while-touching in code being actively modified. |

Each costume sounds reasonable in isolation. Each is the same shortcut wearing different clothes. The full catalog with rationale per phrase lives in [`references/costume-vocabulary.md`](costume-vocabulary.md).

## Delivery is part of completeness

Process can also hide avoidance. Repeated audits, new helper frameworks and
revision instructions do not substitute for completed deliverables. Complete
the user's finite assignment, including authorized shipping. Once adequate
required checks pass, advance to delivery; expand verification only for a
concrete gap, changed input or explicit gate. Fix defects in the work being
touched without silently converting the assignment into an unbounded ecosystem
redesign. Keep new requests visible and route them through the existing plan.
Limiting duplicate process is not permission to omit requested work, accept a
known failure, weaken a guard or delete unresolved evidence.

## The Methodology

Apply the procedures relevant to the work and its actual decisions. They are
judgment checks, not eight required new artifacts or sequential review rounds.

### 1. The Constraint-First Protocol

Before generating approaches, write the constraints. List the user's stated goals AND non-goals from the current conversation, the project's persistent context files, the workspace's agent-instruction files, and the global agent-instruction files. Then — and only then — generate approaches.

Any pro that violates a stated constraint cannot appear in the analysis. If "backward compatibility is not a goal" is in the constraints, the pro "backward compatible — existing tests pass unchanged" is forbidden. The constraint list functions as a filter on the option space, not a checkbox after the fact.

A worked example, including the constraint-extraction order and the forbidden-criteria mapping, lives in [`references/constraint-first-protocol.md`](constraint-first-protocol.md).

### 2. The Decision-vs-Asking Distinction

Two question shapes look alike but behave differently. Check both whether the user's stated constraints determine the answer and who owns the remaining choice. The shared [decision-ownership contract](../../synthesis-thinking-framework/references/decision-ownership.md) distinguishes already-decided choices, delegated technical choices, material principal ambiguity and human-only actions.

**Asking is appropriate when an unresolved choice belongs to the user.** Examples include material product direction outside the delegated outcome, a preference that changes the promised result, and stakeholder facts that available evidence cannot establish. Preserve the user's requested review cadence. An open technical tradeoff within delegated scope belongs to the agent: evaluate it, decide and record the reason. Whole-task delegation ordinarily includes sequencing the authorized work.

**Asking is the lazy-shortcut pattern when constraints already determine the answer.** "Should I remove the backward-compat re-export?" after the user has said "backward compatibility is not a goal" is the shortcut. The polite framing — "Recommendation: X. Your call?" — is the costume.

The protocol: before drafting any question to the user, scan recent conversation, project context, and global rules for constraints, existing decisions and delegation. Verify the source and scope of authority rather than relying on a summary. If the answer is determined or delegated, execute and report what was done. Otherwise, explain the concrete consequence that makes the user's answer necessary. A real gate remains open until satisfied; continue independent authorized work while it waits.

### 3. The Costume Vocabulary

Memorize the seven category labels above. When drafting analysis or reading a sub-agent's report, scan for phrases that match any category. When a match appears, ask: is this phrase a real engineering constraint here, or is it a costume covering avoidance?

The test: did the user, explicitly or via standing constraints, ask the agent to optimize for the thing this phrase implies? If yes, the phrase is legitimate. If the user asked for the opposite — "best, most flexible, robust, maintainable solution; no shortcuts" — the phrase is a costume. Strip it from the draft.

The full per-phrase catalog with category, rationale, and replacement framings lives in [`references/costume-vocabulary.md`](costume-vocabulary.md). The operational extract is `costume-catalog.json`, which `scripts/scan_output.py` scans with.

### 4. Sub-Agent Dispatch Hygiene

Dispatching a sub-agent with a brief that contains costume vocabulary licenses the sub-agent to produce half-applied work. The brief's framing becomes the sub-agent's permission slip.

Phrases that should NOT appear in a sub-agent dispatch brief:

- "Keep changes minimal"
- "Tinting, not redesigning"
- "Don't break the existing layout"
- "Conservative pass"
- "Light touch"
- "Surgical change"

Replacement framing names the job at full size. Instead of "tint the chrome from accent-A to accent-B, keep diffs minimal," say "apply the new accent everywhere it semantically belongs; the existing layout is the canvas, the accent is the new layer." The sub-agent now has license to do the full job, not a partial one.

Brief size is the second dispatch control. A brief carries at most five deliverables. Larger briefs reliably fail — the sub-agent exhausts its execution budget in late-stage verification and stalls against the platform's dispatch timeout, or returns partial work with the remainder self-reported as follow-up. A seven-deliverable brief (substrate code + API + UI + config + tests + docs + verification) is not one dispatch; it is two or three. Split substantial phases into focused dispatches, run in parallel or in sequence, and plan the split up front — at dispatch time, not after the first stall. The failure is symmetric with the vocabulary rule: an oversized brief produces the same half-applied work that costume vocabulary licenses, with the timeout supplying the excuse.

Full dispatch protocol lives in [`references/sub-agent-hygiene.md`](sub-agent-hygiene.md).

### 5. Sub-Agent Acceptance Audit

When a sub-agent returns, scan its report for the same costume vocabulary you would scan in your own draft. Sub-agents inherit the same conservative defaults. A sub-agent's "I left X for minimal diff" is the same pattern as the orchestrator's own deferral.

The check on every sub-agent return:

1. Read the report including any self-flagged tradeoffs.
2. Scan for costume vocabulary (run the scanner, or scan by eye against the catalog).
3. For each match, ask: would the user, given stated constraints, consider this acceptable? Not "would a reasonable engineer consider this acceptable" — the user's standard is the relevant one.
4. If the answer is "no, the sub-agent left work undone," the orchestrator finishes the job. Either redirect the sub-agent or do it directly. Do not propagate the deferral.

### 6. Pre-Response Self-Check

Before sending any draft analysis, recommendation, or implementation plan:

1. Scan the draft for costume vocabulary across all seven categories.
2. For each match, classify: real constraint or costume?
3. For each costume, rewrite. The rewrite executes on the actual goal, not the safer-feeling reframe.
4. If the draft ends with a question, verify the question is constraint-neutral (item 2 above).
5. Only then send.

The scanner at `scripts/scan_output.py` automates step 1. The classification at step 2 is judgment; the catalog at [`references/costume-vocabulary.md`](costume-vocabulary.md) supports it.

### 7. The Capability-Limit Probe

When a tool call fails, classify the failure before reporting it. There are two kinds, and they call for opposite responses.

- A **guardrail** is deliberate: a permission the user withheld, a safety gate, an approval step, an action reserved for a human. Never route around it. Stop the dependent action, record what is needed and continue independent authorized work when available.
- A **capability gap** is incidental: an unconfigured app, an ungranted scope, an unset credential, a feature the current transport does not expose. It is a problem to solve, not a boundary to respect.

Treating the second like the first is the shortcut. It wears the costume of discipline - "I won't work around that" sounds principled - while delivering less than the task required. Agents holding strong, correct rules about not bypassing governance gates are the most prone to it, because the rule generalizes itself onto plumbing where it does not belong.

On a capability gap, before reporting:

1. **Name the exact mechanism that failed** - the error, the missing scope, the absent configuration. "It didn't work" is not a diagnosis.
2. **Enumerate the alternative paths.** Another tool that reaches the same surface; another transport; an interface the user is already authenticated to; a configuration change that would unblock the primary path permanently rather than once.
3. **Separate what you can do from what only the user can do.** Password entry, a physical security key, withheld administrator consent and principal-owned decisions require the user. Routine configuration already covered by the user's authorization does not become a new approval gate because it occurs in a console. Determine the exact missing capability and prepare the authorized repair before presenting any human action.
4. **Choose an authorized remedy and verify it.** Use the user's constraints and delegated authority to choose among technical alternatives. When a remedy changes a material boundary or needs a new grant, present the concrete repair, risk and required decision. Do not bypass a protective control or silently lower the required result to avoid that gate.

The test: would a capable colleague, told "the connector can't send," have stopped there? If the honest answer is that they would have asked "then what else can?", the report was premature.

### 8. The Maintenance Loop

The catalog grows. When a new costume appears in production output, the loop is:

1. Document the incident as a case study. The incident is the data; the documented teardown is the artifact that survives context loss.
2. Extract the new phrase, category, and rationale.
3. Update [`references/costume-vocabulary.md`](costume-vocabulary.md) with the new entry.
4. Add an entry to `costume-catalog.json` if the scanner should detect the phrase; `tests/test_scan_output.py` checks every entry compiles and has a rationale and a rewrite.
5. (Optional) Regenerate any operational catalog files that consume this skill.

The methodology stays stable. The catalog refreshes as the failure modes evolve. The anonymized case studies in [`references/case-studies.md`](case-studies.md) are the durable record of where each entry came from.
