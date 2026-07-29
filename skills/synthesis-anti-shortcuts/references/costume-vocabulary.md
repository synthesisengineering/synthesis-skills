# Costume Vocabulary

The full human-readable catalog of phrases that signal the lazy-shortcut antipattern. Each entry includes the phrase, its category, the kind of incident that produced it, and the replacement framing that executes on the actual goal.

This file is the reference companion to the scanner at [`../scripts/scan_output.py`](../scripts/scan_output.py). The scanner detects the phrases; this file explains why each one matters and what to write instead.

## How to Read This Catalog

Each entry follows the same shape:

- **Phrase:** the literal or regex pattern to recognize
- **Category:** one of the seven categories below
- **Why it is a shortcut:** the underlying behavior the phrase covers
- **Replacement framing:** what to write instead
- **Discussion exemption:** when the same phrase appears as a teaching example or quoted reference, the scan should not fire

The seven categories: `backward_compat`, `minimal_diff`, `asking_as_shortcut`, `deferral`, `archive_value`, `dismissal`, `scope_excuse`.

The rule across all categories: if the user has explicitly removed the consideration the phrase optimizes for, the phrase is a costume and the draft needs to be rewritten.

---

## Category 1: `backward_compat`

**The pattern:** preserving old APIs, paths, imports, or behaviors when the user has stated breaking changes are fine. The shortcut is avoiding the work of updating all consumers and instead landing a shim layer.

**The constraint that makes it a costume:** "Breaking changes are acceptable" or "best solution, no shortcuts" or "no one else uses this yet."

### `backward compatible`

Why it is a shortcut: preserves the old API surface. When the user has stated they want the clean refactor, "backward compatible" is an unrequested constraint imposed by the agent.

Replacement framing: name the clean refactor that updates all consumers. State the count of files touched as evidence of completeness, not as a deterrent.

### `preserves existing imports` / `preserves existing API`

Why it is a shortcut: justifies a shim or partial migration by what it preserves rather than what it accomplishes.

Replacement framing: name what the change accomplishes for the new architecture. The old imports are exactly what is being replaced — preserving them defeats the migration.

### `shim layer` / `compatibility layer`

Why it is a shortcut: a shim is a structural choice to avoid the work of updating consumers. It also leaves a permanent maintenance cost in the codebase.

Replacement framing: update the consumers. If there are many, batch them; the work is mechanical and bounded.

### `easier rollback` / `lower risk of breaking`

Why it is a shortcut: optimizes for the failure scenario instead of the success one. When the user has accepted breaking changes, the rollback path is not the relevant axis.

Replacement framing: name the architectural improvement the change delivers. Rollback is a deployment concern, not a design constraint.

### `no breaking changes`

Why it is a shortcut: imposes a constraint the user did not state and explicitly rejected.

Replacement framing: list the specific breaking changes and what each consumer needs to update to.

---

## Category 2: `minimal_diff`

**The pattern:** leaving half-applied work after a partial pass because "the rest can be a follow-up." Surfaces as residual styling, residual stale references, half-migrated code. Especially common in sub-agent self-reports where the sub-agent's brief licensed the partial pass.

**The constraint that makes it a costume:** "best, most flexible, robust, maintainable solution" or any framing where completeness is the goal.

### `minimal diff` / `keep changes minimal`

Why it is a shortcut: license to leave half-applied work as a follow-up. Reads as scope discipline; behaves as avoidance.

Replacement framing: name the full scope of the semantic change ("apply the accent everywhere it semantically belongs"). The diff size is a consequence of the scope, not a constraint on it.

### `tinting not redesigning` / `light touch` / `surgical change`

Why it is a shortcut: vocabulary that pre-licenses a partial pass.

Replacement framing: state the job's actual size. If the job is "re-theme the chrome," do the chrome — all of it. If the job is one specific element, name that element explicitly.

### `low risk change` / `low-risk pass`

Why it is a shortcut: optimizing for risk minimization when the user has stated completeness matters more than risk.

Replacement framing: name the completeness criterion. The risk discussion belongs in the deployment plan, not the design.

### `preserve existing layout` / `don't break the existing layout`

Why it is a shortcut: in sub-agent dispatch briefs, this phrase licenses the sub-agent to leave design problems untouched.

Replacement framing: "the existing layout is the canvas; the new layer is X; apply X everywhere it semantically belongs."

---

## Category 3: `asking_as_shortcut`

**The pattern:** surfacing decisions to the user as questions when the user's stated constraints already determine the answer. Polite-feeling consultation that is actually an offload.

