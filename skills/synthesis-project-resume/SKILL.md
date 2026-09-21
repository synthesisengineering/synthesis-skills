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

1. Pull the knowledge repo (fast-forward only; divergence is
   reported, never force-resolved).
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
