---
name: synthesis-code-integration
description: "The adopt-and-adapt integration pattern for multi-contributor synthesis-coded projects. Covers the lead synthesist role, quality gates, cherry-pick safety, and graduated integration intensity. Use when asked to: synthesis coding, multi-contributor, integration, cherry-pick, adopt and adapt, lead synthesist, integrate contributions, merge contributor work."
license: "CC0-1.0"
depends_on: []
metadata:
  author: "Rajiv Pant"
  version: "1.3.1"
  source_repo: "github.com/synthesisengineering/synthesis-skills"
  source_type: "public"
---

# Code Integration

When multiple people contribute to a project built through synthesis coding, integration is fundamentally different from a standard open source merge workflow. This skill defines how it works.

---

## The Core Problem

In synthesis coding, the lead developer (the "lead synthesist") builds and evolves the system through continuous, context-rich collaboration with AI. The result is a codebase with:

- Deep architectural consistency — decisions compound across sessions
- Implicit conventions — not all standards are documented yet because one person held them all in their head
- Rapid evolution — the codebase may change substantially between the time an external contributor branches off and the time they submit a PR

When an external contributor forks or branches, they get a snapshot. They build against that snapshot. Meanwhile, the lead may have evolved the architecture, introduced new patterns, improved output quality, or refactored entire subsystems. The contributor's code reflects the old state.

A blind merge risks:

- **Regression** — undoing improvements the lead made after the contributor branched
- **Inconsistency** — introducing patterns that conflict with the codebase's evolved conventions
- **Security gaps** — missing safeguards the lead added (audit logging, rate limiting, input validation)
- **Quality drift** — code that works but does not meet the project's current bar

---

## Adopt-and-Adapt: The Integration Pattern

The lead synthesist does not merge external contributions directly. Instead:

1. **Adopt** the intent, the design, and the valuable implementation work
2. **Adapt** the code to meet current standards, architecture, and quality bar

This is neither a merge nor a rewrite. It is selective integration with improvement. The contributor's work is the foundation; the lead brings it up to production standard.

### Why This Works

- **Respects the contributor's work.** Their design thinking, feature concept, and implementation effort are preserved.
- **Maintains quality.** The lead synthesist is the quality gate. Nothing ships that does not meet the bar.
- **Avoids regression.** By starting from current `main` and selectively pulling in changes, the lead never risks overwriting recent improvements.
- **Educates through feedback.** The review process teaches contributors the project's standards, making future contributions smoother.

### Why Direct Merge Does Not Work

- The contributor did not have the latest context. Their code is correct for a codebase that no longer exists in that exact form.
- Standards evolve faster than documentation. The lead synthesist holds conventions that are not yet written down.
- AI-accelerated development means the codebase moves fast. A branch that is a week old may be dozens of commits behind.

---

## Roles

### Lead Synthesist

The person who holds the architectural vision, maintains the quality bar, and has the deepest context on the system.

**Responsibilities:**
- Define and evolve project standards
- Review all external contributions
- Perform adopt-and-adapt integration
- Maintain the canonical repository
- Control production deployments
- Document standards as they emerge through the integration process

**Key principle:** The lead synthesist's standards ARE the project's standards. Integration is the forcing function that makes those standards explicit and documented.

### Contributors

Developers who build features on branches or forks. They may or may not use synthesis coding themselves.

**Responsibilities:**
- Understand existing standards before building (read the contributor guide)
- Submit complete features (both frontend and backend, with tests)
- Maintain clean branch hygiene (one feature per branch, meaningful commits)
- Respond to review feedback and iterate

---

## Contribution Workflow

### Before Building

1. **Read the project's contributor guide.** Every synthesis-coded project with external contributors should maintain one.
2. **Sync to latest main.** Do not build on stale code.
3. **Discuss the approach for significant features.** Especially anything touching auth, security, the data model, or user-facing architecture.

### While Building

