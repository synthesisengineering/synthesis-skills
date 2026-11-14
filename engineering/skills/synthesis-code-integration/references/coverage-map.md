# Coverage map: code integration 1.3.1 to 2.0.0

Every part of the 1.3.1 SKILL.md and where it lives now. Nothing was removed.

| 1.3.1 section | Now |
|---|---|
| Frontmatter description (357 characters) | Shortened to 287 characters; it keeps the four topics and the trigger words synthesis coding, multi-contributor, integration, cherry-pick, adopt and adapt, lead synthesist, integrate contributions and merge contributor work |
| Frontmatter metadata | `metadata.version` 2.0.0 and `metadata.format: v5` added; `depends_on`, `source_repo` and `source_type` kept because the onboarding installer (`modular.py`) and agent-conformance read them |
| Title and opening paragraph | SKILL.md (verbatim) |
| The Core Problem | references/pattern-and-roles.md (verbatim) |
| Adopt-and-Adapt: The Integration Pattern (Why This Works, Why Direct Merge Does Not Work) | references/pattern-and-roles.md (verbatim); distilled into Binding rule 1 |
| Roles (Lead Synthesist, Contributors) | references/pattern-and-roles.md (verbatim) |
| Contribution Workflow (Before Building, While Building, Submitting) | references/pattern-and-roles.md (verbatim) |
| The Integration Process (Steps 1 to 4) | SKILL.md (verbatim); distilled into Binding rule 1 |
| Branch Hygiene: PR Branches Stay Clean of Other Branches' Content (pattern, why, incident, when safe) | references/branches-and-cherry-picks.md (verbatim); distilled into Binding rule 4 |
| Post-Cherry-Pick Regression Verification | references/branches-and-cherry-picks.md (verbatim); distilled into Binding rule 5 |
| Cherry-Picking from Old Branch Bases, Cherry-Pick Test Cascade | references/branches-and-cherry-picks.md (verbatim); distilled into Binding rule 5 |
| Contributor Attribution | references/integration-options.md (verbatim); distilled into Binding rule 10 |
| Quality Gates (Meta-Principle: Zero Accepted Failures, Gates 1 to 4) | references/review-gates.md (verbatim); distilled into Binding rules 2 and 3; gate numbers unchanged |
| Communication and Feedback (Principles, Ground All Technical Replies in Code, The Integration Review Document) | references/communication.md (verbatim); distilled into Binding rules 9 and 11 |
| Investigate Before Concluding | references/communication.md (verbatim); distilled into Binding rule 9 |
| Integrating Multiple PRs | references/integration-options.md (verbatim) |
| Fallback: Selective File Checkout | references/integration-options.md (verbatim) |
| Evolution of Integration Intensity (Phases 1 to 4, adjusting, choosing between Phases 2 and 3) | references/integration-options.md (verbatim); the upgrade and downgrade signals are summarized in Binding rule 1 |
| Staging Branch Management | references/branches-and-cherry-picks.md (verbatim); distilled into Binding rule 6 |
| Convention Review Checklist | references/review-gates.md (verbatim) |
| Pre-Squash PR Manifest Check (MANDATORY), Changelog Verification | references/squash-and-changelog.md (verbatim); distilled into Binding rule 7 |
| Critical Config Regression Guards | references/review-gates.md (verbatim); distilled into Binding rule 8 |
| Lessons and Anti-Patterns | references/lessons.md (verbatim); the auto-deploy anti-pattern is Binding rule 12 |
| Binding rules, Contents | New in 2.0.0; each binding rule restates rules already in the sections it names |
