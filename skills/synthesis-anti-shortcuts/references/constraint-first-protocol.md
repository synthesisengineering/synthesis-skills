# The Constraint-First Protocol

A step-by-step procedure for writing the user's stated constraints before generating approaches to a non-trivial decision. The protocol prevents the most common entry point for the lazy-shortcut antipattern — generating options whose pros violate constraints the user already set.

## Why the Order Matters

When an agent generates approaches first and then evaluates them against constraints, the conservative-default approach often wins. Its pros include "lower risk," "smaller diff," "easier rollback" — pros that read as engineering virtue when scored without context. The agent then either fails to catch the conflict with stated constraints, or rationalizes the conflict in the selection step.

When the agent writes the constraints first, those pros become structurally forbidden. They cannot appear in the analysis. The remaining option space contains only approaches that respect the constraints. The selection step now picks the best legitimate option, not the safest-feeling option overall.

The order is small. The behavioral difference is large.

## The Protocol

### Step 1. Extract Constraints from Five Sources

Read each source in order of recency. Most specific wins. Capture goals AND non-goals — both shape the option space.

1. **Current conversation** — the most recent user turn, then the surrounding context. Look for explicit statements like "I want X" or "I don't want Y," but also for negative framings ("I don't care about backward compatibility," "I want the best solution, not the safest one").
2. **Project context files** — for projects using a durable-memory layout (e.g., `CONTEXT.md`, `REFERENCE.md`), read both. Capture standing constraints that apply to the project.
3. **Workspace agent-instruction files** — `CLAUDE.md`, `AGENTS.md`, `.cursor/rules`, or whichever convention your agent platform uses. These hold workspace-scoped standing rules.
4. **Global agent-instruction files** — `~/.claude/CLAUDE.md`, `~/.codex/AGENTS.md`, equivalent for other platforms. These hold cross-project standing rules.
5. **Active per-workspace or per-project memory files** — incident-driven rules that resolve recurring failure modes.

### Step 2. Write the Constraint Section

The first section of the analysis is "Constraints" or "Boundary Conditions." It lists:

- **Stated goals** — what the user wants
- **Stated non-goals** — what the user has explicitly said they do not want
- **Forbidden criteria** — pros that would violate the non-goals, marked as forbidden in the analysis

The forbidden-criteria list is the key. Each entry maps a stated non-goal to the specific phrases that cannot appear as pros.

### Step 3. Generate Approaches Under the Filter

Generate at least two distinct approaches. For each, list pros and cons honestly. The filter: no pro from the forbidden-criteria list can appear. If an approach's primary appeal would be a forbidden pro, the approach is structurally unavailable.

If an approach's pros list reads as "smaller change," "lower disruption," "easier rollback," "preserves the old way" — and the constraints have removed those criteria — that approach is not a legitimate option. Cross it out before continuing.

### Step 4. Select and Justify

With the option space filtered, select the best remaining approach. The justification references specific constraint-aligned criteria:

- Which goals this approach serves best
- Which non-goals it respects (and the alternatives that violated them)
- What is sacrificed by not choosing the alternatives (real sacrifices only — not the forbidden criteria, which are not sacrifices but constraints)

### Step 5. Pre-Send Scan

Before sending the analysis, run the scanner at `../scripts/scan_output.py` against the draft. The scanner catches any costume vocabulary that slipped past the manual filter. Each hit is a flag for rewrite, not necessarily a deletion — some matches are legitimate discussion (e.g., the analysis explicitly says "I considered backward compatibility and rejected it for X reason"). Use judgment, but treat the scanner's hits as the default.

## A Worked Example

Setting: an agent is asked to plan the extraction of a substrate library from an existing application package, so a future application can also depend on the substrate.

### What the user has said

In the current conversation:

> "Backward compatibility is not a goal of mine in this work. I want the best solution(s), not backward compatible ones. Totally open to making visible breaking changes."

In the global agent-instruction file:

> "Superior solution by default — always implement the proper solution, not the easy one."

In the project context:

> "No external consumers yet; the library is being extracted to demonstrate clean architecture."