1. **One feature per branch.** Never bundle unrelated work.
2. **Complete features only.** Backend + frontend + tests = complete.
3. **Follow existing patterns.** Before creating a new component, search the codebase for similar ones.
4. **Meaningful commits.** Use conventional commit format (`feat:`, `fix:`, `docs:`, `test:`, `chore:`).

### Submitting

1. **Rebase onto latest main.** Minimize divergence.
2. **Clean diff.** No debugging artifacts, no commented-out experiments, no unrelated changes.
3. **Share early if uncertain.** A draft PR with a question is better than a finished PR that needs fundamental rework.

---

## The Integration Process

### Step 1: Assess

- Fetch the branch and review the diff
- Identify what the contribution does, what it changes, and what assumptions it makes
- Check: how far has `main` moved since the contributor branched off?
- Check: does the contribution touch sensitive areas (auth, security, data model, user-facing text)?

### Step 2: Review

Evaluate against the project's quality gates. Produce written feedback covering:

- **What's strong** — acknowledge good work
- **What must change** — security issues, broken functionality, standards violations
- **What should change** — code quality improvements, performance concerns, architectural suggestions

### Step 3: Integrate (Adopt-and-Adapt)

1. **Create a fresh branch off current `main`.** Never merge the contributor's branch directly.
2. **Selectively bring in changes.** File by file, function by function. Cherry-pick the implementation, not the entire branch.
3. **Fix identified issues during integration.** Do not merge first and fix later. The adapted code should be production-ready when it hits `main`.
4. **Test the integrated result.** Run the full test suite — not just the tests for the PRs being merged. Test the feature manually. Verify nothing regressed.
5. **Squash merge to canonical `main`.** Use contributor attribution (see below).
6. **Sync mirrors/forks.** Push the updated `main` to any mirrors.

### Step 4: Communicate

- Share the integration review with the contributor
- Explain what was changed and why — this is how standards transfer
- Acknowledge their contribution's value
- Note lessons that should go into the contributor guide

---

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

## Contributor Attribution

GitHub's contributor graph counts commits where you are the **author**. Custom text like `Contributor: Name (PR #5)` in the commit body is human-readable but GitHub does not parse it.

Use `Co-authored-by` trailers, which GitHub officially recognizes:

```
feat: add product description field to content pipeline

Integrates product description generation with writer guidance support.

Co-authored-by: Contributor Name <contributor@example.com>
```

The attribution model should match the integration intensity:

- **Full adopt-and-adapt** (substantial rework): Lead as commit author, contributor as `Co-authored-by`.
- **Lighter-touch integration** (minor adjustments): Contributor as commit `--author`, lead as `Co-authored-by`.
- **Merge-then-refine** (editorial improvements after merge): PR merge preserves contributor's commits. Lead's follow-up commit is separate, referencing the PR.
- **Direct merge** (zero-adjustment): Standard PR merge flow.

Attribution is not decoration. Developers use contribution graphs for career advancement. A workflow that funnels all commits through the lead's name effectively erases contributors from the project's visible history.

---

## Quality Gates

Every contribution must pass these gates before integration.

### Meta-Principle: Zero Accepted Failures

Every test must pass. Every lint error must be clean. No exceptions for "pre-existing" or "known" failures.

When you encounter a failing test you didn't cause, fix it — right then, in the same branch. The distinction between "my failure" and "someone else's failure" is irrelevant; the only question is whether the suite is green when you're done.

**Why:** A test suite with accepted failures is a broken smoke detector. It cannot tell you whether your change is safe. Every "known failure" you walk past teaches the next engineer that failing tests are normal. This is how test suites die — not in one catastrophic event, but through gradual normalization of red.

**The cost argument:** Fixing a pre-existing failure while you're already in the code costs minutes. Coming back later after context is lost costs hours. The cheapest time to fix is always now.

**The campsite rule for code:** Leave the test suite greener than you found it. If you touched the codebase, you own its health when you leave.

### Gate 1: Completeness

