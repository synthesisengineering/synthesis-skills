---
name: synthesis-preflight
description: >
  Pre-merge quality gate framework with six orthogonal dimensions: branch
  hygiene, clean tree, tests and types, code audit, temporary considerations,
  and commit history. Produces a mechanical go/no-go verdict. Use when asked
  to: preflight, pre-merge check, ready to merge, can I ship this, branch
  ready, quality gate, merge readiness, pre-PR check.
license: "CC0-1.0"
depends_on: ["synthesis-code-audit"]
metadata:
  author: "Emil Peñaló"
  version: "1.1.0"
  source_repo: "github.com/synthesisengineering/synthesis-skills"
  source_type: "public"
---

# Synthesis Preflight

Preflight is a branch readiness gate. It does not evaluate whether your code is correct — that is the job of synthesis-implementation-integrity (self-review) and synthesis-code-audit (quality scan). Preflight asks a different question: *is this branch mechanically ready to become a PR?*

A branch can contain perfectly good code and still fail preflight: tests broken, uncommitted changes left behind, vague commit messages, a stale workaround that should have been removed. Preflight catches the things that fall between "the code works" and "the branch is ready."

---

## Where This Fits

| Skill | Scope | When to use |
|-------|-------|-------------|
| **implementation-integrity** | Self-verification of a single implementation | After completing work — "Is my code genuinely complete?" |
| **code-audit** | 10-dimension quality scan of a diff | After implementation — systematic quality measurement |
| **preflight** (this one) | Branch readiness gate | Before creating a PR — "Is this branch ready?" |

**The natural flow:** Implement → self-verify (implementation-integrity) → quality scan (code-audit) → branch gate (preflight) → create PR → peer review (pr-review).

Preflight consumes current implementation-integrity and audit evidence. It checks that the evidence covers the exact proposed branch state and required consumers; it does not repeat an unchanged review merely to produce another report. A readiness verdict does not grant merge, release or deployment authority. Apply the shared [decision-ownership contract](../synthesis-thinking-framework/references/decision-ownership.md) and the action owner's existing gate.

---

## The Quality Gate Framework

Preflight evaluates six orthogonal dimensions. Each is graded independently:

- **Pass** — no issues
- **Warning** — potential concern, does not block
- **Fail** — blocks the PR until resolved
- **Unknown** — required evidence is unavailable, incomplete or stale; blocks readiness
- **N/A** — the dimension does not apply, with a concrete reason tied to the project contract

A single FAIL or UNKNOWN in a required dimension means the branch is NOT READY. Warnings are surfaced for awareness but do not block. An approved contract amendment may change a requirement; it cannot relabel a failed or missing observation as a pass.

---

## Quality Dimensions

### 1. Branch Verification

- Confirm you are on a feature, fix, or working branch — not on the default branch (main, master, or whatever the project designates as protected). Refuse to proceed if on a protected branch.
- Count commits ahead of the base branch. If the branch is behind the base, warn that a sync may be needed before PR creation.

### 2. Clean Working Tree

- Check for uncommitted changes. If any exist, warn that they will not be included in the PR.
- If there are unstaged changes, surface them explicitly so the developer can decide whether to commit or discard before proceeding.
- The goal is awareness, not enforcement — uncommitted work may be intentional (unrelated experiments, local config).

### 3. Test & Type Verification

- Run the project's full test suite. Report pass/fail summary.
- If the project uses a type checker (TypeScript, mypy, pyright, or equivalent), run it. Report any type errors.
- These are binary gates. If tests fail or types do not check, the branch is not ready.

### 4. Code Audit

- Run the synthesis-code-audit methodology against the full branch diff (base to HEAD).
- Any FAIL dimension in the audit = preflight FAIL for this gate.
- WARNING dimensions are surfaced in the preflight report but do not block.
- A "Clean" audit verdict = PASS for this gate.

### 5. Temporary Considerations

Check whether the project tracks temporary workarounds, known issues, or time-limited technical debt.

For each tracked entry:

1. **Run its resolution verification check.** Each temporary consideration should define criteria for when it can be removed (a flag is deleted, a migration is complete, a dependency is upgraded).
2. **Resolved entries** — remove them from tracking. Report the resolution in the preflight output.
3. **Still-active entries** — list them in the preflight output. Verify each proposed exclusion against the governing contract and its actual decision owner. A tracked workaround or known failure is not permission to skip a required check. Keep unresolved required checks blocking and preserve the original evidence.

If the project does not track temporary considerations, grade this dimension as N/A.

### 6. Commit History

Review the commits on this branch (from the base branch to HEAD):

- **Secrets or credentials in commit messages** — FAIL. Even if the secret is not in the code, its presence in a commit message means it will persist in git history.
- **Message clarity within repository policy** — flag unclear messages when the repository calls for descriptive subjects. Explicit disclosure rules may require generic messages; do not demand sensitive detail or history rewriting to satisfy a generic style preference.
- **Convention compliance** — check that commit messages follow the project's documented format (conventional commits, imperative mood, character limits, or whatever the project specifies). Flag violations.

---

## Verdict

Present findings as a status report:

```
PREFLIGHT REPORT — {branch-name}

Branch:           pass/warning/fail/unknown (details)
Clean tree:       pass/warning/fail/unknown (details)
Tests & types:    pass/fail/unknown/N/A (X passed, Y failed; applicability)
Code audit:       pass/warning/fail/unknown (coverage and findings)
Temp items:       pass/fail/unknown/N/A (N resolved, N still active)
Commit history:   pass/warning/fail/unknown (details)

VERDICT: READY / NOT READY (with blockers listed)
```

**READY** — all required dimensions have current passing evidence; genuine N/A dimensions and nonblocking warnings are explained.

**NOT READY** — one or more required dimensions are FAIL or UNKNOWN. List blockers in priority order. For each blocker, state what is wrong or missing and what observation will resolve it.

---

## The Temporary Considerations Pattern

This pattern is worth explaining because most projects do not formalize it, and workarounds accumulate silently as a result.

### What to Track

- Workarounds for known bugs in dependencies or infrastructure
- Feature flags that were meant to be temporary
- Hardcoded values that should come from configuration after a specific migration
- Compatibility shims for deprecated APIs
- Any code with an implicit expiration date

### Entry Format

Each tracked consideration should include:

- **Description** — what the workaround does and why it exists
- **Reason it is temporary** — what event or change will make it unnecessary
- **Resolution verification** — a concrete, checkable condition (a file is deleted, a config key exists, a dependency version is above X, a feature flag is removed)
- **Proposed exclusions** — identify the affected requirement, its decision owner and any applicable grant. Record failures once without suppressing their blocking consequence. No exclusion arises merely from being listed here.

### Why Preflight Checks This

Workarounds that are not tracked and not checked tend to become permanent. Preflight auto-cleaning resolved entries prevents accumulation. The developer who resolves the underlying issue may not remember every workaround it affects — preflight remembers for them.

---

## Rules

- Never skip a dimension. A genuinely inapplicable check may be N/A with evidence of why it does not apply. A missing tool, absent required suite, inaccessible environment or failed check is UNKNOWN or FAIL, never N/A.
- The verdict is mechanical. Any required FAIL or UNKNOWN makes it NOT READY.
- Warnings are informational. They surface concerns but do not block.
- If preflight is invoked by another workflow (a shipping or CI pipeline), return the full report to that workflow for decision-making.
- Reuse evidence only while its source/base hashes, relevant inputs, tool/environment assumptions and criterion remain valid. After a change, rerun the affected checks and every check the repository explicitly requires; retain unaffected evidence. A same-session timestamp alone does not establish validity.
