# Codebase review: background

Where this skill sits among the verification skills, and the principles behind it.

## Relationship to Other Verification Skills

This skill evaluates the **entire system**. Four companion skills cover narrower scopes:

- **synthesis-implementation-integrity** — verifies a single change is genuinely complete (self-review, run after every implementation)
- **synthesis-code-audit** — systematic 10-dimension quality scan of a diff (run after implementation, as input to preflight or pr-review)
- **synthesis-preflight** — branch readiness gate that orchestrates tests, types, audit, and commit hygiene into a go/no-go verdict (run before creating a PR)
- **synthesis-pr-review** — evaluates a change proposed for merge (peer review, run on every PR)

Together these five skills form a verification chain: implementation-integrity catches change-level gaps, code-audit measures quality across 10 dimensions, preflight gates the branch before it becomes a PR, pr-review catches what earlier checks missed through judgment-based evaluation, and this skill catches systemic patterns that no single change reveals.

---

## Key Principles

1. **Tier-appropriate rigor.** Do not apply Tier 4 scrutiny to a weekend project. Do not skip Tier 1 basics for an enterprise system.
2. **Evidence-based findings.** Every finding must cite specific file paths and line numbers with concrete remediation steps.
3. **Practical over theoretical.** Every checklist item should catch real issues found in real codebases.
4. **AI-friendly wording.** Checklist items should be clear enough for AI assistants to evaluate programmatically.
5. **Strengths first.** Understanding what the team did well is as important as finding problems.
