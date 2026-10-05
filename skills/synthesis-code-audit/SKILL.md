---
name: synthesis-code-audit
description: "Score a code diff on ten dimensions (conventions, reuse, consistency, security, scalability, future-proofing, quality, tests, docs, cleanup) with PASS, WARNING, FAIL or UNKNOWN and an overall verdict; PR review mode cross-references reviewer comments. Use to audit or review a diff."
license: "CC0-1.0"
depends_on: []
metadata:
  author: "Emil Peñaló"
  version: "2.0.0"
  format: v5
  source_repo: "github.com/synthesisengineering/synthesis-skills"
  source_type: "public"
---

# Synthesis Code Audit

A code audit is a systematic quality measurement of a diff. It is not a judgment call about whether a change should merge — that is the reviewer's job (see synthesis-pr-review). An audit produces a scored report across 10 orthogonal dimensions, each graded independently. The report tells you *where the quality problems are*; the reviewer decides *what to do about them*.

## Binding rules

1. **Measure; don't decide.** The audit grades the diff; merging is the reviewer's call. When another workflow (preflight, PR review) invoked the audit, return the findings to it.
2. **Compare against a fresh base ref**, never a stale local one: a stale base causes both false positives and false negatives.
3. **Read every changed file in full**, not just the diff hunks; the surrounding file shows whether the change makes sense.
4. **Give the reviewer the complete requirements** (frozen artifact universe, user outcome, acceptance criteria, exclusions, decisions) without priming the verdict. Challenge a mistaken premise with evidence and route amendments to the decision owner.
5. **Grade changed behavior and its affected consumers.** An outcome-blocking defect stays a blocker even when its lines predate the diff; record unrelated findings separately and never call unreviewed code clean.
6. **Apply project conventions explicitly**, including stronger fix-while-touching rules, and don't flag style nits in code this diff did not change.
7. **Partial coverage is Incomplete, never Clean.** Track reviewed and unreviewed paths; an UNKNOWN dimension or an unreviewed path cannot satisfy a readiness gate.
8. **Bind reused findings** to the actual diff, required consumer and evidence inputs; changed material reopens the affected judgment.

## Contents

- [references/dimensions.md](references/dimensions.md): what to check under each of the ten dimensions. Read it before grading any dimension.
- [references/principles-and-rules.md](references/principles-and-rules.md): where this skill fits beside pr-review and codebase-review, and the full text of the four principles and the rules. Read it when a rule's reach is unclear or when choosing between those skills.
- [references/coverage-map.md](references/coverage-map.md): where each part of the 1.1.0 text now lives.
- Diff scope detection, the grading scale and dimension list, reporting, PR review mode: below.

## Diff Scope Detection

Determine what to audit:

- **Uncommitted changes exist** — audit staged and unstaged changes against HEAD.
- **Branch has commits ahead of base** — audit the range from base to HEAD.
- **Nothing to diff** — report that and stop.

**Large diffs (40+ files):** Prioritize investigation by consequence, including configuration, generated assets and lock files when they affect execution or supply-chain integrity. Divide the frozen universe into bounded review assignments with one integration owner. Track reviewed and unreviewed paths explicitly. Partial coverage produces an incomplete audit, never an unqualified Clean verdict; finish required coverage before the package can pass.

## The 10-Dimension Framework

For each dimension, evaluate the changed code and assign one of:

- **PASS** — no issues, or only trivial stylistic preferences
- **WARNING** — potential problem that deserves attention but does not block shipping (missing edge-case test, minor inconsistency, could-be-better pattern)
- **FAIL** — concrete defect, security hole, convention violation, or missing coverage that should be fixed before merge
- **UNKNOWN** — a required judgment cannot be established from the available evidence or completed review coverage

The ten dimensions, each detailed in [references/dimensions.md](references/dimensions.md):

1. Project Convention Compliance
2. Code Reuse — Existing Before New
3. Consistency with Existing Patterns
4. Security
5. Scalability & Enterprise Readiness
6. Future-Proofing (Without Over-Engineering)
7. Code Quality
8. Test Coverage
9. Documentation & Comments
10. Cleanup

## Reporting

Present findings as a table:

| # | Dimension | Result | Notes |
|---|-----------|--------|-------|
| 1 | Project Convention Compliance | PASS/WARNING/FAIL | details |
| 2 | Code Reuse | PASS/WARNING/FAIL | details |
| ... | ... | ... | ... |

Below the table, add a one-line verdict:

- **"Clean"** — all applicable dimensions PASS for the complete declared universe, with exact source/base bindings
- **"Has warnings"** — one or more WARNING, no FAIL
- **"Has blockers"** — one or more FAIL
- **"Incomplete"** — any required dimension or part of the declared universe is UNKNOWN or unreviewed; this cannot satisfy a readiness gate

Then list actionable findings with file and line references. For each issue, state what is wrong and how to fix it.

## PR Review Mode (Cross-Referencing)

When invoked as part of a PR review workflow, existing reviewer comments may be available as context — a list of entries with reviewer, file path, line number, and comment body.

After completing all 10 dimensions, cross-reference each finding:

1. **File + Line match** — Is there an existing reviewer comment on the same file within +/-10 lines?
2. **Semantic match** — Does an existing comment raise the same category of concern (both flagging missing auth, both noting duplication)?
3. **Annotate each finding:**
   - `[Already noted by @reviewer]` — same or very similar concern at the same location
   - `[Related to @reviewer's comment on file:line]` — similar concern, different location
   - `[New finding]` — not covered by any existing reviewer

End with a **Cross-Reference Summary**: count of new findings vs. already-covered findings.

This mode does not change which dimensions are checked or how issues are evaluated — it only adds overlap annotations so the reviewer knows where their review adds new value vs. confirms existing feedback.
