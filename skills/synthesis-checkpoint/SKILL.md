---
name: synthesis-checkpoint
description: "Re-sync a session with ground truth: verified clock, project records, git, dated session entries and board claims. Use for checkpoints, drift or compaction recovery, 'where are we?', resuming after a pause, and refresh-and-report after an ecosystem upgrade."
license: "CC0-1.0"
depends_on: []
metadata:
  author: "Rajiv Pant"
  version: "2.0.0"
  source_repo: "github.com/synthesisengineering/synthesis-skills"
  source_type: "public"
  format: v5
---

# Synthesis Checkpoint

LLMs drift from what is actually on disk: the clock moves, other sessions edit
the records, compaction drops details, cached facts age. This is the recovery
primitive: a short, codified, visible re-sync against the clock, the project
files, git and the board, run on demand or when a drift signal fires. It is
the NTP of synthesis project management: periodic, authoritative-source-driven,
automatic.

## Binding rules

1. **Verify before you claim.** Run `date` and read the record before any time-interval claim, status quote, session-log entry or dated commit message; correcting afterwards is dearer.
2. **Records are caches; git and dated session entries are evidence.** Commit times never define a workday; a matching date does not prove a current record.
3. **Use this session's own project.** Nothing another session wrote may switch an established conversation to a different project.
4. **Run on the triggers:** a status or "continue" request, a pause of 10 minutes or more, about 25 tool calls, "I don't recall", an unexpected file, a correction, a new board message, a project switch.
5. **Show the verification** in the next reply: date, latest session and its source, any divergence, the claim, the next step.
6. **Correct stale records only under a claim.** A refused claim is reported as `id (project · harness)`; the work is kept, never forced.
7. **A checkpoint does not trigger another checkpoint.** Reuse evidence already in hand; then return to the next deliverable.
8. **Ask before closing: What executable state or required input data still exists only in this session's scratchpad?** If a durable record cites its output, preserve the script and required inputs under resources/scripts/ before the checkpoint can close.
9. **Refresh-and-report is read-only.** It inspects and reports; installed files are not a reloaded harness.

## Contents

- **Procedure** (below): the six steps in short. Read every time.
- [references/protocol.md](references/protocol.md): the problem, every trigger, each step in full, output examples, what counts as substantive work, relationship to the other skills. Read on first use in a session and when a step is unclear.
- [references/refresh-and-report.md](references/refresh-and-report.md): the read-only pass after an upgrade, reload evidence and the restart ladder. Read when asked to refresh after an ecosystem change or report readiness.
- [references/coverage-map.md](references/coverage-map.md): where every part of 1.9.1 lives now.
- [references/preserved.md](references/preserved.md): what was cut and why, and the 1.9.1 text verbatim. Read only to review the cut.

## Procedure

Use the full protocol for recovery, material drift and an explicit refresh.
During continuous work on a verified project, check only the live facts the
next claim or change needs; a new contradiction triggers full recovery.

0. **Board.** `synthesis who` and `synthesis inbox`: is the claim still right, is there a message, is anyone else here?
1. **Clock.** `date "+%Y-%m-%d %H:%M:%S %Z (%A)"`; note any drift from what you believed.
2. **Project.** `synthesis brief` (directive, current state, plan), then read CONTEXT.md, the plan, the newest session entry and REFERENCE.md. In a fresh session use `synthesis resume <id>`; a CONFLICT warning stops project writes.
3. **Evidence.** `git log -10 --pretty=format:"%h %ai %ci %s" -- <project>` and `git status --short -- <project>`; compare dated session entries with the header and index. Optionally `python3 <synthesis-context-lifecycle>/scripts/context_doctor.py --project <path>`.
4. **Decisions.** Re-read the plan and the in-session task list; check that the facts, reasons and conditions the next step depends on are in the record.
5. **Report** one short paragraph:

   > **Checkpoint complete.** Today 2026-05-27 10:49 EDT (Wednesday). Latest recorded session 2026-05-25 (`sessions/2026-05.md`); last commit 2026-05-26 is publication evidence. CONTEXT.md and the index agree. Claim: `<paths>`, no conflict. Proceeding with [next action].

6. **Fix** a stale header or record under a claim, keep it on disk, and answer rule 8's scratchpad question.
