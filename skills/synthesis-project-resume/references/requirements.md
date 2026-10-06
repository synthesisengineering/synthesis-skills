# Project resume — requirements

Open-source requirements for `synthesis-project-resume` and its
companion surface in synthesis-console. The problem: one principal,
several computers, several agentic harnesses per computer (Claude
Code, Codex, Muse, and more coming). Any project must start or resume
in any harness on any machine with full context, safely. v5 delivers
R1 to R8 and R10 through `synthesis resume` and the procedure in
SKILL.md; R9 retired with format versions.

## Contents

- [R1 — One prompt resumes anywhere](#r1--one-prompt-resumes-anywhere)
- [R2 — The skill detects the session situation](#r2--the-skill-detects-the-session-situation)
- [R3 — Fresh resume loads full context, verified](#r3--fresh-resume-loads-full-context-verified)
- [R4 — Never write through a live foreign claim](#r4--never-write-through-a-live-foreign-claim)
- [R5 — Cross-machine continuity is ordinary](#r5--cross-machine-continuity-is-ordinary)
- [R6 — Start is a degenerate resume](#r6--start-is-a-degenerate-resume)
- [R7 — Console shows recency first, groups on demand](#r7--console-shows-recency-first-groups-on-demand)
- [R8 — Resume brief, not resume dump](#r8--resume-brief-not-resume-dump)
- [R9 — Stale-context guard (retired)](#r9--stale-context-guard-retired)
- [R10 — Harness-neutral, name-addressed](#r10--harness-neutral-name-addressed)
- [Console UX contract (companion surface)](#console-ux-contract-companion-surface)

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
order in the skill's procedure.

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
`synthesis resume` applies the same three cases to the project on the
session's own board file.

## R3 — Fresh resume loads full context, verified

A fresh resume reads, in order: the source's `projects/index.yaml`
entry, `CONTEXT.md` (its current-state block first), the plan its one
`Plan:` field names, `REFERENCE.md`, the two most recent session
files, and any brief another agent left in `resources/artifacts/`
with a board message pointing at it. It fetches the knowledge repo
first, when the network allows, so "full context" includes work done
on other Macs, and fast-forwards only a clean checkout. It states what
it loaded and the newest item's date — never claims context it did
not read.

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
continuity, not a cold start. It never pulls over this machine's
uncommitted changes, and it reports two diverged copies as a
conflict instead of picking one by date.

## R6 — Start is a degenerate resume

Starting a brand-new project uses the same prompt shape and the same
skill: unknown id → the skill interviews (name, goal, workspace,
repo family) and scaffolds the project per the project-management
contract. One entry point for start and resume. An unknown id is
never resolved to a similar existing name.

## R7 — Console shows recency first, groups on demand

The console project list defaults to recently-active-first ordering
(computed from session-file activity, not just index metadata) and
offers sort/group by status, workspace source, initiative, and
recency. Every row and every detail page carries the R1 resume
prompt with a copy action. Finding a project and resuming it is one
screen and one paste.

## R8 — Resume brief, not resume dump

The resumption brief fits on one screen: project goal in one line,
where it stands, the newest three facts, open loops with owners, and
the suggested next action. Full context is loaded; the brief is what
the principal reads. Detail stays a question away.

## R9 — Stale-context guard (retired)

v5 has one plain-markdown project format, so there is no older
format to upgrade before resuming. The original requirement is
preserved verbatim in [preserved.md](preserved.md).

## R10 — Harness-neutral, name-addressed

The skill is addressed by name and works from repo paths alone. It
assumes no slash commands, no plugin loader APIs, no MCP servers,
no network beyond git remotes. Anything it needs beyond the repo
(board claims) degrades to a named, read-only limitation — never a
silent skip and never a crash. An unreachable remote is said once,
and the resume continues from local files.

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
