# PR review: where it fits

How PR review relates to the other engineering skills, and to code-audit in particular.

## Where This Fits

Eight related engineering skills cover different scopes and lifecycle phases:

| Skill | Scope | When to use |
|-------|-------|-------------|
| **preplan** | Architecture decisions and their owners | Before implementation when material choices remain — preserve existing decisions, decide delegated choices and ask only the actual owner of unresolved choices |
| **code-planning** | Approach selection for a task | Before writing code — evaluate alternatives, pick the best approach |
| **implementation-integrity** | Self-verification of a single implementation | After completing work — "Is my code genuinely complete?" |
| **code-audit** | 10-dimension quality scan of a diff | After implementation — systematic quality measurement |
| **preflight** | Branch readiness gate | Before creating a PR — tests, types, audit, commit hygiene |
| **review-triage** | PR queue prioritization | Before starting review — which PR to review next |
| **pr-review** (this one) | Delta review of a single change | Every PR, before peer approval or lead integration |
| **code-integration** | Integration workflow (adopt-and-adapt pattern, quality gates) | When merging contributor work into main |
| **codebase-review** | Full codebase audit (16 categories, tiered) | Periodic health check or major milestone |

PR review is the most frequent *review* skill. It happens on every change. The synthesis-code-audit skill provides systematic quality data that feeds into reviews; this skill provides the judgment-based evaluation and communication. The quality gates from synthesis-code-integration apply here, but this skill operationalizes them as specific review steps.

---

## Using the Code Audit Skill Alongside PR Review

The synthesis-code-audit skill provides a 10-dimension scored quality scan of a diff. When used alongside this skill, code-audit provides systematic data; this skill provides judgment-based evaluation. The two are complementary:

- **Code-audit** measures: convention compliance, code reuse, pattern consistency, security, scalability, future-proofing, code quality, test coverage, documentation, cleanup. It produces a PASS/WARNING/FAIL table.
- **PR-review** evaluates: scope, root cause, regression risk, architectural consistency, completeness, security, data integrity. It produces a review verdict with severity-tiered findings.

Some subject matter overlaps (security appears in both; consistency appears in both), but the purpose differs. Code-audit asks "does this code meet standards?" PR-review asks "should this change enter the codebase?" A diff can pass all 10 audit dimensions and still warrant a request-changes verdict because the approach is wrong, the root cause is misidentified, or the solution is incomplete.

The audit findings feed into the review, but the review verdict considers factors the audit does not measure.
