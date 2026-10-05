---
name: synthesis-review-triage
description: "Prioritize a PR review queue: classify, exclude, detect author responses, score by review gap, CI, age, size and labels, and gate re-reviews (full, delta or skip). Use when asked to triage PRs, which PR to review next, review queue, PR backlog, review priority or review workload."
license: "CC0-1.0"
depends_on: []
metadata:
  author: "Emil Peñaló"
  version: "2.0.0"
  source_repo: "github.com/synthesisengineering/synthesis-skills"
  source_type: "public"
  format: v5
---

# Synthesis Review Triage

Review triage decides *which* PR to review next. It does not evaluate code — that is the job of synthesis-pr-review and synthesis-code-audit. Triage is a routing and scheduling methodology: classify the queue, score each item by urgency, and direct review effort where it has the most impact.

## Binding rules

1. **Triage is routing, not evaluation.** Do not assess code quality during triage. That is what pr-review and code-audit are for.
2. **The scoring is a framework, not a formula.** Adapt weights to your team's context. A team with a strict SLA on review turnaround might weight age higher. A team with frequent CI flakiness might weight CI status lower.
3. **Author-response detection prevents misclassification.** Always check for post-review commits before labeling a PR as "waiting on author."
4. **"Already reviewed" does not mean "already approved."** Distinguish carefully — a commented review with no verdict is not a completed review.
5. **Respect explicit team signals.** Priority labels, blocker tags, and team conventions override the scoring framework.
6. **Exclude before scoring:** your own PRs, drafts, PRs you already approved, and PRs you reviewed with no code commits since.
7. **Review in tier order;** within a tier, the scoring dimensions break ties. Priority labels override the scores.
8. **Before re-reviewing a PR you already reviewed, run the prior-review gate** and choose full, delta or skip; a rebase alone rarely earns a full review.

## Contents

- [references/scoring.md](references/scoring.md): the scoring dimensions in full: review gap, CI status, age and staleness, size, labels, and updated-since-last-review, with their weights and tables. Read it when scoring the reviewable queue or adapting the weights to a team.
- [references/prior-review-gate.md](references/prior-review-gate.md): the three-step gate (summarize the prior review, classify new activity, decide full, delta or skip). Read it before spending time on a PR you have already reviewed.
- [references/background.md](references/background.md): why triage matters and where it sits beside pr-review and code-audit. Read it when deciding which review skill a request needs.
- [references/coverage-map.md](references/coverage-map.md): where each part of the 1.0.0 text now lives.
- Queue Classification, Exclusion Rules, Author-Response Detection, Tier Assignment: below.

## Queue Classification

Every open PR belongs to exactly one of three categories:

### 1. Reviewable

PRs that need your review action. This is the working queue — everything you score and prioritize comes from here.

### 2. Waiting on Author

PRs that are genuinely blocked on the author. Changes were requested or a blocker was raised, and the author has not responded. These are visible for awareness but not actionable by the reviewer.

### 3. Blocked

PRs held by external factors — labels like "blocked" or "do not merge," dependency on another PR, or infrastructure holds. Shown for awareness, not actionable.

## Exclusion Rules

Before scoring, remove PRs that should not be in your queue:

- **Self-authored** — you do not review your own PRs.
- **Drafts** — the author has not marked the PR ready for review.
- **Already approved by you** — your review work is done. This includes dismissed approvals that were positive in nature (contained "LGTM," "looks good," or similar signals with no blockers). A dismissed approval after a force-push does not mean the reviewer's assessment was wrong — it means the platform reset the review state.
- **Already reviewed by you with no new code commits** — you have seen this code. If the most recent commit on the PR predates your last review, there is nothing new to evaluate.

### Classifying Post-Review Commits

When a PR has new commits since your last review, classify them before deciding what to do:

- **Merge-only commits** (all new commits have 2+ parents, or messages begin with "Merge branch") — likely no code changes. Flag as "rebase/merge since your last review — verify manually." These rarely warrant a full re-review.
- **Code commits** (at least one new commit with 1 parent and a substantive message) — actual changes since your review. Flag as "new code commits since your last review — delta review needed." Boost priority.

## Author-Response Detection

This is the single most important classification decision in triage. Get it wrong and review-ready PRs hide in the "waiting on author" bucket.

**The insight:** A PR with changes requested + new commits pushed after the review is not blocked on the author. The author already responded. It is blocked on the *reviewer* to re-review.

**How to determine this:**

1. Find the timestamp of the most recent changes-requested review (or blocker comment).
2. Find the timestamp of the latest commit on the PR.
3. Compare:
   - **Latest commit is after the review** — the author likely addressed feedback. Move to the **Reviewable** queue with flag: "Author pushed changes after review — re-review needed." Boost priority.
   - **No new commits since the review** — genuinely **Waiting on Author**.

Apply the same logic to inline blocker comments (comments containing "blocker," "must fix before merge," "do not merge," or similar signals). If commits arrived after the blocker was posted, the author may have addressed it.

**Why this matters:** Teams that classify all "changes requested" PRs as "waiting on author" create invisible review debt. The author did their part. The reviewer is now the bottleneck but does not know it.

## Tier Assignment

Group scored PRs into tiers:

| Tier | Criteria |
|------|----------|
| **Critical** | 1 approval + CI passing + no conflicts. Your review unblocks merge. |
| **High** | 0 reviews + CI passing. Or: updated since last review (author responded to feedback). |
| **Medium** | Reviewable but not urgent — CI mixed, very recently opened, or already has non-blocking reviews. |
| **Waiting on Author** | Changes requested with no author response since the blocking review. |

Review in tier order. Within a tier, use the scoring dimensions as tiebreakers.
