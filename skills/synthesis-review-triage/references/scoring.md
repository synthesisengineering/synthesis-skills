# Review triage: scoring dimensions

How to score each reviewable PR, used after queue classification and exclusion and before tier assignment.

Contents:
- Review Gap
- CI Status
- Age & Staleness
- Size
- Labels
- Updated Since Last Review

## Scoring Dimensions

Score each reviewable PR across these dimensions. The goal: maximize the impact of your review time.

### Review Gap — weight: highest

How far is the PR from its approval threshold?

| State | Urgency |
|-------|---------|
| 1 approval, CI passing, no conflicts | **Critical** — your review unblocks merge |
| 0 reviews | **High** — nobody has looked at it |
| Has review comments but 0 approvals | **High** — reviewed but not approved |
| Already meets approval threshold | **Low** — threshold met, your review is additive |

This is the most impactful dimension because it directly connects your review to an unblock event.

### CI Status — weight: medium

| Status | Effect |
|--------|--------|
| All passing | Boost — PR is actionable right now |
| Some failing | Neutral — may still be worth reviewing |
| All failing | Deprioritize — author needs to fix CI first |

### Age & Staleness — weight: medium

- Days since PR opened
- Days since last activity (commits, comments, reviews)
- Open > 7 days with no review = review debt — boost priority
- Updated in last 24h = actively being worked on — slight boost

Review debt compounds. A PR that has waited a week is more urgent than one opened an hour ago, all else being equal.

### Size — weight: low-medium

| Lines changed | Tag | Effect |
|---------------|-----|--------|
| < 50 | S | Quick review — slight boost (fast to unblock) |
| 50–200 | M | Standard |
| 200–500 | L | Significant — no automatic effect |
| > 500 | XL | Flag for possible split — not buried, but noted |

Smaller PRs get a slight boost because they are faster to unblock. XL PRs are flagged but not deprioritized — they may block the most downstream work.

### Labels — weight: override

Labels like "priority," "urgent," "critical," "hotfix," or "blocker" push the PR to the top regardless of other scores. These represent explicit team decisions about urgency.

### Updated Since Last Review

If a PR has reviews AND commits pushed after the most recent review, flag it: "New commits since last review — delta review needed." Boost priority. The author addressed feedback and is waiting for re-review.
