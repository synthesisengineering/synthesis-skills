# Coverage map: project resume 1.1.0 to 2.0.0 (v5)

Ruling D8: every rule of the old text has a new home, or sits in
[preserved.md](preserved.md) with the reason.

## Coverage check results

Run on 2026-10-05 from the v5 worktree:

```text
$ python3 v5-skill-coverage-check.py <v5 worktree> synthesis-project-resume
synthesis-project-resume: 184 old lines, 0 not found verbatim
```

## Frontmatter before v5 (verbatim)

```yaml
---
name: synthesis-project-resume
description: "Start or resume any synthesis project in any harness on any machine with full verified context: classify the session (continuing, fresh, or wrong-project paste), load index plus CONTEXT plus REFERENCE plus recent sessions, respect live foreign claims, surface cross-machine changes, and upgrade stale project formats. Use when pasting a console resume prompt or (re)opening project work."
license: "CC0-1.0"
depends_on: []
metadata:
  author: "Rajiv Pant"
  version: "1.1.0"
  source_repo: "github.com/synthesisengineering/synthesis-skills"
  source_type: "public"
---
```

Kept: `name`, `license`, `depends_on`, `author`, `source_repo`, `source_type`.
Version 2.0.0, `format: v5` added, description under 300 characters without
the retired format upgrade.

## 1.1.0 SKILL.md

| 1.1.0 section | v5 home | How |
|---|---|---|
| Version history lines | [preserved.md](preserved.md) | Kept verbatim there |
| Normative contract pointer; harness assumptions | SKILL.md purpose; Contents | Reworded |
| §1 Invocation: the prompt, native and skill-less lookup, workspace resolution, unknown id → R6 | Procedure 1 and 2; Binding rules 2 and 7 | Verbatim prompt and lookup order; R6 interview kept |
| §2 Classify: continuing, fresh, wrong-project; ambiguity; "false continuity corrupts" | Binding rule 1; Procedure 2; `synthesis resume` | Reworded; the CLI applies the same three cases |
| §3 Fresh load: resolver, read order, `resume_probe.py`, claims, format version, the brief | Procedure 3 and 4 | Reworded: `synthesis resume`; format check cut (R9 retired) |
| §3 Autopilot capsule pointer | Procedure 3 step 4 | Replaced by the autopilot plan file |
| §4 Cross-machine surfacing; unreachable remote said once | Binding rules 5 and 6; Procedure 4 | Verbatim example; reworded |
| §5 What the skill refuses | Binding rules 1, 3, 4, 5 | The stale-format refusal cut (R9) |

## references/requirements.md

| Requirement | v5 home | How |
|---|---|---|
| R1, R2, R4, R7, R8, console C1 to C5 | [requirements.md](requirements.md) | Verbatim |
| R3 read order | requirements.md | Reworded: current-state block and `Plan:` field; `RESUME_STATE.json`, `CURRENT_STATE.json` and the handoff queue removed; "pulls first" became fetch, then fast-forward a clean checkout |
| R5 | requirements.md | Verbatim, plus never pulling over local changes and reporting divergence |
| R6 | requirements.md | Verbatim, plus no near-match resolution |
| R9 | requirements.md (marked retired); preserved.md | Retired: one format |
| R10 | requirements.md | Verbatim except the fleet registry, plus "said once" |

## Scripts

| Script | Verdict | v5 home | Tests |
|---|---|---|---|
| scripts/resume_probe.py | KEEP | the same script; `format_version` dropped (as the evaluation named); PyYAML replaced by a standard-library index reader | tests/test_resume_probe.py |

## Scenarios

The R1.1 resume scenarios from the v5 code evaluation (wrong project, held
project, unknown id, behind upstream, unreachable remote, newer worktree copy,
diverged copies, future dates and the generated index) are tests in the
plugin's `tests/test_resume.py`; see synthesis-project-management's
[coverage map](../../synthesis-project-management/references/coverage-map.md#edge-cases-from-the-code-evaluation).
