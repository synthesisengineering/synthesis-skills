# Process: inputs and Steps 1 to 4

Read for a real choice between approaches or a defect (SKILL.md, Which path). The binding rules in SKILL.md govern every step; the steps point to them by number rather than restate them.

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

For each distinct viable approach that remains under binding rule 4, document it in this exact template, with as many advantages and drawbacks as it has:

```markdown
**Approach N:** <brief description>
- Pros:
  - <advantage>
- Cons:
  - <drawback>
```

Investigate the uncertainty that could change the selection. Generate more approaches when they add a materially different tradeoff, not to meet an option quota.

For diagnosis, write binding rule 5's three lines before editing code. Use the thinking framework's [decisive-uncertainty method](https://github.com/synthesisengineering/synthesis-skills/blob/v5.28.2/skills/synthesis-thinking-framework/references/decisive-uncertainty.md); preserve refuted predictions and re-open only the acceptance checks they affect. Inspect the actual consumer program as well as its result so a test that prints a fixed answer cannot certify the fix.

### Step 3: Evaluate and select

Select the optimal solution and justify the choice with specific reasoning:

- Reference the pros and cons of each approach
- Explain why the chosen approach best addresses the task requirements
- Acknowledge what is sacrificed by not choosing the alternatives
- If the decision is close, state that explicitly

Binding rule 6 settles a close call, and rules 1 and 3 name the only reasons to ask. New counterevidence can reopen a prior premise through its recorded owner.

### Step 4: Implement

Implement the chosen solution by modifying or creating code:

- Mark changes clearly when modifying existing code
- Follow the conventions and patterns already present in the codebase
- Optimize for performance, maintainability, and adherence to best practices
- Include necessary error handling and edge case coverage
- Decompose around acceptance checks and real dependencies; reserve integration and verification work before parallelizing. Detail the next executable unit and refine later units as their inputs become known.
- Run the checks binding rule 7 names.
