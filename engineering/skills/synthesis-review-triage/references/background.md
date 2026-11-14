# Review triage: background

Why triage matters, and where it sits among the review skills.

## Why triage

The most common failure in code review is not low-quality reviews — it is reviewing the wrong thing at the wrong time. A team that reviews the newest PR first while a merge-ready PR sits waiting for one more approval is wasting reviewer capacity. Triage prevents this.

## Where This Fits

| Skill | Scope | When to use |
|-------|-------|-------------|
| **review-triage** (this one) | PR queue prioritization | Before starting a review session — decide which PR to review next |
| **pr-review** | Delta review of a single change | Every PR, before peer approval or lead integration |
| **code-audit** | 10-dimension quality scan of a diff | During review, as systematic input alongside judgment-based evaluation |

Triage is upstream of everything in the review path. Run it before opening any PR.
