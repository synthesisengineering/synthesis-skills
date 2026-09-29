---
name: synthesis-context-lifecycle
description: "Three-tier context architecture for managing AI working memory across long-running projects. Use when asked to: manage context, project context, session management, context lifecycle, working memory, archival, archive sessions, context maintenance, garbage collection for context, tiered context."
license: "CC0-1.0"
depends_on: []
metadata:
  author: "Rajiv Pant"
  version: "1.22.0"
  source_repo: "github.com/synthesisengineering/synthesis-skills"
  source_type: "public"
---

# Context Lifecycle Management

## The Problem

AI collaborators start every session with zero context. Their effectiveness depends entirely on the quality of the context they receive. For short-lived projects (2-3 sessions), a single context file works. For long-running projects spanning weeks or months, that file grows unboundedly — combining four types of information with fundamentally different lifecycles:

| Information type | Access pattern | Growth pattern | Ideal treatment |
|-----------------|----------------|----------------|-----------------|
| **Working memory** (current state, active tasks) | Every session | Constant | Keep lean, refresh often |
| **Episodic memory** (session logs) | Rarely after 1 week | Unbounded append | Archive monthly |
| **Semantic memory** (stable facts, reference) | Most sessions | Slow, update-in-place | Separate file |
| **Completed work records** | Almost never | Unbounded append | Delete after archiving |

Combining all four in one file means the file grows linearly with session count, with no mechanism for information to leave. This is the classic **hot/warm/cold data problem** from database engineering, manifesting in AI context management.

---

## The Architecture

