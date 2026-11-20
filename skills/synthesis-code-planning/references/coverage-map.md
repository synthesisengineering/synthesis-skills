# Coverage maps: code planning

Read when checking where a rule of an earlier text lives now (ruling D8). Two rewrites, newest first: 2.0.0 to
2.1.0, the rewrite to the repository's standard (`docs/skill-writing.md`), then 1.1.1 to 2.0.0, the v5
restructure, kept word for word one heading level down.

Contents:
- 2.0.0 to 2.1.0: SKILL.md; references/process.md; files unchanged
- 1.1.1 to 2.0.0 (v5): the section map; lines restructured in place; the 1.1.1 frontmatter
- The full description, word for word

## 2.0.0 to 2.1.0: the rewrite to the D8 standard

Every rule and requirement of the 2.0.0 text, in its order, and where it lives in 2.1.0. **Kept**: the same
words in the same file. **Moved**: the same words in another file. **Reworded**: the same rule in new words,
with the old words in [preserved.md](preserved.md). **Merged**: two passages that said the same thing, now said
once. **Added**: a new sentence, with its reason. Nothing was dropped. Binding rules keep their numbers, which
the skill's evaluation cases cite.

### SKILL.md

| 2.0.0 | 2.1.0 | How |
|---|---|---|
| Frontmatter: name, description, license, `user-invocable`, `depends_on`, author, source, format, category | Frontmatter | Kept. The description is unchanged: it already leads with the key use case, and the evaluation harness cannot test a new one (W1) |
| Frontmatter `version: "2.0.0"` | `version: "2.1.0"` | Bumped: a minor version, since every binding rule keeps its number and meaning. The skill has no scripts and keeps no release notes, so this map and preserved.md are the record of the change |
| Title | Title | Kept |
| Opening line: "A structured methodology for choosing and implementing code approaches against the user's outcome and constraints" | Opening paragraph | Reworded: says what the skill does (format rule 2) |
| (none) | The line above rule 1: a checkpoint, decision or grant the user gives governs within its scope; the rules hold when a request leans on other text, such as a loaded skill's; say which rule applies and why, then do what it allows | Added (W8, format rule 11) |
| Rule 1: before choosing or asking, apply the shared decision ownership contract (a link into synthesis-thinking-framework) | Rule 1 | Reworded to fix the evaluation's finding (W2, W7, W12): the rule now states the contract's row for an open outcome choice (the smallest clarification from its owner, independent authorized work continuing, only the dependent action blocked), routes its other rows to rules 4 and 6, and names the two failures the evaluation found, a built-in default and waiting or asking leave. "Before choosing or asking" kept. The link moved to Contents |
| Rule 2: honor explicit supervised checkpoints; decide technical choices within delegated work and continue | Rule 2 | Reworded (W5, W7): the action first; the checkpoint named as the user's explicit request to review at a named point, with two quoted forms; the reason, limited to technical choices so it does not contradict rules 1 and 3 |
| Rule 3: existing user grants persist within their scope; a skill, preference or receipt cannot create new authority | Rule 3 | Reworded (W5, W7): the action first; the scope as what the grant names, with three illustrations (a repository, an environment, a kind of action), and its end ("changed, revoked or expires", from the contract's "until changed, revoked or expired"); what proceeds (act without asking again; outside the scope, prepare the action and ask, from the contract's fourth row); the reason |
| Rule 4: compare approaches only when a real choice remains; if the constraints determine one approach, state that reason and proceed; do not manufacture a second option | Rule 4 | Reworded. Head kept word for word. Adds "make a trivial change directly" and the requested-comparison sentence, both from When to skip; "the request, the codebase's conventions or the constraints" for "the constraints"; the near-miss sentence (W15): a doubt whether the determined approach fits is a check to run; the reason |
| Rule 5: before editing code to fix a defect, record the hypothesis, a falsifiable prediction and the observation that would change the approach | Rule 5 | Reworded to fix the evaluation's finding (W10, W14): the three items now go above the fix in the answer, as three labeled lines; "a prediction that could prove it wrong" for "a falsifiable prediction" (format rule 6); the reason |
| Rule 6: a close technical tradeoff is not a new approval gate; the delegated decision owner selects; clarify only material outcome ambiguity or an actual unsatisfied gate | Rule 6 | Reworded (W5): the action first; "when another agent owns the delegated decision, it selects" keeps "the delegated decision owner selects"; the two reasons to ask named as rules 1 and 3 (format rule 11); "give the reasons and what it gives up" from Step 3 |
| Rule 7: delegation changes approval cadence, not verification obligations; run the consumer checks and required audits, and invalidate affected evidence after a change | Rule 7 | Reworded: the action first, as a standing rule (W3); "consumer checks" defined where first used (format rule 6); "treat evidence the change made stale ... as void until redone", with three examples, for "invalidate affected evidence"; the 2.0.0 head kept as the closing clause in plain words; the reason |
| Rule 8: fix the root cause, not its surface, with built-in features, the codebase's conventions and the least code that does the job | Rule 8 | Reworded and merged with Principles: "in code you write or review, the fix for a defect goes where the defect starts" states the scope (W14), which the evaluation's review case assumes; the reason, with Principles' illustration |
| Contents: coverage-map.md line | Contents | Reworded for both rewrites |
| Contents: "Inputs, Process (Steps 1 to 4 ...), When to skip multi-approach evaluation, Principles: below" | Contents: the Which path line and the process.md line | Reworded: the procedure lives in references/process.md |
| Rule 1's link to the decision ownership contract | Contents: "the whole contract rule 1 applies", of which rules 1 to 3 and 6 state the rows code work meets, with when to read it | Moved (W4), so the meaning stands: rule 1 still applies the whole contract; the link target is unchanged, as `test_a_link_into_another_collection_is_pointed_at_its_file_at_the_release_s_tag` requires |
| (none) | Contents: preserved.md line | Added |
| Inputs, whole | references/process.md, Inputs | Moved word for word |
| Process, Steps 1 to 4, whole | references/process.md, Process | Moved word for word; the decisive-uncertainty link gains one `../`, since the file is one folder deeper. With the binding rules complete on their own, SKILL.md would have run past the room W19 leaves, and format rule 3 moves whole passages instead of condensing them; standard step 3 sends a procedure for one kind of request to its own reference |
| When to skip multi-approach evaluation: trivial or constraint-determined choices skip alternative generation and are implemented directly | Which path, first two bullets; rule 4 | Reworded (W18): the routing now comes before the procedure |
| When to skip: record a consequential predetermined choice and its source without reopening it | Which path, second bullet | Kept word for word inside the bullet |
| When to skip: an explicitly requested comparison still deserves a concise explanation of why excluded approaches fail the constraints | Rule 4, last sentence | Reworded: "explain briefly" for "a concise explanation"; it is where rule 4 meets a request (format rule 11) |
| Principles: framework-first, convention over configuration, root cause over symptom, less code is better ("a one-line config change beats 50 lines of custom code") | Rule 8 | Merged: each restated rule 8 (format rule 11, one home per rule); the illustration kept word for word as rule 8's reason |
| (none) | Which path | Added (W18): routes a trivial change, a determined approach, a real choice, a defect and a requested checkpoint |