**The constraint that makes it a costume:** any standing constraint that determines the answer. The user has paid the cognitive cost of stating the constraint once; asking them to re-state it for every decision is offloading the work back.

### `Recommendation: X. Your call?`

Why it is a shortcut: the format mimics junior-engineer consultation but applies in the wrong direction when X is constraint-determined.

Replacement framing: execute on the constraint-determined answer. State what was done in the response. If the constraint genuinely does not determine the answer, drop the recommendation framing and ask a precise question.

### `your call` / `up to you` / `let me know your preference`

Why it is a shortcut: offloads constraint-determined decisions.

Replacement framing: execute. Tell the user what was done.

### `should I (do|use|build|pick|choose|select)` patterns

Why it is a shortcut: should-I questions are legitimate only when constraints leave a real open. Often they don't — the agent simply forgot to scan for constraints first.

Replacement framing: scan constraints. If determined, execute. If not determined, the question is fine — keep it brief and specific.

### `would you like me to...?`

Why it is a shortcut: same offloading pattern in a softer register.

Replacement framing: same — scan constraints, execute if determined.

---

## Category 4: `deferral`

**The pattern:** pushing real work to "later" / "follow-up" / "next phase" when the user has explicitly said "complete this, no shortcuts." Includes the classic "for now" and a long tail of synonyms.

**The constraint that makes it a costume:** "don't defer," "complete this today," "no shortcuts," or the absence of any signal that work should be split.

### `for now` (with comma or period)

Why it is a shortcut: classic deferral. The phrase implies a follow-up that often never happens, and the deferred item becomes the user's mental load.

Replacement framing: do the work. If the work is genuinely too large for the session, name a concrete scope split rather than a vague "for now."

### `as a first pass` / `as a starting point`

Why it is a shortcut: implies a follow-up pass. Again, the follow-up often never happens.

Replacement framing: name the complete version. If the complete version is too large, propose the split with concrete cuts.

### `can revisit later` / `revisit in a future session`

Why it is a shortcut: the revisit is not on anyone's calendar.

Replacement framing: do it now or name the specific trigger that would cause the revisit.

### `follow-up the orchestrator can request`

Why it is a shortcut: specific costume from sub-agent reports. The phrase licenses the sub-agent to stop short and asks the orchestrator to choose whether to finish the job.

Replacement framing: the orchestrator catches this and finishes the work in-session. Do not propagate the deferral up the chain.

### `leave for (a |the )?follow-up` / `tackle in a follow-up`

Why it is a shortcut: same pattern, different phrasing.

Replacement framing: same — finish the work in-session.

### `future session` / `next phase` / `in the interim`

Why it is a shortcut: vocabulary that distances the work from the current session.

Replacement framing: name the work and do it.

### `audit later` / `handle later` / `we can defer`

Why it is a shortcut: explicit deferral.

Replacement framing: audit now or handle now. If a real reason to defer exists, name it concretely (specific blocker, specific dependency).

### `we'll tackle` / `we'll handle` (future tense, vague)

Why it is a shortcut: future-tense vagueness covering present-tense avoidance.

Replacement framing: present-tense action or concrete scheduling.

---

## Category 5: `archive_value`

**The pattern:** leaving stale content (old model names, deprecated examples, outdated tables) under labels like "archive," "historical reference," "legacy" when the user wants clean public-facing artifacts. Git history serves the archival purpose better than stale content in a live README.

**The constraint that makes it a costume:** "clean public artifact," "professional positioning," "current state of the world," or any signal that the artifact represents the present rather than the past.

### `archive value` / `historical archive`

Why it is a shortcut: excuse for leaving stale content. The genuine archive is git history.

Replacement framing: delete the stale content. If a historical reference is genuinely useful, write a new section explicitly framed as "historical context" with current commentary, not a frozen artifact of the old state.

### `historical reference`

Why it is a shortcut: same pattern. Often a costume for "I left it because deleting was work."

Discussion exemption: the phrase "historical reference frame" or "historical reference article" or "as a historical reference piece" is a legitimate usage referring to scholarly framing.

Replacement framing: delete and rely on git history, or rewrite as current-context commentary.

### `as-is for legacy` / `legacy reasons`

Why it is a shortcut: invokes legacy as a permission to leave alone.

Replacement framing: identify the actual constraint (specific consumers, specific dependencies). If no concrete constraint exists, the artifact gets updated.

---

## Category 6: `dismissal`

**The pattern:** dismissing user-raised concerns as "not a real issue," "theoretical," "not a pain point today" instead of solving them. The user raised it; that is the data point that determines whether it matters.

**The constraint that makes it a costume:** any user-raised concern, even an oblique one phrased as a question.

