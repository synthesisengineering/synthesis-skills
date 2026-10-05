---
name: synthesis-codebase-review
description: "Enterprise-scale codebase audit methodology with tiered review system (Essential through Mission-Critical). Use when asked to: codebase review, code audit, code review, review codebase, architecture review, security audit, full code review, enterprise review, codebase health check."
license: "CC0-1.0"
depends_on: []
metadata:
  author: "Rajiv Pant"
  version: "2.0.0"
  format: v5
  source_repo: "github.com/synthesisengineering/synthesis-skills"
  source_type: "public"
---

# Enterprise-Grade Codebase Review

A comprehensive, practical codebase audit methodology for projects of any size. Not every project needs every check — the tiered system ensures you apply the right level of rigor.

For the full detailed checklist, see `references/detailed-checklist.md` in this skill directory.

## Binding rules

1. **Run the pre-flight checklist before reviewing.** Confirm which branch holds the current work (never assume `main`), what to exclude, whether a prior review exists, and the output format and audience; skipping it has wasted real engagements.
2. **Score the project, then apply its tier's checks.** No Tier 4 scrutiny for a weekend project, and no skipped Tier 1 basics for an enterprise system.
3. **Every finding cites file paths and line numbers** and gives concrete remediation steps.
4. **Strengths before findings** in every report, so critical findings land as guidance rather than an attack.
5. **Use delta mode when a prior review exists.** Classify each earlier finding as Fixed, Partially Fixed, Still Present, Worse or New, because a trajectory is more useful than a list of problems.
6. **Secrets scanning is critical at every tier.**
7. **Checklist items are practical and checkable:** each catches real issues and is worded so an AI assistant can evaluate it.

## Contents

- [references/detailed-checklist.md](references/detailed-checklist.md): every check in the 16 categories and the addenda, each marked with its tier. Read while reviewing, keeping to the project's tier.
- [references/quick-check-and-categories.md](references/quick-check-and-categories.md): the 15-minute minimum viable review, and a one-paragraph overview of each of the 16 categories and the addenda. Read for a rapid health check, or when planning which categories to cover.
- [references/report-formats.md](references/report-formats.md): strengths before findings, the Tier 1-2 report template, the Tier 3-4 full report, delta review mode, and how to file deliverables. Read when writing the report.
- [references/background.md](references/background.md): how this skill relates to implementation-integrity, code-audit, preflight and pr-review, and the five key principles. Read when choosing between these skills.
- [references/coverage-map.md](references/coverage-map.md): where each part of the 1.0.0 text now lives (ruling D8).
- How to Use This Skill, Pre-Flight Checklist, Project Complexity Assessment: below. The steps, what to confirm first, and how to pick the tier.

## How to Use This Skill

### Step 1: Assess Project Tier

Complete the Project Complexity Assessment to determine which tier applies.

### Step 2: Review Applicable Sections

Each section and many individual items are marked with tier indicators:
- **Essential** (Tier 1) — Apply to ALL projects, even weekend hacks
- **Standard** (Tier 2) — Apply to team projects and production apps
- **Enterprise** (Tier 3) — Apply to large-scale, multi-team, or regulated systems
- **Mission-Critical** (Tier 4) — Apply to financial, healthcare, infrastructure, or high-stakes systems

### Step 3: Skip What Doesn't Apply

- Tier 1: focus only on Essential items (~50 checks)
- Tier 2: include Essential and Standard items (~150 checks)
- Tier 3: include Essential, Standard, and Enterprise items (~400 checks)
- Tier 4: include everything (~900+ checks)

## Pre-Flight Checklist

Complete these checks before starting any review. Skipping pre-flight has caused real wasted effort on real engagements.

### Branch Selection

- Confirm which branch represents the current working state — do NOT assume `main` is current
- Check the most recent commit date on the target branch. If `main` has not been updated in weeks and there is an active branch with many commits ahead, you are likely reviewing a stale snapshot
- Ask whether the team uses git-flow, trunk-based, or another model. In git-flow, `develop` is often the correct review target

### Review Scope

- Confirm which directories to exclude (vendor/, node_modules/, generated/, etc.)
- Ask if a previous review has been conducted. If yes, obtain prior findings to enable delta review mode
- Confirm expected output format (markdown, PDF, etc.) and audience (engineering team, leadership, both)

## Project Complexity Assessment

Score each characteristic (0 = No, 1 = Yes):

**Scale & Users:** >1 developer, >5 developers, >20 developers, >100 users, >10K users, >1M users

**Business Criticality:** Production system, downtime costs money, downtime costs >$10K/hour, breach would make news, contractual SLAs

**Data Sensitivity:** User accounts, PII, financial data, health data (HIPAA), regulated data (GDPR, SOX)

**Architecture Complexity:** >1 service, >5 services, database exists, multiple data stores, third-party integrations, >5 integrations

**Operational Requirements:** 99% uptime, 99.9% uptime, 99.99% uptime, dedicated ops/SRE team, 24/7 on-call

| Score Range | Tier | Description |
|-------------|------|-------------|
| 0-4 | Tier 1 - Essential | Solo/hobby projects, prototypes, internal tools |
| 5-10 | Tier 2 - Standard | Small team projects, production apps, startups |
| 11-18 | Tier 3 - Enterprise | Large teams, regulated industries, enterprise customers |
| 19+ | Tier 4 - Mission-Critical | Financial systems, healthcare, critical infrastructure |