- Feature is fully implemented (not half-frontend, half-backend)
- No dead code, no references to methods that do not exist
- No dependency on unreleased or unmerged work
- Tests exist for new backend logic

### Gate 2: Security

- Privileged operations produce audit log entries
- Auth tokens handled correctly (claims propagated through refresh, appropriate expiry)
- Rate limiting on sensitive endpoints
- No credentials or secrets hardcoded in code
- Input validation at system boundaries
- User data exposure reviewed (no unnecessary information leakage)

### Gate 3: Architecture

- One feature per branch (no bundled unrelated changes)
- Follows existing codebase patterns (component structure, API client usage, error handling)
- Uses framework features properly (not fighting the framework with workarounds)
- No regression of existing functionality
- No unnecessary complexity

### Gate 4: Project-Specific Standards

These vary by project. The contributor guide should document these. If a standard is not documented and a contributor violates it, that is the lead's responsibility to document — not the contributor's fault.

---

## Communication and Feedback

### Principles

- **Be specific, not vague.** "This has security issues" is useless. Name the issue, explain why it matters, and suggest the fix.
- **Explain the why.** Contributors who understand the reasoning behind a standard will follow it naturally in future work.
- **Acknowledge good work.** People do more of what gets recognized.
- **Distinguish severity levels.** "Must fix before production" vs. "should fix" vs. "consider for future."
- **Fix first, talk later.** When you find a bug with an obvious fix during integration: fix it, test it, deploy it, THEN tell people. Do not draft Slack messages explaining your findings when you could ship the fix in 2 minutes. Action before communication when the action is quick and the risk of delay is real.

### Ground All Technical Replies in Code

Before drafting ANY technical reply (to a contributor, in a PR comment, in a Slack thread), verify your claims against actual code. The lead synthesist sending a reply that agrees with a wrong analysis undermines credibility and trust.

**Verification checklist by reply type:**

| Reply type | Before responding, verify |
|-----------|--------------------------|
| Bug report | Reproduce the bug. Read the relevant code paths. Confirm the reported behavior matches what the code actually does. |
| PR review | Read the diff AND the surrounding code. Understand what the change interacts with, not just what it changes. |
| Feature request | Check if the feature already exists, partially exists, or conflicts with planned work. |
| Infrastructure question | Check actual config files, deployment scripts, and environment variables. Do not rely on memory. |

### The Integration Review Document

For each set of contributions, produce a written review covering:

1. **Project standards the contributor needs to know** — extracted from the lead's implicit knowledge
2. **Specific feedback on each PR** — strengths, issues, recommendations
3. **The integration plan** — what the lead will do with the code and in what order
4. **Contribution workflow for next time** — how to submit work that integrates more smoothly

---

## Investigate Before Concluding

Get basic facts before forming hypotheses. This applies to integration review, bug triage, and any technical analysis.

**Rules:**
- Do not test with wrong inputs. Verify you are using the correct test data, credentials, and environment before drawing conclusions.
- Do not confuse access from your machine with access from the server. Local environment variables, network access, and permissions differ from production.
- Say "I don't know" when you do not know. An incorrect confident answer causes more damage than admitting uncertainty.
- Check the simplest explanation first. Before hypothesizing about race conditions or distributed system failures, verify that the basic inputs and configuration are correct.

**Before publishing any analysis:**
1. State your evidence explicitly
2. Distinguish between "I observed X" and "I conclude Y"
3. Check if alternative explanations fit the same evidence
4. If the conclusion has material consequences (reverting code, blocking a deploy, escalating to a stakeholder), get a second pair of eyes

---

## Integrating Multiple PRs

When integrating more than two or three PRs in a session, ordering becomes a design decision.

### Dependency-Aware Ordering

1. **Independent PRs first.** Zero-overlap PRs validate the integration pipeline before tackling complex merges.
2. **Within a subsystem, simpler PR first.** When multiple PRs modify the same files, integrate the smaller one first.
3. **Read the merged result fresh.** After auto-merge resolves conflicts, read the merged code as if reviewing it for the first time. Auto-merged regions can produce semantic errors that no tool will flag.

