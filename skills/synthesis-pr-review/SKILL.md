---
name: synthesis-pr-review
description: "Delta review of a pull request in a synthesis-coded project: regression risk, root cause, scope, and handoff to adopt-and-adapt integration. Use when asked to: PR review, pull request, code review, review PR, delta review, review pull request, check PR, evaluate PR."
license: "CC0-1.0"
depends_on: ["synthesis-code-integration", "synthesis-codebase-review"]
metadata:
  author: "Rajiv Pant"
  version: "2.0.0"
  format: v5
  source_repo: "github.com/synthesisengineering/synthesis-skills"
  source_type: "public"
---

# Synthesis PR Review

A pull request in a synthesis-coded project is not just "does the code work?" It is "does this change make the system better without making it worse?" This skill defines how to evaluate that.

## Binding rules

1. **Review the delta, not the codebase.** Ask whether the change does what it claims, regresses anything, fixes the root cause, is complete, and follows existing patterns.
2. **Every changed file must trace to the stated scope.** Compare the title and ticket with the file list; bundled or unexplained changes get justified or split, because they hide regressions and make bisects and reverts unsafe.
3. **Read the diff backward.** Removed and changed lines are where regressions hide; account for every caller of changed shared code.
4. **A symptom fix is not a fix.** Ask whether it still works when the underlying condition recurs in a slightly different way.
5. **Verify conclusions against the code yourself,** whether they came from an AI tool, a contributor or your own AI-assisted pass. Post a finding only if you can say "I have verified this against the actual code."
6. **Grade every finding:** Must fix (blocks merge), Should fix, Consider or Nit. Be specific, explain the consequence, and name what is good, so the contributor knows what blocks merge and what to repeat.
7. **No rubber stamps.** An approval without reading creates a false record; if you lack the time, say so.
8. **Check the project's own conventions first** (`CLAUDE.md`, `AGENTS.md`, project review checklists). One convention violation means checking the whole diff for related ones.
9. **Approval is not authorization.** Technical acceptance, merge authorization, release or deployment authorization and the delivered outcome are separate facts under the [decision-ownership contract](../synthesis-thinking-framework/references/decision-ownership.md); required remaining work stays an open obligation.
10. **Merge is step one of two.** Run the project's post-merge verification, and flag files that other in-flight PRs also touch.

## Contents

Read in this order during a review: the checklist, then verifying analysis when one is presented or AI helped you, then writing the review.

- [references/checklist.md](references/checklist.md): the seven-part review checklist (scope, root cause, regression risk, architectural consistency, completeness, security, data integrity), project-specific convention checks, and which codebase-review categories to pull for a PR. Read on every substantive review.
- [references/verifying-analysis.md](references/verifying-analysis.md): how to check a root-cause analysis from an AI tool, contributor or teammate, and how to vet your own AI-assisted findings. Read before acting on an analysis or posting AI-assisted findings.
- [references/writing-the-review.md](references/writing-the-review.md): focus for peer reviewers and for the lead synthesist, how to write feedback, the review comment format, and common anti-patterns. Read when composing the review.
- [references/after-review.md](references/after-review.md): integration with adopt-and-adapt and post-merge verification. Read when a PR passes review or has just merged.
- [references/background.md](references/background.md): where PR review sits among the eight related engineering skills, and how it complements code-audit. Read when choosing between these skills.
- [references/coverage-map.md](references/coverage-map.md): where each part of the 1.2.0 text now lives (ruling D8).
- The Delta Review Mindset: below. The five questions every review answers.

## The Delta Review Mindset

A PR review is a delta review — you are evaluating a change against the current state of the codebase, not evaluating the codebase itself.

**Key questions:**

1. **Does this change do what it claims?** — Read the PR description. Read the code. Do they match?
2. **Does it introduce regressions?** — What worked before that might break now?
3. **Is it the right fix?** — Does it address root cause, or a symptom?
4. **Is it complete?** — Or does it need companion changes to actually solve the problem?
5. **Is it consistent?** — Does it follow existing patterns, or does it diverge without justification?