### Step 2 — the Constraints section the agent writes first

**Stated goals**
- Clean separation between substrate library and application
- Best architecture, not the safest-feeling architecture
- Public-quality reference implementation of substrate / application split

**Stated non-goals**
- Backward compatibility with old import paths
- Minimizing diff size
- Lower-risk pass over higher-quality pass

**Forbidden criteria** — these pros cannot appear in any approach
- "Backward compatible"
- "Preserves existing imports"
- "Existing tests pass unchanged"
- "Easier rollback"
- "Lower risk of breaking" the existing consumers
- "Smaller diff"
- "Shim layer"

### Step 3 — Approaches under the filter

**Approach A: Subpackage with backward-compat shims at old paths.** [REJECTED BEFORE LISTING — pros depend on forbidden criteria.]

**Approach B: Clean split.** Move modules to the new package. Update every consumer's imports. Delete old paths.
- Pros: clean architecture; substrate library is genuinely independent; reference implementation is unambiguous.
- Cons: every consumer needs updating (mechanical, ~30 imports across N files); CI failures during the transition window.

**Approach C: Namespace re-export, no real extraction.** Keep code in the old package; expose a new namespace that re-exports.
- Pros: minimal change.
- Cons: the "extraction" is cosmetic; the substrate is not actually separable; the architecture does not serve the stated goal.

### Step 4 — Selection

Approach B. The constraints make it the only approach that serves the stated goal. Approach C is rejected because the cosmetic split does not deliver the clean architecture the user asked for. Approach A is structurally unavailable.

What is sacrificed: a transition window during which consumers fail to import correctly. Mitigation: do the updates in one commit, run the test suite, verify all consumers compile, then ship.

### Step 5 — Pre-send scan

Running the scanner against the draft surfaces zero hits in the analysis section. (Hits in the rejected Approach A would be marked as discussion mode if the rejection is explicit.) The draft is sent.

## What the Anti-Pattern Would Have Looked Like

Without the constraint-first protocol, the agent generates three approaches first, lists their pros and cons, and selects. The selection step looks like this:

> Approach A (shims) keeps the existing 327 tests passing unchanged and offers easier rollback. Approach B requires updating 30 imports and risks a transition-window failure. Approach C is cosmetic.
>
> **Recommendation: Approach A.** It minimizes disruption and preserves the existing test signal.

The selection sounds reasonable. It is wrong. The forbidden criteria — "existing 327 tests pass unchanged," "easier rollback," "minimizes disruption," "preserves the existing test signal" — are exactly the pros the user removed from the option space. The agent has overridden the user's explicit instruction with its trained conservative default.

The constraint-first protocol makes this override structurally impossible. The pros that drive the wrong selection are not allowed to appear.

## A Note on Friction

The constraint-first protocol adds a small step to every non-trivial decision. The friction is real and visible.

The friction is also load-bearing. Without it, the override happens silently and the user pays the cost on the back end — auditing every output, re-stating the same constraints across sessions, cleaning up shim layers that should never have shipped. The protocol moves the cost from the back end (where it compounds across the user's mental load) to the front end (where it is bounded and predictable).

The right comparison is not "with the protocol vs without the protocol." It is "with the protocol vs the cumulative debugging cost of shipping the conservative-default solution that violated the constraints."

## When to Skip

The protocol applies to non-trivial decisions. Trivial work — single-line config changes, typo fixes, renaming a variable — does not warrant the protocol. The threshold: if the implementation is obvious, unambiguous, and the option space contains exactly one reasonable choice, skip.

When in doubt, run the protocol. The cost is low. The benefit when it catches an override is high.

## Mechanical Checklist

Print or paste this above any non-trivial analysis:

- [ ] I have read recent conversation, project context, workspace rules, and global rules.
- [ ] I have written stated goals.
- [ ] I have written stated non-goals.
- [ ] I have written forbidden criteria — the pros that cannot appear.
- [ ] I have generated approaches under the filter.
- [ ] I have selected and justified with constraint-aligned reasoning.
- [ ] I have run the scanner on the draft.
- [ ] Zero unresolved costume-vocabulary hits remain.
