# Coverage map: PR review 1.2.0 to 2.0.0

Every part of the 1.2.0 SKILL.md and where it lives now. Nothing was removed.

| 1.2.0 section | Now |
|---|---|
| Frontmatter description (306 characters) | Shortened to 266 characters; it keeps regression risk, root cause, adopt-and-adapt, and every trigger word (PR review, pull request, code review, review PR, delta review, review pull request, check PR, evaluate PR) |
| Frontmatter metadata | `metadata.version` 2.0.0 and `metadata.format: v5` added; `depends_on`, `source_repo` and `source_type` kept because the onboarding installer (`modular.py`) and agent-conformance read them |
| Title and opening paragraph | SKILL.md (verbatim) |
| Where This Fits (table of eight related skills and the paragraph after it) | references/background.md (verbatim) |
| The Delta Review Mindset | SKILL.md (verbatim); distilled into Binding rule 1 |
| Review Checklist, parts 1 to 7 | references/checklist.md (verbatim); distilled into Binding rules 2, 3 and 4 |
| Verifying AI-Generated Analysis, including When You Use AI to Help Review | references/verifying-analysis.md (verbatim); distilled into Binding rule 5 |
| The Review Process (For Peer Reviewers, For the Lead Synthesist, Writing Review Feedback, Review Comment Format) | references/writing-the-review.md (verbatim); distilled into Binding rules 6 and 7 |
| Project-Specific Extension Points | references/checklist.md (verbatim); distilled into Binding rule 8 |
| Common Anti-Patterns | references/writing-the-review.md (verbatim) |
| Integration with Adopt-and-Adapt, Post-Merge Verification | references/after-review.md (verbatim, except the link below); distilled into Binding rules 9 and 10 |
| Using the Codebase Review Skill for PR Review | references/checklist.md (verbatim) |
| Using the Code Audit Skill Alongside PR Review | references/background.md (verbatim) |
| Binding rules, Contents | New in 2.0.0; each binding rule restates rules already in the sections it names |

## Lines reworded

| Line | Change and reason |
|---|---|
| "The review findings feed directly into the integration plan. ..." (Integration with Adopt-and-Adapt) | The link to the decision-ownership contract now reads `../../synthesis-thinking-framework/references/decision-ownership.md`, because the paragraph moved one directory deeper into references/. The words are unchanged. |