Read [the complete protocol](references/context-protocol-details.md#the-architecture) before work in this area. Its requirements remain mandatory.

## Session Start Protocol — MANDATORY before substantive project work

The tiered architecture (CONTEXT.md / REFERENCE.md / sessions/) is only useful if the agent reads it. LLMs default to working from in-context memory; rules at session start lose salience as conversation grows. The Session Start Protocol makes the read explicit and non-skippable.

When you begin substantive work on any project — at client session start, when
the user first mentions it, or after switching from another project — run these
steps in order before substantive action. First resolve this conversation's
established project through its Git-tracked registry with the installed
project-management resolver, `--no-fetch --no-coordination-refresh` and
`GIT_OPTIONAL_LOCKS=0`; no automatic fast-forward. A global pointer cannot
override the conversation's project. CONFLICT/FAIL/UNKNOWN stops dependent
project reads and writes, including generated-state build and migration.

1. **Verify current time.** Run `date "+%Y-%m-%d %H:%M:%S %Z (%A)"`. The model has no clock; the OS does. Use the output as your authoritative "today" anchor for the rest of the session. The harness may have injected a date earlier, but that injection drifts; `date` does not.
2. **Inspect Git publication and working state.** Run `git log -10 --pretty=format:"%h %ai %ci %s" -- <project-path>` and `git status --short -- <project-path>`. These establish commit author/committer times and pending changes. Commit times do not define session workdays; delayed publication, overnight work and timezone boundaries may put them on different dates.
3. **Read CONTEXT.md.** Read the full working-memory file. Treat its "Last session" header as a claim to compare with dated session records and current source evidence. A commit-date difference alone does not make it stale, and matching dates alone do not establish semantic currency.
4. **Read the latest dated entries in sessions/YYYY-MM.md.** Locate the newest recorded workday across the archive, not just the file's final heading. Compare the narrative with CONTEXT.md, structured state where present, and index metadata. Report older or newer cache dates with both sources; recover missing, invalid or unreadable evidence without inventing a session date from Git. When archiving older work, retain its verified workday and label the current recording time separately. A repair done today may have its own entry; it must not rewrite the earlier workday to match its commit.
5. **Skim REFERENCE.md if you have not recently.** This is the project's stable facts and design spec. Full read on the first session resumption of the day; quick skim of section headers otherwise.
6. **Name this session after the project where the client allows it.** When the client exposes session/thread renaming, set this conversation's own title to the project's id (e.g. `synthesis-ecosystem-engineering`) so the thread list reads as the work queue. Claude Code: MCP tool `mcp__ccd_session_mgmt__set_session_title` with `{session_id: "self", title: "<project-id>"}` (verified 2026-09-21; a user-set title asks approval first, auto-generated titles replace silently). No verified equivalent on other clients as of that date — check yours and apply the same convention if one exists; if not, this step does not apply.
7. **Only then begin substantive work.**

When `synthesis-agent-conformance` is available and this session has an accepted
owner claim, record the local active-project pointer after verification.
Report-only refreshes and contributors do not activate the canonical pointer:

```bash
python3 <skill-root>/scripts/conformance.py activate \
  --project <project-directory> --session-id <coordination-session-id>
```

The pointer accelerates SessionStart and PostCompact recovery. It is a cache;
the project files and git history remain authoritative.

### Seamless client and computer switching

Rajiv never has to run this protocol or save state manually. The working agent
owns the checkpoint before it yields. A normal stopped-task transition is:

1. the agent updates `CONTEXT.md`, stable `REFERENCE.md` facts, the current
   session log, and the controlling plan as the work changes;
2. the client adapter records the exact context paths changed by that session;
3. Stop hashes the attributed files into a local receipt without committing or
   using the network; an interruption before Stop leaves the manifest plus Git
   working-tree state as `LOCAL_RECOVERABLE` evidence;
4. an explicit remote handoff or day-end publishes source work under repository
   policy and batches exact private-context paths before the destination
   computer fast-forwards; and
5. when Rajiv names the project, the receiving client resolves it through the
   git-tracked `projects/index.yaml` and runs this Session Start Protocol
   automatically.

A valid live pointer accelerates the same-client case. Its absence after claim
release is normal and must not block recovery from the durable record. A single
global durable "current project" marker is prohibited because independent
Claude Code and Codex tasks may own different projects simultaneously.

The guarantee has explicit boundaries: do not switch while a task is still
running; an offline origin can preserve a local checkpoint but cannot make it
available on another computer; divergence, a behind checkout, missing
authentication, and overlapping claims must surface visibly instead of being
called seamless.

**Why this order matters.** Steps 1 and 2 establish ground truth from external sources (OS clock, git). Step 3 reads the cache. Step 4 reads the most recent narrative. The order means by the time you act, you have verified facts AND the project's own framing — and you have noticed any discrepancy between them.

**Visible to the user.** Show the verification step in your first response of the session. Example:

> Session start verified. Today: 2026-05-27 10:49 EDT (Wednesday). Last project commit: 2026-05-26 12:47 EDT (`51b8e6d`, "Maintain context: refresh inbox-cleanup CONTEXT.md"). CONTEXT.md matches git log. Proceeding with [next task].

The visible verification is the L4 cross-tool drift-detection mechanism — the user must be able to see that ground truth was checked.

---

## Mid-Session Refresh Protocol — MANDATORY under drift conditions

Long conversations cause context drift. The mid-session refresh protocol re-syncs the agent against ground truth without requiring a full restart.

**Mandatory triggers.** Re-run the Session Start Protocol (or invoke the `synthesis-checkpoint` skill, which is the codified version of these steps) under ANY of these conditions:

- **Before any time-interval claim in output.** "Yesterday", "N days ago", "last session", "this week", "earlier today" — verify the clock and the dated evidence for the event BEFORE generating the claim. Use `git log` for commit intervals; use session records for session dates, and do not infer an exact elapsed interval from a date-only entry. After-the-fact correction is more expensive than upfront verification.
- **After a long real-time pause.** If `date` reveals more than 1 hour has passed since you last checked, re-read CONTEXT.md and re-run `git log`. Long pauses correlate with the user resuming after a break — the world may have changed.
- **After ~25 substantive tool calls** since the last refresh. This is the unconditional cadence: even with no drift signal, re-read CONTEXT.md and `git log` to verify your accumulated context still matches disk.
- **On any drift signal:**
  - You say or think "I don't recall" about a recent decision
  - A file read returns content you didn't expect
  - The user references a decision you have no record of
  - The user corrects you ("that's not right", "actually...", "you said earlier...")
  - You notice the conversation has touched many topics and feel uncertain about project state
- **Before writing to a session-log file** (a markdown file under `sessions/`). The date you write into the header MUST be from `date`, not from memory.
- **Before generating a commit message that mentions dates or intervals.** The interval claim must be backed by `git log`.

**The protocol itself.** Run the steps from synthesis-checkpoint (preferred if loaded), or as a fallback the same steps inline:

1. `date "+%Y-%m-%d %H:%M:%S %Z (%A)"` — verify current time
2. `git log -10 --pretty=format:"%h %ai %s" -- <project-path>` — verify project history
3. Re-read CONTEXT.md from disk
4. Re-read the latest sessions/YYYY-MM.md entry
5. Reconcile: where does in-context memory disagree with disk/git? Report the discrepancy in the next response.
6. If CONTEXT.md is stale, update it and preserve session-attributed local evidence. Publish it during explicit remote handoff or day-end.

**Compaction detection signals.** Context-window compaction (the harness summarizing older turns) is opaque — you cannot reliably detect when it happened. Treat these as red flags suggesting compaction may have occurred:

- You suddenly cannot recall the user's stated goal for the session
- A task you remember as in-progress has unclear next steps
- Tool outputs reference files or decisions you have no context for
- Your last few tool calls feel disconnected from the current request

When any of these fire, run the Mid-Session Refresh Protocol unconditionally.

**Delegation.** When the `synthesis-checkpoint` skill is available, prefer invoking it — it is the canonical codification of this protocol, runs the same steps every time, and produces consistent visible output the user can spot. Use the inline fallback only when synthesis-checkpoint is not loaded.

---

## Editing a Durable Context File — MANDATORY for scripted edits

Scripted edits must use the public context editor and its budget/currency gates. Multi-file edits use apply-transaction with exact native/claim authority; interrupted intent must be reconciled through recover-transaction before further managed reads or writes. A journal never grants authority. Read and apply this section's complete [operating protocol](references/durable-record-operations.md) before acting.

## Decision and transfer succession

For material facts, rationale, constraints, temporary conditions or changed
instructions, follow [material context](references/material-context.md) before
dependent work, compaction or handoff. Capture the explicit input denominator,
then associate it through the existing editor. Pending capture, missing material,
unreachable records and unknown semantic or endpoint coverage remain distinct.
This applies to ordinary prose projects without autopilot or format enrollment.

Before retiring a decision interface or absorbing transferred ideas, read
[artifact succession](references/artifact-succession.md). Use the existing
`context_edit.py review-succession` and `apply-succession` owners. Exact
item accounting, evidence quality, principal answers and action authority
are separate axes. Unanswered and unverified historical items retain explicit
obligations. Archive bytes before changing live records; the existing record
transaction owns recovery. Never turn a transfer or archive into approval.

## The Archival Protocol

Archive before removing content from working memory; preserve decisions, outcomes, agent attribution and unresolved work in the correct durable tier. Read and apply this section's complete [operating protocol](references/durable-record-operations.md) before acting.

## Migration Guide

Apply the size-appropriate migration protocol only after registry-first recovery; preserve the original record and its authority boundaries. Read and apply this section's complete [operating protocol](references/durable-record-operations.md) before acting.

## Project Status Transitions

Apply the declared lifecycle definitions and update all corresponding records when transitioning a project. Read and apply this section's complete [operating protocol](references/durable-record-operations.md) before acting.

## Project Spawning

Use the project-spawning protocol and retain the originating relationship, goals, scope and handoff in durable records. Read and apply this section's complete [operating protocol](references/durable-record-operations.md) before acting.

## Repo Families and Deletion Units

Route relationship-bound content to its deletion unit and permanent personal material to its permanent root. The ALWAYS-PRESERVE class takes precedence; inventories count unselected content without itemizing it. Read and apply this section's complete [operating protocol](references/durable-record-operations.md) before acting.

## Measuring Context Quality

Use both quantitative bounds and qualitative recovery checks when judging context quality. Read and apply this section's complete [operating protocol](references/durable-record-operations.md) before acting.

## Executable Working State — resources/scripts/

Retain executable working state, exact inputs and reproducible scripts in durable project records; prose alone cannot replace recoverable execution evidence. Read and apply this section's complete [operating protocol](references/durable-record-operations.md) before acting.

## The Context Doctor — verification, not diligence

`bounded` defaults to `true` when unset; `bounded: false` explicitly declares a
standing operational stream and changes the applicable closure remedy.
After reference sharding, the reference index has a 150-line budget and each
topic has a 300-line budget. Repair the named condition without dropping content
or changing a project's declared lifecycle to silence a diagnostic.

Use the context doctor and its documented remedies, including reference-budget, reference-shard, reference-index-budget, reference-topic-budget, reference-index-orphan, reference-index-missing, terminal-project-active, terminal-project-open-items and post-close-review-unresolvable. The index field post_close_reviewed_through names the reviewed commit; a new project commit re-arms review, and dirty/untracked evidence, changed index dates or archive gaps cannot inherit it. Coverage is a claim that needs its own verification: report every check’s examined/skipped denominator. Suppressing an inapplicable check is only safe when you add the check that becomes applicable in its place. Read and apply this section's complete [operating protocol](references/durable-record-operations.md) before acting.

## Context as Infrastructure

Treat context as maintained infrastructure with explicit ownership and verification. Read and apply this section's complete [operating protocol](references/durable-record-operations.md) before acting.

## Evolution Stages

Use the documented evolution stages and their evidence requirements before changing the architecture. Read and apply this section's complete [operating protocol](references/durable-record-operations.md) before acting.

## Local Continuity and Remote Readiness Protocol

Distinguish LOCAL_READY from REMOTE_READY. Verify local recovery before switching clients and complete the explicit remote-readiness protocol before switching computers; never infer native acceptance from installed bytes. Read and apply this section's complete [operating protocol](references/durable-record-operations.md) before acting.


The context doctor reports `skill-outputs` for unverifiable active packet
pages. A rulings file's presence does not prove closure. Retired interfaces
require exact source custody, an explicit verified succession record, and
surviving obligations. Missing or changed custody fails; a changed live
destination is a separate review warning. A generated page without its filed
spec remains incomplete filing. No check grants action authority.


The complete [context protocol details](references/context-protocol-details.md)
remain mandatory for the corresponding lifecycle operations.


### Durable custody before a session ends

Long-lived worktrees, source copies, environments and sole recovery inputs must
live in the durable workspace, outside system temp roots and session scratchpads.
Keep bounded test fixtures separately identified and capture their evidence
before closure. Temporary retention is policy- and clock-dependent, never a
universal four-day guarantee. Follow PM's [durable placement and missing-work
protocol](../synthesis-project-management/references/parallel-agent-protocol.md#durable-work-placement-and-unexplained-loss).
A vanished `.git` link or tracked file is unresolved loss evidence; retain its
registration, refs and surviving files. It is not retirement, deletion authority,
or a reason to discard foreign claims.
