# Preserved: what project resume 2.0.0 does not carry, and why

Ruling D8: a rewritten skill loses nothing. This file says what the v5 rewrite
of synthesis-project-resume did not carry from 1.1.0 (`origin/main` on
2026-10-05) and why, and holds the 1.1.0 SKILL.md and requirements verbatim.
[coverage-map.md](coverage-map.md) maps every part to its new home. Nothing in
this file is current procedure.

## Contents

- [What was cut and why](#what-was-cut-and-why)
- [The 1.1.0 SKILL.md](#the-110-skillmd)
- [requirements.md](#requirementsmd)

## What was cut and why

- **R9, the stale-format guard, and the format-version check.** v5 has one
  plain-markdown project format (v5 code evaluation: `project_format.py` and
  `project_migration.py` CUT), so there is nothing to migrate before resuming.
  `resume_probe.py` (KEEP) dropped its `format_version` field.
- **`RESUME_STATE.json` and `CURRENT_STATE.json`.** Generated state files were
  adopted by a handful of projects; v5 reads the current-state block in
  CONTEXT.md, which the SessionStart hook re-injects.
- **The causal project resolver** (`project_state.py resolve`). Replaced by
  `synthesis resume`, which warns about upstream changes, newer or diverged
  copies and other live sessions from local git, and never picks a copy by
  date.
- **The handoff queue** (`handoff.py`). Replaced by a brief file under
  `resources/artifacts/` and a board message pointing at it.
- **Autopilot recovery capsules.** Replaced by the autopilot plan file (R6.1).
- **The version history lines** at the top of 1.1.0's SKILL.md are kept below.
- **`resume_probe.py`'s PyYAML import.** v5 code is standard library only, so
  the probe reads the index with a small parser of its own.

## The 1.1.0 SKILL.md

Verbatim from `skills/synthesis-project-resume/SKILL.md` at 1.1.0. Links inside point where they pointed then.

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

# Project Resume

**Version 1.1.0** (2026-09-21): name-addressed invocation — the R1
prompt names the skill and the workspace, never a filesystem path.

**Version 1.0.0** (2026-09-20): first release — the R1–R10 resume
contract, the three-way session classification, the one-screen
resumption brief, and `scripts/resume_probe.py` for machine-readable
project status.

The normative contract is
[references/requirements.md](references/requirements.md). This file
is the operating protocol. It assumes nothing about the harness
beyond a file system and git: no slash commands, no plugin loader,
no MCP servers.

## 1. Invocation

The console emits the resume prompt (R1):

```
Use the skill synthesis-project-resume to resume the synthesis
project with id <id> in the synthesis project management
workspace <name>.
```

If your harness loads synthesis skills natively, this skill is
already in your context under that name — invoke it if your
harness needs an explicit call (Codex: `$synthesis-project-resume`)
and continue at §2. Otherwise (skill-less harnesses such as
Cursor), locate the skill file by searching your installed skills
for `synthesis-project-resume/SKILL.md`: the Claude, Codex, and
Muse plugin caches first, then `~/.claude/skills` and
`~/.agents/skills`. Read it first and follow it. If no copy
exists anywhere, stop and say to install synthesis-skills.

Resolve the workspace name to its repo checkout: the knowledge
repo is `ai-knowledge-{workspace}` — exact match first — else the
unique `ai-knowledge-{workspace}-*` directory under the workspace
roots (`~/workspaces/*`). If several match or none does, ask once
and remember. Unknown project id means R6 (start): interview
briefly (name, goal, workspace, repo family) and scaffold per the
project-management contract, then continue as a fresh resume.

## 2. Classify the session (R2)

Compare the requested project against the project your loaded
context names — the index entry, CONTEXT, or working files already
live in this session:

1. **Continuing** — same project already live. Say so in one line
   and keep working. Never reload-and-resummarize live context.
2. **Fresh** — no project loaded. Run the fresh-resume load (§3).
3. **Wrong-project paste** — a different project is live here. STOP.
   Name both projects and what is at stake in the live one, then ask
   whether to switch, and wait. Never strand live work silently.

When the session's project is ambiguous (fragments of several
projects in context), treat it as case 3 and name the candidates.
False continuity corrupts; false caution costs one question.

## 3. Fresh-resume load (R3, R5, R8)

1. Resolve the project through the PM registry and causal resolver before
   reading project prose or choosing a checkout. Use its selected path and
   exact local attribution roots; do not pull over unresolved local work.
2. Read the index entry, `RESUME_STATE.json` (v2; verify the
   skeleton when present), `CURRENT_STATE.json` (operational
   handoff, when present), `CONTEXT.md`, `REFERENCE.md`, the two
   most recent session files, and any handoff queue entries — in
   that order.
3. Run `scripts/resume_probe.py` (sibling of this SKILL.md) for
   the machine-readable status (newest session, cross-machine
   changes, format version).
4. Check the coordination board for live foreign claims on the
   project paths (R4). Overlap means read-only until the principal
   decides — say who, what, since when.
5. Check the format version (R9). Older than installed means
   migrate-verify-resume through the versioned format contract
   before any other write.
6. Deliver the one-screen resumption brief: goal in one line, where
   it stands, the newest three facts, open loops with owners, the
   suggested next action. State what was loaded and the newest
   item's date.

For an interrupted autopilot run, apply the
[capsule and cold-resume protocol](../synthesis-context-lifecycle/references/autopilot-recovery.md)
after project selection and fresh ownership. Recover from the authoritative
journal, reconcile effects and child output, and report unknown survival
boundaries. A saved capsule cannot grant a claim or replay an external action.

## 4. Cross-machine surfacing (R5)

`git log` on the project path since this machine's last touch is
part of every brief: "Mac B moved this yesterday — two session
appends and a REFERENCE update." The principal should feel
continuity, not a cold start. When the probe cannot reach the
remotes, say so once (R10) and resume from local state.

## 5. What the skill refuses

- Switching projects on a wrong-project paste without confirmation.
- Writing through a live foreign claim.
- Claiming context it did not read.
- Resuming a stale-format project without migrating it first.
- Force-resolving repo divergence to make a resume "clean."

## requirements.md

Verbatim from `skills/synthesis-project-resume/references/requirements.md` at 1.1.0. Links inside point where they pointed then.

# Project resume — requirements

Open-source requirements for `synthesis-project-resume` and its
companion surface in synthesis-console. The problem: one principal,
several computers, several agentic harnesses per computer (Claude
Code, Codex, Muse, Cursor, and more coming). Any project must start
or resume in any harness on any machine with full context, safely.

## R1 — One prompt resumes anywhere

The console renders a short copy-paste prompt per project. Pasting it
into any harness — whether or not that harness loads synthesis skills
natively — resumes the project. The prompt names the skill, never a
filesystem path, so it is identical on every machine: no client
name, no release version:

```
Use the skill synthesis-project-resume to resume the synthesis
project with id <id> in the synthesis project management
workspace <name>.
```

Harnesses that load synthesis skills natively invoke the skill by
name. Skill-less harnesses locate the skill file via the lookup
order in the skill's §1.

No flags, no setup, no harness-specific variants. One prompt shape.

## R2 — The skill detects the session situation

On invocation the skill classifies the session into exactly one of:

1. **Continuing** — this session already has this project's context
   loaded (its index entry, CONTEXT, or working files are the live
   context). Confirm in one line and continue; never reload and
   re-summarize what is already live.
2. **Fresh** — a new session with no project loaded. Load full
   context per R3 and report the resumption brief.
3. **Wrong-project paste** — the session is mid-work on a different
   project. STOP, warn naming both projects, and confirm before
   switching. A paste must never silently strand live work.

Classification is behavioral and harness-neutral: the agent compares
the requested project against the project its loaded context names.
No harness-specific session APIs.

## R3 — Fresh resume loads full context, verified

A fresh resume reads, in order: the source's `projects/index.yaml`
entry, `CONTEXT.md`, `REFERENCE.md`, the two most recent session
files, `RESUME_STATE.json` (v2 resume state), `CURRENT_STATE.json`
(operational handoff), and any handoff queue entries. It pulls
the knowledge repo first so "full context" includes work done on
other Macs. It states what it loaded and the newest item's date —
never claims context it did not read.

## R4 — Never write through a live foreign claim

Before taking any write action, the resuming session reads the
coordination board. If another live session holds an overlapping
claim, the skill reports who, on what, since when — and works
read-only (or on a non-overlapping slice) until the principal
decides. Resuming must never corrupt a sibling session's work.

## R5 — Cross-machine continuity is ordinary

Work done on Mac A yesterday appears in the resume on Mac B today,
because project memory lives in synced repos, not in chat history.
The skill treats "another machine worked here" as the normal case:
it surfaces what changed elsewhere since this machine last touched
the project (git log on the project path), so the principal sees
continuity, not a cold start.

## R6 — Start is a degenerate resume

Starting a brand-new project uses the same prompt shape and the same
skill: unknown id → the skill interviews (name, goal, workspace,
repo family) and scaffolds the project per the project-management
contract. One entry point for start and resume.

## R7 — Console shows recency first, groups on demand

The console project list defaults to recently-active-first ordering
(computed from session-file activity, not just index metadata) and
offers sort/group by status, workspace source, initiative, and
recency. Every row and every detail page carries the R1 resume
prompt with a copy action. Finding a project and resuming it is one
screen and one paste.

## R8 — Resume brief, not resume dump

The resumption brief fits on one screen: project goal in one line,
where it stands, the newest three facts, open loops with owners,
and the suggested next action. Full context is loaded; the brief is
what the principal reads. Detail stays a question away.

## R9 — Stale-context guard

If the project's format version is older than the installed
project-management system (see the versioned format contract), the
skill says so, upgrades the project through the migration path, and
then resumes. Resume never strands a project on a dead format — and
never breaks one mid-upgrade: migrate-verify-resume, in that order.

## R10 — Harness-neutral, name-addressed

The skill is addressed by name and works from repo paths alone. It
assumes no slash commands, no plugin loader APIs, no MCP servers,
no network beyond git remotes. Anything it needs beyond the repo
(board claims, fleet registry) degrades to a named, read-only
limitation — never a silent skip and never a crash.

## Console UX contract (companion surface)

- C1: `/projects` gains `sort=recent|name|status` (default recent)
  and keeps existing `group`/`filter` behavior.
- C2: Recency derives from newest session-file mtime per project,
  falling back to the index `updated` field, falling back to name.
- C3: Each project row shows relative recency ("2h ago") and a
  "Copy resume prompt" control emitting the R1 prompt for click-to-copy.
- C4: The project detail page shows the same prompt plus the
  resumption-brief fields it can compute statically (goal, status,
  newest session period).
- C5: No new dependencies; no writes from the console to repos —
  it renders prompts, agents execute them.
