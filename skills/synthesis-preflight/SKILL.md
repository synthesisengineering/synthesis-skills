---
name: synthesis-preflight
description: "Pre-merge gate that grades six dimensions (branch, clean tree, tests and types, code audit, temporary workarounds, commit history) into a mechanical go/no-go verdict. Use for preflight, pre-merge or pre-PR check, ready to merge, can I ship this, branch ready, quality gate, merge readiness."
license: "CC0-1.0"
depends_on: ["synthesis-code-audit"]
metadata:
  author: "Emil Peñaló"
  version: "2.0.0"
  format: v5
  source_repo: "github.com/synthesisengineering/synthesis-skills"
  source_type: "public"
---

# Synthesis Preflight

Preflight is a branch readiness gate. It does not evaluate whether your code is correct — that is the job of synthesis-implementation-integrity (self-review) and synthesis-code-audit (quality scan). Preflight asks a different question: *is this branch mechanically ready to become a PR?*

A branch can contain perfectly good code and still fail preflight: tests broken, uncommitted changes left behind, vague commit messages, a stale workaround that should have been removed. Preflight catches the things that fall between "the code works" and "the branch is ready."

## Binding rules

1. **Grade all six dimensions on every run.** N/A needs a concrete reason tied to the project contract; a missing tool, absent required suite, inaccessible environment or failed check is UNKNOWN or FAIL, never N/A.
2. **The verdict is mechanical.** Any required FAIL or UNKNOWN makes the branch NOT READY; warnings inform and never block. An approved contract amendment may change a requirement, never relabel a failed or missing observation as a pass.
3. **Refuse on a protected branch.** Preflight runs on a feature, fix or working branch, never on the default branch.
4. **The default test gate is the full suite plus the configured type checker.** Targeted tests alone do not satisfy it; only an explicit project or user policy narrows it, never silence.
5. **Reuse evidence only while it is still valid:** same source and base hashes, inputs, environment and criterion. After a change, rerun the affected checks and every check the repository requires; a same-session timestamp proves nothing.
6. **Consume current evidence instead of repeating it.** Check that implementation-integrity and audit evidence covers the exact branch state, and audit only what is uncovered.
7. **A secret in a commit message fails the branch,** because it persists in git history even when the code is clean.
8. **A tracked workaround or known failure never excuses a required check.** Remove resolved temporary considerations and report them.
9. **READY grants nothing.** It is not merge, release or deployment authority; apply the [decision-ownership contract](../synthesis-thinking-framework/references/decision-ownership.md) and the action owner's gate. When another workflow invoked preflight, return the full report to it.

## Contents

- [references/dimensions-and-rules.md](references/dimensions-and-rules.md): the full checks for each of the six dimensions, and the grading rules. Read on every preflight run, before grading.
- [references/temporary-considerations.md](references/temporary-considerations.md): the temporary considerations pattern: what to track, the entry format, and why preflight checks it. Read when the project tracks workarounds or should start to.
- [references/background.md](references/background.md): where preflight sits beside implementation-integrity and code-audit, the handoff between them, and decision ownership. Read when choosing between these skills.
- [references/coverage-map.md](references/coverage-map.md): where each part of the 1.1.1 text now lives (ruling D8).
- The Quality Gate Framework, Verdict: below. The five grades and the report format.

## The Quality Gate Framework

Preflight evaluates six orthogonal dimensions. Each is graded independently:

- **Pass** — no issues
- **Warning** — potential concern, does not block
- **Fail** — blocks the PR until resolved
- **Unknown** — required evidence is unavailable, incomplete or stale; blocks readiness
- **N/A** — the dimension does not apply, with a concrete reason tied to the project contract

A single FAIL or UNKNOWN in a required dimension means the branch is NOT READY. Warnings are surfaced for awareness but do not block. An approved contract amendment may change a requirement; it cannot relabel a failed or missing observation as a pass.

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
