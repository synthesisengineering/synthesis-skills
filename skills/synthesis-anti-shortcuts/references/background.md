# Anti-shortcuts: background

Why the lazy-shortcut pattern happens, how the pieces of this skill fit together, how it relates to other skills, and the principle under all of it.

## Why this exists

A discipline for catching the lazy-shortcut antipattern in AI-assistant output before it ships. The pattern is simple: when a user states "best solution, no shortcuts," the agent often produces a draft that looks like good engineering but quietly substitutes a lower-effort path. The substitution hides under reasonable-sounding vocabulary — "for now," "minimal diff," "backward compatible," "out of scope," "archive value." This skill names those costumes and provides the protocol to strip them out.

The pattern is not unique to one model or one user. It is a structural failure mode of agents trained on conservative defaults — minimize change, hedge claims, defer hard choices. Those defaults are correct when no one has said otherwise. They are wrong, and quietly harmful, when the user has explicitly removed them from the constraint set and the agent overrides that instruction with its trained safety preference.

This skill is the methodology. The operational catalog in `scripts/scan_output.py` is the extract — a phrase scanner that any agent or pipeline can run against draft output. The detailed catalog with rationale, the constraint-first protocol with a worked example, the sub-agent dispatch and acceptance rules, and the anonymized case studies all live in `references/` and load on demand.

## How the Pieces Fit

```
SKILL.md (this file)
   |
   |-- references/costume-vocabulary.md      Full phrase catalog with rationale
   |-- references/constraint-first-protocol.md  Worked-example procedure
   |-- references/sub-agent-hygiene.md       Dispatch + acceptance rules
   |-- references/case-studies.md            Anonymized incident teardowns
   |
   |-- scripts/scan_output.py                Standalone scanner (Python 3, stdlib + pyyaml)
```

A reader who installs only this skill can apply the methodology end-to-end. The references load on demand; the scanner runs standalone or as a hook in any agent platform.

## Relationship to Other Skills

This skill is methodology. It pairs naturally with the synthesis skills that produce the artifacts it audits.

- **[synthesis-grounding-discipline](../../synthesis-grounding-discipline/SKILL.md)** — The truth-side companion. This skill catches output that does less than the work requires; grounding discipline catches output that claims more than the evidence supports — confabulated events, quotes with no tool-surfaced source, stale cached facts, absences established by a broken probe. One output can fail both at once: a fabricated "already handled" is a shortcut and a grounding failure in the same sentence.
- **[synthesis-thinking-framework](../../synthesis-thinking-framework/SKILL.md)** — Foundational reasoning methodology. The constraint-first protocol is a specialization of first-principles thinking applied to the option-evaluation step.
- **[synthesis-code-planning](../../synthesis-code-planning/SKILL.md)** — Multi-approach evaluation for code tasks. This skill's constraint-first protocol slots in as the first step before the approach-generation step in code-planning.
- **[synthesis-implementation-integrity](../../synthesis-implementation-integrity/SKILL.md)** — Post-implementation verification. This skill catches shortcuts before they're built; implementation-integrity catches incomplete work after it's built. Use both.
- **[synthesis-content-quality](../../synthesis-content-quality/SKILL.md)** — AI-pattern detection in prose. Different domain (prose patterns vs decision patterns) but a similar shape — both maintain a catalog that grows as failure modes evolve.

These skills work independently. They are stronger together. When loaded as a stack, the constraint-first protocol shapes how options are generated, the costume vocabulary scan shapes how drafts are reviewed, and implementation-integrity verifies that nothing slipped through to the build.

## The Underlying Principle

The pattern this skill catches is one specific manifestation of a more general issue: an agent's trained defaults can quietly override the user's explicit instructions, in ways the agent itself does not notice. The fix is not "try harder to follow instructions." The fix is structural — make the conflict visible at the moment of drafting, so the override cannot happen silently.

The constraint-first protocol makes the user's constraints the first thing in the draft. The costume vocabulary scan makes the override detectable in the draft. The sub-agent acceptance audit makes the same checks portable across delegated work. The maintenance loop makes new failure modes part of the system as they emerge.

The reader who applies this discipline ships work that respects the constraints the user actually stated, not the ones the agent's training would have preferred.
