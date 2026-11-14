# Code integration: squash merges and changelogs

The check that stops a squash merge from dropping a PR, and the rule that keeps changelogs true.

## Pre-Squash PR Manifest Check (MANDATORY)

Before squash-merging an integration branch to `main`, verify that every PR on the branch is represented in the squash diff. This catches the most dangerous synthesis merge failure: a PR that was on the integration branch but accidentally excluded from the squash.

### Why This Exists

On 2026-03-31, two PRs (#85 and #78) were on an integration branch pushed to `develop` (staging). Users saw the features working on staging. But when the integration branch was squash-merged to `main`, these PRs were excluded. The squash commit only contained 6 of the 8 PRs' work. No test failed. No error was raised. The features simply vanished from `main`, and when the next version was built from `main`, they were gone.

The changelog was then written to describe these features as shipped — because the agent relied on conversation context ("we merged these PRs") rather than verifying against the actual squash commit.

### The Check

Before running `git merge --squash`:

```bash
# 1. List all unique PRs/features on the integration branch
git log integration/vX.Y.Z ^main --oneline

# 2. After squash-merging (before committing), verify the diff includes
#    changes from EVERY PR listed above
git diff --cached --stat

# 3. Cross-reference: for each PR, at least one file it touched must
#    appear in the staged diff. If a PR's files are missing, the squash
#    excluded it.
```

**If any PR is missing from the squash diff:** Do NOT commit. Investigate why it was excluded. Re-do the squash merge including the missing work.

### Changelog Verification

**Never write a changelog entry for a feature without verifying it exists in the code on the target branch.**

```bash
# Before writing "Feature X is in v0.82.0":
git grep "FeatureXComponent\|featureXFunction" main -- frontend/src/
# If zero results → the feature is NOT on main. Do NOT add a changelog entry.
```

The changelog describes the codebase as it IS, not as you believe it to be. Conversation context, Slack transcripts, and integration branch state are NOT valid sources for changelog claims. The code is.
