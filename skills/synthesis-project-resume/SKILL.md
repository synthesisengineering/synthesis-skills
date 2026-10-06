---
name: synthesis-project-resume
description: "Start or resume any synthesis project in any harness on any machine with verified context: classify the session (continuing, fresh, wrong project), load the records, respect live claims, surface other Macs' changes. Use when pasting a resume prompt or (re)opening project work."
license: "CC0-1.0"
depends_on: []
metadata:
  author: "Rajiv Pant"
  version: "2.0.0"
  source_repo: "github.com/synthesisengineering/synthesis-skills"
  source_type: "public"
  format: v5
---

# Project Resume

One prompt resumes a synthesis project anywhere: any harness, any Mac, with or
without native skill loading. The skill decides whether this session is
continuing, fresh or pointed at the wrong project, loads the records it needs,
and hands the principal a one-screen brief. `synthesis resume` does the
mechanical part from local files and local git; this skill is the protocol
around it, and works by hand where the CLI is absent.

## Binding rules

1. **Classify before loading.** Continuing: confirm in one line and keep working. Fresh: load fully. Wrong project: stop, name both projects and what is at stake, and ask. Fragments of several projects count as wrong project.
2. **An unknown id offers a new project.** Never resolve it to a similar existing name.
3. **Never claim context you did not read.** State what was loaded and the newest item's date.
4. **Never write through a live foreign claim.** Say who, on what, since when, and work read-only until the principal decides.
5. **Another Mac's work is the normal case.** Surface what changed there; never pull over local uncommitted changes; report two diverged copies as a conflict, never pick one by date.
6. **An unreachable remote is said once,** and the resume continues from local files.
7. **The prompt names the skill, never a path,** so it is identical on every machine.

## Contents

- **Procedure** (below): invocation, classification, the fresh load, the brief.
- [references/requirements.md](references/requirements.md): the R1 to R10 resume contract and the console companion surface. Read when changing this skill or the console prompt.
- [references/coverage-map.md](references/coverage-map.md): where every part of 1.1.0 lives now.
- [references/preserved.md](references/preserved.md): what was cut and why, and the 1.1.0 text verbatim. Read only to review the cut.

## Procedure

**1. Invocation.** The console emits:

```
Use the skill synthesis-project-resume to resume the synthesis
project with id <id> in the synthesis project management
workspace <name>.
```

Harnesses that load synthesis skills invoke it by name (Codex:
`$synthesis-project-resume`). Otherwise locate `synthesis-project-resume/SKILL.md`
in the Claude, Codex and Muse plugin caches, then `~/.claude/skills` and
`~/.agents/skills`, read it and follow it; if no copy exists, say to install
synthesis-skills. The workspace's knowledge repo is `ai-knowledge-{workspace}`
(exact match first), else the one `ai-knowledge-{workspace}-*` folder under
`~/workspaces/*`; if several or none match, ask once.

**2. Classify** (rule 1). `synthesis resume <id>` applies the same test to the
project on this session's board file: it answers "Already working <id>" for a
continuing session, and for a session on another project it names both, asks,
and switches nothing. After the principal says yes:
`synthesis resume <id> --switch`. For an unknown id it offers to start the
project: interview briefly (name, goal, workspace, repo family) and scaffold it
per synthesis-project-management, then continue as a fresh resume.

**3. Fresh load.**

1. `git -C <knowledge repo> fetch --quiet` (offline: go on; resume says so once).
2. `synthesis resume <id>`. It prints the directive, the current-state block,
   phase, status, last session and the newest session entry, the next actions,
   the plan, and a "Before working" list: the checkout behind its fetched
   upstream (with the commits), uncommitted local changes not to pull over,
   newer or diverged copies on other worktrees or branches, and other live
   sessions on the project.
3. Behind and clean: `git -C <knowledge repo> pull --ff-only`, then resume
   again. Any CONFLICT line: stop and ask before writing.
4. Read CONTEXT.md, the plan, REFERENCE.md, the two most recent session files,
   and any brief left for you (a board message names it). For an interrupted
   autopilot run, read its plan file first (synthesis-autopilot); a saved plan
   never grants a claim or replays an outside action.
5. Optional machine-readable status: `python3 <skill>/scripts/resume_probe.py
   <knowledge repo> <id>` prints JSON with `id`, `name`, `goal`, `status`,
   `updated`, `newest_session`, `session_mtime` and `recent_changes`; exit 2
   for an unreadable index, 3 for an unknown id.
6. Claims: `synthesis who`; overlap means read-only (rule 4). Then claim what
   you will write.

Without the CLI, do steps 3 and 4 by hand with `git log` on the project path.

**4. The brief, one screen:** the goal in one line, where it stands, the newest
three facts, open loops with owners, the suggested next action, what was
loaded, and the newest item's date. Lead with what changed on another Mac
("Mac B moved this yesterday: two session entries and a REFERENCE update") so
the principal feels continuity, not a cold start.
