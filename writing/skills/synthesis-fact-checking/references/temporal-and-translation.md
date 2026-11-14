# Fact-checking: temporal and translation-pass verification

Sections 9 and 10 of the fact-check process, verbatim. Apply section 9 when an article carries a publication date in the past, and section 10 after any pass that trades precise terms for accessible ones.

## 9. Temporal Verification (for Backdated Articles)

When writing or revising an article with a publication date in the past, temporal integrity must be maintained.

### Rules

1. **All cited sources must predate the article's stated publication date.**
2. **External sources that postdate the article date require an explicit "Updated on" note.**
3. **Time-relative language must be accurate relative to the article date.** "Recently," "this year," "last month," "emerging."
4. **Do not cite preliminary data if final data was available by the article date.**

### Common Temporal Errors

- Calling a 2022 report "recent" in an article dated 2025.
- Citing a December 2024 source in an article dated November 2024.
- Using "the emerging field of..." for something well-established by the article date.
- Describing future events as future when they have already occurred by the article date.

---

## 10. Translation-Pass Re-Verification

Apply this protocol when an article has been through a de-jargoning, anonymization, or accessibility pass: any pass that replaces precision-bearing terms with vaguer prose for the benefit of a wider audience.

The translation pass introduces its own accuracy hazard. The pre-translation prose was precise and verifiable. The post-translation prose is accessible: and may no longer be true.

### Why this is a distinct fact-check step

The standard fact-check (sections 1-8) verifies that claims match source material. The translation pass happens AFTER that verification, when accessibility editing rephrases verified claims. The rephrasing can:

1. **Generalize what was specific.** "v0.8.0" replaced by "the first version" is wrong if earlier versions existed.
2. **Soften what was definite.** Specific function descriptions replaced by layer-level abstractions that may not be accurate.
3. **Lose load-bearing precision.** Specific metrics rephrased generally may obscure results the argument depended on.
4. **Convert verified facts into approximations the writer cannot defend.**

### Procedure

1. **List the changes.** During the translation pass, keep a list of every replacement: original term, replacement, reason.
2. **Re-verify each entry against the source.** For every replacement, ask: is the new wording true at its new level of precision?
3. **Flag soft drift.** Replacements that lose precision without losing truth are fine. Replacements that change truth conditions are not fine.
4. **Restore precision when the translation breaks the claim.** If the rephrasing makes a claim wrong, restructure rather than restore the original term.

### Worked example

Original: "I shipped synthesis-console v0.8.0 with the cockpit view of my daily plan."

De-jargoning replaced: "synthesis-console v0.8.0" → "the first version of the dashboard."

Re-verification flagged: the dashboard had been shipping for many versions before v0.8.0; v0.8.0 added the cockpit view as a new feature, not as the dashboard's first version. The replacement was wrong.

Restored: "I shipped the cockpit view of the daily plan as a new feature." Preserves accessibility (no version number) while keeping the claim true.
