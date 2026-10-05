# Coverage map: code audit 1.1.0 to 2.0.0

Every part of the 1.1.0 SKILL.md and where it lives now. Nothing was removed, and the coverage check finds every old line verbatim.

| 1.1.0 section | Now |
|---|---|
| Frontmatter description (long keyword list) | Shortened to 282 characters; the 1.1.0 text is kept below |
| `depends_on`, `source_repo`, `source_type` | Kept: `conformance.py source` (skill-contract check) and onboarding's `modular.py` dependency selection read them; `synthesis-preflight` and `synthesis-preplan` depend on this skill |
| Opening paragraph ("A code audit is a systematic quality measurement...") | SKILL.md (verbatim); Binding rule 1 |
| Where This Fits | references/principles-and-rules.md (verbatim) |
| Principles 1 to 4 | references/principles-and-rules.md (verbatim); Binding rules 2 to 5 |
| Diff Scope Detection, including large diffs | SKILL.md (verbatim); Binding rule 7 |
| The 10-Dimension Framework: grading scale | SKILL.md (verbatim), followed by a new list of the ten dimension names |
| Dimensions 1 to 10 | references/dimensions.md (verbatim) |
| Reporting | SKILL.md (verbatim); Binding rule 7 |
| PR Review Mode (Cross-Referencing) | SKILL.md (verbatim) |
| Rules | references/principles-and-rules.md (verbatim); Binding rules 1, 2, 3, 5, 6 and 8 |

## The 1.1.0 description

> Systematic 10-dimension quality scan of code diffs, producing scored PASS/WARNING/FAIL verdicts per dimension with a machine-readable overall result. Includes PR review mode for cross-referencing findings against existing reviewer comments. Use when asked to: code audit, audit my changes, quality check, review the diff, check this code, audit my code, scan for issues, code quality scan, diff review.
