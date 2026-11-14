# Codebase review: report formats

How to present findings for each tier, how to run a delta review, and how to file the deliverables.

## Output Format

### Key Principle: Strengths Before Findings

All reports lead with strengths before findings. Demonstrating that you understand what the team built well makes critical findings land as constructive guidance rather than an attack.

### Tier 1-2: Simplified Report

```markdown
## Codebase Review Summary

**Project**: [Name]
**Tier**: [1-Essential / 2-Standard]
**Date**: YYYY-MM-DD

### Quick Health Check: Pass / Issues / Fail

### Strengths
1. [What the codebase does well]
2. [Notable good practices]

### Key Findings

| # | Finding | Severity | Location | Fix |
|---|---------|----------|----------|-----|
| 1 | [Description] | Critical/High/Medium/Low | `path:line` | [Action] |

### Recommended Actions
1. [Top priority action]
2. [Second priority]
3. [Third priority]
```

### Tier 3-4: Full Report

Include executive summary with overall score, per-category scores, top strengths, top critical findings, detailed findings with severity/location/evidence/recommendation/effort, and a phased action plan (immediate, short-term, medium-term).

### Delta Review Mode

When a prior review exists, use delta mode. A standalone review says "here are your problems." A delta review says "here is your trajectory." The second is far more useful for engineering leadership.

For each finding from the prior review, classify its current status:

| Status | Meaning |
|--------|---------|
| **Fixed** | Finding fully resolved |
| **Partially Fixed** | Improvement made but not complete |
| **Still Present** | No change — deferred or not yet addressed |
| **Worse** | Finding has regressed or expanded in scope |
| **New** | Finding not present in prior review |

### Deliverable Organization

Date-stamp review deliverables in folders:

```
reviews/
├── 2025-01-15/
│   ├── review-summary.md
│   ├── detailed-findings.md
│   └── executive-report.pdf
├── 2025-04-15/
│   ├── delta-review.md         ← compares against 2025-01-15
│   ├── detailed-findings.md
│   └── executive-report.pdf
```
