# Code integration: branches and cherry-picks

Git mechanics that silently lose or leak work, and how to avoid them.

Contents:
- Branch Hygiene: PR branches stay clean of other branches' content
- Post-Cherry-Pick Regression Verification
- Cherry-Picking from Old Branch Bases, with the cherry-pick test cascade
- Staging Branch Management

## Branch Hygiene: PR Branches Stay Clean of Other Branches' Content

**When a PR targets one branch and you need the same commit on another long-lived branch (for QA, staging, or any other reason), put the commit on that other branch as a separate operation. NEVER merge that other branch INTO the PR branch.**

This rule is branch-name-agnostic. Teams use many conventions — `main`/`develop`, `master`/`staging`, `trunk`/`release`, GitHub Flow with feature flags, environment branches, Gitflow, and more. The rule applies whenever a PR branch must stay scoped to the change it represents, and the commit also needs to live on a separate long-lived branch for deployment, QA, or similar reasons.

Terminology used below:

- **PR target branch** — the branch the PR will merge into (often `main`, `master`, or `trunk`)
- **Staging branch** — any separate long-lived branch the commit also needs to reach (e.g., `develop`, `staging`, `release/*`, a UAT branch, etc.)

Merging a staging branch into a PR branch is a shortcut that pollutes the PR diff with all of that branch's in-progress work. GitHub shows hundreds or thousands of changes that aren't actually part of the PR. A reviewer cannot see the actual change. Worse, if the PR is squash-merged, every unreleased commit from the staging branch lands on the PR target branch in one shot — shipping untested and unrelated work under the PR's name.

### The correct pattern

You have one commit on a branch based on the PR target branch (call it `feature-X`). You need:

1. PR open with that commit — reviewers see only the change
2. The same commit on a staging branch so deployment / QA picks it up

The safe sequence — substitute your project's actual branch names:

```bash
# Variables — replace with your team's branch names:
#   PR_TARGET    = the PR's target branch (e.g., main, master, trunk)
#   STAGING      = the long-lived branch that also needs the commit
#                  (e.g., develop, staging, release, uat)

# 1. Keep feature-X scoped to your commit (based on PR_TARGET)
git push origin feature-X

# 2. Open PR against PR_TARGET from feature-X

# 3. Put the commit on STAGING WITHOUT polluting feature-X:
git checkout $STAGING
git pull origin $STAGING
git merge feature-X          # fast-forward or small merge commit
git push origin $STAGING

# 4. Return to feature-X for any follow-up work
git checkout feature-X
```

Concrete example for a Gitflow-style team (`PR_TARGET=main`, `STAGING=develop`):

```bash
git push origin feature-X                  # PR branch stays clean
# open PR against main from feature-X
git checkout develop && git pull origin develop
git merge feature-X && git push origin develop
git checkout feature-X
```

Never run `git merge origin/<staging-branch>` while on your PR branch. That's the anti-pattern this rule exists to prevent, regardless of what the staging branch is named.

### Why this matters

The PR diff is how reviewers form their opinion. A misleading diff:

- Costs the reviewer's time (they have to mentally subtract unrelated changes)
- Invites "request changes" from reviewers worried about scope
- Creates real risk: if the PR gets squash-merged (or a reviewer clicks "merge" without checking), all of the staging branch's unreleased work ships to the PR target branch

### Incident this rule came from

One team's workflow uses `main` as the PR target and `develop` as the staging branch. On 2026-04-20, a one-commit chore PR (~23 files, 358/110 lines) was opened against `main`. To make a subsequent push to `develop` a fast-forward, the agent merged `origin/develop` into the PR branch. The PR diff ballooned to 6,900 changes spanning unreleased staging work. Reviewers opened "request changes" and flagged the squash-merge risk. The branch was force-pushed back to the single commit within the hour, but the confusion was avoidable. The rule above is the procedural fix — it applies to any team regardless of branch naming.

### When this is safe

Merging a staging branch into a PR branch IS appropriate when the PR explicitly represents the staging-to-target promotion (e.g., a release PR from `develop` → `main`, or a `staging` → `production` cutover PR). Those PRs exist specifically to land that accumulated work, so the diff should show it.

For all other PRs — feature, chore, fix, refactor — the default is branch hygiene above.

---

## Post-Cherry-Pick Regression Verification

Cherry-picking is the most common integration mechanism, but it carries a hidden risk: files from a contributor's old branch may silently overwrite work from prior synthesis merges. The cherry-pick succeeds without conflicts because the contributor's version is "newer" in git's view, but it reverts improvements that were made after the contributor branched.

**If your project has a dedicated merge verification skill, run it after every cherry-pick.** A good verification protocol covers file overlap detection, prior feature survival, orphaned component checks, test cascades, and content replacement verification.

**If no dedicated verification skill is available, check manually:**

**For each file modified by the cherry-pick:**

1. Check if the same file was modified by any prior synthesis merge:
   ```bash
   git log --oneline --diff-filter=M -- <file> | head -5
   ```
2. If overlap exists, read the diff carefully. Do not rely on the absence of merge conflicts.
3. Check component PROPS and IMPORTS, not just methods. Regressions often hide in declarations that git merges without conflict.
4. Verify all prior synthesis merge features still work in the cherry-picked result.
5. Run the full test suite after each cherry-pick, not just at the end.
6. Compare line counts before and after. If a file shrank, investigate what was removed.

**The pattern:** A contributor branches from main at commit A. The lead synthesist merges improvements at commits B, C, D. The contributor's branch still has the file as it was at commit A. Cherry-picking their changes brings back the commit-A version of any file they touched, silently reverting B, C, and D for that file.

---

## Cherry-Picking from Old Branch Bases

When a contributor's branch is based on old main, GitHub diffs show their changes PLUS apparent "deletions" of everything added to main since their branch point. This creates misleading diffs with extreme signal-to-noise ratios (real-world example: 1 meaningful change among 83 apparent deletions).

**Rules for old-branch integration:**

1. **Cherry-pick only the feature commits**, not the entire branch. Use `--no-commit` to stage changes without committing, allowing inspection before finalizing.
2. **Verify method counts.** After cherry-picking, confirm the target file has the expected number of methods/functions. A dropped method is a silent regression.
3. **Never trust the GitHub diff for old branches.** The diff shows the contributor's branch vs current main, not the contributor's actual changes. Use `git log contributor-branch --oneline` to identify which commits are actually theirs.

### Cherry-Pick Test Cascade

Behavioral changes in cherry-picked code can break tests in other files that depended on the old behavior. This is not limited to the cherry-picked files' own tests.

**After every cherry-pick:**
1. Run the full test suite, not just tests for modified files.
2. If tests in unrelated files fail, investigate whether the cherry-picked code changed an interface, default value, or behavior that other code depended on.
3. Track which tests broke — this tells you the blast radius of the cherry-picked change.

---

## Staging Branch Management

When the project uses a staging branch (`develop`) that auto-deploys to staging:

**Never force-push `main` to the staging branch.** This destroys contributors' unintegrated work. Instead, merge `main` into the staging branch:

```bash
git fetch origin
git checkout -b temp-staging origin/develop
git merge main
git push origin temp-staging:develop
git checkout main
git branch -d temp-staging
```

Before every push to the staging branch, check for divergence:

```bash
git fetch origin
git log main..origin/develop --oneline
```

If the log shows commits, merge rather than overwrite.
