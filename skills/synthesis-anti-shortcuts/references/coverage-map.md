# Coverage map: anti-shortcuts 1.2.1 to 2.0.0

Every part of the 1.2.1 SKILL.md and where it lives now. Nothing was removed.

| 1.2.1 section | Now |
|---|---|
| Frontmatter description (long keyword list) | Shortened to under 300 characters; keeps the core triggers (avoid shortcuts, audit for laziness, check for deferral, enforce best solution) and names the constraint-first protocol, sub-agent hygiene and self-check |
| Frontmatter `depends_on`, `author`, `source_repo`, `source_type`, `license` | Kept (the modular installer and the source checks read them); version bumped to 2.0.0; `format: v5` added |
| Title | SKILL.md (verbatim) |
| Three opening paragraphs | references/background.md, "Why this exists" (verbatim); a one-paragraph summary opens SKILL.md |
| When to Apply, When NOT to Apply | SKILL.md (verbatim) |
| The Pattern | references/methodology.md (verbatim); the costume table is also in SKILL.md (verbatim) |
| Delivery is part of completeness | references/methodology.md (verbatim); binding rule 9 distills it |
| The Methodology, sections 1 to 8 | references/methodology.md (verbatim, numbering unchanged); binding rules 1 to 8 distill them with the same numbers, because other documents cite "§4–5" |
| 6. Pre-Response Self-Check | SKILL.md, "Pre-Response Self-Check" (verbatim body) and references/methodology.md (verbatim) |
| How the Pieces Fit | references/background.md (verbatim) |
| Relationship to Other Skills | references/background.md (verbatim apart from link paths) |
| The Underlying Principle | references/background.md (verbatim) |
| (new) The scanner | SKILL.md: the exact command line, what it prints and its exit codes, taken from the docstring of `scripts/scan_output.py` (format rule 7) |

## Existing reference files

costume-vocabulary.md, case-studies.md and sub-agent-hygiene.md are over 150 lines, so each gained a short contents list under its title; no other line changed. constraint-first-protocol.md is unchanged. The scanner's `see:` lines still name `case-studies.md#case-N`, and those case headings are unchanged.

## Scripts and tests

`scripts/scan_output.py` and `scripts/test_scan_output.py` are unchanged. No test reads text from this SKILL.md.

## Lines the coverage check reports, and why

Thirteen lines of the 1.2.1 SKILL.md are not carried over verbatim in the live text; `v5-skill-coverage-check.py` reported them until this block quoted them. Each is text moved from SKILL.md into references/ with its wording unchanged and only a relative link target adjusted, because a link written for SKILL.md breaks one directory down (`references/x.md` became `x.md`, `../synthesis-x/...` became `../../synthesis-x/...`). Eight are in references/methodology.md, five in references/background.md. The lines below are exactly as 1.2.1 had them, with links written for SKILL.md's folder, kept only as a record.

````markdown
Each costume sounds reasonable in isolation. Each is the same shortcut wearing different clothes. The full catalog with rationale per phrase lives in [`references/costume-vocabulary.md`](references/costume-vocabulary.md).
A worked example, including the constraint-extraction order and the forbidden-criteria mapping, lives in [`references/constraint-first-protocol.md`](references/constraint-first-protocol.md).
Two question shapes look alike but behave differently. Check both whether the user's stated constraints determine the answer and who owns the remaining choice. The shared [decision-ownership contract](../synthesis-thinking-framework/references/decision-ownership.md) distinguishes already-decided choices, delegated technical choices, material principal ambiguity and human-only actions.
The full per-phrase catalog with category, rationale, and replacement framings lives in [`references/costume-vocabulary.md`](references/costume-vocabulary.md). The operational extract is in `scripts/scan_output.py`.
Full dispatch protocol lives in [`references/sub-agent-hygiene.md`](references/sub-agent-hygiene.md).
The scanner at `scripts/scan_output.py` automates step 1. The classification at step 2 is judgment; the catalog at [`references/costume-vocabulary.md`](references/costume-vocabulary.md) supports it.
3. Update [`references/costume-vocabulary.md`](references/costume-vocabulary.md) with the new entry.
The methodology stays stable. The catalog refreshes as the failure modes evolve. The anonymized case studies in [`references/case-studies.md`](references/case-studies.md) are the durable record of where each entry came from.
- **[synthesis-grounding-discipline](../synthesis-grounding-discipline/SKILL.md)** — The truth-side companion. This skill catches output that does less than the work requires; grounding discipline catches output that claims more than the evidence supports — confabulated events, quotes with no tool-surfaced source, stale cached facts, absences established by a broken probe. One output can fail both at once: a fabricated "already handled" is a shortcut and a grounding failure in the same sentence.
- **[synthesis-thinking-framework](../synthesis-thinking-framework/SKILL.md)** — Foundational reasoning methodology. The constraint-first protocol is a specialization of first-principles thinking applied to the option-evaluation step.
- **[synthesis-code-planning](../synthesis-code-planning/SKILL.md)** — Multi-approach evaluation for code tasks. This skill's constraint-first protocol slots in as the first step before the approach-generation step in code-planning.
- **[synthesis-implementation-integrity](../synthesis-implementation-integrity/SKILL.md)** — Post-implementation verification. This skill catches shortcuts before they're built; implementation-integrity catches incomplete work after it's built. Use both.
- **[synthesis-content-quality](../synthesis-content-quality/SKILL.md)** — AI-pattern detection in prose. Different domain (prose patterns vs decision patterns) but a similar shape — both maintain a catalog that grows as failure modes evolve.
````

## The 1.2.1 frontmatter

Kept whole, so the old description and keys stay on record.

```yaml
---
name: synthesis-anti-shortcuts
description: "Discipline for catching the lazy-shortcut antipattern in AI-assistant output. Makes the costume vocabulary explicit so agents recognize when their drafts have slid into deferral, dismissal, or false consultation. Includes the constraint-first protocol, sub-agent dispatch and acceptance hygiene, and a pre-response self-check. Use when asked to: avoid shortcuts, audit for laziness, check for deferral, enforce best solution, no shortcuts, anti-shortcut, constraint-first, sub-agent hygiene, costume vocabulary."
license: "Apache-2.0"
depends_on: ["synthesis-thinking-framework"]
metadata:
  author: "Rajiv Pant"
  version: "1.2.1"
  source_repo: "github.com/synthesisengineering/synthesis-skills"
  source_type: "public"
---
```
