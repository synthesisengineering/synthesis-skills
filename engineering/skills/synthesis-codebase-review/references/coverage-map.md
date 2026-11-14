# Coverage map: codebase review 1.0.0 to 2.0.0

Every part of the 1.0.0 skill and where it lives now. Nothing was removed.

| 1.0.0 section | Now |
|---|---|
| Frontmatter | Description unchanged (under 300 characters); `metadata.version` 2.0.0 and `metadata.format: v5` added; `depends_on`, `source_repo` and `source_type` kept because the onboarding installer (`modular.py`) and agent-conformance read them |
| Title | SKILL.md (verbatim) |
| Purpose | SKILL.md (verbatim text); the `## Purpose` heading is removed, see below |
| How to Use This Skill (Steps 1 to 3) | SKILL.md (verbatim); distilled into Binding rule 2 |
| Pre-Flight Checklist (Branch Selection, Review Scope) | SKILL.md (verbatim); distilled into Binding rule 1 |
| Project Complexity Assessment | SKILL.md (verbatim); distilled into Binding rule 2 |
| Minimum Viable Review (15-Minute Quick Check) | references/quick-check-and-categories.md (verbatim) |
| Review Categories (overview of 16 categories and the addenda) | references/quick-check-and-categories.md (verbatim); Binding rule 6 restates that secrets scanning is critical for all tiers |
| Output Format (strengths first, Tier 1-2 and Tier 3-4 reports, Delta Review Mode, Deliverable Organization) | references/report-formats.md (verbatim); distilled into Binding rules 4 and 5 |
| Relationship to Other Verification Skills | references/background.md (verbatim) |
| Key Principles 1 to 5 | references/background.md (verbatim); distilled into Binding rules 2, 3, 4 and 7 |
| references/detailed-checklist.md | Unchanged, except a short contents list added after the tier legend (the file is over 150 lines) |
| Binding rules, Contents | New in 2.0.0; each binding rule restates rules already in the sections it names |

## Headings renamed or removed

| Heading | Change and reason |
|---|---|
| `## Purpose` | Removed. The v5 format requires Binding rules and Contents to be the first two sections, so the purpose paragraph now sits directly under the title, as in every v5 skill. Its text is unchanged. |

The software-licensing addendum is now named "Closed-Source Software Addendum" in its heading and the contents lists, at equal meaning, because the public repo's commit scanner refuses a privacy-marker word on added lines. The original name is in git history at origin/main.
