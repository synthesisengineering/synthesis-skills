---
name: synthesis-code-integration
description: "The adopt-and-adapt pattern for integrating contributions to a synthesis-coded project: lead synthesist, quality gates, cherry-pick safety, integration intensity. Use for synthesis coding, multi-contributor, integration, cherry-pick, adopt and adapt, integrate or merge contributor work."
license: "CC0-1.0"
depends_on: []
metadata:
  author: "Rajiv Pant"
  version: "2.0.0"
  format: v5
  source_repo: "github.com/synthesisengineering/synthesis-skills"
  source_type: "public"
---

# Code Integration

When multiple people contribute to a project built through synthesis coding, integration is fundamentally different from a standard open source merge workflow. This skill defines how it works.

## Binding rules

1. **Adopt and adapt by default; never blind-merge.** Branch fresh from current `main`, bring changes in selectively, and fix issues before they reach `main`, because the contributor built against a codebase that has since moved. Lighter phases are earned by a contributor's record and lost on a regression.
2. **Zero accepted failures.** Every test passes and every lint is clean, including failures you did not cause, fixed in the same branch; a suite with known failures cannot tell you whether a change is safe.
3. **Every contribution passes Gates 1 to 4** (completeness, security, architecture, project-specific standards) before integration. An undocumented standard is the lead's to document, not the contributor's fault.
4. **Never merge another long-lived branch into a PR branch.** Put the commit on that branch as a separate operation; only a promotion PR (such as `develop` to `main`) carries another branch's work.
5. **After every cherry-pick, look for silent reversions and run the full suite.** A conflict-free cherry-pick can bring back an old version of a file; never trust the GitHub diff for an old branch.
6. **Never force-push `main` to the staging branch.** Check for divergence and merge instead, so contributors' unintegrated work survives.
7. **Run the pre-squash PR manifest check before every squash merge,** and write no changelog entry for a feature you have not found in the code on the target branch.
8. **Guard every deliberate upgrade of a critical config value** (effort level, token budget, model, retries) with a test that explains why the value matters.
9. **Ground every technical reply in code.** Separate what you observed from what you conclude, and say "I don't know" when you don't.
10. **Credit contributors with `Co-authored-by` trailers** that match the integration intensity, because contribution graphs feed careers.
11. **Fix first, talk later** when the fix is quick and delay is risky.
12. **Production deploys always require explicit human approval.**

## Contents

- [references/pattern-and-roles.md](references/pattern-and-roles.md): the core problem, the adopt-and-adapt pattern and why direct merge fails, the lead synthesist and contributor roles, and the contribution workflow. Read when explaining the model or writing a contributor guide.
- [references/review-gates.md](references/review-gates.md): the zero-accepted-failures principle, Gates 1 to 4, the convention review checklist, and config regression guards. Read when assessing a contribution (step 2 below).
- [references/communication.md](references/communication.md): feedback principles, grounding replies in code, the integration review document, and investigating before concluding. Read before any technical reply, PR comment or published analysis.
- [references/integration-options.md](references/integration-options.md): contributor attribution, ordering several PRs, selective file checkout, and the four phases of integration intensity. Read when choosing how to integrate (step 3 below).
- [references/branches-and-cherry-picks.md](references/branches-and-cherry-picks.md): branch hygiene for PR branches, post-cherry-pick regression checks, old branch bases, and staging branch management. Read before any cherry-pick, any push to a second long-lived branch, or any push to staging.
- [references/squash-and-changelog.md](references/squash-and-changelog.md): the mandatory pre-squash PR manifest check and changelog verification. Read before a squash merge or a changelog entry.
- [references/lessons.md](references/lessons.md): the anti-patterns and lessons that produced these rules. Read when a situation is unclear.
- [references/coverage-map.md](references/coverage-map.md): where each part of the 1.3.1 text now lives (ruling D8).
- The Integration Process: below. The four steps: assess, review, integrate, communicate.

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
