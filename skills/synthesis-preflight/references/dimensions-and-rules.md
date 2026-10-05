# Preflight: the six dimensions and the rules

What to check in each dimension, then the rules that govern grading. Grades and the report format are in SKILL.md.

## Quality Dimensions

### 1. Branch Verification

- Confirm you are on a feature, fix, or working branch — not on the default branch (main, master, or whatever the project designates as protected). Refuse to proceed if on a protected branch.
- Count commits ahead of the base branch. If the branch is behind the base, warn that a sync may be needed before PR creation.

### 2. Clean Working Tree

- Check for uncommitted changes. If any exist, warn that they will not be included in the PR.
- If there are unstaged changes, surface them explicitly so the developer can decide whether to commit or discard before proceeding.
- The goal is awareness, not enforcement — uncommitted work may be intentional (unrelated experiments, local config).

### 3. Test & Type Verification

- The default gate is the project's full test suite and configured type checker, plus any additional repository requirements. Consume valid results for the exact candidate, relevant inputs and environment; run missing or invalidated checks. Targeted authoring tests alone do not satisfy the default full-suite gate. A narrower gate requires an explicit governing project or user policy, never an inference from silence.
- Report actual passed, failed, skipped and not-run coverage. A required check that failed or did not execute blocks readiness.
- A new preflight invocation alone does not invalidate a completed check.

### 4. Code Audit

- Confirm current audit evidence covers the full branch diff (base to HEAD). Apply synthesis-code-audit to uncovered changes and affected risks; consume valid coverage instead of commissioning another identical audit.
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

## Rules

- Never skip a dimension. A genuinely inapplicable check may be N/A with evidence of why it does not apply. A missing tool, absent required suite, inaccessible environment or failed check is UNKNOWN or FAIL, never N/A.
- The verdict is mechanical. Any required FAIL or UNKNOWN makes it NOT READY.
- Warnings are informational. They surface concerns but do not block.
- If preflight is invoked by another workflow (a shipping or CI pipeline), return the full report to that workflow for decision-making.
- Reuse evidence only while its source/base hashes, relevant inputs, tool/environment assumptions and criterion remain valid. After a change, rerun the affected checks and every check the repository explicitly requires; retain unaffected evidence. A same-session timestamp alone does not establish validity.
