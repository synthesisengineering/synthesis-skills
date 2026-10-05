# Coverage map: preflight 1.1.1 to 2.0.0

Every part of the 1.1.1 SKILL.md and where it lives now. Nothing was removed.

| 1.1.1 section | Now |
|---|---|
| Frontmatter description (346 characters) | Shortened to 290 characters; it keeps the six dimensions and the trigger words preflight, pre-merge check, pre-PR check, ready to merge, can I ship this, branch ready, quality gate and merge readiness |
| Frontmatter metadata | `metadata.version` 2.0.0 and `metadata.format: v5` added; `depends_on`, `source_repo` and `source_type` kept because the onboarding installer (`modular.py`) and agent-conformance read them |
| Title and the two opening paragraphs | SKILL.md (verbatim) |
| Where This Fits (table, the handoff, evidence consumption and decision ownership) | references/background.md (verbatim, except one link below); distilled into Binding rules 6 and 9 |
| The Quality Gate Framework | SKILL.md (verbatim); distilled into Binding rule 2 |
| Quality Dimensions 1 to 6 | references/dimensions-and-rules.md (verbatim); distilled into Binding rules 3, 4, 6, 7 and 8 |
| Verdict | SKILL.md (verbatim) |
| The Temporary Considerations Pattern | references/temporary-considerations.md (verbatim); distilled into Binding rule 8 |
| Rules | references/dimensions-and-rules.md (verbatim); distilled into Binding rules 1, 2, 5 and 9 |
| Binding rules, Contents | New in 2.0.0; each binding rule restates rules already in the sections it names |

## Lines reworded

| Line | Change and reason |
|---|---|
| "Preflight consumes current implementation-integrity and audit evidence. ..." (Where This Fits) | The link to the decision-ownership contract now reads `../../synthesis-thinking-framework/references/decision-ownership.md`, because the paragraph moved one directory deeper into references/. The words are unchanged. |
