# Per-repo overrides

The default policy (Tier 0 always + Tier 1 in strict) is read from `~/.synthesis/git-hook-config.yaml` and is sufficient for almost all cases. This reference covers the rare cases where you want a repo to do MORE than the default.

## When you need an override

- A repo has its own naming conventions that the universal pattern set should not flag (allowlist-style override)
- A repo has its own additional sensitivity rules (extra-pattern override)
- A repo is doing something genuinely unusual that warrants a custom check entirely

## The delegation mechanism

The universal engine at `~/.synthesis/git-hooks/pre-commit` chains to a repo-local hook if one exists:

```bash
# Inside the engine, after the universal check passes:
REPO_ROOT=$(git rev-parse --show-toplevel)
REPO_HOOK="$REPO_ROOT/.githooks/pre-commit"
if [ -f "$REPO_HOOK" ] && [ -x "$REPO_HOOK" ]; then
    exec "$REPO_HOOK"
fi
```

The repo-local hook receives `$SYNTHESIS_REPO_CLASS` (`personal` or `strict`) in its environment, so the repo-local logic can adapt to the same classification the universal engine used.

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

1. **Better:** Add an allowlist line to the universal config that captures the legitimate context:

   ```yaml
   allowlist_lines:
     - 'acme cartoon|acme brand'
   ```

   This is the right move for context that's clearly legitimate.

2. **For one-off:** Use `git commit --no-verify` for the specific commit.

The repo-local hook IS NOT a way to override the universal hook — git only runs one pre-commit hook (whichever `core.hooksPath` points at), and the engine chains to the repo-local one ONLY after the universal check passes. You can't suppress a universal-hook trip from a repo-local file.

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

Those repo-local files were deleted in the migration. One source of truth.

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

For one-off testing, set `SYNTHESIS_GIT_HOOK_CONFIG`:

```bash
SYNTHESIS_GIT_HOOK_CONFIG=/tmp/test-policy.yaml git commit -m "test"
```

This is meant for development of the engine itself, not for production policy variation.
