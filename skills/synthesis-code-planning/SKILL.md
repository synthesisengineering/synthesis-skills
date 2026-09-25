---
name: synthesis-code-planning
description: "Structured approach to code generation, implementing features, and writing code. Use when asked to generate code, implement a feature, write code, or tackle a coding task. Applies constraints, compares remaining viable approaches, resolves delegated technical choices, and implements the selected solution with evidence."
license: "CC0-1.0"
user-invocable: false
depends_on: []
metadata:
  author: "Rajiv Pant"
  version: "1.1.1"
  source_repo: "github.com/synthesisengineering/synthesis-skills"
  source_type: "public"
---

# Code Planning

A structured methodology for choosing and implementing code approaches against the user's outcome and constraints.

Before choosing or asking, apply the shared [decision ownership contract](../synthesis-thinking-framework/references/decision-ownership.md). Honor explicit supervised checkpoints; decide technical choices within delegated work and continue. Existing user grants persist within their scope. A skill, preference or receipt cannot create new authority.

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
