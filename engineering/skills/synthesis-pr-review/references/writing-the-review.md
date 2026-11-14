# PR review: writing the review

What each kind of reviewer focuses on, how to write and format feedback, and the anti-patterns to avoid.

## The Review Process

### For Peer Reviewers

Focus on:

1. **Does the code make sense?** — Can you follow the logic without the author explaining it?
2. **Does it match the PR description?** — If not, which is wrong — the code or the description?
3. **Would you be comfortable debugging this at 2 AM?** — If no, the code needs to be clearer.
4. **Check the analog.** — Find the closest similar code in the codebase. Does this PR follow the same pattern?

Peer reviewers should feel empowered to request changes, not just approve. A rubber-stamp approval is worse than no review — it creates false confidence.

### For the Lead Synthesist

In addition to everything above, evaluate:

1. **Project-specific standards** — white-labeling compliance, UI terminology, deployment safety
2. **Architectural fit** — does this change move the codebase in the right direction?
3. **Integration complexity** — what will the adopt-and-adapt process look like?
4. **Completeness of the solution** — does this fully solve the problem, or is it a partial fix?

### Writing Review Feedback

- **Be specific.** "Line 47 removes the error recovery path — if the API call fails, polling never resumes" is actionable. "This has issues" is not.
- **Explain the why.** Do not just say what is wrong; explain the consequence.
- **Distinguish severity:**
  - **Must fix** — blocks merge, causes regression or data loss
  - **Should fix** — does not block merge, but should be addressed soon
  - **Consider** — suggestion for improvement, not blocking
  - **Nit** — style or preference, take it or leave it
- **Acknowledge what is good.** Name specific things done well. This reinforces patterns you want to see again.

### Review Comment Format

Use a structured format for lead integration reviews. This makes it clear what blocks merge, what is advisory, and gives contributors numbered labels for threaded discussion.

```
## Lead Integration Review

**Verdict:** Approve / Request Changes

### Must Fix
- [M1] Description of blocking issue with file and line reference
- [M2] ...

### Should Fix
- [S1] Description of non-blocking issue that should be addressed soon
- [S2] ...

### Consider
- [C1] Suggestion for improvement
- [C2] ...

### Nit
- [N1] Style or minor preference
- [N2] ...

### What's Good
- Specific thing done well and why it matters
- ...
```

**Why this structure matters:**

- **Verdict at top** — the contributor immediately knows the overall status without reading every comment first.
- **Numbered labels** (M1, S1, C1, N1) — enable precise threaded discussion. "Regarding M2, here is why I chose that approach" is clearer than "regarding your second comment."
- **Severity tiers** — contributors know exactly what blocks merge and what is advisory. This reduces back-and-forth and prevents important issues from getting lost among nits.

Not every review needs every section. Omit empty sections. For small, clean PRs, a short "Approve — looks good, one nit" is fine. Reserve the full template for substantive reviews.

---

## Common Anti-Patterns

### The Rubber Stamp

Approving without actually reading the code. Worse than no review — it creates a false record.

**Fix:** If you do not have time to review properly, say so.

### The Bundled PR

Multiple unrelated changes in one PR. Makes review harder, makes git bisect useless, makes reverts dangerous.

**Fix:** Request the author split the PR.

### The Symptom Fix

A fix that makes the visible problem go away without addressing the underlying cause.

**Fix:** Ask "what happens if the underlying condition occurs again in a slightly different way?"

### The Untested Assumption

"This should work" without verification. Especially dangerous for hard-to-reproduce bugs.

**Fix:** Ask for reproduction steps and verification.

### The Divergent Pattern

Implementing something one way while the rest of the codebase does it another way.

**Fix:** Point to the existing pattern and ask for alignment.