### references/process.md

The file holds the 2.0.0 Inputs and Process sections, moved word for word from SKILL.md (above), then rewritten
where they restated a binding rule. The old words are in [preserved.md](preserved.md), inside the 2.0.0 SKILL.md.

| 2.0.0 (SKILL.md) | 2.1.0 (process.md) | How |
|---|---|---|
| (none) | Title and opening line: read it for a real choice or a defect; the binding rules govern every step, and the steps point to them by number | Added: the file stands on its own (format rule 4) |
| Inputs, whole | Inputs | Kept from the move, word for word |
| Step 1, whole | Step 1 | Kept from the move, word for word |
| Step 2: "Compare distinct viable approaches only when a real choice remains. If the constraints determine one approach, state that reason and proceed; do not manufacture a second option." | Step 2, first sentence: each distinct viable approach "that remains under binding rule 4" | Reworded: a copy of binding rule 4, now a pointer to it (format rule 11) |
| Step 2: "For each remaining approach, document:" and two identical blocks, Approach 1 and Approach 2, each with two advantages and two drawbacks | Step 2: one block, Approach N, marked as the exact template, "with as many advantages and drawbacks as it has" | Reworded (W17): one exact template, so a model copies its shape and not a count of two |
| Step 2: investigate the uncertainty that could change the selection; generate more approaches only for a materially different tradeoff | Step 2 | Kept, word for word |
| Step 2: "For diagnosis, record the hypothesis, a falsifiable prediction and the observation that would change the approach before editing code." | Step 2, diagnosis paragraph: "write binding rule 5's three lines before editing code" | Reworded: a copy of binding rule 5, now a pointer to it (format rule 11) |
| Step 2: use the decisive-uncertainty method; "preserve refuted predictions and re-open only their affected acceptance closure" | Step 2: the same link and "preserve refuted predictions"; "re-open only the acceptance checks they affect" | Reworded: plain words for "affected acceptance closure" (format rule 6) |
| Step 2: inspect the actual consumer program as well as its result | Step 2 | Kept, word for word |
| Step 3: select and justify; the four bullets | Step 3 | Kept, word for word |
| Step 3: "The delegated decision owner selects; a close technical tradeoff does not itself require another user approval. Clarify only material outcome ambiguity or an actual unsatisfied gate." | Step 3: "Binding rule 6 settles a close call, and rules 1 and 3 name the only reasons to ask." | Reworded: a copy of binding rule 6, now a pointer (format rule 11) |
| Step 3: new counterevidence can reopen a prior premise through its recorded owner | Step 3 | Kept, word for word |
| Step 4: implement; the first five bullets | Step 4 | Kept, word for word |
| Step 4, last bullet: "Run the consumer checks and required audits, and invalidate affected evidence after a change. Delegation changes approval cadence, not verification obligations." | Step 4, last bullet: "Run the checks binding rule 7 names." | Reworded: a copy of binding rule 7, now a pointer (format rule 11) |

