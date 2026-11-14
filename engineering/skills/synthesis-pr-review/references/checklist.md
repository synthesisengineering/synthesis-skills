# PR review: the checklist

What to check in every substantive review, the project's own conventions, and which codebase-review categories apply to a single PR.

## Review Checklist

### 1. Scope and Separation of Concerns

- [ ] PR does one thing (not multiple unrelated fixes bundled together)
- [ ] PR description accurately describes the change and its motivation
- [ ] If the PR bundles fixes, each fix is clearly identified and could stand alone
- [ ] Actual code changes match the stated scope in the PR title and ticket
- [ ] Any expansion beyond the title scope is explicitly justified in the description
- [ ] Editorial or business decisions follow the actual decision owner's grant and scope; existing decisions and delegated choices are preserved without repeated sign-off, and a new material direction has the required approval
- [ ] All test files test the feature being implemented, not unrelated features
- [ ] Test files covering different functionality are flagged for separation into their own PR

**Red flag:** A PR titled "fix X" that also quietly changes Y.

**Red flag:** A PR titled "fix X for component Y" that quietly changes components A through Z. Compare the PR title and ticket scope against the actual file list — discrepancies indicate scope creep.

**Red flag:** Large test additions where test class names or test descriptions do not match the feature being implemented. Test files covering unrelated functionality should move to a separate PR.

**How to catch scope drift:** Compare the PR title and linked ticket against the list of changed files. Every changed file should have a clear connection to the stated scope. If you cannot draw that line, ask the author to explain or split the PR.

### 2. Root Cause Analysis

- [ ] The fix addresses the actual root cause, not a downstream symptom
- [ ] If the root cause is complex, the PR explains why this specific approach was chosen
- [ ] The PR does not mask a deeper architectural issue

**How to evaluate:** Ask — if the underlying condition that caused the bug occurs again in a slightly different way, does this fix still work? If not, it is a symptom fix.

### 3. Regression Risk

- [ ] No existing behavior is broken by the change
- [ ] Error handling paths are preserved (not accidentally removed)
- [ ] Edge cases still work (empty states, error states, concurrent access)
- [ ] If the PR modifies shared code, all callers are accounted for

**Technique:** Read the diff backward — look at what was REMOVED or CHANGED, not just what was added. Removed lines are where regressions hide.

### 4. Architectural Consistency

- [ ] The pattern used matches how similar things are done elsewhere in the codebase
- [ ] If the pattern diverges from existing code, the divergence is justified
- [ ] No architectural debt is introduced without acknowledgment

**Technique:** Find the closest analog in the codebase. If component A handles retries one way and this PR makes component B handle retries a different way, ask why.

### 5. Completeness

- [ ] The fix is sufficient to actually solve the stated problem
- [ ] Companion changes needed for the promised outcome are included and exercised in the integration package, or the current PR is explicitly a dependency with a named owner and remains incomplete for that outcome
- [ ] Tests cover the new behavior (or a clear reason why they do not)

**Red flag:** A frontend fix for a problem whose root cause is in the backend.

### 6. Security

- [ ] No credentials or secrets in the diff
- [ ] Input validation at system boundaries
- [ ] Auth checks preserved for protected endpoints
- [ ] No new SQL injection, XSS, or command injection vectors
- [ ] Grep the diff for `secret`, `token`, `password`, `key` in any `logger.*`, `print()`, or `console.log()` statement
- [ ] Check JWT/auth code never logs credentials
- [ ] Verify dev conveniences are removed (hardcoded emails, auto-login, skip-auth flags)
- [ ] For large PRs (>1000 lines), question whether it should be split
- [ ] Require PR description — PRs without descriptions are harder to review and more likely to hide issues

**AI code assistant warning:** AI coding tools commonly introduce debug logging that includes sensitive data. Add a pre-commit check that flags patterns like `log.*secret`, `print.*token`, `console.log.*password` in staged files. Prevention is more reliable than review-time detection.

### 7. Data Integrity

- [ ] Database schema changes are idempotent (safe to run multiple times)
- [ ] New fields have sensible defaults or are nullable
- [ ] No data loss scenarios (e.g., overwriting fields without preserving previous values)
- [ ] API contracts are backward-compatible (or breaking changes are intentional and documented)

---

## Project-Specific Extension Points

Every project has conventions that go beyond language syntax and framework patterns. A PR review that only checks generic code quality will miss violations that matter to the project.

### Checking for Project-Level Conventions

Before starting a review, check whether the project has:

1. **A project-level instruction file** — Files such as `CLAUDE.md`, `AGENTS.md`, or equivalent configuration often encode naming rules, terminology requirements, deployment constraints, and other conventions that are not enforced by linters.
2. **Project-level review skills or checklists** — Some projects define their own review criteria that supplement this skill.
3. **Convention debt patterns** — Recurring violations that the project is actively trying to eliminate.

### The Convention Violation Cascade

Convention violations rarely appear in isolation. One violation often signals others:

- **UI text conventions** — If a PR uses the wrong product name in one place, check every user-facing string in the diff. Projects with white-labeling, multi-tenant branding, or specific terminology rules are especially vulnerable.
- **API and client conventions** — If a PR introduces an API endpoint that does not follow the project's naming scheme, check whether the corresponding client code, error messages, and documentation also diverge.
- **Framework conventions** — If a PR handles state management differently from the rest of the codebase, check whether error handling, data fetching, and component structure also diverge in the same PR.
- **Messaging rules** — If the project has rules about how errors, notifications, or status messages are worded, check every new string in the diff against those rules.

### Convention Review Checklist

- [ ] Checked for project-level instruction or convention files
- [ ] Checked for project-specific review skills or checklists
- [ ] All user-facing text follows project terminology and branding rules
- [ ] API naming follows the project's established conventions
- [ ] New patterns are consistent with the project's framework usage
- [ ] If one convention violation was found, checked the full diff for related violations

---

## Using the Codebase Review Skill for PR Review

The synthesis-codebase-review skill has 16 categories with tiered checks. Not all are relevant to a single PR. For delta reviews, apply selectively:

| Always check (every PR) | Check if relevant |
|-------------------------|-------------------|
| Security (Gate 2) | Performance (if the change touches hot paths) |
| Architecture (Gate 3) | Database (if schema changes are involved) |
| Completeness (Gate 1) | API design (if endpoints are added/modified) |
| Error handling | Observability (if logging/monitoring is affected) |

The synthesis-codebase-review skill is the reference catalog. This PR review skill tells you which items to pull from it for a given change.
