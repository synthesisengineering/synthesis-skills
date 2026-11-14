# Coverage map: checkpoint 1.9.1 to 2.0.0 (v5)

Ruling D8: every rule of the old text has a new home, or sits in
[preserved.md](preserved.md) with the reason.

## Coverage check results

Run on 2026-10-05 from the v5 worktree:

```text
$ python3 v5-skill-coverage-check.py <v5 worktree> synthesis-checkpoint
synthesis-checkpoint: 389 old lines, 0 not found verbatim
```

## Frontmatter before v5 (verbatim)

```yaml
---
name: synthesis-checkpoint
description: "Refresh project context and verify recovery, current skills and session ownership. Use for checkpoints, drift or compaction recovery, and refresh-and-report after ecosystem upgrades. Supports existing and fresh sessions without repeating completed project work."
license: "CC0-1.0"
depends_on: []
metadata:
  author: "Rajiv Pant"
  version: "1.9.1"
  source_repo: "github.com/synthesisengineering/synthesis-skills"
  source_type: "public"
---
```

Kept: `name`, `license`, `depends_on`, `author`, `source_repo`, `source_type`.
Version 2.0.0, `format: v5` added, description rewritten with the same
triggers.

## 1.9.1 SKILL.md

| 1.9.1 section | v5 home | How |
|---|---|---|
| Refresh-and-report mode paragraph | Binding rule 9; [refresh-and-report.md](refresh-and-report.md) | Reworded; campaign feedback cut |
| Current skill text versus native reload | refresh-and-report.md ("Reload evidence") | Verbatim |
| The Problem (five drift sources, self-discipline degrades, recovery primitive) | SKILL.md purpose; [protocol.md](protocol.md#the-problem) | Verbatim in the reference |
| When To Invoke: user and self-monitoring triggers | Binding rule 4; [protocol.md](protocol.md#when-to-invoke) | Verbatim |
| When To Invoke: lifecycle hooks | protocol.md | Replaced by the v5 hooks (SessionStart re-injection, prompt-time messages) |
| The Protocol: full versus continuous, no recursion, reuse evidence | Procedure intro; Binding rule 7; protocol.md | Verbatim |
| Step 0, coordination board | Procedure 0; protocol.md | Reworded to `synthesis who` and `synthesis inbox` |
| Step 1, current time | Procedure 1; protocol.md | Verbatim |
| Step 2, project state: established project, no global pointer, resolver, read order | Binding rule 3; Procedure 2; protocol.md | Reworded: `synthesis brief` and `synthesis resume`; the resolver and `CURRENT_STATE.json` cut |
| Step 3, session evidence versus Git publication | Binding rule 2; Procedure 3; protocol.md | Verbatim, plus the context doctor |
| Step 4, tasks, material context, plan | Procedure 4; protocol.md | Reworded without coverage projections |
| Step 5, conformance hook-live receipts and the restart ladder | refresh-and-report.md | Replaced by `synthesis doctor` and the reload-evidence ladder |
| Step 5, the one-paragraph report and L4 visibility | Binding rule 5; Procedure 5; protocol.md | Verbatim |
| Step 6, stale context under a claim; scratchpad question | Binding rules 6 and 8; Procedure 6; protocol.md | Reworded to `synthesis claim`; the scratchpad question verbatim |
| Output Format examples | Procedure 5; [protocol.md](protocol.md#output-format) | Verbatim |
| What Counts as "Substantive Work" | Binding rule 1; protocol.md | Verbatim |
| Relationship to Other Synthesis Skills | protocol.md | Verbatim |
| Why This Works (lightweight, codified, visible; NTP) | SKILL.md purpose; protocol.md | Verbatim |

## 1.9.1 references and scripts

| Item | v5 home | How |
|---|---|---|
| references/refresh-and-report.md: scope and recovery, native identity, inspector command | [refresh-and-report.md](refresh-and-report.md) | Replaced: `synthesis version`, `doctor`, `who`, `brief`, the context doctor |
| ...: finishing inspection, NOT_APPLICABLE, Stop termination | — | Cut with structured state and Stop receipts |
| ...: optional reusable campaign; explicit feedback | — | Cut with `refresh.py`; peer reports use `synthesis msg` |
| ...: final result and claim disposition | refresh-and-report.md ("Report") | Reworded |
| scripts/refresh.py (REPLACE) and test_refresh.py | `synthesis resume`, `synthesis brief`, `synthesis doctor`; context doctor | tests/test_resume.py, tests/test_doctor.py, synthesis-context-lifecycle tests/test_context_doctor.py |
