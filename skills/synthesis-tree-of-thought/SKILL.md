---
name: synthesis-tree-of-thought
description: "Multi-expert collaborative reasoning technique. Use when asked to apply tree of thought, multi-expert brainstorming, collaborative reasoning, expert panel analysis, or when a problem benefits from simulating multiple domain experts debating step by step to reach a well-vetted conclusion."
license: "CC0-1.0"
depends_on: []
metadata:
  author: "Rajiv Pant"
  version: "2.0.0"
  source_repo: "github.com/synthesisengineering/synthesis-skills"
  source_type: "public"
  format: v5
---

# Tree of Thought

A reasoning technique that simulates multiple domain experts brainstorming step by step, critiquing each other's work, backtracking on flaws, and converging on a well-vetted conclusion.

## Binding rules

1. **Use it where a single line of reasoning could converge early on a wrong answer:** no obvious single answer, real trade-offs, or expertise from several fields. Skip it for simple lookups, single-answer tasks, or when speed matters more than depth.
2. **Match the experts to the problem,** named by specific expertise: three by default, four only for four genuinely distinct domains, and at least one whose domain creates productive tension with the others.
3. **At every step each expert critiques their own reasoning and every other expert's,** and checks it against their domain knowledge.
4. **Backtrack to the flaw, and admit error.** An expert who finds a flaw returns to where it occurred; one who realizes they are wrong says so and starts a new line of thought.
5. **Each expert states the likelihood that their current assertion is correct,** and the process continues until the experts converge.

## Contents

- [references/coverage-map.md](references/coverage-map.md): where each part of the 1.0.0 text now lives.
- How it works, Template 1 (general-purpose), Template 2 (domain-expert variant), Guidance for choosing experts, When to use tree of thought, When NOT to use tree of thought: below.

## How it works

1. Multiple experts each write one step of their thinking, then share it with the group.
2. Each expert critiques their own reasoning and the reasoning of every other expert.
3. Experts validate their assertions against their domain knowledge.
4. All experts proceed to the next step, incorporating feedback from the group.
5. If any expert identifies a flaw in their logic, they backtrack to where the flaw occurred and restart that line of reasoning.
6. If any expert realizes they are wrong, they acknowledge it and begin a new train of thought.
7. Each expert assigns a confidence level (likelihood of correctness) to their current assertion.
8. The process continues until the experts converge on a conclusion.

## Template 1: General-purpose

Use this template for any question or problem that benefits from multi-perspective reasoning.

---

Imagine three different experts are answering this question.
They will brainstorm the answer step by step, reasoning carefully and taking all facts into consideration.
All experts will write down one step of their thinking, then share it with the group.
They will each critique their response and all the responses of others.
They will check their answer based on established knowledge and sound reasoning.
Then all experts will go on to the next step and write down this step of their thinking.
They will keep going through steps until they reach their conclusion, taking into account the thoughts of the other experts.
If at any time they realize that there is a flaw in their logic, they will backtrack to where that flaw occurred.
If any expert realizes they are wrong at any point, they acknowledge this and start another train of thought.
Each expert will assign a likelihood of their current assertion being correct.
Continue until the experts agree on the single most likely answer.

The question is: **[INSERT QUESTION]**

---

## Template 2: Domain-expert variant

Use this template when the problem requires specific domain expertise. Define the experts to match the problem domain.

---

Imagine three different deeply knowledgeable and experienced experts. One is an expert in **[DOMAIN 1]**. The second is an expert in **[DOMAIN 2]**. The third is an expert in **[DOMAIN 3]**.

They are helping with the following task.
They will brainstorm the answer step by step, reasoning carefully and taking all facts into consideration.
All experts will write down a first draft of their thinking, then share it with the group.
They will each critique their response and all the responses of others.
They will check their drafts based on their expertise in their respective fields.
Then all experts will go on to the next step and write down the next draft of their thinking.
They will keep going through steps until they reach their conclusion, taking into account the thoughts of the other experts.
If at any time they realize that there is a flaw in their logic, they will backtrack to where that flaw occurred.
If any expert realizes they are wrong at any point, they acknowledge this and start another train of thought.
Each expert will assign a likelihood of their current assertion being correct.
Continue until the experts agree on a comprehensive result.

The task is: **[INSERT TASK]**

---

## Guidance for choosing experts

- Match expert domains to the problem. A technical question needs technical experts; a business strategy question needs business, economics, and industry experts.
- Three experts is the standard. Use four when the problem spans four genuinely distinct domains.
- Name specific expertise areas rather than generic titles. "Expert in distributed systems and database internals" is better than "technology expert."
- Include at least one expert whose domain creates productive tension with the others (e.g., a security expert alongside a UX expert, or an economist alongside an engineer).

## When to use tree of thought

- Complex problems with no obvious single correct answer
- Decisions where trade-offs matter and different perspectives reveal different trade-offs
- Questions where domain expertise from multiple fields is required
- Situations where premature convergence on a wrong answer is a risk

## When NOT to use tree of thought

- Simple factual lookups
- Tasks with a single well-defined correct answer
- When speed matters more than depth
