# Code integration: lessons and anti-patterns

The failures and lessons behind the rules in SKILL.md.

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
