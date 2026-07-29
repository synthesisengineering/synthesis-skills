---
name: synthesis-anti-shortcuts
description: "Discipline for catching the lazy-shortcut antipattern in AI-assistant output. Makes the costume vocabulary explicit so agents recognize when their drafts have slid into deferral, dismissal, or false consultation. Includes the constraint-first protocol, sub-agent dispatch and acceptance hygiene, and a pre-response self-check. Use when asked to: avoid shortcuts, audit for laziness, check for deferral, enforce best solution, no shortcuts, anti-shortcut, constraint-first, sub-agent hygiene, costume vocabulary."
license: "Apache-2.0"
depends_on: []
metadata:
  author: "Rajiv Pant"
  version: "1.0.0"
  source_repo: "github.com/synthesisengineering/synthesis-skills"
  source_type: "public"
---

# Synthesis Anti-Shortcuts

A discipline for catching the lazy-shortcut antipattern in AI-assistant output before it ships. The pattern is simple: when a user states "best solution, no shortcuts," the agent often produces a draft that looks like good engineering but quietly substitutes a lower-effort path. The substitution hides under reasonable-sounding vocabulary — "for now," "minimal diff," "backward compatible," "out of scope," "archive value." This skill names those costumes and provides the protocol to strip them out.

The pattern is not unique to one model or one user. It is a structural failure mode of agents trained on conservative defaults — minimize change, hedge claims, defer hard choices. Those defaults are correct when no one has said otherwise. They are wrong, and quietly harmful, when the user has explicitly removed them from the constraint set and the agent overrides that instruction with its trained safety preference.

This skill is the methodology. The operational catalog in `scripts/scan_output.py` is the extract — a phrase scanner that any agent or pipeline can run against draft output. The detailed catalog with rationale, the constraint-first protocol with a worked example, the sub-agent dispatch and acceptance rules, and the anonymized case studies all live in `references/` and load on demand.

## When to Apply

- Before generating any non-trivial implementation plan, design recommendation, or multi-option analysis
- Before accepting a sub-agent's report — especially when the sub-agent self-flags a tradeoff
- Before committing prose to public-facing artifacts where reputation is at stake (READMEs, blog posts, marketing copy, OSS docs)
- Before responding when the user has explicitly stated "complete this, no shortcuts," "best solution," or equivalent
- As part of a pre-response self-check on any draft that touches code, content, or strategy

## When NOT to Apply

- Trivial single-line changes where the implementation is obvious
- Genuine constraint-neutral decisions where the user's input is actually required (e.g., product direction, scheduling, stakeholder facts the agent cannot know)
- Discussions where the agent is teaching about shortcuts, not committing one (the skill recognizes quoted and discussion-mode usage)

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

Each costume sounds reasonable in isolation. Each is the same shortcut wearing different clothes. The full catalog with rationale per phrase lives in [`references/costume-vocabulary.md`](references/costume-vocabulary.md).

## The Methodology

Seven procedures, applied in order on non-trivial work. Each is small. Together they catch the pattern before it ships.

### 1. The Constraint-First Protocol

Before generating approaches, write the constraints. List the user's stated goals AND non-goals from the current conversation, the project's persistent context files, the workspace's agent-instruction files, and the global agent-instruction files. Then — and only then — generate approaches.

Any pro that violates a stated constraint cannot appear in the analysis. If "backward compatibility is not a goal" is in the constraints, the pro "backward compatible — existing tests pass unchanged" is forbidden. The constraint list functions as a filter on the option space, not a checkbox after the fact.

A worked example, including the constraint-extraction order and the forbidden-criteria mapping, lives in [`references/constraint-first-protocol.md`](references/constraint-first-protocol.md).

### 2. The Decision-vs-Asking Distinction

Two question shapes look alike but behave differently. The decision is whether the user's stated constraints determine the answer.

**Asking is appropriate when constraints leave a real choice open.** Sequencing, scope, product direction, stakeholder facts the agent cannot know — these deserve a real question, asked briefly.

**Asking is the lazy-shortcut pattern when constraints already determine the answer.** "Should I remove the backward-compat re-export?" after the user has said "backward compatibility is not a goal" is the shortcut. The polite framing — "Recommendation: X. Your call?" — is the costume.

