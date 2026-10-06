---
name: synthesis-anti-shortcuts
description: "Catch the lazy-shortcut antipattern: costume vocabulary that hides deferral, dismissal or false consultation. Constraint-first protocol, sub-agent dispatch and acceptance hygiene, pre-response self-check. Use to avoid shortcuts, audit for laziness, check for deferral or enforce the best solution."
license: "Apache-2.0"
depends_on: ["synthesis-thinking-framework"]
metadata:
  author: "Rajiv Pant"
  version: "2.0.0"
  source_repo: "github.com/synthesisengineering/synthesis-skills"
  source_type: "public"
  format: v5
---

# Synthesis Anti-Shortcuts

Catches the draft that looks like good engineering but quietly substitutes a lower-effort path after the user asked for the best solution, hidden under reasonable-sounding vocabulary ("for now," "minimal diff," "backward compatible," "out of scope"). This skill names those costumes and gives the protocol to strip them out.

## Binding rules

Rules 1 to 8 carry the methodology section numbers other documents cite (for example "§4–5"). New rules are appended.

1. **Constraint-first.** Write the user's goals and non-goals (conversation, project context, workspace and global instructions) before generating approaches; a pro that violates one cannot appear.
2. **Decide what constraints decide.** Ask only when an unresolved choice belongs to the user. "Recommendation: X. Your call?" on a determined or delegated choice is the costume; execute and report.
3. **Scan for costume vocabulary** in drafts and sub-agent reports. A phrase is legitimate only when the user asked to optimize for what it implies.
4. **Dispatch briefs name the job at full size** (no "keep changes minimal," "light touch," "surgical change") and carry at most five deliverables.
5. **Audit every sub-agent return** for the same costumes. If work was left undone, redirect the sub-agent or finish it; never propagate the deferral.
6. **Run the pre-response self-check** (below) before any analysis, recommendation or plan ships.
7. **A capability gap is not a guardrail.** Never route around a guardrail; on a gap, name the failed mechanism, list alternatives and choose an authorized remedy before reporting.
8. **Grow the catalog.** A new costume in production output becomes a case study, a catalog entry and, where useful, a scanner pattern.
9. **Delivery is part of completeness.** Finish the finite assignment, including authorized shipping; more audits or frameworks do not substitute for deliverables.

## Contents

- [references/methodology.md](references/methodology.md): the full pattern, "Delivery is part of completeness" and methodology sections 1 to 8. Read it when applying a rule for the first time in a session or when a case is unclear.
- [references/costume-vocabulary.md](references/costume-vocabulary.md): every phrase with category, rationale and replacement framing. Read it to classify a hit or rewrite a costume.
- [references/constraint-first-protocol.md](references/constraint-first-protocol.md): the five-step protocol and a worked example. Read it before a multi-option analysis.
- [references/sub-agent-hygiene.md](references/sub-agent-hygiene.md): dispatch and acceptance rules, brief template, size cap. Read it before dispatching or accepting a sub-agent.
- [references/case-studies.md](references/case-studies.md): the incidents each entry came from; scanner `see:` lines point here. Read it when a hit's origin matters.
- [references/background.md](references/background.md): why the pattern happens, how the pieces fit, sibling skills, the underlying principle. Read once per session.
- [costume-catalog.json](costume-catalog.json): the phrase catalog the scanner reads (id, pattern, category, exemptions, rationale, rewrite). Edit it when a new costume should fire automatically.
- [references/coverage-map.md](references/coverage-map.md): where each part of the 1.2.1 text and each script change now lives (ruling D8).
- [references/preserved.md](references/preserved.md): sentences replaced when the catalog moved out of the scanner, verbatim. Read only to review the change.
- When to Apply, The Pattern, Pre-Response Self-Check, The scanner: below.

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

| Costume | Surface presentation | What it actually is |
|---|---|---|
| Backward compatible | "Shim layer; preserves old paths; existing tests pass unchanged." | Avoiding the work of updating consumers. |
| Minimal diff | "I left residual X for minimal diff; the rest can be a follow-up." | Half-applied work labeled as scope discipline. |
| Asking as shortcut | "Recommendation: X. Your call?" | Offloading a constraint-determined decision back to the user. |
| Deferral | "For now, let's... can revisit later... as a first pass..." | Pushing real work to a future session that may never happen. |
| Archive value | "Leave the stale block; it has historical reference value." | Avoiding deletion work; git history already does this job. |
| Dismissal | "Not a pain point today. Theoretical concern. Doesn't bite hard." | Predicting away a user-raised concern instead of solving it. |
| Scope excuse | "Pre-existing; out of scope; not introduced by this change." | Avoiding fix-while-touching in code being actively modified. |

## Pre-Response Self-Check

Before sending any draft analysis, recommendation, or implementation plan:

1. Scan the draft for costume vocabulary across all seven categories.
2. For each match, classify: real constraint or costume?
3. For each costume, rewrite. The rewrite executes on the actual goal, not the safer-feeling reframe.
4. If the draft ends with a question, verify the question is constraint-neutral (item 2 above).
5. Only then send.

## The scanner

`python3 scripts/scan_output.py draft.md` (or text on stdin) prints each hit by category: line and column, the matched phrase, why it is a shortcut, a rewrite framing and a `see:` case. Exit 0 clean, 1 detections, 2 error. Flags: `--json`, `--quiet` (exit code only, for hooks), `--context 120`, `--category <name>`, `--catalog <file>` (JSON; YAML needs PyYAML). It reads `costume-catalog.json`, the one public catalog, and skips phrases quoted or in code, since those are being discussed. The v5 Stop hook checks every reply against a short built-in subset of the same catalog.
