# Preserved text: code planning, retired in 2.1.0

Read this only to review what a rewrite replaced. The passages below are no longer instructions; they are kept
word for word so the reasoning stays readable (ruling D8).

Contents:
- Retired in 2.1.0, the rewrite to the D8 standard: why each part of SKILL.md changed, why each part of
  references/process.md changed, then the 2.0.0 SKILL.md word for word

## Retired in 2.1.0: the rewrite to the D8 standard

2.1.0 rewrote the skill's instruction text to the repository's rewrite standard, `docs/skill-writing.md`
(writing rules W1 to W19). Every rule's new place is in [coverage-map.md](coverage-map.md). A passage moved word
for word to another file is recorded there; the whole 2.0.0 SKILL.md is below all the same, so every word of it
stays readable in one place.

### SKILL.md

Why each part changed:

- **Opening line.** It named the skill a structured methodology. The paragraph now says what the skill does:
  who decides each open choice, when to compare approaches, a defect's hypothesis, and checks through the code
  that uses a change (format rule 2).
- **The line above rule 1.** New: it says that the user's own checkpoints, decisions and grants govern within
  their scope, that the rules hold when a request leans on other text such as a loaded skill's, and how to
  answer such a request (W8, format rule 11).
- **Binding rule 1.** In 2.0.0 the rule said only to apply the decision ownership contract, a file in
  synthesis-thinking-framework, so its trigger, scope and action all lived in another skill's reference (W2).
  The evaluation harness serves only the files inside the loaded skill's folder: it answers "No file" for that
  link, and several answers said they could not open it. On the case for this rule (cp-12, a product decision
  nobody has made), the "continues" check failed in all twelve B1 answers, with the skill and without: answers
  waited for the decision before building anything, asked leave to build the parts the decision does not touch,
  built the data-removal step under a default, or held the whole feature back. The "asks-owner" check failed in
  each answer that built a default in. The rule now states the contract's row for an open outcome choice (ask
  its owner the smallest question, keep doing the independent authorized work, block only the dependent action),
  sends the contract's other rows to rules 4 and 6, names those two failures (W12), and keeps the link to the
  whole contract in Contents with when to read it.
- **Binding rules 2 to 8.** Rewritten to W5 (the action as the bold head, then the scope, the reason, and a stop
  where an evaluation found one) and made complete on their own (W2). Rule 2 names its trigger as the model
  meets it, the user's explicit request to review at a named point, and limits its last sentence to technical
  choices so it does not contradict the stops rules 1 and 3 define (W7). Rule 3 names a grant's scope and end,
  and what proceeds inside and outside it, from the contract (W7). Rule 4 takes the trivial-change path and the
  requested comparison from "When to skip", and a near-miss sentence (W15): one B1 answer (cp-01, Opus) set out
  two courses of action in case the codebase's shared retry decorator used a fixed wait, and the judge failed it
  for offering approaches to choose between. The B1 report counts that verdict as judge noise, since a baseline
  answer with the same contingency passed; the sentence states what the case's oracle does instead, a check on
  the decorator. Rule 5 carries the fix for the other finding (W10, W14): two of the four Opus answers with the
  skill gave the falsifying prediction only after the changed code (cp-03), so the rule says where the three
  items go (above the fix in the answer) and in what form (three labeled lines). Rule 6 names its two reasons
  to ask as rules 1 and 3 (format rule 11). Rule 7 defines "consumer checks" where it first uses the term
  (format rule 6) and reads as a standing rule (W3). Rule 8 absorbs Principles and states its scope, code
  written or reviewed (W14).
- **Contents.** Lists references/process.md, the decision ownership contract (moved from rule 1) with when to
  read it, and this file, and says when to read the coverage map.
- **Inputs and Process.** Moved word for word to references/process.md, the decisive-uncertainty link one
  folder deeper. With the binding rules complete on their own, SKILL.md would have run past the room W19 leaves
  under 8,000 bytes; format rule 3 moves whole passages rather than condensing them, and standard step 3 sends a
  procedure for one kind of request to its own reference.
- **When to skip multi-approach evaluation.** Its routing became Which path's first two bullets, before the
  procedure, where a model meets it before running the steps (W18); its last sentence, the requested comparison,
  became rule 4's last sentence, where the rule meets a request (format rule 11).
- **Principles.** Each restated rule 8, so rule 8 now says them once (format rule 11): built-in features,
  the codebase's conventions, the root cause and the least code, with "a one-line config change beats 50 lines
  of custom code" kept as its reason.

### references/process.md

The file holds the 2.0.0 Inputs and Process, moved word for word from SKILL.md. Its old words are in the 2.0.0
SKILL.md below, from "## Inputs" to the end of Step 4. Why each part changed in the rewrite that followed:

- **Title and opening line.** New, so the file says when to read it and that the binding rules govern its steps
  (format rule 4).
- **Four passages that restated binding rules 4, 5, 6 and 7.** Step 2's first two sentences (rule 4), the first
  sentence of Step 2's diagnosis paragraph (rule 5), the first two sentences of Step 3's last paragraph (rule 6)
  and Step 4's last bullet (rule 7) said those rules again in the 2.0.0 words, beside rules now worded
  differently. Each is now a pointer to its rule by number, since two wordings of one rule drift apart and leave
  the model to reconcile them (format rule 11).