### Cross-PR Test Failures

Each PR may pass its own CI independently. The synthesis merge still catches failures caused by cross-PR interactions. Run the **full** test suite on the integration branch.

---

## Fallback: Selective File Checkout

When a contributor's branch has a complex commit history (multiple renames, moves, reorganizations), cherry-picking may fail with rename/delete conflicts.

When the desired change is a known set of **new** files:

```bash
# 1. Identify what files actually changed
git diff --name-only main...contributor/branch

# 2. Checkout only those specific files
git checkout contributor/branch -- path/to/new/file1 path/to/new/file2

# 3. Commit with attribution
git commit -m "integrate PR #N: description

Co-authored-by: Contributor Name <contributor@example.com>"
```

**When to use:** Docs-only PRs with messy history, configuration file additions, any PR where `git diff --name-only` shows a small obvious set of new files.

**When NOT to use:** Changes that modify existing files (you would overwrite main's version), changes where semantic conflicts are possible.

---

## Evolution of Integration Intensity

### Phase 1: Full Adopt-and-Adapt

The lead creates a fresh integration branch, selectively brings in changes, and fixes every issue during integration.

**When appropriate:** First contributions from a new contributor. Contributions touching sensitive areas. Contributions built against significantly stale `main`.

### Phase 2: Lighter-Touch Integration

The lead merges with minor adjustments. The contributor's code structure is preserved.

**When appropriate:** Contributor has had at least one round of detailed review feedback. Issues are minor and localized.

### Phase 3: Merge-then-Refine

The lead merges the PR directly via GitHub, preserving the contributor's commits and authorship. Then creates a separate follow-up commit with editorial improvements, referencing the original PR.

**When appropriate:** Contribution is PR-based and high quality. The contributor did the creative work and deserves primary credit — first contributions, open-source visibility, career attribution. The lead's changes are editorial or cosmetic, not structural.

**When NOT appropriate (use Phase 1 instead):** Lead's changes are structural — different approach, architectural redesign. Branch is significantly stale. Security issues require pre-merge remediation.

**Workflow:**
1. Merge the PR via GitHub (`gh pr merge N --merge` or `--rebase`)
2. Create a separate follow-up commit with improvements, attributed to the lead
3. Commit message references the original PR: `Refinements to #N`

### Phase 4: Direct Merge with Review

Standard pull request workflow. The contributor submits, gets peer and lead review, and it merges directly.

**When appropriate:** Contributor consistently meets the quality bar across multiple contributions.

### Adjusting in Both Directions

The phases are not permanent promotions. If a contribution introduces a security gap or regression, intensity goes back up.

**Upgrade signal:** Fewer than half the issues of the previous round, and those issues are cosmetic.

**Downgrade signal:** A contribution introduces a security gap, architectural regression, or bundled unrelated changes.

### Choosing Between Lighter-Touch and Merge-then-Refine

| Factor | Lighter-Touch (Phase 2) | Merge-then-Refine (Phase 3) |
|--------|------------------------|-----------------------------|
| Contribution source | Branch cherry-pick or non-PR | PR-based contribution |
| Lead's changes | Interleaved with contributor's code | Separable from contributor's code |
| Git blame accuracy | Single combined commit | Per-line attribution preserved |
| GitHub merge event | No PR merge recorded | PR shows as merged, contributor credited |

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

---

## Convention Review Checklist

Contributors using AI coding tools produce code that is functionally correct but drifts from project-specific conventions.

### Standard Items (Every Project)

1. **Correctness** — edge cases, race conditions, error paths
2. **Existing pattern adherence** — matches codebase conventions
3. **Test coverage** — new backend logic has tests; existing tests still pass
4. **Security** — audit logging, auth handling, input validation

### Project-Specific Items (Define Per Project)

These are the conventions that AI tools miss because they do not exist in training data:
- Brand terminology compliance
- AI messaging rules
- CSS/UI framework conventions
- Role-based access patterns

Add this checklist to the project's contributor guide. Make it a formal gate, not an optional pass.

---

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

---

## Critical Config Regression Guards

When a configuration value is deliberately upgraded (e.g., thinking effort from "high" to "max", or token budgets from 16K to 24K), add a test that asserts the new value and will fail if it's reverted.

### Why This Exists

Cherry-picks from older branches carry the old config values. A merge conflict in a config file can resolve to the older value. A contributor who copies a config pattern from their older branch silently downgrades the value. None of these trigger test failures because the old value is "valid" — it just produces worse results.

### The Pattern

```python
def test_thinking_effort_is_max(self):
    """Content generation MUST use max thinking effort.

    Downgrading to 'high' causes thinking-phase exhaustion on complex
    articles. See incident 2026-03-30.
    """
    assert THINKING_CONFIG["content"]["output_config"]["effort"] == "max", (
        "CRITICAL: Content thinking effort was downgraded from 'max'. "
        "If intentional, update this test with justification."
    )
```

### When to Add Config Guards

Add a guard test whenever you:
- Upgrade a thinking/reasoning effort level
- Raise token budgets or context limits
- Change a model selection (e.g., from Sonnet to Opus for a task)
- Enable a feature flag that affects output quality
- Change a retry count, timeout, or resilience parameter

The test comment must explain WHY the value matters, not just WHAT it is. A future developer encountering a failing guard test needs to understand the consequences of the old value before deciding to change it.

---

## Lessons and Anti-Patterns

### Anti-Pattern: The Blind Merge
Merging without reviewing against current standards. **Prevention:** Every external contribution goes through adopt-and-adapt.

### Anti-Pattern: Bundled Features
Multiple unrelated features in one PR. **Prevention:** One feature per branch.

### Anti-Pattern: Orphaned Half-Features
Frontend code calling backend endpoints that do not exist. **Prevention:** Require complete features.

### Anti-Pattern: Auto-Deploy Without Approval
CI/CD that deploys to production on push with no approval gate. **Prevention:** Production deploys always require explicit human approval.

### Anti-Pattern: Stale Documentation
Integration documents that describe the system as it was. **Prevention:** Update the contributor guide as part of every integration cycle.

### Lesson: Integration Is When Standards Get Documented
The act of reviewing external contributions forces the lead synthesist to make implicit standards explicit.

### Lesson: The Contributor Guide Is a Living Document
It should grow with every integration.

### Lesson: Review the Branches, Not Just the PRs
Contributors may have branches beyond what is in the PRs. Fetch all remote branches and understand the full scope.

### Anti-Pattern: Squash Merge Without PR Manifest Check
Squash-merging an integration branch without verifying that every PR on the branch is represented in the squash diff. **Prevention:** Run the pre-squash PR manifest check before committing.

### Anti-Pattern: Changelog from Conversation Context
Writing changelog entries based on what you discussed or planned rather than what's actually in the code. **Prevention:** Verify every changelog entry with `git grep` or file read against the target branch.

### Anti-Pattern: "Worked on Staging" = "Merged to Main"
Assuming a feature is in `main` because it was visible on staging. Staging (`develop`) can contain integration branch work that was never squash-merged to `main`. **Prevention:** Verify features against `main`, not `develop`.

### Anti-Pattern: Unguarded Config Upgrades
Upgrading a critical config value (thinking effort, token budgets, model selection) without adding a test that asserts the new value. **Prevention:** Every deliberate config upgrade gets a guard test.

### Lesson: Squash Merges Are Inherently Lossy
A squash merge combines N commits into 1. If any commit is excluded, there's no trace in the git history. The defense is the pre-squash manifest check — without it, you're relying on memory to track what was included.

### Lesson: The Integration Branch Is Not Main
Features exist on `main` only after the squash merge commit. The integration branch is a workspace, not a release. Changelogs, release notes, and "what's shipped" claims must be verified against `main`.
