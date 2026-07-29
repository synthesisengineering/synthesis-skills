# Sub-Agent Hygiene

When an orchestrating agent dispatches a sub-agent to do a portion of the work, two failure points appear that do not exist in single-agent work. Both are entry points for the lazy-shortcut antipattern. This reference covers the discipline at both points.

The two failure points:

1. **Dispatch** — The orchestrator's brief licenses the sub-agent to leave work undone. If the brief contains costume vocabulary, the sub-agent will produce work that matches.
2. **Acceptance** — When the sub-agent returns, the orchestrator accepts its self-flagged tradeoffs without scrutiny. The sub-agent's "I left X for minimal diff" propagates into the orchestrator's summary unchallenged.

The discipline below addresses each in turn.

---

## Part 1: Dispatch

### The Principle

A sub-agent reads its brief as the definition of the job. Vocabulary in the brief that limits scope ("minimal," "surgical," "conservative") will be read as "do less than the job appears to require." The sub-agent will then produce work that matches the limited framing, often with a self-report that proudly identifies what it chose to leave undone.

This is not the sub-agent failing. It is the brief failing. The brief gave permission for the partial pass.

### Phrases That Should NOT Appear in a Sub-Agent Brief

Each of these phrases licenses the sub-agent to leave work undone:

- "Keep changes minimal"
- "Minimal diff"
- "Light touch"
- "Surgical change"
- "Conservative pass"
- "Tinting, not redesigning"
- "Don't break the existing X"
- "Preserve the existing X" (when the existing X is the thing being changed)
- "Low-risk pass"
- "Where possible, leave existing code alone"
- "Touch as little as possible"

When any of these appear in a draft brief, rewrite before dispatch. The replacement is below.

### Replacement Framing

The replacement names the full size of the semantic job. The brief defines the work in terms of what the world should look like after the change, not in terms of how little code should move.

| Costume framing | Replacement framing |
|---|---|
| "Tint the chrome blue → new color, keep diffs minimal." | "The existing layout is the canvas. The new accent is the new layer. Apply it everywhere it semantically belongs — buttons, focus rings, active states, hover states, text where blue currently signals interactivity." |
| "Conservative pass over the README to fix the 2024-era model references." | "Update the README so every model reference reflects the 2026 ecosystem. Delete stale examples that no longer represent the project. Replace `<details>Legacy</details>` blocks with current equivalents or remove them — git history is the archive." |
| "Light touch on the import paths — keep existing paths working." | "Move modules to the new package. Update every consumer's import path. Delete the old paths. The transition window is acceptable; the substrate must be genuinely independent." |
| "Surgical fix for the failing test." | "Find the root cause of the failure, fix it at the root, and verify nothing else depends on the broken behavior. If the root cause is a design issue in code the fix touches, fix the design too." |

### The Brief Template

A clean brief contains four sections:

1. **The change in the world** — what should be different about the system after the work is done. Stated in terms of outcomes, not diff size.
2. **The boundaries** — explicit scope statements. What is in scope, what is out of scope. Both stated affirmatively; neither stated as "minimal" or "conservative."
3. **The constraints** — the user's stated goals and non-goals carried forward from the orchestrator's constraint extraction. The forbidden criteria list goes here too.
4. **The signal of completion** — what the orchestrator will check to verify the sub-agent finished. Specific files, specific search results, specific behaviors.

A sub-agent that reads this brief knows the full size of the job, knows what is in scope, knows what cannot appear in its pros list, and knows how its work will be verified. The license to leave work undone is removed.

---

## Part 2: Acceptance

### The Principle

When a sub-agent returns, it reports its work and often flags tradeoffs it made. Self-flagged tradeoffs read as honest disclosure. They often are. They are also the most common entry point for propagating the lazy-shortcut antipattern from the sub-agent up to the orchestrator's summary.

The orchestrator's job at acceptance: scrutinize the self-flagged tradeoffs against the user's constraints. If the tradeoff violates a constraint, the orchestrator finishes the work in-session. It does not propagate the deferral.

### The Acceptance Checklist

Run this on every sub-agent return:

1. **Read the full report.** Including any "tradeoffs," "notes," "follow-ups," "things I left for the orchestrator," "future improvements." This section is where the shortcuts hide.

2. **Scan for costume vocabulary.** Either by eye against the catalog at [`costume-vocabulary.md`](costume-vocabulary.md), or by running the scanner at [`../scripts/scan_output.py`](../scripts/scan_output.py) against the sub-agent's report.

3. **For each hit, classify.** Is the phrase legitimate in this context, or is it a costume?

   The test: would the user, given stated goals and non-goals, consider this acceptable? Not "would a reasonable engineer consider this acceptable" — the user's standard is the relevant one. The user's "best, most flexible, robust, maintainable solution" framing sets the bar.