### `not a pain point today` / `not a pain point yet`

Why it is a shortcut: predicts away a user-raised concern by guessing about the future.

Replacement framing: solve the concern. If it is genuinely speculative, name the conditions under which it would matter and the cost of preparing now.

### `doesn't bite hard` / `doesn't bite at current volume`

Why it is a shortcut: dismissal via predicted impact.

Replacement framing: same — solve, or name conditions.

### `not a real concern` / `not a real issue`

Why it is a shortcut: directly contradicts the user's own framing.

Replacement framing: take the concern at face value. Propose the implementation that addresses it.

### `the only real con is`

Why it is a shortcut: pre-dismisses other listed concerns to elevate the chosen approach.

Replacement framing: list the real cons honestly. If they don't sink the approach, say why each is acceptable in the specific situation.

### `that's a theoretical concern` / `theoretical concern`

Why it is a shortcut: invokes "theoretical" to avoid building defenses.

Replacement framing: name when the theoretical becomes practical, and what would change at that point.

### `still unused` / `won't matter until`

Why it is a shortcut: deferral and dismissal merged.

Replacement framing: solve now or name the specific trigger.

### `not urgent`

Why it is a shortcut: triage vocabulary used to deprioritize a user-raised concern.

Discussion exemption: legitimate triage discussion ("we are marking this not urgent because X") is fine. The costume is using it to wave away a concern.

Replacement framing: if genuinely lower priority, name the higher priorities concretely. Don't strand the concern with a label.

### `mitigated by`

Why it is a shortcut: implies a mitigation without naming one.

Discussion exemption: concrete mitigations ("mitigated by the fix in PR #123," "mitigated by alerting") are legitimate. The costume is the bare phrase.

Replacement framing: name the specific mitigation, where it lives, and what it covers.

---

## Category 7: `scope_excuse`

**The pattern:** using "pre-existing," "out of scope," "not introduced by this change" to avoid fixing problems in code being actively modified. The right approach is fix-while-touching unless the work is genuinely outside the scope the user defined.

**The constraint that makes it a costume:** "zero accepted code-health debt," "leave it greener than you found it," or simply the fact that the code is being actively modified in the same session.

### `pre-existing so` / `pre-existing issue`

Why it is a shortcut: invokes the issue's age to avoid fixing it.

Replacement framing: fix it. The mental model is loaded; the marginal cost is low.

### `out of scope`

Why it is a shortcut: often a costume for "I don't feel like doing this."

Discussion exemption: legitimate scoping ("this is the scope of this PR / this commit / this task") is fine. The costume is the bare phrase.

Replacement framing: name the scope boundary explicitly and why the item falls outside it. If you cannot name the boundary, the item is in scope.

**Sub-agent dispatch note (confirmed 2026-07-17):** in a sub-agent brief specifically, the automated dispatch-time scanner appears to match on the bare phrase regardless of whether a boundary reason follows it in the same sentence — a brief that wrote "leave X untouched, don't merge it, don't delete it — it's a separate, already-curated artifact" was blocked even though it satisfies the discussion exemption above by any reasonable read. Rather than relitigate the block, the reliable fix is to skip the phrase entirely in dispatch briefs: state the concrete instruction ("leave X untouched: don't do Y to it, don't do Z to it, because [reason]") without ever writing "out of scope" as a label. This produces a brief that is also better on its own terms (a concrete instruction is less ambiguous to a sub-agent than an abstract scope label), so the workaround is not a compromise.

### `not introduced by this change`

Why it is a shortcut: same pattern, slightly different wording.

Replacement framing: same — fix while touching.

### `that's a larger task`

Why it is a shortcut: invokes size to defer.

Replacement framing: if it is genuinely larger, propose the split. If it is the same size, do it.

### `YAGNI` (as dismissal)

Why it is a shortcut: invokes a legitimate engineering principle to dismiss a user-raised concern.

Discussion exemption: "the YAGNI principle" or quoted "YAGNI" references the principle, not applying it.

Replacement framing: real YAGNI is about not building speculative features. Applying it to user-raised concerns is misuse. Solve the concern.

---

## How the Catalog Maintains Itself

When a new costume appears in production output, three steps:

1. Document the incident with enough detail that the failure mode is clear. The anonymized case studies in [`case-studies.md`](case-studies.md) follow a consistent shape — situation, costume, why it counted as a costume, what should have happened.
2. Add the phrase to this catalog. Pick the right category. Write the rationale and replacement framing.
3. Add the phrase to the scanner's embedded catalog in [`../scripts/scan_output.py`](../scripts/scan_output.py) if it should fire automatically.

The methodology is durable. The catalog grows.
