# Per-repo overrides

The default policy (Tier 0 always + Tier 1 in strict and public-surface repos) is read from the policy file `commit_policy` names in `~/.synthesis/v5/config.json`, and is sufficient for almost all cases. This reference covers the rare cases where you want a repo to do MORE than the default.

## When you need an override

- A repo has its own naming conventions that the universal pattern set should not flag (allowlist-style override)
- A repo has its own additional sensitivity rules (extra-pattern override)
- A repo is doing something genuinely unusual that warrants a custom check entirely

## The delegation mechanism

The universal check (`~/.synthesis/v5/git-hooks/pre-commit`, running `synthesis/commit_check.py`) chains to the repository's own hooks after its own checks pass: `.githooks/pre-commit`, then `.git/hooks/pre-commit`, each once, never itself. A repository that must not run without its own hook declares `.githooks/required`; a missing or non-executable `.githooks/pre-commit` then blocks the commit and names the fix (see [scanning.md](scanning.md#repository-hooks)). `commit-msg` chains the same way to `.githooks/commit-msg` and `.git/hooks/commit-msg`; a clean automatic merge runs `.githooks/pre-commit` too.

The repo-local hook receives `$SYNTHESIS_REPO_CLASS` (`personal`, `public-surface` or `strict`) in its environment, so the repo-local logic can adapt to the same classification the universal engine used.

## Override pattern: extra allowlist

Suppose a public repo uses a substring like `acme` legitimately (e.g., it's a CSS library themed after the historic "ACME" brand from cartoons). If `acme` were in your `confidential_names` list, the universal hook would flag this in any strict repo. The repo-local hook can pre-filter:

```bash
#!/bin/bash
# .githooks/pre-commit in this repo
#
# Adds context-allowance for "acme" because this repo refers to the
# cartoon brand, not a confidential client.
set -euo pipefail

CHANGED=$(git diff --cached --diff-filter=AM -U0 | grep '^+' | grep -v '^+++' || true)
SUSPECT=$(echo "$CHANGED" | grep -i 'acme' | grep -ivE 'acme cartoon|acme brand' || true)
if [ -n "$SUSPECT" ]; then
    echo "Lines mentioning acme NOT in the cartoon-brand context:"
    echo "$SUSPECT"
    exit 1
fi
exit 0
```

The universal hook would have caught and BLOCKED on `acme`; the repo-local hook never runs because the universal hook exited with non-zero. Solutions:

1. For a Tier-1-only finding, review an allowlist line that captures the legitimate context:

   ```yaml
   allowlist_lines:
     - 'acme cartoon|acme brand'
   ```

   This is the right move for context that's clearly legitimate.

2. A Tier-0 detection-rule false positive requires a scanner-owner correction. Preserve the exact finding and its positive material controls; neither an allowlist nor a path exception can admit it. The correction is a change to `synthesis/commit_check.py` with a test; the key-marker rule is in [scanning.md](scanning.md#private-keys).

The repo-local hook IS NOT a way to override the universal hook — git only runs one pre-commit hook (whichever `core.hooksPath` points at), and the engine chains to the repo-local one ONLY after the universal check passes. You can't suppress a universal-hook trip from a repo-local file.

## Repo-local hooks are additive, not superseded

If a repo has its own `.githooks/pre-commit` (version-controlled, executable), this engine **chains to it** — runs its own Tier-0/Tier-1 pass first, then runs the repo-local hook. It does not replace or subsume it.

This matters because it's easy to assume the opposite: "the global hook already covers confidentiality, so the repo-local one is redundant — delete it." That assumption is wrong and removes protection rather than deduplicating it. A repo-local hook typically exists because the repo needs a check the global config can't express safely — for example, a repo whose whole purpose is documenting a specific client relationship needs `personal`-class handling (so the client's own name isn't flagged as a leak) while still blocking a different category the global patterns don't cover, like engagement financials or a partner's personnel names. Verify what a repo-local hook actually checks before assuming it's covered elsewhere, and don't delete it as part of unrelated cleanup.

## Override pattern: extra checks

Suppose a public repo wants to ALSO check for the substring "TODO" in `src/security/`. The repo-local hook adds the extra check on top of the universal one:

```bash
#!/bin/bash
# .githooks/pre-commit in this repo
# Add: catch TODO comments in security-critical paths.
set -euo pipefail

TODOS=$(git diff --cached --diff-filter=AM -U0 -- src/security/ | grep '^+' | grep -v '^+++' | grep -i 'TODO' || true)
if [ -n "$TODOS" ]; then
    echo "Refusing to ship TODOs in src/security/:"
    echo "$TODOS"
    exit 1
fi
exit 0
```

The repo-local hook is purely additive. The universal check has already run by the time it executes.

## What happened to the per-repo client-name hooks?

Before this skill existed, several of the author's public repos had repo-local `.githooks/pre-commit` files that re-implemented the confidential-client-name check. Those files became redundant once the universal engine read the patterns from `~/.synthesis/git-hook-config.yaml`. The universal engine applies them automatically to any repo that classifies as `strict`.

Those repo-local files were deleted in the migration. One source of truth. (That deletion was right because those hooks only repeated the global patterns; a repo-local hook that checks something else stays, per the section above.)

## Environment variable: SYNTHESIS_REPO_CLASS

Repo-local hooks receive the universal engine's classification via `$SYNTHESIS_REPO_CLASS`. Use it to apply different rules per class:

```bash
if [ "${SYNTHESIS_REPO_CLASS:-strict}" = "strict" ]; then
    # Stricter check
    ...
fi
```

This is useful if the repo-local logic should mirror the universal classification's effects.

## Override pattern: using a different config file

For one-off testing of the engine itself, point `SYNTHESIS_HOME` at a scratch folder whose `config.json` names a test policy:

```bash
SYNTHESIS_HOME=/tmp/test-home git commit -m "test"   # reads /tmp/test-home/config.json
```

This is meant for development of the engine itself, not for production policy variation.