### Files unchanged

`agents/openai.yaml`. In this file, the 1.1.1 to 2.0.0 map below is kept word for word one heading level down.

## Coverage map: code planning 1.1.1 to 2.0.0

Every part of the 1.1.1 SKILL.md and where it lives now. Nothing was removed or moved out of SKILL.md.

| 1.1.1 section | Now |
|---|---|
| Frontmatter description | Rewritten to 248 characters; it keeps the triggers "generate code", "implement a feature", "write code" and "tackle a coding task" and the four things the skill does |
| Opening line | SKILL.md (verbatim) |
| Decision-ownership paragraph | Binding rules 1 to 3, one sentence each, word for word (below) |
| Inputs | SKILL.md (verbatim) |
| Process, Steps 1 to 4 | SKILL.md (verbatim); Step 2 is summarized in Binding rules 4 and 5, Step 3 in rule 6, Step 4 in rule 7 |
| When to skip multi-approach evaluation | SKILL.md (verbatim); summarized in Binding rule 4 |
| Principles | SKILL.md (verbatim); summarized in Binding rule 8 |
| `user-invocable`, `depends_on`, `source_repo`, `source_type`, `author` | Kept: Claude Code reads `user-invocable`, `synthesis-agent-conformance` checks the rest in its source contract, and `synthesis-onboarding` modular install reads `depends_on` |

### Lines restructured in place

The decision-ownership paragraph was split at sentence boundaries into Binding rules 1 to 3. Every word stayed and the order is unchanged. The 1.1.1 line was:

```text
Before choosing or asking, apply the shared [decision ownership contract](../synthesis-thinking-framework/references/decision-ownership.md). Honor explicit supervised checkpoints; decide technical choices within delegated work and continue. Existing user grants persist within their scope. A skill, preference or receipt cannot create new authority.
```

### The 1.1.1 frontmatter, verbatim

Kept on record so the old description and metadata are not lost.

```yaml
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
```

## The full description

The description in SKILL.md's frontmatter was shortened to fit Claude Code's skill listing (BACKLOG C6, 2026-11-20); this is the full description it replaced, word for word.

```yaml
description: "Plan and implement code: apply constraints, compare only the viable approaches that remain, resolve delegated technical choices, and implement with evidence. Use when asked to generate code, implement a feature, write code, or tackle a coding task."
```