- **The approach template.** Two identical blocks, each with exactly two advantages and two drawbacks, became one
  block marked as the exact template, with "as many advantages and drawbacks as it has": a model copies an
  example's shape, count included (W17, format rule 17).
- **"Re-open only their affected acceptance closure."** Now "re-open only the acceptance checks they affect":
  the same set in plain words (format rule 6).

The 2.0.0 SKILL.md, verbatim:

````markdown
---
name: synthesis-code-planning
description: "Plan and implement code: apply constraints, compare only the viable approaches that remain, resolve delegated technical choices, and implement with evidence. Use when asked to generate code, implement a feature, write code, or tackle a coding task."
license: "CC0-1.0"
user-invocable: false
depends_on: []
metadata:
  author: "Rajiv Pant"
  version: "2.0.0"
  source_repo: "github.com/synthesisengineering/synthesis-skills"
  source_type: "public"
  format: v5
  category: engineering
---

# Code Planning

A structured methodology for choosing and implementing code approaches against the user's outcome and constraints.

## Binding rules

1. Before choosing or asking, apply the shared [decision ownership contract](../synthesis-thinking-framework/references/decision-ownership.md).
2. Honor explicit supervised checkpoints; decide technical choices within delegated work and continue.
3. Existing user grants persist within their scope. A skill, preference or receipt cannot create new authority.
4. **Compare approaches only when a real choice remains.** If the constraints determine one approach, state that reason and proceed; do not manufacture a second option.
5. **Before editing code to fix a defect,** record the hypothesis, a falsifiable prediction and the observation that would change the approach.
6. **A close technical tradeoff is not a new approval gate.** The delegated decision owner selects; clarify only material outcome ambiguity or an actual unsatisfied gate.
7. **Delegation changes approval cadence, not verification obligations.** Run the consumer checks and required audits, and invalidate affected evidence after a change.
8. **Fix the root cause, not its surface,** with built-in features, the codebase's conventions and the least code that does the job.

## Contents

- [references/coverage-map.md](references/coverage-map.md): where each part of the 1.1.1 text now lives.
- Inputs, Process (Steps 1 to 4: analyze, generate approaches, evaluate and select, implement), When to skip multi-approach evaluation, Principles: below.

## Inputs

Before generating code, gather three inputs:

1. **Task description** -- what needs to be built or changed
2. **Existing code** -- the current codebase or relevant files (if any)
3. **Contextual documentation** -- relevant API docs, framework guides, coding standards, or architectural decisions

## Process

### Step 1: Analyze

Carefully analyze the task description and existing code. Consider:

- What is the actual goal (not just the literal request)?
- What constraints does the existing code impose?
- What are the performance, maintainability, and correctness requirements?
- What best practices apply to this language, framework, or domain?
- Which user goals, non-goals and prior decisions eliminate approaches?
- What evidence could change the choice, and what consumer check would establish success?

### Step 2: Generate approaches

Compare distinct viable approaches only when a real choice remains. If the constraints determine one approach, state that reason and proceed; do not manufacture a second option. For each remaining approach, document:

**Approach 1:** [Brief description]
- Pros:
  - [Advantage 1]
  - [Advantage 2]
- Cons:
  - [Drawback 1]
  - [Drawback 2]

**Approach 2:** [Brief description]
- Pros:
  - [Advantage 1]
  - [Advantage 2]
- Cons:
  - [Drawback 1]
  - [Drawback 2]

Investigate the uncertainty that could change the selection. Generate more approaches when they add a materially different tradeoff, not to meet an option quota.

For diagnosis, record the hypothesis, a falsifiable prediction and the observation that would change the approach before editing code. Use the thinking framework's [decisive-uncertainty method](../synthesis-thinking-framework/references/decisive-uncertainty.md); preserve refuted predictions and re-open only their affected acceptance closure. Inspect the actual consumer program as well as its result so a test that prints a fixed answer cannot certify the fix.

### Step 3: Evaluate and select

Select the optimal solution and justify the choice with specific reasoning:

- Reference the pros and cons of each approach
- Explain why the chosen approach best addresses the task requirements
- Acknowledge what is sacrificed by not choosing the alternatives
- If the decision is close, state that explicitly

The delegated decision owner selects; a close technical tradeoff does not itself require another user approval. Clarify only material outcome ambiguity or an actual unsatisfied gate. New counterevidence can reopen a prior premise through its recorded owner.

### Step 4: Implement

Implement the chosen solution by modifying or creating code:

- Mark changes clearly when modifying existing code
- Follow the conventions and patterns already present in the codebase
- Optimize for performance, maintainability, and adherence to best practices
- Include necessary error handling and edge case coverage
- Decompose around acceptance checks and real dependencies; reserve integration and verification work before parallelizing. Detail the next executable unit and refine later units as their inputs become known.
- Run the consumer checks and required audits, and invalidate affected evidence after a change. Delegation changes approval cadence, not verification obligations.

## When to skip multi-approach evaluation

For trivial changes or choices already determined by constraints, skip alternative generation and implement directly. Record a consequential predetermined choice and its source without reopening it. An explicitly requested comparison still deserves a concise explanation of why excluded approaches fail the constraints.

## Principles

- **Framework-first**: prefer built-in features over custom solutions
- **Convention over configuration**: follow established patterns in the codebase
- **Root cause over symptom**: fix the underlying problem, not its surface manifestation
- **Less code is better**: a one-line config change beats 50 lines of custom code
````
