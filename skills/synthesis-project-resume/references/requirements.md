# Project resume — requirements

Open-source requirements for `synthesis-project-resume` and its
companion surface in synthesis-console. The problem: one principal,
several computers, several agentic harnesses per computer (Claude
Code, Codex, Muse, Cursor, and more coming). Any project must start
or resume in any harness on any machine with full context, safely.

## R1 — One prompt resumes anywhere

The console renders a short copy-paste prompt per project. Pasting it
into any harness — whether or not that harness loads synthesis skills
natively — resumes the project. The prompt names the skill file by
absolute path so skill-less harnesses can read it directly:

```
Resume synthesis project <id> (source <name>).
Skill: <abs path>/skills/synthesis-project-resume/SKILL.md
```

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

## R10 — Harness-neutral, path-absolute

The skill works from a file path and repo paths alone. It assumes no
slash commands, no plugin loader, no MCP servers, no network beyond
git remotes. Anything it needs beyond the repo (board claims, fleet
registry) degrades to a named, read-only limitation — never a silent
skip and never a crash.

## Console UX contract (companion surface)

- C1: `/projects` gains `sort=recent|name|status` (default recent)
  and keeps existing `group`/`filter` behavior.
- C2: Recency derives from newest session-file mtime per project,
  falling back to the index `updated` field, falling back to name.
- C3: Each project row shows relative recency ("2h ago") and a
  Resume control emitting the R1 prompt for click-to-copy.
- C4: The project detail page shows the same prompt plus the
  resumption-brief fields it can compute statically (goal, status,
  newest session period).
- C5: No new dependencies; no writes from the console to repos —
  it renders prompts, agents execute them.