The protocol: before drafting any question to the user, scan recent conversation, project context, and global rules for constraints that might determine the answer. If a constraint determines it, do not draft the question. Execute on the constraint. Report what was done.

### 3. The Costume Vocabulary

Memorize the seven category labels above. When drafting analysis or reading a sub-agent's report, scan for phrases that match any category. When a match appears, ask: is this phrase a real engineering constraint here, or is it a costume covering avoidance?

The test: did the user, explicitly or via standing constraints, ask the agent to optimize for the thing this phrase implies? If yes, the phrase is legitimate. If the user asked for the opposite — "best, most flexible, robust, maintainable solution; no shortcuts" — the phrase is a costume. Strip it from the draft.

The full per-phrase catalog with category, rationale, and replacement framings lives in [`references/costume-vocabulary.md`](references/costume-vocabulary.md). The operational extract is in `scripts/scan_output.py`.

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

Full dispatch protocol lives in [`references/sub-agent-hygiene.md`](references/sub-agent-hygiene.md).

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

The scanner at `scripts/scan_output.py` automates step 1. The classification at step 2 is judgment; the catalog at [`references/costume-vocabulary.md`](references/costume-vocabulary.md) supports it.

### 7. The Maintenance Loop

The catalog grows. When a new costume appears in production output, the loop is:

1. Document the incident as a case study. The incident is the data; the documented teardown is the artifact that survives context loss.
2. Extract the new phrase, category, and rationale.
3. Update [`references/costume-vocabulary.md`](references/costume-vocabulary.md) with the new entry.
4. Update `scripts/scan_output.py` if the embedded catalog should detect the phrase.
5. (Optional) Regenerate any operational catalog files that consume this skill.

The methodology stays stable. The catalog refreshes as the failure modes evolve. The anonymized case studies in [`references/case-studies.md`](references/case-studies.md) are the durable record of where each entry came from.

## How the Pieces Fit

```
SKILL.md (this file)
   |
   |-- references/costume-vocabulary.md      Full phrase catalog with rationale
   |-- references/constraint-first-protocol.md  Worked-example procedure
   |-- references/sub-agent-hygiene.md       Dispatch + acceptance rules
   |-- references/case-studies.md            Anonymized incident teardowns
   |
   |-- scripts/scan_output.py                Standalone scanner (Python 3, stdlib + pyyaml)
```

A reader who installs only this skill can apply the methodology end-to-end. The references load on demand; the scanner runs standalone or as a hook in any agent platform.

## Relationship to Other Skills

This skill is methodology. It pairs naturally with the synthesis skills that produce the artifacts it audits.

- **[synthesis-thinking-framework](../synthesis-thinking-framework/SKILL.md)** — Foundational reasoning methodology. The constraint-first protocol is a specialization of first-principles thinking applied to the option-evaluation step.
- **[synthesis-code-planning](../synthesis-code-planning/SKILL.md)** — Multi-approach evaluation for code tasks. This skill's constraint-first protocol slots in as the first step before the approach-generation step in code-planning.
- **[synthesis-implementation-integrity](../synthesis-implementation-integrity/SKILL.md)** — Post-implementation verification. This skill catches shortcuts before they're built; implementation-integrity catches incomplete work after it's built. Use both.
- **[synthesis-content-quality](../synthesis-content-quality/SKILL.md)** — AI-pattern detection in prose. Different domain (prose patterns vs decision patterns) but a similar shape — both maintain a catalog that grows as failure modes evolve.

These skills work independently. They are stronger together. When loaded as a stack, the constraint-first protocol shapes how options are generated, the costume vocabulary scan shapes how drafts are reviewed, and implementation-integrity verifies that nothing slipped through to the build.

## The Underlying Principle

The pattern this skill catches is one specific manifestation of a more general issue: an agent's trained defaults can quietly override the user's explicit instructions, in ways the agent itself does not notice. The fix is not "try harder to follow instructions." The fix is structural — make the conflict visible at the moment of drafting, so the override cannot happen silently.

The constraint-first protocol makes the user's constraints the first thing in the draft. The costume vocabulary scan makes the override detectable in the draft. The sub-agent acceptance audit makes the same checks portable across delegated work. The maintenance loop makes new failure modes part of the system as they emerge.

The reader who applies this discipline ships work that respects the constraints the user actually stated, not the ones the agent's training would have preferred.
