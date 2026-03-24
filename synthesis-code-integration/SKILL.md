---
name: synthesis-code-integration
description: "The adopt-and-adapt integration pattern for multi-contributor synthesis-coded projects. Covers the lead synthesist role, quality gates, cherry-pick safety, and graduated integration intensity. Use when asked to: synthesis coding, multi-contributor, integration, cherry-pick, adopt and adapt, lead synthesist, integrate contributions, merge contributor work."
license: "CC0-1.0"
depends_on: []
metadata:
  author: "Rajiv Pant"
  version: "1.0.0"
  source_repo: "github.com/rajivpant/synthesis-skills"
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

## Post-Cherry-Pick Regression Verification

Cherry-picking is the most common integration mechanism, but it carries a hidden risk: files from a contributor's old branch may silently overwrite work from prior synthesis merges. The cherry-pick succeeds without conflicts because the contributor's version is "newer" in git's view, but it reverts improvements that were made after the contributor branched.

**If your project has a `synthesis-merge-verification` skill, run it after every cherry-pick.** It provides a complete 5-step protocol covering file overlap detection, prior feature survival, orphaned component checks, test cascades, and content replacement verification.

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
- **Direct merge** (zero-adjustment): Standard PR merge flow.

Attribution is not decoration. Developers use contribution graphs for career advancement. A workflow that funnels all commits through the lead's name effectively erases contributors from the project's visible history.

---

## Quality Gates

Every contribution must pass these gates before integration.

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

### Phase 3: Direct Merge with Review

Standard pull request workflow. The contributor submits, gets peer and lead review, and it merges directly.

**When appropriate:** Contributor consistently meets the quality bar across multiple contributions.

### Adjusting in Both Directions

The phases are not permanent promotions. If a contribution introduces a security gap or regression, intensity goes back up.

**Upgrade signal:** Fewer than half the issues of the previous round, and those issues are cosmetic.

**Downgrade signal:** A contribution introduces a security gap, architectural regression, or bundled unrelated changes.

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
