# Process: inputs and Steps 1 to 4

Read for a real choice between approaches or a defect (SKILL.md, Which path). The binding rules in SKILL.md govern every step.

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

For diagnosis, record the hypothesis, a falsifiable prediction and the observation that would change the approach before editing code. Use the thinking framework's [decisive-uncertainty method](../../synthesis-thinking-framework/references/decisive-uncertainty.md); preserve refuted predictions and re-open only their affected acceptance closure. Inspect the actual consumer program as well as its result so a test that prints a fixed answer cannot certify the fix.

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