4. **For each costume, decide the remediation.**

   - **Redirect the sub-agent.** Send the sub-agent back with a narrower brief that addresses the specific gap.
   - **Finish in-session.** The orchestrator does the remaining work directly.
   - **Verify the framing.** If the orchestrator decides the sub-agent's framing was actually correct (rare, but possible), document why and move on.

5. **Update the orchestrator's summary.** The summary the user sees should not contain the sub-agent's costume framing. If the costume was real (the sub-agent left work undone), the summary reports the work as complete (after the orchestrator's finishing pass) — not as "the sub-agent left X for follow-up, here is what to do next."

### Examples of What to Catch

**Sub-agent reports:** "I applied the new accent to the main chrome surfaces called out in the brief. I left residual blue Tailwind classes (`bg-blue-100`, `focus:ring-blue-500`) elsewhere as a follow-up the orchestrator can request."

**Catch:** The brief, if written cleanly per Part 1, said "apply the new accent everywhere it semantically belongs." The sub-agent's "follow-up the orchestrator can request" is the costume. The remediation: sweep the residual classes. Either redirect the sub-agent or do it directly. Do not propagate the deferral.

**Sub-agent reports:** "I deprecated the legacy examples block but left it in place under a `<details>` collapse for historical reference."

**Catch:** "Historical reference" is the costume. Git history serves the archive role; stale content in a live README undermines the artifact. The remediation: delete the block.

**Sub-agent reports:** "I considered three approaches and selected Approach A. Pros: backward compatible — existing 327 tests pass unchanged."

**Catch:** "Backward compatible" and "existing tests pass unchanged" are costumes if the constraints list "backward compatibility is not a goal." The remediation: redirect the sub-agent with a sharper constraint statement, or run the constraint-first protocol on the orchestrator side and pick the right approach.

### When the Sub-Agent Is Right

Sometimes the sub-agent's "I left X" is correct. The orchestrator's brief was wrong, or the constraint set genuinely permits the partial pass, or new information emerged during the work that changed the scope.

In these cases, the orchestrator's job is to document the corrected framing — not to propagate the original framing unchanged. The summary the user sees explains why the partial pass was the right call, with reference to a specific constraint or new information. "Follow-up the orchestrator can request" is not an explanation. "The X surface is owned by a separate team and out of scope for this repo" is.

---

## Common Failure Modes

### Failure Mode 1: The brief uses costume vocabulary; the orchestrator forgets to audit acceptance

The orchestrator wrote "keep changes minimal" in the brief, the sub-agent produced half-applied work and self-reported "I kept it minimal as requested," and the orchestrator's summary read "sub-agent completed the minimal pass as expected."

The work has now shipped with the partial pass labeled as success. The user discovers the gap downstream.

**Fix:** scrub the brief before dispatch (Part 1), and audit acceptance even when the sub-agent reports success (Part 2). Both checks are independent.

### Failure Mode 2: The orchestrator stages its own work and commits the sub-agent's parallel work by accident

The orchestrator runs `git add <its-files>` and then `git commit`. The sub-agent had staged work via `git mv` for an in-progress refactor. The `git commit` sweeps everything in the index into the commit. The commit message describes only the orchestrator's work; the sub-agent's partial refactor is silently included.

**Fix:** before any `git commit` in a session where a sub-agent has run or is running in the same repo, run `git status` and `git diff --cached --name-only` to verify the index contents. Use `git commit -o <paths>` to commit only specific paths regardless of index state, or `git restore --staged <other-files>` to unstage what isn't yours.

This is a process failure rather than a vocabulary failure, but it has the same shape: the agent accepted the default behavior (commit everything in the index) when the situation required explicit inspection.

### Failure Mode 3: The orchestrator's summary launders the sub-agent's costume into success

The sub-agent reports "minimal diff, residual X left for follow-up." The orchestrator's summary to the user says "applied the new accent across the chrome." Two things are wrong: the work was not actually complete, and the summary actively misrepresents what happened.

**Fix:** the orchestrator's summary must reflect actual state. If the sub-agent left work undone and the orchestrator finished it, say so. If the orchestrator chose not to finish it, name the specific reason. Never launder a partial pass into a clean summary.

---

## When to Apply

- Every sub-agent dispatch, regardless of task size
- Every sub-agent return
- Every cross-agent handoff where one agent's brief becomes another agent's instructions
- Any pipeline where a previous stage's output feeds a next stage

The discipline scales down to small dispatches. It is cheap on a small task and load-bearing on a large one. The cost of skipping it on a small task is low; the cost of skipping it on a large one is the propagation of the antipattern through every downstream stage.

## The Underlying Principle

Sub-agents inherit their orchestrator's trained defaults. A sub-agent given an ambiguous or costume-laden brief will produce work that matches the framing. The orchestrator owns both the brief and the acceptance — that is the structural fix. The sub-agent cannot fix a brief it did not write.
