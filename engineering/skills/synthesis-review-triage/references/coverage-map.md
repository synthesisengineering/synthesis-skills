# Coverage map: review triage 1.0.0 to 2.0.0

Every part of the 1.0.0 SKILL.md and where it lives now. Nothing was removed.

| 1.0.0 section | Now |
|---|---|
| Frontmatter description (folded block) | A quoted string of 280 characters; it keeps the triggers "triage PRs", "which PR to review", "review queue", "PR backlog", "review priority" and "review workload" |
| Opening paragraph 1 (triage decides which PR to review next) | SKILL.md opening (verbatim) |
| Opening paragraph 2 (reviewing the wrong thing at the wrong time) | references/background.md (verbatim) |
| Where This Fits | references/background.md (verbatim) |
| Queue Classification | SKILL.md (verbatim) |
| Exclusion Rules, with Classifying Post-Review Commits | SKILL.md (verbatim); summarized in Binding rule 6 |
| Author-Response Detection | SKILL.md (verbatim); Binding rule 3 states its rule |
| Scoring Dimensions (Review Gap, CI Status, Age & Staleness, Size, Labels, Updated Since Last Review) | references/scoring.md (verbatim) |
| Tier Assignment | SKILL.md (verbatim); summarized in Binding rule 7 |
| Prior-Review Gate | references/prior-review-gate.md (verbatim); summarized in Binding rule 8 |
| Rules | Became Binding rules 1 to 5, below |
| Horizontal rules between sections | Dropped as layout only |
| `depends_on`, `source_repo`, `source_type`, `author` | Kept: `synthesis-agent-conformance` checks them in its source contract and `synthesis-onboarding` modular install reads `depends_on` |

## Lines restructured in place

The `## Rules` heading became `## Binding rules`, and its five bullets became Binding rules 1 to 5: the bullet marker changed to a number and every word stayed. The 1.0.0 lines were:

```text
## Rules
- **Triage is routing, not evaluation.** Do not assess code quality during triage. That is what pr-review and code-audit are for.
- **The scoring is a framework, not a formula.** Adapt weights to your team's context. A team with a strict SLA on review turnaround might weight age higher. A team with frequent CI flakiness might weight CI status lower.
- **Author-response detection prevents misclassification.** Always check for post-review commits before labeling a PR as "waiting on author."
- **"Already reviewed" does not mean "already approved."** Distinguish carefully — a commented review with no verdict is not a completed review.
- **Respect explicit team signals.** Priority labels, blocker tags, and team conventions override the scoring framework.
```

## The 1.0.0 frontmatter, verbatim

Kept on record so the old description and metadata are not lost.

```yaml
---
name: synthesis-review-triage
description: >
  PR queue prioritization methodology with weighted scoring across review gap,
  CI status, age, size, and labels. Includes author-response detection, queue
  classification, and prior-review gate for deciding full audit vs. delta-only
  vs. skip. Use when asked to: triage PRs, which PR should I review, review
  queue, prioritize reviews, PR backlog, review priority, what needs review,
  PR triage, review workload.
license: "CC0-1.0"
depends_on: []
metadata:
  author: "Emil Peñaló"
  version: "1.0.0"
  source_repo: "github.com/synthesisengineering/synthesis-skills"
  source_type: "public"
---
```
