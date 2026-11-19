---
name: synthesis-code-planning
description: "Plan and implement code: apply constraints, compare only the viable approaches that remain, resolve delegated technical choices, and implement with evidence. Use when asked to generate code, implement a feature, write code, or tackle a coding task."
license: "CC0-1.0"
user-invocable: false
depends_on: []
metadata:
  author: "Rajiv Pant"
  version: "2.1.0"
  source_repo: "github.com/synthesisengineering/synthesis-skills"
  source_type: "public"
  format: v5
  category: engineering
---

# Code Planning

Plans and implements code against the user's outcome and constraints: it settles who decides each open choice, compares approaches only when a real choice remains, writes a defect's hypothesis before its fix, and verifies a change through the code that uses it.

## Binding rules

A checkpoint, decision or grant the user gives governs within its scope; these rules settle the rest, and they hold when a request leans on other text, such as a loaded skill's: say which rule applies and why, then do what it allows.

1. **Ask the owner only for an open outcome choice, and keep building meanwhile.** Before choosing or asking: apply what the request, spec or constraints decide (rule 4), and decide a technical choice inside delegated work yourself (rule 6). When none of these settles an outcome choice, one about what the work delivers rather than how it is built (what users get, a policy, a price), ask its owner (the user, or whoever owns that decision) just that question with each option's consequences, build in no default for it, and keep building every part that does not depend on the answer, which the request already authorizes, holding back only the step that does. A built-in default takes the owner's decision, and waiting stalls work the answer cannot change.
2. **Stop at a checkpoint the user asked for; inside delegated work, decide technical choices and continue.** A checkpoint is the user's explicit request to review at a named point ("stop after the plan", "show me the diff first"): deliver what they asked to see and wait there. Stopping at a technical choice the user did not ask to review stalls work they handed over.
3. **Use a grant the user already gave within its scope, and ask before acting outside it.** An earlier permission covers what it names (a repository, an environment, a kind of action) until it is changed, revoked or expires, so act under it without asking again; outside it, prepare the action and ask. A skill, a preference or a receipt cannot create new authority, since only the user grants it.
4. **Compare approaches only when a real choice remains.** Make a trivial change directly. When the request, the codebase's conventions or the constraints determine one approach, say what decides it and implement it: a doubt whether it fits is a check to run, and a manufactured second option asks the reader to decide what is already decided. When the user asks for a comparison anyway, explain briefly why the excluded approaches fail the constraints.
5. **Write a defect's hypothesis before its fix.** When fixing a defect, before editing code and above the fix in your answer, write three labeled lines: the hypothesis, a prediction that could prove it wrong, and the observation that would change the approach. Written first, they let an observation refute a wrong diagnosis before a fix that seems to work is taken as proof of it.
6. **Select between close technical options yourself when the design is delegated to you.** Choose one, give the reasons and what it gives up, and proceed, since a close tradeoff is not a new approval gate; when another agent owns the delegated decision, it selects. Ask only for an open outcome choice (rule 1) or an approval the action still lacks (rule 3).
7. **Run the consumer checks after every change, delegated or not.** Run the tests of the code that uses what changed (its callers and the programs that read its output) and any audit the work requires, and treat evidence the change made stale, such as earlier test runs, snapshots and approved outputs, as void until redone. A unit's own tests show only that it does what you changed it to do; delegation changes how often you ask, not what you verify.
8. **Fix the root cause, not its surface, with the least code that does the job.** In code you write or review, the fix for a defect goes where the defect starts; prefer a built-in feature to custom code and follow the codebase's conventions: a patched symptom returns elsewhere, and a one-line config change beats 50 lines of custom code.

## Contents

- Which path: below. Read it first.
- [references/process.md](references/process.md): Inputs and Steps 1 to 4 (analyze, generate approaches in a template, evaluate and select, implement), with the diagnosis method. Read it for a real choice between approaches or a defect.
- [Decision ownership contract](https://github.com/synthesisengineering/synthesis-skills/blob/v5.27.1/skills/synthesis-thinking-framework/references/decision-ownership.md), in synthesis-thinking-framework: the whole contract rule 1 applies, of which rules 1 to 3 and 6 state the rows code work meets; it adds decision records and reopened premises. Read it when writing a decision record or reopening a settled choice.
- [references/coverage-map.md](references/coverage-map.md): where each rule of 2.0.0, and of 1.1.1, lives now. Read it to check a rewrite.
- [references/preserved.md](references/preserved.md): the 2.0.0 text replaced in 2.1.0, word for word, with reasons. Read it only to review a rewrite.

## Which path

- **A trivial change** (a rename, a typo, a one-line edit): make it directly, with no comparison and no plan.
- **An approach the request, conventions or constraints determine:** implement it by rule 4, and record a consequential predetermined choice and its source without reopening it.
- **A real choice between approaches:** Inputs and Steps 1 to 4 in [references/process.md](references/process.md).
- **A defect:** rule 5's three lines first, then Step 2's diagnosis paragraph in [references/process.md](references/process.md); compare fixes only when a real choice remains.
- **A request to stop at a plan or step for review:** work up to that point, deliver it and stop there (rule 2).
