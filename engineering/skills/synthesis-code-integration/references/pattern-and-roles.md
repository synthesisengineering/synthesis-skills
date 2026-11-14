# Code integration: the pattern and the roles

Why integration in a synthesis-coded project needs its own pattern, who does what, and how contributors should work.

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
