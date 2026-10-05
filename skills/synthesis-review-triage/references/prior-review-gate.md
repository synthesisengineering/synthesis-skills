# Review triage: the prior-review gate

Run this before investing time in a PR you have already reviewed.

## Prior-Review Gate

Before investing time in a PR you have already reviewed, run this decision gate:

### Step 1: Summarize Prior Review

State your prior review's outcome (approved, changes requested, commented), when it happened, and a one-line summary of what you covered.

### Step 2: Classify New Activity

Determine what changed since your last review:

- **Merge-only commits** — branch was rebased or merged from base. Likely no code changes.
- **Code commits** — actual new code since your review. Count them and note their scope.
- **New reviewer comments** — other reviewers may have covered ground you would duplicate.

### Step 3: Decide

| Situation | Action |
|-----------|--------|
| Merge-only commits, no code changes | **Skip** or quick manual verify |
| Small code commits addressing your feedback | **Delta review** — diff only new commits, check if feedback was addressed |
| Large code commits or significant new work | **Full review** — treat as a fresh evaluation |
| Other reviewers covered your concerns | **Skip** — your review adds no new value |

**Why this gate exists:** A rebase or merge-of-base produces "new commits since your last review" but often changes nothing in the PR's own code. Running a full review wastes time and produces identical findings. The prior-review gate prevents this wasted effort.
